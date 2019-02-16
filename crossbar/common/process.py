#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
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

import sys
import os
import gc

from datetime import datetime

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall
from twisted.python.failure import Failure


try:
    # Manhole support needs a couple of packages optional for Crossbar.
    # So we catch import errors and note those.
    #
    # twisted.conch.manhole_ssh will import even without, but we _need_ SSH
    import pyasn1  # noqa
    import cryptography  # noqa
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
from autobahn import wamp

import txaio
from txaio import make_logger

from twisted.cred import portal

from crossbar.common.twisted.endpoint import create_listening_port_from_config

from crossbar.common.processinfo import _HAS_PSUTIL
if _HAS_PSUTIL:
    import psutil
    from crossbar.common.processinfo import ProcessInfo
    from crossbar.common.monitor import ProcessMonitor

if _HAS_MANHOLE:
    class ManholeService(object):

        """
        Manhole service running inside a native processes (controller, router, container).

        This class is for _internal_ use within NativeProcess.
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
                u'created': utcstr(self.created),
                u'status': self.status,
                u'started': utcstr(self.started) if self.started else None,
                u'uptime': (now - self.started).total_seconds() if self.started else None,
                u'config': self.config
            }


class NativeProcess(ApplicationSession):
    """
    A native Crossbar.io process (currently: controller, router or container).
    """
    log = make_logger()

    WORKER_TYPE = u'native'

    def onUserError(self, fail, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ISession.onUserError`
        """
        if isinstance(fail.value, ApplicationError):
            self.log.debug('{klass}.onUserError(): "{msg}"',
                           klass=self.__class__.__name__,
                           msg=fail.value.error_message())
        else:
            self.log.error(
                '{klass}.onUserError(): "{msg}"\n{traceback}',
                klass=self.__class__.__name__,
                msg=msg,
                traceback=txaio.failure_format_traceback(fail),
            )

    def __init__(self, config=None, reactor=None, personality=None):
        # Twisted reactor
        if not reactor:
            from twisted.internet import reactor
            self._reactor = reactor
        self._reactor = reactor

        # node/software personality
        if personality:
            self.personality = personality
        else:
            from crossbar.personality import Personality
            self.personality = Personality

        self._node_id = config.extra.node if config and config.extra else None
        self._worker_id = config.extra.worker if config and config.extra else None
        self._uri_prefix = u'crossbar.worker.{}'.format(self._worker_id)

        # base ctor
        super(ApplicationSession, self).__init__(config=config)

    def onConnect(self, do_join=True):
        if not hasattr(self, 'cbdir'):
            self.cbdir = self.config.extra.cbdir

        if not hasattr(self, '_uri_prefix'):
            self._uri_prefix = 'crossbar.node.{}'.format(self.config.extra.node)

        self._started = datetime.utcnow()

        # see: BaseSession
        self.include_traceback = False

        self._manhole_service = None

        if _HAS_PSUTIL:
            self._pinfo = ProcessInfo()
            self._pmonitor = ProcessMonitor(self.WORKER_TYPE, {})
            self._pinfo_monitor = None
            self._pinfo_monitor_seq = 0
        else:
            self._pinfo = None
            self._pmonitor = None
            self._pinfo_monitor = None
            self._pinfo_monitor_seq = None
            self.log.info("Process utilities not available")

        if do_join:
            self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when process has joined the node's management realm.
        """

        regs = yield self.register(
            self,
            prefix=u'{}.'.format(self._uri_prefix),
            options=RegisterOptions(details_arg='details'),
        )

        self.log.info("Registered {len_reg} procedures", len_reg=len(regs))
        for reg in regs:
            if isinstance(reg, Failure):
                self.log.error("Failed to register: {f}", f=reg, log_failure=reg)
            else:
                self.log.debug('  {proc}', proc=reg.procedure)
        returnValue(regs)

    @wamp.register(None)
    def get_cpu_count(self, logical=True, details=None):
        """
        Returns the CPU core count on the machine this process is running on.

        :param logical: If enabled (default), include logical CPU cores ("Hyperthreading"),
            else only count physical CPU cores.
        :type logical: bool

        :returns: The number of CPU cores.
        :rtype: int
        """
        if not _HAS_PSUTIL:
            emsg = "unable to get CPU count: required package 'psutil' is not installed"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        return psutil.cpu_count(logical=logical)

    @wamp.register(None)
    def get_cpus(self, details=None):
        """

        :returns: List of CPU IDs.
        :rtype: list[int]
        """
        if not _HAS_PSUTIL:
            emsg = "unable to get CPUs: required package 'psutil' is not installed"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        return self._pinfo.cpus

    @wamp.register(None)
    def get_cpu_affinity(self, details=None):
        """
        Get CPU affinity of this process.

        :returns: List of CPU IDs the process affinity is set to.
        :rtype: list[int]
        """
        if not _HAS_PSUTIL:
            emsg = "unable to get CPU affinity: required package 'psutil' is not installed"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        try:
            p = psutil.Process(os.getpid())
            current_affinity = p.cpu_affinity()
        except Exception as e:
            emsg = "Could not get CPU affinity: {}".format(e)
            self.log.failure(emsg)
            raise ApplicationError(u"crossbar.error.runtime_error", emsg)
        else:
            return current_affinity

    @wamp.register(None)
    def set_cpu_affinity(self, cpus, relative=True, details=None):
        """
        Set CPU affinity of this process.

        :param cpus: List of CPU IDs to set process affinity to. Each CPU ID must be
            from the list `[0 .. N_CPUs]`, where N_CPUs can be retrieved via
            ``crossbar.worker.<worker_id>.get_cpu_count``.
        :type cpus: list[int]

        :returns: List of CPU IDs the process affinity is set to.
        :rtype: list[int]
        """
        if not _HAS_PSUTIL:
            emsg = "Unable to set CPU affinity: required package 'psutil' is not installed"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        if sys.platform.startswith('darwin'):
            # https://superuser.com/questions/149312/how-to-set-processor-affinity-on-os-x
            emsg = "Unable to set CPU affinity: OSX lacks process CPU affinity"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        if relative:
            _cpu_ids = self._pinfo.cpus
            _cpus = [_cpu_ids[i] for i in cpus]
        else:
            _cpus = cpus

        try:
            p = psutil.Process(os.getpid())
            p.cpu_affinity(_cpus)
            new_affinity = p.cpu_affinity()
            if set(_cpus) != set(new_affinity):
                raise Exception('CPUs mismatch after affinity setting ({} != {})'.format(set(_cpus), set(new_affinity)))
        except Exception as e:
            emsg = "Could not set CPU affinity: {}".format(e)
            self.log.failure(emsg)
            raise ApplicationError(u"crossbar.error.runtime_error", emsg)
        else:

            # publish info to all but the caller ..
            #
            cpu_affinity_set_topic = u'{}.on_cpu_affinity_set'.format(self._uri_prefix)
            cpu_affinity_set_info = {
                u'cpus': cpus,
                u'relative': relative,
                u'affinity': new_affinity,
                u'who': details.caller
            }
            self.publish(cpu_affinity_set_topic, cpu_affinity_set_info, options=PublishOptions(exclude=details.caller))

            # .. and return info directly to caller
            #
            return new_affinity

    @wamp.register(None)
    def get_process_info(self, details=None):
        """
        Get process information (open files, sockets, ...).

        :returns: Dictionary with process information.
        """
        self.log.debug("{cls}.get_process_info",
                       cls=self.__class__.__name__)

        if self._pinfo:
            # psutil.AccessDenied
            # PermissionError: [Errno 13] Permission denied: '/proc/14787/io'
            return self._pinfo.get_info()
        else:
            emsg = "Could not retrieve process statistics: required packages not installed"
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

    @wamp.register(None)
    def get_process_stats(self, details=None):
        """
        Get process statistics (CPU, memory, I/O).

        :returns: Dictionary with process statistics.
        """
        self.log.debug("{cls}.get_process_stats", cls=self.__class__.__name__)

        if self._pinfo:
            return self._pinfo.get_stats()
        else:
            emsg = "Could not retrieve process statistics: required packages not installed"
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

    @wamp.register(None)
    def get_process_monitor(self, details=None):
        self.log.debug("{cls}.get_process_monitor", cls=self.__class__.__name__)

        if self._pmonitor:
            return self._pmonitor.poll()
        else:
            emsg = "Could not retrieve process statistics: required packages not installed"
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

    @wamp.register(None)
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

                self.publish(stats_monitor_set_topic, 0, options=PublishOptions(exclude=details.caller))

            # possibly start a new monitor
            if interval > 0:
                stats_topic = '{}.on_process_stats'.format(self._uri_prefix)

                def publish_stats():
                    stats = self._pinfo.get_stats()
                    self._pinfo_monitor_seq += 1
                    stats[u'seq'] = self._pinfo_monitor_seq
                    self.publish(stats_topic, stats)

                self._pinfo_monitor = LoopingCall(publish_stats)
                self._pinfo_monitor.start(interval)

                self.publish(stats_monitor_set_topic, interval, options=PublishOptions(exclude=details.caller))
        else:
            emsg = "Cannot setup process statistics monitor: required packages not installed"
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

    @wamp.register(None)
    def trigger_gc(self, details=None):
        """
        Manually trigger a garbage collection in this native process.

        This procedure is registered under
        ``crossbar.node.<node_id>.worker.<worker_id>.trigger_gc``
        for native workers and under
        ``crossbar.node.<node_id>.controller.trigger_gc``
        for node controllers.

        The procedure will publish an event when the garabage collection has finished to
        ``crossbar.node.<node_id>.worker.<worker_id>.on_gc_finished``
        for native workers and
        ``crossbar.node.<node_id>.controller.on_gc_finished``
        for node controllers:

        .. code-block:: javascript

            {
                "requester": {
                    "session_id": 982734923,
                    "auth_id": "bob",
                    "auth_role": "admin"
                },
                "duration": 190
            }

        .. note:: The caller of this procedure will NOT receive the event.

        :returns: Time (wall clock) consumed for garbage collection in ms.
        :rtype: int
        """
        self.log.debug("{cls}.trigger_gc", cls=self.__class__.__name__)

        started = rtime()

        # now trigger GC .. this is blocking!
        gc.collect()

        duration = int(round(1000. * (rtime() - started)))

        on_gc_finished = u'{}.on_gc_finished'.format(self._uri_prefix)
        self.publish(
            on_gc_finished,
            {
                u'requester': {
                    u'session_id': details.caller,
                    # FIXME:
                    u'auth_id': None,
                    u'auth_role': None
                },
                u'duration': duration
            },
            options=PublishOptions(exclude=details.caller)
        )

        return duration

    @wamp.register(None)
    @inlineCallbacks
    def start_manhole(self, config, details=None):
        """
        Start a Manhole service within this process.

        **Usage:**

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.start_manhole`` - for native workers
        * ``crossbar.node.<node_id>.controller.start_manhole`` - for node controllers

        The procedure takes a Manhole service configuration which defines
        a listening endpoint for the service and a list of users including
        passwords, e.g.

        .. code-block:: javascript

            {
                "endpoint": {
                    "type": "tcp",
                    "port": 6022
                },
                "users": [
                    {
                        "user": "oberstet",
                        "password": "secret"
                    }
                ]
            }

        **Errors:**

        The procedure may raise the following errors:

        * ``crossbar.error.invalid_configuration`` - the provided configuration is invalid
        * ``crossbar.error.already_started`` - the Manhole service is already running (or starting)
        * ``crossbar.error.feature_unavailable`` - the required support packages are not installed

        **Events:**

        The procedure will publish an event when the service **is starting** to

        * ``crossbar.node.<node_id>.worker.<worker_id>.on_manhole_starting`` - for native workers
        * ``crossbar.node.<node_id>.controller.on_manhole_starting`` - for node controllers

        and publish an event when the service **has started** to

        * ``crossbar.node.<node_id>.worker.<worker_id>.on_manhole_started`` - for native workers
        * ``crossbar.node.<node_id>.controller.on_manhole_started`` - for node controllers

        :param config: Manhole service configuration.
        :type config: dict
        """
        self.log.debug("{cls}.start_manhole(config = {config})",
                       cls=self.__class__.__name__, config=config)

        if not _HAS_MANHOLE:
            emsg = "Could not start manhole: required packages are missing ({})".format(_MANHOLE_MISSING_REASON)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        if self._manhole_service:
            emsg = "Could not start manhole - already running (or starting)"
            self.log.warn(emsg)
            raise ApplicationError(u"crossbar.error.already_started", emsg)

        try:
            self.personality.check_manhole(self.personality, config)
        except Exception as e:
            emsg = "Could not start manhole: invalid configuration ({})".format(e)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.invalid_configuration', emsg)

        from twisted.conch.ssh import keys
        from twisted.conch.manhole_ssh import (
            ConchFactory, TerminalRealm, TerminalSession)
        from twisted.conch.manhole import ColoredManhole
        from twisted.conch.checkers import SSHPublicKeyDatabase

        class PublicKeyChecker(SSHPublicKeyDatabase):
            def __init__(self, userKeys):
                self.userKeys = {}
                for username, keyData in userKeys.items():
                    self.userKeys[username] = keys.Key.fromString(data=keyData).blob()

            def checkKey(self, credentials):
                username = credentials.username.decode('utf8')
                if username in self.userKeys:
                    keyBlob = self.userKeys[username]
                    return keyBlob == credentials.blob

        # setup user authentication
        #
        authorized_keys = {
            'oberstet': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCz7K1QwDhaq/Bi8o0uqiJQuVFCDQL5rbRvMClLHRx9KE3xP2Fh2eapzXuYGSgtG9Fyz1UQd+1oNM3wuNnT/DsBUBQrECP4bpFIHcJkMaFTARlCagkXosWsadzNnkW0osUCuHYMrzBJuXWF2GH+0OFCtVu+8E+4Mhvchu9xsHG8PM92SpI6aP0TtmT9D/0Bsm9JniRj8kndeS+iWG4s/pEGj7Rg7eGnbyQJt/9Jc1nWl6PngGbwp63dMVmh+8LP49PtfnxY8m9fdwpL4oW9U8beYqm8hyfBPN2yDXaehg6RILjIa7LU2/6bu96ZgnIz26zi/X9XlnJQt2aahWJs1+GR oberstet@thinkpad-t430s'
        }
        checker = PublicKeyChecker(authorized_keys)

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

        ptl = portal.Portal(rlm)
        ptl.registerChecker(checker)

        factory = ConchFactory(ptl)
        factory.noisy = False

        private_key = keys.Key.fromFile(os.path.join(self.cbdir, 'ssh_host_rsa_key'))
        public_key = private_key.public()

        publicKeys = {
            b'ssh-rsa': public_key
        }
        privateKeys = {
            b'ssh-rsa': private_key
        }
        factory.publicKeys = publicKeys
        factory.privateKeys = privateKeys

        self._manhole_service = ManholeService(config, details.caller)

        starting_topic = '{}.on_manhole_starting'.format(self._uri_prefix)
        starting_info = self._manhole_service.marshal()

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=details.caller))

        try:
            self._manhole_service.port = yield create_listening_port_from_config(config['endpoint'],
                                                                                 self.cbdir,
                                                                                 factory,
                                                                                 self._reactor,
                                                                                 self.log)
        except Exception as e:
            self._manhole_service = None
            emsg = "Manhole service endpoint cannot listen: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.cannot_listen", emsg)

        # alright, manhole has started
        self._manhole_service.started = datetime.utcnow()
        self._manhole_service.status = 'started'

        started_topic = '{}.on_manhole_started'.format(self._uri_prefix)
        started_info = self._manhole_service.marshal()
        self.publish(started_topic, started_info, options=PublishOptions(exclude=details.caller))

        returnValue(started_info)

    @wamp.register(None)
    @inlineCallbacks
    def stop_manhole(self, details=None):
        """
        Stop the Manhole service running in this process.

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.stop_manhole`` for native workers and under
        * ``crossbar.node.<node_id>.controller.stop_manhole`` for node controllers

        When no Manhole service is currently running within this process,
        or the Manhole service is already shutting down, a
        ``crossbar.error.not_started`` WAMP error is raised.

        The procedure will publish an event when the service **is stopping** to

        * ``crossbar.node.<node_id>.worker.<worker_id>.on_manhole_stopping`` for native workers and
        * ``crossbar.node.<node_id>.controller.on_manhole_stopping`` for node controllers

        and will publish an event when the service **has stopped** to

        * ``crossbar.node.<node_id>.worker.<worker_id>.on_manhole_stopped`` for native workers and
        * ``crossbar.node.<node_id>.controller.on_manhole_stopped`` for node controllers
        """
        self.log.debug("{cls}.stop_manhole", cls=self.__class__.__name__)

        if not self._manhole_service or self._manhole_service.status != 'started':
            emsg = "Cannot stop manhole: not running (or already shutting down)"
            raise ApplicationError(u"crossbar.error.not_started", emsg)

        self._manhole_service.status = 'stopping'

        stopping_topic = u'{}.on_manhole_stopping'.format(self._uri_prefix)
        stopping_info = None

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(stopping_info)

        # .. while all others get an event
        self.publish(stopping_topic, stopping_info, options=PublishOptions(exclude=details.caller))

        try:
            yield self._manhole_service.port.stopListening()
        except Exception as e:
            self.log.warn("error while stop listening on endpoint: {error}", error=e)

        self._manhole_service = None

        stopped_topic = u'{}.on_manhole_stopped'.format(self._uri_prefix)
        stopped_info = None
        self.publish(stopped_topic, stopped_info, options=PublishOptions(exclude=details.caller))

        returnValue(stopped_info)

    @wamp.register(None)
    def get_manhole(self, details=None):
        """
        Get current manhole service information.

        :returns: A dict with service information or `None` if the service is not running.
        """
        self.log.debug("{cls}.get_manhole", cls=self.__class__.__name__)

        if not _HAS_MANHOLE:
            emsg = "Could not start manhole: required packages are missing ({})".format(_MANHOLE_MISSING_REASON)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.feature_unavailable", emsg)

        if not self._manhole_service:
            return None
        else:
            return self._manhole_service.marshal()

    @wamp.register(None)
    def utcnow(self, details=None):
        """
        Return current time as determined from within this process.

        **Usage:**

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.utcnow`` for native workers and under
        * ``crossbar.node.<node_id>.controller.utcnow`` for node controllers

        :returns: Current time (UTC) in UTC ISO 8601 format.
        :rtype: str
        """
        self.log.debug("{cls}.utcnow", cls=self.__class__.__name__)

        return utcnow()

    @wamp.register(None)
    def started(self, details=None):
        """
        Return start time of this process.

        **Usage:**

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.started`` for native workers and under
        * ``crossbar.node.<node_id>.controller.started`` for node controllers

        :returns: Start time (UTC) in UTC ISO 8601 format.
        :rtype: str
        """
        self.log.debug("{cls}.started", cls=self.__class__.__name__)

        return utcstr(self._started)

    @wamp.register(None)
    def uptime(self, details=None):
        """
        Return uptime of this process.

        **Usage:**

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.uptime`` for native workers and under
        * ``crossbar.node.<node_id>.controller.uptime`` for node controllers

        :returns: Uptime in seconds.
        :rtype: float
        """
        self.log.debug("{cls}.uptime", cls=self.__class__.__name__)

        now = datetime.utcnow()
        return (now - self._started).total_seconds()
