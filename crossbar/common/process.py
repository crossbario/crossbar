#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

import gc

from datetime import datetime

from twisted.internet import reactor
from twisted.internet.defer import DeferredList, inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall


try:
    # Manhole support needs a couple of packages optional for Crossbar.
    # So we catch import errors and note those.
    #
    # twisted.conch.manhole_ssh will import even without, but we _need_ SSH
    import Crypto  # noqa
    import pyasn1  # noqa
    from twisted.cred import checkers, portal
    from twisted.conch.manhole import ColoredManhole
    from twisted.conch.manhole_ssh import ConchFactory, \
        TerminalRealm, \
        TerminalSession
except ImportError as e:
    _HAS_MANHOLE = False
    _MANHOLE_MISSING_REASON = str(e)
else:
    _HAS_MANHOLE = True
    _MANHOLE_MISSING_REASON = None


from autobahn.util import utcnow, utcstr, rtime
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, RegisterOptions

from crossbar._logging import make_logger
from crossbar.common import checkconfig
from crossbar.common.checkconfig import get_config_value
from crossbar.twisted.endpoint import create_listening_port_from_config

from crossbar.common.processinfo import _HAS_PSUTIL
if _HAS_PSUTIL:
    from crossbar.common.processinfo import ProcessInfo
    # from crossbar.common.processinfo import SystemInfo

try:
    from txpostgres import txpostgres
    _HAS_POSTGRESQL = True
except ImportError:
    _HAS_POSTGRESQL = False

__all__ = ('NativeProcessSession',)


if _HAS_POSTGRESQL:

    class PostgreSQLConnection(object):
        """
        A PostgreSQL database connection pool.
        """

        log = make_logger()

        def __init__(self, id, config):
            """

            :param id: The ID of the connection item.
            :type id: unicode
            :param config: The connection item configuration.
            :type config: dict
            """
            self.id = id
            self.config = config
            self.started = None
            self.stopped = None

            params = {
                'host': config.get('host', 'localhost'),
                'port': config.get('port', 5432),
                'database': config['database'],
                'user': config['user'],
                'password': get_config_value(config, 'password'),
            }
            self.pool = txpostgres.ConnectionPool(None, min=5, **params)

        def start(self):
            self.started = datetime.utcnow()
            return self.pool.start()

        def stop(self):
            self.stopped = datetime.utcnow()
            return self.pool.close()

        def marshal(self):
            return {
                'id': self.id,
                'started': utcstr(self.started),
                'stopped': utcstr(self.stopped) if self.stopped else None,
                'config': self.config,
            }

if _HAS_MANHOLE:
    class ManholeService(object):

        """
        Manhole service running inside a native processes (controller, router, container).

        This class is for _internal_ use within NativeProcessSession.
        """

        def __init__(self, config, who):
            """
            Ctor.

            :param config: The configuration the manhole service was started with.
            :type config: dict
            :param who: Who triggered creation of this service.
            :type who: str
            """
            self.config = config
            self.who = who
            self.status = 'starting'
            self.created = datetime.utcnow()
            self.started = None
            self.port = None

        def marshal(self):
            """
            Marshal object information for use with WAMP calls/events.

            :returns: dict -- The marshalled information.
            """
            now = datetime.utcnow()
            return {
                'created': utcstr(self.created),
                'status': self.status,
                'started': utcstr(self.started) if self.started else None,
                'uptime': (now - self.started).total_seconds() if self.started else None,
                'config': self.config
            }


