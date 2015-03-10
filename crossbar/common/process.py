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

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.defer import DeferredList, \
    inlineCallbacks, \
    returnValue

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
from autobahn.wamp.types import PublishOptions, \
    RegisterOptions

from crossbar.common import checkconfig
from crossbar.twisted.endpoint import create_listening_port_from_config

from crossbar.common.processinfo import _HAS_PSUTIL
if _HAS_PSUTIL:
    from crossbar.common.processinfo import ProcessInfo
    # from crossbar.common.processinfo import SystemInfo

__all__ = ('NativeProcessSession',)


if _HAS_MANHOLE:
    class ManholeService:

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

    def onConnect(self, do_join=True):
        """
        """
        if not hasattr(self, 'debug'):
            self.debug = self.config.extra.debug

        if not hasattr(self, 'cbdir'):
            self.cbdir = self.config.extra.cbdir

        if not hasattr(self, '_uri_prefix'):
            self._uri_prefix = 'crossbar.node.{}'.format(self.config.extra.node)

        if self.debug:
            log.msg("Session connected to management router")

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
            log.msg("Warning: process utilities not available")

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
            if self.debug:
                log.msg("Registering procedure '{}'".format(uri))
            dl.append(self.register(getattr(self, proc), uri, options=RegisterOptions(details_arg='details')))

        regs = yield DeferredList(dl)

        if self.debug:
            log.msg("{} registered {} procedures".format(self.__class__.__name__, len(regs)))

    def get_process_info(self, details=None):
        """
        Get process information (open files, sockets, ...).

        :returns: dict -- Dictionary with process information.
        """
        if self.debug:
            log.msg("{}.get_process_info".format(self.__class__.__name__))

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
        if self.debug:
            log.msg("{}.get_process_stats".format(self.__class__.__name__))

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
        if self.debug:
            log.msg("{}.set_process_stats_monitoring".format(self.__class__.__name__), interval)

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
        if self.debug:
            log.msg("{}.trigger_gc".format(self.__class__.__name__))

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
        if self.debug:
            log.msg("{}.start_manhole".format(self.__class__.__name__), config)

        if not _HAS_MANHOLE:
            emsg = "ERROR: could not start manhole - required packages are missing ({})".format(_MANHOLE_MISSING_REASON)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.feature_unavailable", emsg)

        if self._manhole_service:
            emsg = "ERROR: could not start manhole - already running (or starting)"
            log.msg(emsg)
            raise ApplicationError("crossbar.error.already_started", emsg)

        try:
            checkconfig.check_manhole(config)
        except Exception as e:
            emsg = "ERROR: could not start manhole - invalid configuration ({})".format(e)
            log.msg(emsg)
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
            log.msg(emsg)
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
        if self.debug:
            log.msg("{}.stop_manhole".format(self.__class__.__name__))

        if not _HAS_MANHOLE:
            emsg = "ERROR: could not start manhole - required packages are missing ({})".format(_MANHOLE_MISSING_REASON)
            log.msg(emsg)
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
        if self.debug:
            log.msg("{}.get_manhole".format(self.__class__.__name__))

        if not _HAS_MANHOLE:
            emsg = "ERROR: could not start manhole - required packages are missing ({})".format(_MANHOLE_MISSING_REASON)
            log.msg(emsg)
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
        if self.debug:
            log.msg("{}.utcnow".format(self.__class__.__name__))

        return utcnow()

    def started(self, details=None):
        """
        Return start time of this process.

        :returns str -- Start time (UTC) in UTC ISO 8601 format.
        """
        if self.debug:
            log.msg("{}.started".format(self.__class__.__name__))

        return utcstr(self._started)

    def uptime(self, details=None):
        """
        Uptime of this process.

        :returns float -- Uptime in seconds.
        """
        if self.debug:
            log.msg("{}.uptime".format(self.__class__.__name__))

        now = datetime.utcnow()
        return (now - self._started).total_seconds()
