##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import os
import time
import threading

import six
import psutil
from twisted.internet.defer import inlineCallbacks, DeferredList
from twisted.internet.threads import deferToThread

from txaio import make_logger, time_ns
from autobahn import wamp
from autobahn.wamp.types import PublishOptions
from autobahn.wamp.exception import ApplicationError
from crossbar.node.worker import NativeWorkerProcess
from crossbar.worker.controller import WorkerController

from crossbar.edge.worker.monitor import MONITORS

__all__ = ('HostMonitor', 'HostMonitorProcess')


class HostMonitorProcess(NativeWorkerProcess):

    TYPE = 'hostmonitor'
    LOGNAME = 'HostMon'


class HostMonitor(WorkerController):
    """
    Gather resource usage statistics and feed them back to the client
    """

    WORKER_TYPE = u'hostmonitor'
    WORKER_TITLE = u'HostMonitor'

    log = make_logger()

    def __init__(self, config=None, reactor=None, personality=None):
        super(HostMonitor, self).__init__(config=config, reactor=reactor, personality=personality)

        self._process = psutil.Process(os.getpid())

        self._run = False
        self._is_running = False
        self._monitors = {}
        self._config = None

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info('HostMonitor connected (monitors available: {monitors})', monitors=sorted(MONITORS.keys()))

        yield WorkerController.onJoin(self, details, publish_ready=False)

        # register monitor procedures
        dl = []
        for monitor in self._monitors.values():
            d = self.register(monitor.get, u'{}.get_{}'.format(self._prefix, monitor.ID))
            dl.append(d)
        res = yield DeferredList(dl, fireOnOneErrback=True)
        print(res)
        self.log.info('HostMonitor {pcnt} procedures registered', pcnt=len(res))

        # signal this worker is done with setup and ready
        yield self.publish_ready()

    def onLeave(self, details):
        self.log.info('HostMonitor shutting down ..')
        self.stop_monitoring()
        self.disconnect()

    @wamp.register(None)
    def get_monitoring(self, sensors=None, details=None):
        if self._run:
            if self._is_running:
                status = u'running'
            else:
                status = u'starting'
            pass
        else:
            status = u'stopped'

        if sensors is None:
            sensors = list(self._monitors.keys())
        else:
            sensors = list(set(self._monitors.keys()).intersection(sensors))

        monitoring = {
            u'status': status,
            u'config': self._config,
            u'current': {sensor: self._monitors[sensor].get()
                         for sensor in sensors}
        }
        return monitoring

    @wamp.register(None)
    def start_monitoring(self, config, details=None):
        """
        Start monitoring.

        :param config: Monitoring configuration.
        :type config: dict
        """
        self.log.info('HostMonitor start monitoring (config={config})', config=config)

        # after the worker is up and running, host monitoring must be started
        # (host monitoring can only be started or off, there is nothing to start instances of)
        if self._run:
            if self._is_running:
                raise ApplicationError(u'crossbar.error.already_running',
                                       u'cannot start host monitoring - monitoring already running')
            else:
                raise ApplicationError(u'crossbar.error.already_running',
                                       u'cannot start host monitoring - monitoring currently starting')

        # submonitors specified in the config
        monitors = config.get('monitors', {})
        if len(monitors) == 0:
            raise ApplicationError(u'crossbar.error.invalid_configuration',
                                   u'cannot start monitoring from empty monitors list')

        # save config for later access
        self._config = config

        # sensor polling interval in ms
        self._interval = config.get('interval', 500)

        self._monitors = {}
        for monitor_key, monitor_config in monitors.items():

            if type(monitor_key) != six.text_type:
                raise ApplicationError(u'crossbar.error.invalid_configuration',
                                       u'invalid monitor key type "{}"'.format(type(monitor_key)))

            if monitor_key not in MONITORS.keys():
                raise ApplicationError(
                    u'crossbar.error.invalid_configuration',
                    u'unknown monitor type "{}" (available monitors: {})'.format(monitor_key, sorted(MONITORS.keys())))

            # get submonitor class
            klass = MONITORS[monitor_key]

            # instantiate submonitor
            self._monitors[monitor_key] = klass(monitor_config)

        def after_exit_success(_):
            self._run = False

        def after_exit_error(err):
            self._run = False

        self._run = True
        d = deferToThread(self._loop)
        d.addCallbacks(after_exit_success, after_exit_error)

        self.log.info('HostMonitor loop started _from_ main thread (PID={pid}, thread={tid})',
                      pid=os.getpid(),
                      tid=threading.get_ident())

        started = {u'monitors': sorted(list(self._monitors.keys()))}
        topic = u'{}.on_mon_started'.format(self._uri_prefix)

        self.publish(topic, started)

        self.log.info('HostMonitor started monitoring (started={started})', started=started)

        return started

    @wamp.register(None)
    def stop_monitoring(self, details=None):
        self.log.info('HostMonitor stop monitoring ..')

        if not self._run:
            if self._is_running:
                self.log.warn('cannot stop host monitoring - monitoring already told to stop (but still running)')
            else:
                self.log.info('cannot stop host monitoring - monitoring already stopped')
            return None

        stopped = {u'monitors': sorted(list(self._monitors.keys()))}
        topic = u'{}.on_monitoring_stopped'.format(self._uri_prefix)

        self._run = False
        self._monitors = {}
        self._config = None

        self.publish(topic, stopped)

        self.log.info('HostMonitor stopped monitoring (stopped={stopped})', stopped=stopped)

        return stopped

    def _loop(self):
        # this is running on a background thread! eg you cannot just call self.publish() or self.log()!

        self._is_running = True

        try:
            print('HostMonitor entering loop on background thread (PID={pid}, thread={tid})'.format(
                pid=os.getpid(), tid=threading.get_ident()))
            while self._run:
                started = time_ns()

                self.log.debug(
                    'HostMonitor gather sensor data on background thread (started={started}, PID={pid}=thread {tid})',
                    started=started,
                    pid=os.getpid(),
                    tid=threading.get_ident())

                # poll all configured submonitors and collect the data
                hdata = {}
                for monitor in self._monitors.values():
                    hdata[monitor.ID] = monitor.poll()

                self._reactor.callFromThread(self._publish, hdata)

                # next time we want to loop (takes into account time for monitoring)
                next_time = started + self._interval * 10**6

                # wake up every 100ms until we want to loop
                while self._run and time_ns() < next_time:
                    time.sleep(.1)
        except Exception as e:
            print('HostMonitor ending loop because of exception: {}'.format(e))

            # mark the thread as "done" when still on the background thread
            self._is_running = False

            # the deferred return on the main thread from deferToThread will fire its errback
            raise

        else:
            print('HostMonitor ending loop gracefully')
            # the deferred return on the main thread from deferToThread will fire its callback

    def _publish(self, hdata):
        self.log.debug('HostMonitor publish sensor data on main thread (PID {pid} thread {tid})',
                       pid=os.getpid(),
                       tid=threading.get_ident())

        # this is running on the main thread: doing the publishes here avoids a couple
        # of context switches, and this way the background thread doesn't touch any
        # WAMP stuff (which is good in general .. decoupling)
        options = PublishOptions(acknowledge=True)

        dl = []
        for monitor_id, monitor_data in hdata.items():
            d = self.publish(u'{}.on_{}_sample'.format(self._uri_prefix, monitor_id), monitor_data, options=options)
            dl.append(d)

        d = DeferredList(dl)

        def done(results):
            ok = 0
            err = 0
            for success, result in results:
                if success:
                    ok += 1
                else:
                    err += 1
                    self.log.warn('HostMonitor publication failed with - {error}', error=result)
            self.log.debug('HostMonitor publish: ok={ok}, err={err}', ok=ok, err=err)

        d.addCallback(done)