class NativeProcessSession(ApplicationSession):
    """
    A native Crossbar.io process (currently: controller, router or container).
    """
    log = make_logger()

    def onConnect(self, do_join=True):
        """
        """
        if not hasattr(self, 'cbdir'):
            self.cbdir = self.config.extra.cbdir

        if not hasattr(self, '_uri_prefix'):
            self._uri_prefix = 'crossbar.node.{}'.format(self.config.extra.node)

        self._started = datetime.utcnow()

        # see: BaseSession
        self.include_traceback = False
        self.debug_app = False

        self._manhole_service = None

        if _HAS_PSUTIL:
            self._pinfo = ProcessInfo()
            self._pinfo_monitor = None
            self._pinfo_monitor_seq = 0
        else:
            self._pinfo = None
            self._pinfo_monitor = None
            self._pinfo_monitor_seq = None
            self.log.info("Process utilities not available")

        self._connections = {}

        if do_join:
            self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when process has joined the node's management realm.
        """
        procs = [
            'start_manhole',
            'stop_manhole',
            'get_manhole',
            'start_connection',
            'stop_connection',
            'get_connections',
            'trigger_gc',
            'utcnow',
            'started',
            'uptime',
            'get_process_info',
            'get_process_stats',
            'set_process_stats_monitoring'
        ]

        dl = []
        for proc in procs:
            uri = '{}.{}'.format(self._uri_prefix, proc)
            self.log.debug("Registering procedure '{uri}'", uri=uri)
            dl.append(self.register(getattr(self, proc), uri, options=RegisterOptions(details_arg='details')))

        regs = yield DeferredList(dl)

        self.log.debug("Registered {len_reg} procedures", len_reg=len(regs))

    @inlineCallbacks
    def start_connection(self, id, config, details=None):
        """
        Starts a connection in this process.

        :param id: The ID for the started connection.
        :type id: unicode
        :param config: Connection configuration.
        :type config: dict
        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns dict -- The connection.
        """
        self.log.debug("start_connection: id={id}, config={config}", id=id, config=config)

        # prohibit starting a component twice
        #
        if id in self._connections:
            emsg = "cannot start connection: a connection with id={} is already started".format(id)
            self.log.warn(emsg)
            raise ApplicationError("crossbar.error.invalid_configuration", emsg)

        # check configuration
        #
        try:
            checkconfig.check_connection(config)
        except Exception as e:
            emsg = "invalid connection configuration ({})".format(e)
            self.log.warn(emsg)
            raise ApplicationError("crossbar.error.invalid_configuration", emsg)
        else:
            self.log.info("Starting {} in process.".format(config['type']))

        if config['type'] == u'postgresql.connection':
            if _HAS_POSTGRESQL:
                connection = PostgreSQLConnection(id, config)
            else:
                emsg = "unable to start connection - required PostgreSQL driver package not installed"
                self.log.warn(emsg)
                raise ApplicationError("crossbar.error.feature_unavailable", emsg)
        else:
            # should not arrive here
            raise Exception("logic error")

        self._connections[id] = connection

        try:
            yield connection.start()
            self.log.info("Connection {connection_type} started '{connection_id}'", connection_id=id, connection_type=config['type'])
        except Exception as e:
            del self._connections[id]
            raise

        state = connection.marshal()

        self.publish(u'crossbar.node.process.on_connection_start', state)

        returnValue(state)

    @inlineCallbacks
    def stop_connection(self, id, details=None):
        """
        Stop a connection currently running within this process.

        :param id: The ID of the connection to stop.
        :type id: unicode
        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns dict -- A dict with component start information.
        """
        self.log.debug("stop_connection: id={id}", id=id)

        if id not in self._connections:
            raise ApplicationError('crossbar.error.no_such_object', 'no connection with ID {} running in this process'.format(id))

        connection = self._connections[id]

        try:
            yield connection.stop()
        except Exception as e:
            self.log.warn('could not stop connection {id}: {error}', error=e)
            raise

        del self._connections[id]

        state = connection.marshal()

        self.publish(u'crossbar.node.process.on_connection_stop', state)

        returnValue(state)

    def get_connections(self, details=None):
        """
        Get connections currently running within this processs.

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns list -- List of connections.
        """
        self.log.debug("get_connections")

        res = []
        for c in self._connections.values():
            res.append(c.marshal())
        return res

    def get_process_info(self, details=None):
        """
        Get process information (open files, sockets, ...).

        :returns: dict -- Dictionary with process information.
        """
        self.log.debug("{cls}.get_process_info",
                       cls=self.__class__.__name__)

        if self._pinfo:
            return self._pinfo.get_info()
        else:
            emsg = "ERROR: could not retrieve process statistics - required packages not installed"
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

    def get_process_stats(self, details=None):
        """
        Get process statistics (CPU, memory, I/O).

        :returns: dict -- Dictionary with process statistics.
        """
        self.log.debug("{cls}.get_process_stats", cls=self.__class__.__name__)

        if self._pinfo:
            return self._pinfo.get_stats()
        else:
            emsg = "ERROR: could not retrieve process statistics - required packages not installed"
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

    def set_process_stats_monitoring(self, interval, details=None):
        """
        Enable/disable periodic publication of process statistics.

        :param interval: The monitoring interval in seconds. Set to 0 to disable monitoring.
        :type interval: float
        """
        self.log.debug("{cls}.set_process_stats_monitoring(interval = {interval})",
                       cls=self.__class__.__name__, interval=interval)

        if self._pinfo:

            stats_monitor_set_topic = '{}.on_process_stats_monitoring_set'.format(self._uri_prefix)

            # stop and remove any existing monitor
            if self._pinfo_monitor:
                self._pinfo_monitor.stop()
                self._pinfo_monitor = None

                self.publish(stats_monitor_set_topic, 0, options=PublishOptions(exclude=[details.caller]))

            # possibly start a new monitor
            if interval > 0:
                stats_topic = '{}.on_process_stats'.format(self._uri_prefix)

                def publish_stats():
                    stats = self._pinfo.get_stats()
                    self._pinfo_monitor_seq += 1
                    stats['seq'] = self._pinfo_monitor_seq
                    self.publish(stats_topic, stats)

                self._pinfo_monitor = LoopingCall(publish_stats)
                self._pinfo_monitor.start(interval)

                self.publish(stats_monitor_set_topic, interval, options=PublishOptions(exclude=[details.caller]))
        else:
            emsg = "ERROR: cannot setup process statistics monitor - required packages not installed"
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

    def trigger_gc(self, details=None):
        """
        Triggers a garbage collection.

        :returns: float -- Time consumed for GC in ms.
        """
        self.msg.debug("{cls}.trigger_gc", cls=self.__class__.__name__)

        started = rtime()
        gc.collect()
        return 1000. * (rtime() - started)

    @inlineCallbacks
    def start_manhole(self, config, details=None):
        """
        Start a manhole (SSH) within this worker.

        :param config: Manhole configuration.
        :type config: obj
        """
        self.log.debug("{cls}.start_manhole(config = {config})",
                       cls=self.__class__.__name__, config=config)

        if not _HAS_MANHOLE:
            emsg = "ERROR: could not start manhole - required packages are missing ({})".format(_MANHOLE_MISSING_REASON)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

        if self._manhole_service:
            emsg = "ERROR: could not start manhole - already running (or starting)"
            self.log.warn(emsg)
            raise ApplicationError("crossbar.error.already_started", emsg)

        try:
            checkconfig.check_manhole(config)
        except Exception as e:
            emsg = "ERROR: could not start manhole - invalid configuration ({})".format(e)
            self.log.error(emsg)
            raise ApplicationError('crossbar.error.invalid_configuration', emsg)

        # setup user authentication
        #
        checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        for user in config['users']:
            checker.addUser(user['user'], user['password'])

        # setup manhole namespace
        #
        namespace = {'session': self}

        class PatchedTerminalSession(TerminalSession):
            # get rid of
            # exceptions.AttributeError: TerminalSession instance has no attribute 'windowChanged'

            def windowChanged(self, winSize):
                pass

        rlm = TerminalRealm()
        rlm.sessionFactory = PatchedTerminalSession  # monkey patch
        rlm.chainedProtocolFactory.protocolFactory = lambda _: ColoredManhole(namespace)

        ptl = portal.Portal(rlm, [checker])

        factory = ConchFactory(ptl)
        factory.noisy = False

        self._manhole_service = ManholeService(config, details.caller)

        starting_topic = '{}.on_manhole_starting'.format(self._uri_prefix)
        starting_info = self._manhole_service.marshal()

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=[details.caller]))

        try:
            self._manhole_service.port = yield create_listening_port_from_config(config['endpoint'], factory, self.cbdir, reactor)
        except Exception as e:
            self._manhole_service = None
            emsg = "ERROR: manhole service endpoint cannot listen - {}".format(e)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.cannot_listen", emsg)

        # alright, manhole has started
        self._manhole_service.started = datetime.utcnow()
        self._manhole_service.status = 'started'

        started_topic = '{}.on_manhole_started'.format(self._uri_prefix)
        started_info = self._manhole_service.marshal()
        self.publish(started_topic, started_info, options=PublishOptions(exclude=[details.caller]))

        returnValue(started_info)

    @inlineCallbacks
    def stop_manhole(self, details=None):
        """
        Stop Manhole.
        """
        self.log.debug("{cls}.stop_manhole", cls=self.__class__.__name__)

        if not _HAS_MANHOLE:
            emsg = "ERROR: could not start manhole - required packages are missing ({})".format(_MANHOLE_MISSING_REASON)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

        if not self._manhole_service or self._manhole_service.status != 'started':
            emsg = "ERROR: cannot stop manhole - not running (or already shutting down)"
            raise ApplicationError("crossbar.error.not_started", emsg)

        self._manhole_service.status = 'stopping'

        stopping_topic = '{}.on_manhole_stopping'.format(self._uri_prefix)
        stopping_info = None

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(stopping_info)

        # .. while all others get an event
        self.publish(stopping_topic, stopping_info, options=PublishOptions(exclude=[details.caller]))

        try:
            yield self._manhole_service.port.stopListening()
        except Exception as e:
            raise Exception("INTERNAL ERROR: don't know how to handle a failed called to stopListening() - {}".format(e))

        self._manhole_service = None

        stopped_topic = '{}.on_manhole_stopped'.format(self._uri_prefix)
        stopped_info = None
        self.publish(stopped_topic, stopped_info, options=PublishOptions(exclude=[details.caller]))

        returnValue(stopped_info)

    def get_manhole(self, details=None):
        """
        Get current manhole service information.

        :returns: dict -- A dict with service information or `None` if the service is not running.
        """
        self.log.debug("{cls}.get_manhole", cls=self.__class__.__name__)

        if not _HAS_MANHOLE:
            emsg = "ERROR: could not start manhole - required packages are missing ({})".format(_MANHOLE_MISSING_REASON)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

        if not self._manhole_service:
            return None
        else:
            return self._manhole_service.marshal()

    def utcnow(self, details=None):
        """
        Return current time as determined from within this process.

        :returns str -- Current time (UTC) in UTC ISO 8601 format.
        """
        self.log.debug("{cls}.utcnow", cls=self.__class__.__name__)

        return utcnow()

    def started(self, details=None):
        """
        Return start time of this process.

        :returns str -- Start time (UTC) in UTC ISO 8601 format.
        """
        self.log.debug("{cls}.started", cls=self.__class__.__name__)

        return utcstr(self._started)

    def uptime(self, details=None):
        """
        Uptime of this process.

        :returns float -- Uptime in seconds.
        """
        self.log.debug("{cls}.uptime", cls=self.__class__.__name__)

        now = datetime.utcnow()
        return (now - self._started).total_seconds()
