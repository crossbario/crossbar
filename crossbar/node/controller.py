#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import sys
import signal
import threading
import binascii
from datetime import datetime
from shutil import which
from collections import namedtuple

import cbor2

from twisted.python.reflect import qual
from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.internet.error import ProcessExitedAlready
from twisted.python.runtime import platform

from autobahn.util import utcnow, utcstr
from autobahn.wamp.cryptosign import format_challenge, sign_challenge
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, ComponentConfig, Challenge
from autobahn import wamp

import crossbar
from crossbar._util import term_print, hl, hlid, hltype, class_name
from crossbar.common.checkconfig import NODE_SHUTDOWN_ON_WORKER_EXIT, NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR, NODE_SHUTDOWN_ON_LAST_WORKER_EXIT
from crossbar.common.twisted.processutil import WorkerProcessEndpoint
from crossbar.node.native import create_native_worker_client_factory
from crossbar.node.guest import create_guest_worker_client_factory
from crossbar.node.worker import NativeWorkerProcess
from crossbar.node.worker import GuestWorkerProcess
from crossbar.common.process import NativeProcess
from crossbar.common.monitor import SystemMonitor
from crossbar.common.fswatcher import HAS_FS_WATCHER, FilesystemWatcher

import txaio
from txaio import make_logger, get_global_log_level
txaio.use_twisted()
from txaio import time_ns  # noqa

__all__ = ('NodeController', 'create_process_env')


def check_executable(fn):
    """
    Check whether the given path is an executable.
    """
    return os.path.exists(fn) and os.access(fn, os.F_OK | os.X_OK) and not os.path.isdir(fn)


class NodeController(NativeProcess):

    log = make_logger()

    WORKER_TYPE = 'controller'

    def __init__(self, node):
        # call base ctor
        extra = namedtuple('Extra', ['node', 'worker'])(node._node_id, 'controller')
        config = ComponentConfig(realm=node._realm, extra=extra)
        NativeProcess.__init__(self, config=config, reactor=node._reactor, personality=node.personality)

        # associated node
        self._node = node

        # node directory
        self.cbdir = self._node._cbdir

        # overwrite URI prefix for controller (normally: "crossbar.worker.<worker_id>")
        self._uri_prefix = 'crossbar'

        self._started = None
        self._pid = os.getpid()

        # map of worker processes: worker_id -> NativeWorkerProcess
        self._workers = {
            # add worker tracking instance to the worker map for the controller itself (!) ..
            # 'controller': self
        }

        # shutdown of node is requested, and further requests to shutdown (or start)
        # are denied
        self._shutdown_requested = False

        # when shutting down, this flags marks if the shutdown is graceful and clean,
        # and expected (under the node configuration/settings) or if the shutdown is
        # under error or unnormal conditions. this flag controls the final exit
        # code returned by crossbar: 0 in case of "clean shutdown", and 1 otherwise
        self._shutdown_was_clean = None

        # node-wide system monitor running here in the node controller
        self._smonitor = SystemMonitor()

    def onConnect(self):

        self.log.debug("Connected to node management router")

        NativeProcess.onConnect(self, False)

        # self.join(self.config.realm)
        self.join(self._realm)

    @inlineCallbacks
    def onJoin(self, details):

        from autobahn.wamp.types import SubscribeOptions

        self.log.info(
            '{func}: joined realm="{realm}" on local node management router [authid="{authid}", authrole="{authrole}"]',
            func=hltype(self.onJoin),
            authid=hlid(details.authid),
            authrole=hlid(details.authrole),
            realm=hlid(details.realm))

        # When a (native) worker process has connected back to the router of
        # the node controller, the worker will publish this event
        # to signal it's readyness.
        #
        def on_worker_ready(res):
            worker_id = res['id']
            if worker_id in self._workers:
                ready = self._workers[worker_id].ready
                if not ready.called:
                    # fire the Deferred previously stored for
                    # signaling "worker ready"
                    ready.callback(worker_id)
                else:
                    self.log.error(
                        "Internal error: on_worker_ready() fired for process {process}, but already called earlier",
                        process=worker_id)
            else:
                self.log.error(
                    "Internal error: on_worker_ready() fired for process {process}, but no process with that ID",
                    process=worker_id)

        self.subscribe(on_worker_ready, 'crossbar.worker..on_worker_ready', SubscribeOptions(match='wildcard'))

        yield NativeProcess.onJoin(self, details)

        # above upcall registers procedures we have marked with @wamp.register(None)

        # we need to catch SIGINT here to properly shutdown the
        # node explicitly (a Twisted system trigger wouldn't allow us to distinguish
        # different reasons/origins of exiting ..)
        def signal_handler(_signal, frame):
            if _signal == signal.SIGINT:
                # CTRL-C'ing Crossbar.io is considered "willful", and hence we want to exit cleanly
                self._shutdown_was_clean = True
            elif _signal == signal.SIGTERM:
                self._shutdown_was_clean = False
            else:
                # FIXME: can we run into others here?
                self._shutdown_was_clean = False

            self.log.warn(
                'Controller received SIGINT [signal={signal}]: shutting down node [shutdown_was_clean={shutdown_was_clean}] ..',
                signal=_signal,
                shutdown_was_clean=self._shutdown_was_clean)

            # the following will shutdown the Twisted reactor in the end
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        self.log.info('Signal handler installed on process {pid} thread {tid}',
                      pid=os.getpid(),
                      tid=threading.get_ident())

        self._started = utcnow()

        self.publish("crossbar.on_ready")

        self.log.debug("Node controller ready")

    @wamp.register(None)
    def get_status(self, details=None):
        """
        Return basic information about this node.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: Information on the Crossbar.io node.
        :rtype: dict
        """
        workers_by_type = {}
        for worker in self._workers.values():
            if worker.TYPE not in workers_by_type:
                workers_by_type[worker.TYPE] = 0
            workers_by_type[worker.TYPE] += 1

        return {
            'title': '{} {}'.format(self.personality.TITLE, crossbar.__version__),
            'started': self._started,
            'controller_pid': self._pid,
            'running_workers': len(self._workers),
            'workers_by_type': workers_by_type,
            'directory': self.cbdir,
            'pubkey': self._node._node_key.public_key(),
        }

    @wamp.register(None)
    def get_system_stats(self, details=None):
        """
        Return system statistics on this node.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Current system statistics for this node.
        :rtype: dict
        """
        started = time_ns()
        res = self._smonitor.poll()
        us = int(round((time_ns() - started) / 1000.))

        if us > 5000:
            self.log.warn("{cls}.get_system_stats()->{mcls} excessive run-time of {duration}us!",
                          cls=self.__class__.__name__,
                          mcls=self._smonitor.__class__.__name__,
                          duration=us)
        else:
            self.log.debug("{cls}.get_system_stats()->{mcls} ran in {duration}us",
                           cls=self.__class__.__name__,
                           mcls=self._smonitor.__class__.__name__,
                           duration=us)
        return res

    @wamp.register(None)
    @inlineCallbacks
    def shutdown(self, restart=False, mode=None, details=None):
        """
        Explicitly stop this node.
        """
        if self._shutdown_requested:
            # we're already shutting down .. ignore ..
            return

        self._shutdown_requested = True
        self.log.info('Node shutdown requested (restart={}, mode={}, reactor.running={}) ..'.format(
            restart, mode, self._reactor.running))

        term_print('CROSSBAR:NODE_SHUTDOWN_REQUESTED')

        try:
            # shutdown any specific to the node controller
            yield self._shutdown(restart, mode)

            # node shutdown information
            shutdown_info = {
                'node_id': self._node._node_id,
                'restart': restart,
                'mode': mode,
                'who': details.caller if details else None,
                'when': utcnow(),
                'was_clean': self._shutdown_was_clean,
            }

            if self._node._shutdown_complete:
                self._node._shutdown_complete.callback(shutdown_info)

            # publish management API event
            yield self.publish('{}.on_shutdown'.format(self._uri_prefix),
                               shutdown_info,
                               options=PublishOptions(exclude=details.caller if details else None, acknowledge=True))

            def stop_reactor():
                try:
                    self._reactor.stop()
                except ReactorNotRunning:
                    pass

            _SHUTDOWN_DELAY = 0.2
            self._reactor.callLater(_SHUTDOWN_DELAY, stop_reactor)

        except:
            self.log.failure()
            self._shutdown_requested = False
            raise

        else:
            returnValue(shutdown_info)

    # to be overridden in derived node classes to shutdown any
    # specifics (eg clients like for etcd or docker)
    def _shutdown(self, restart=False, mode=None):
        pass

    @wamp.register(None)
    def get_workers(self, filter_types=[], details=None):
        """
        Returns the list of workers currently running on this node.

        :param filter_types:
        :returns: List of worker processes.
        :rtype: list[dict]
        """
        assert filter_types is None or (type(filter_types) == list and type(ft) == str for ft in filter_types)

        if filter_types:
            ft = set(filter_types)
            worker_ids = [worker_id for worker_id in self._workers if self._workers[worker_id].TYPE in ft]
        else:
            worker_ids = self._workers.keys()
        return sorted(worker_ids)

    @wamp.register(None)
    def get_worker(self, worker_id, include_stats=False, details=None):
        """
        Return detailed information about worker.

        :param worker_id: ID of worker to get information for.
        :type worker_id: str

        :param include_stats: If true, include worker run-time statistics.
        :type include_stats: bool
        """
        if worker_id not in self._workers:
            emsg = "No worker with ID '{}'".format(worker_id)
            raise ApplicationError('crossbar.error.no_such_worker', emsg)

        now = datetime.utcnow()
        worker = self._workers[worker_id]

        worker_info = {
            'id': worker.id,
            'pid': worker.pid,
            'type': worker.TYPE,
            'status': worker.status,
            'created': utcstr(worker.created),
            'started': utcstr(worker.started),
            'startup_time': (worker.started - worker.created).total_seconds() if worker.started else None,
            'uptime': (now - worker.started).total_seconds() if worker.started else None,
        }

        if include_stats:
            stats = {'controller_traffic': worker.get_stats()}
            worker_info['stats'] = stats

        return worker_info

    @wamp.register(None)
    def start_worker(self, worker_id, worker_type, worker_options=None, details=None):
        """
        Start a new worker process in the node.
        """
        if type(worker_id) != str or worker_id in ['controller', '']:
            raise Exception('invalid worker ID "{}"'.format(worker_id))

        self.log.info('Starting {worker_type}-worker "{worker_id}" .. {worker_klass}',
                      worker_type=hl(worker_type),
                      worker_id=hlid(worker_id),
                      worker_klass=hltype(NodeController.start_worker))

        if worker_type == 'guest':
            return self._start_guest_worker(worker_id, worker_options, details=details)

        elif worker_type in self._node._native_workers:
            return self._start_native_worker(worker_type, worker_id, worker_options, details=details)

        else:
            raise Exception('invalid worker type "{}"'.format(worker_type))

    @wamp.register(None)
    def stop_worker(self, worker_id, kill=False, details=None):
        """
        Stop a running worker.

        :param worker_id: ID of worker to stop.
        :type worker_id: str

        :param kill: If ``True``, kill the process. Otherwise, gracefully shut down the worker.
        :type kill: bool

        :returns: Stopping information from the worker.
        :rtype: dict
        """
        if worker_id not in self._workers:
            emsg = "No worker with ID '{}'".format(worker_id)
            raise ApplicationError('crossbar.error.no_such_worker', emsg)

        worker = self._workers[worker_id]

        if worker.TYPE in self._node._native_workers:
            return self._stop_native_worker(worker_id, kill=kill, details=details)

        elif worker.TYPE == 'guest':
            return self._stop_guest_worker(worker_id, kill=kill, details=details)

        else:
            # should not arrive here
            raise Exception('logic error')

    @wamp.register(None)
    def get_worker_log(self, worker_id, limit=100, details=None):
        """
        Get buffered log for a worker.

        :param worker_id: The worker ID to get log output for.
        :type worker_id: str

        :param limit: Limit the amount of log entries returned to the last N entries.
        :type limit: int

        :returns: Buffered log for worker.
        :rtype: list
        """
        if worker_id not in self._workers:
            emsg = "No worker with ID '{}'".format(worker_id)
            raise ApplicationError('crossbar.error.no_such_worker', emsg)

        return self._workers[worker_id].getlog(limit)

    @wamp.register(None)
    def sign_challenge(self,
                       challenge_method,
                       challenge_extra,
                       channel_id_raw,
                       channel_id_type='tls-unique',
                       details=None):
        challenge = Challenge(challenge_method, challenge_extra)
        data = format_challenge(challenge, channel_id_raw, channel_id_type)
        return sign_challenge(data, self._node._node_key.sign)

    @wamp.register(None)
    def get_public_key(self, details=None):
        return self._node._node_key.public_key()

    def _start_native_worker(self, worker_type, worker_id, worker_options=None, details=None):

        # prohibit starting a worker twice
        #
        if worker_id in self._workers:
            emsg = "Could not start worker: a worker with ID '{}' is already running (or starting)".format(worker_id)
            self.log.error(emsg)
            raise ApplicationError('crossbar.error.worker_already_running', emsg)

        # check worker options
        #
        options = worker_options or {}
        if 'extra' in options:
            worker_options_extra = binascii.b2a_hex(cbor2.dumps(dict(options['extra'])))
        else:
            worker_options_extra = None

        try:
            if worker_type in self._node._native_workers:
                if self._node._native_workers[worker_type]['checkconfig_options']:
                    self._node._native_workers[worker_type]['checkconfig_options'](self.personality, options)
                else:
                    raise Exception('No checkconfig_options for worker type "{worker_type}" implemented!'.format(
                        worker_type=worker_type))
            else:
                raise Exception('invalid worker type "{}"'.format(worker_type))
        except Exception as e:
            emsg = "Could not start native worker: invalid configuration ({})".format(e)
            self.log.error(emsg)
            raise ApplicationError('crossbar.error.invalid_configuration', emsg)

        # the fully qualified worker class as a string
        worker_class = qual(self._node._native_workers[worker_type]['worker_class'])

        # allow override Python executable from options
        #
        if 'python' in options:
            exe = options['python']

            # the executable must be an absolute path, e.g. /home/oberstet/pypy-2.2.1-linux64/bin/pypy
            #
            if not os.path.isabs(exe):
                emsg = "Invalid worker configuration: python executable '{}' must be an absolute path".format(exe)
                self.log.error(emsg)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)

            # of course the path must exist and actually be executable
            #
            if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
                emsg = "Invalid worker configuration: python executable '{}' does not exist or isn't an executable".format(
                    exe)
                self.log.error(emsg)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)
        else:
            exe = sys.executable

        # allow override default Python module search paths from options
        #
        if 'pythonpath' in options:
            pythonpaths_to_add = [
                os.path.abspath(os.path.join(self._node._cbdir, p)) for p in options.get('pythonpath', [])
            ]
        else:
            pythonpaths_to_add = []

        # assemble command line for forking the worker
        #
        # all native workers (routers and containers for now) start
        # from the same script in crossbar/worker/process.py or
        # from the command "crossbar _exec_worker" when crossbar is
        # running from a frozen executable (single-file, pyinstaller, etc)
        #
        if getattr(sys, 'frozen', False):
            # if we are inside a frozen crossbar executable, we need to invoke
            # the crossbar executable with a command ("_exec_worker")
            args = [exe, self._node.personality.NAME, "_exec_worker"]
        else:
            # we are invoking via "-m" so that .pyc files, __pycache__
            # etc work properly. this works everywhere, but frozen executables
            args = [exe, "-u", "-m", "crossbar.worker.main"]
        args.extend(["--cbdir", self._node._cbdir])
        args.extend(["--node", str(self._node._node_id)])
        args.extend(["--worker", str(worker_id)])
        args.extend(["--realm", self._realm])
        args.extend(["--personality", class_name(self._node.personality)])
        args.extend(["--klass", worker_class])
        args.extend(["--loglevel", get_global_log_level()])
        if self._node.options.debug_lifecycle:
            args.append("--debug-lifecycle")
        if self._node.options.debug_programflow:
            args.append("--debug-programflow")
        if self._node.options.enable_vmprof:
            args.append("--vmprof")
        if "shutdown" in options:
            args.extend(["--shutdown", options["shutdown"]])
        if "restart" in options:
            args.extend(["--restart", options["restart"]])
        if worker_options_extra:
            args.extend(["--extra", worker_options_extra])

        # Node-level callback to inject worker arguments
        #
        self._node._extend_worker_args(args, options)

        # allow override worker process title from options
        #
        if options.get('title', None):
            args.extend(['--title', options['title']])

        # forward explicit reactor selection
        #
        if 'reactor' in options and sys.platform in options['reactor']:
            args.extend(['--reactor', options['reactor'][sys.platform]])
        # FIXME
        # elif self._node.options.reactor:
        #    args.extend(['--reactor', self._node.options.reactor])

        # create worker process environment
        #
        worker_env = create_process_env(options)

        # We need to use the same PYTHONPATH we were started with, so we can
        # find the Crossbar we're working with -- it may not be the same as the
        # one on the default path
        worker_env["PYTHONPATH"] = os.pathsep.join(pythonpaths_to_add + sys.path)

        # log name of worker
        #
        worker_logname = self._node._native_workers[worker_type]['logname']

        # each worker is run under its own dedicated WAMP auth role
        #
        worker_auth_role = 'crossbar.worker.{}'.format(worker_id)

        # topic URIs used (later)
        #
        starting_topic = self._node._native_workers[worker_type]['topics']['starting']
        started_topic = self._node._native_workers[worker_type]['topics']['started']

        # add worker tracking instance to the worker map ..
        #
        WORKER = self._node._native_workers[worker_type]['class']
        worker = WORKER(self, worker_id, details.caller, keeplog=options.get('traceback', None))
        self._workers[worker_id] = worker

        # create a (custom) process endpoint.
        #
        if platform.isWindows():
            childFDs = None  # Use the default Twisted ones
        else:
            # The communication between controller and container workers is
            # using WAMP running over 2 pipes.
            # For controller->native-worker traffic this runs over FD 0 (`stdin`)
            # and for the native-worker->controller traffic, this runs over FD 3.
            #
            # Note: We use FD 3, not FD 1 (`stdout`) or FD 2 (`stderr`) for
            # container->controller traffic, so that components running in the
            # container which happen to write to `stdout` or `stderr` do not
            # interfere with the container-controller communication.
            childFDs = {0: "w", 1: "r", 2: "r", 3: "r"}

        ep = WorkerProcessEndpoint(self._node._reactor, exe, args, env=worker_env, worker=worker, childFDs=childFDs)

        # ready handling
        #
        def on_ready_success(worker_id):
            self.log.debug('{worker_type} worker "{worker_id}" process {pid} started',
                           worker_type=worker_logname,
                           worker_id=worker.id,
                           pid=worker.pid)

            self._node._reactor.addSystemEventTrigger(
                'before',
                'shutdown',
                self._cleanup_worker,
                self._node._reactor,
                worker,
            )

            worker.on_worker_started()

            started_info = {
                'id': worker.id,
                'status': worker.status,
                'started': utcstr(worker.started),
                'who': worker.who,
                'pid': worker.pid,
                'startup_time': (worker.started - worker.created).total_seconds() if worker.started else None
            }

            # FIXME: make start of stats printer dependent on log level ..
            if False:
                worker.log_stats(5.)

            self.publish(started_topic, started_info, options=PublishOptions(exclude=details.caller))

            return started_info

        def on_ready_error(err):
            del self._workers[worker.id]
            emsg = 'Failed to start native worker: {}'.format(err.value)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.cannot_start", emsg, worker.getlog())

        worker.ready.addCallbacks(on_ready_success, on_ready_error)

        def on_exit_success(_):
            self.log.info("Node worker {worker.id} ended successfully", worker=worker)

            # clear worker log
            worker.log_stats(0)

            # remove the dedicated node router authrole we dynamically
            # added for the worker
            self._node._drop_worker_role(worker_auth_role)

            # remove our metadata tracking for the worker
            del self._workers[worker.id]

            # indicate that the worker excited successfully
            return True

        def on_exit_error(err):
            self.log.info("Node worker {worker.id} ended with error ({err})", worker=worker, err=err)

            # clear worker log
            worker.log_stats(0)

            # remove the dedicated node router authrole we dynamically
            # added for the worker
            self._node._drop_worker_role(worker_auth_role)

            # remove our metadata tracking for the worker
            del self._workers[worker.id]

            # indicate that the worker excited with error
            return False

        def check_for_shutdown(was_successful):
            self.log.info(
                'Checking for node shutdown: worker_exit_success={worker_exit_success}, shutdown_requested={shutdown_requested}, node_shutdown_triggers={node_shutdown_triggers}',
                worker_exit_success=was_successful,
                shutdown_requested=self._shutdown_requested,
                node_shutdown_triggers=self._node._node_shutdown_triggers)

            shutdown = self._shutdown_requested

            # automatically shutdown node whenever a worker ended (successfully, or with error)
            #
            if NODE_SHUTDOWN_ON_WORKER_EXIT in self._node._node_shutdown_triggers:
                self.log.info("Node worker ended, and trigger '{trigger}' is active: will shutdown node ..",
                              trigger=NODE_SHUTDOWN_ON_WORKER_EXIT)
                term_print('CROSSBAR:NODE_SHUTDOWN_ON_WORKER_EXIT')
                shutdown = True

            # automatically shutdown node when worker ended with error
            #
            elif not was_successful and NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR in self._node._node_shutdown_triggers:
                self.log.info("Node worker ended with error, and trigger '{trigger}' is active: will shutdown node ..",
                              trigger=NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR)
                term_print('CROSSBAR:NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR')
                shutdown = True

            # automatically shutdown node when no more workers are left
            #
            elif len(self._workers) == 0 and NODE_SHUTDOWN_ON_LAST_WORKER_EXIT in self._node._node_shutdown_triggers:
                self.log.info("No more node workers running, and trigger '{trigger}' is active: will shutdown node ..",
                              trigger=NODE_SHUTDOWN_ON_LAST_WORKER_EXIT)
                term_print('CROSSBAR:NODE_SHUTDOWN_ON_LAST_WORKER_EXIT')
                shutdown = True

            # initiate shutdown (but only if we are not already shutting down)
            #
            if shutdown:
                self.shutdown()
            else:
                self.log.info('Node will continue to run!')

        d_on_exit = worker.exit.addCallbacks(on_exit_success, on_exit_error)
        d_on_exit.addBoth(check_for_shutdown)

        # create a transport factory for talking WAMP to the native worker
        #
        transport_factory = create_native_worker_client_factory(self._node._router_session_factory, worker_auth_role,
                                                                worker.ready, worker.exit)
        transport_factory.noisy = False
        self._workers[worker_id].factory = transport_factory

        # now (immediately before actually forking) signal the starting of the worker
        #
        starting_info = {
            'id': worker_id,
            'status': worker.status,
            'created': utcstr(worker.created),
            'who': worker.who,
        }

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=details.caller))

        # only the following line will actually exec a new worker process - everything before is just setup
        # for this moment:
        self.log.debug(
            'Starting new managed worker process for {worker_logname} worker "{worker_id}" using {exe} with args {args}',
            worker_id=worker_id,
            worker_logname=worker_logname,
            exe=exe,
            args=args)
        d = ep.connect(transport_factory)

        def on_connect_success(proto):

            # this seems to be called immediately when the child process
            # has been forked. even if it then immediately fails because
            # e.g. the executable doesn't even exist. in other words,
            # I'm not sure under what conditions the deferred will errback ..

            self.log.debug('Native worker "{worker_id}" connected', worker_id=worker_id)

            worker.on_worker_connected(proto)

            # dynamically add a dedicated authrole to the router
            # for the worker we've just started
            self._node._add_worker_role(worker_auth_role, options)

        def on_connect_error(err):

            # not sure when this errback is triggered at all ..
            self.log.error("Internal error: connection to forked native worker failed ({err})", err=err)

            # in any case, forward the error ..
            worker.ready.errback(err)

        d.addCallbacks(on_connect_success, on_connect_error)

        return worker.ready

    @staticmethod
    def _cleanup_worker(reactor, worker):
        """
        This is called during reactor shutdown and ensures we wait for our
        subprocesses to shut down nicely.
        """
        log = make_logger()
        try:
            log.info("sending TERM to subprocess {pid}", pid=worker.pid)
            worker.proto.transport.signalProcess('TERM')
            # wait for the subprocess to shutdown; could add a timeout
            # after which we send a KILL maybe?
            d = Deferred()

            def protocol_closed(_):
                log.debug("{pid} exited", pid=worker.pid)
                d.callback(None)

            # await worker's timely demise
            worker.exit.addCallback(protocol_closed)

            def timeout(tried):
                if d.called:
                    return
                log.info("waiting for {pid} to exit...", pid=worker.pid)
                reactor.callLater(1, timeout, tried + 1)
                if tried > 20:  # or just wait forever?
                    log.info("Sending SIGKILL to {pid}", pid=worker.pid)
                    try:
                        worker.proto.transport.signalProcess('KILL')
                    except ProcessExitedAlready:
                        pass  # ignore; it's already dead
                    d.callback(None)  # or recurse more?

            timeout(0)
            return d
        except ProcessExitedAlready:
            pass  # ignore; it's already dead

    @inlineCallbacks
    def _stop_native_worker(self, worker_id, kill, details=None):

        if worker_id not in self._workers or not isinstance(self._workers[worker_id], NativeWorkerProcess):
            emsg = "Could not stop native worker: no native worker with ID '{}' currently running".format(worker_id)
            raise ApplicationError('crossbar.error.worker_not_running', emsg)

        worker = self._workers[worker_id]

        if worker.status != 'started':
            emsg = "Could not stop native worker: worker with ID '{}' is not in status 'started', but status: '{}')".format(
                worker_id, worker.status)
            raise ApplicationError('crossbar.error.worker_not_running', emsg)

        stop_info = {
            'id': worker.id,
            'type': worker.TYPE,
            'kill': kill,
            'who': details.caller if details else None,
            'when': utcnow(),
        }

        # publish management API event
        #
        yield self.publish('{}.on_stop_requested'.format(self._uri_prefix),
                           stop_info,
                           options=PublishOptions(exclude=details.caller if details else None, acknowledge=True))

        # send SIGKILL or SIGTERM to worker
        #
        if kill:
            self.log.info("Killing {worker_type} worker with ID '{worker_id}'",
                          worker_type=worker.TYPE,
                          worker_id=worker_id)
            self._workers[worker_id].proto.transport.signalProcess("KILL")
        else:
            self.log.info("Stopping {worker_type} worker with ID '{worker_id}'",
                          worker_type=worker.TYPE,
                          worker_id=worker_id)
            self._workers[worker_id].factory.stopFactory()
            self._workers[worker_id].proto.transport.signalProcess('TERM')

        # wait until the worker is actually done before we return from
        # this call
        yield self._workers[worker_id].proto.is_closed

        returnValue(stop_info)

    def _start_guest_worker(self, worker_id, worker_config, details=None):
        """
        Start a new guest process on this node.

        :param config: The guest process configuration.
        :type config: dict

        :returns: The PID of the new process.
        """
        # prohibit starting a worker twice
        #
        if worker_id in self._workers:
            emsg = "Could not start worker: a worker with ID '{}' is already running (or starting)".format(worker_id)
            self.log.error(emsg)
            raise ApplicationError('crossbar.error.worker_already_running', emsg)

        try:
            self.personality.check_guest(self.personality, worker_config)
        except Exception as e:
            raise ApplicationError('crossbar.error.invalid_configuration',
                                   'invalid guest worker configuration: {}'.format(e))

        options = worker_config.get('options', {})

        # guest process working directory
        #
        workdir = self._node._cbdir
        if 'workdir' in options:
            workdir = os.path.join(workdir, options['workdir'])
        workdir = os.path.abspath(workdir)

        # guest process executable and command line arguments
        #

        # first try to configure the fully qualified path for the guest
        # executable by joining workdir and configured exectuable ..
        exe = os.path.abspath(os.path.join(workdir, worker_config['executable']))

        if check_executable(exe):
            self.log.info("Using guest worker executable '{exe}' (executable path taken from configuration)", exe=exe)
        else:
            # try to detect the fully qualified path for the guest
            # executable by doing a "which" on the configured executable name
            exe = which(worker_config['executable'])
            if exe is not None and check_executable(exe):
                self.log.info("Using guest worker executable '{exe}' (executable path detected from environment)",
                              exe=exe)
            else:
                emsg = "Could not start worker: could not find and executable for '{}'".format(
                    worker_config['executable'])
                self.log.error(emsg)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)

        # guest process command line arguments
        #
        args = [exe]
        args.extend(worker_config.get('arguments', []))

        # guest process environment
        #
        worker_env = create_process_env(options)

        # log name of worker
        #
        worker_logname = 'Guest'

        # topic URIs used (later)
        #
        starting_topic = '{}.on_guest_starting'.format(self._uri_prefix)
        started_topic = '{}.on_guest_started'.format(self._uri_prefix)

        # add worker tracking instance to the worker map ..
        #
        worker = GuestWorkerProcess(self, worker_id, details.caller, keeplog=options.get('traceback', None))

        self._workers[worker_id] = worker

        # create a (custom) process endpoint
        #
        ep = WorkerProcessEndpoint(self._node._reactor, exe, args, path=workdir, env=worker_env, worker=worker)

        # ready handling
        #
        def on_ready_success(proto):

            self.log.info('{worker_logname} worker "{worker_id}" started',
                          worker_logname=worker_logname,
                          worker_id=worker.id)

            worker.on_worker_started(proto)

            self._node._reactor.addSystemEventTrigger(
                'before',
                'shutdown',
                self._cleanup_worker,
                self._node._reactor,
                worker,
            )

            # directory watcher
            #
            if 'watch' in options:

                if HAS_FS_WATCHER:

                    # assemble list of watched directories
                    watched_dirs = []
                    for d in options['watch'].get('directories', []):
                        watched_dirs.append(os.path.abspath(os.path.join(self._node._cbdir, d)))

                    worker.watch_timeout = options['watch'].get('timeout', 1)

                    # create a filesystem watcher
                    worker.watcher = FilesystemWatcher(workdir, watched_dirs=watched_dirs)

                    # make sure to stop the watch upon Twisted being shut down
                    def on_shutdown():
                        worker.watcher.stop()

                    self._node._reactor.addSystemEventTrigger('before', 'shutdown', on_shutdown)

                    # this handler will get fired by the watcher upon detecting an FS event
                    def on_filesystem_change(fs_event):
                        worker.watcher.stop()
                        proto.signal('TERM')

                        if options['watch'].get('action', None) == 'restart':
                            self.log.info(
                                "Filesystem watcher detected change {fs_event} - restarting guest in {watch_timeout} seconds ..",
                                fs_event=fs_event,
                                watch_timeout=worker.watch_timeout)
                            # Add a timeout large enough (perhaps add a config option later)
                            self._node._reactor.callLater(worker.watch_timeout, self.start_worker, worker_id,
                                                          worker_config, details)
                            # Shut the worker down, after the restart event is scheduled
                            # FIXME: all workers should have a stop() method ..
                            # -> 'GuestWorkerProcess' object has no attribute 'stop'
                            # worker.stop()
                        else:
                            self.log.info("Filesystem watcher detected change {fs_event} - no action taken!",
                                          fs_event=fs_event)

                    # now start watching ..
                    worker.watcher.start(on_filesystem_change)

                else:
                    self.log.warn("Cannot watch directories for changes - feature not available")

            # assemble guest worker startup information
            #
            started_info = {
                'id': worker.id,
                'status': worker.status,
                'started': utcstr(worker.started),
                'who': worker.who,
            }

            self.publish(started_topic, started_info, options=PublishOptions(exclude=details.caller))

            return started_info

        def on_ready_error(err):
            del self._workers[worker.id]

            emsg = 'Failed to start guest worker: {}'.format(err.value)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.cannot_start", emsg, ep.getlog())

        worker.ready.addCallbacks(on_ready_success, on_ready_error)

        def on_exit_success(res):
            self.log.info("Guest {worker_id} exited with success", worker_id=worker.id)
            del self._workers[worker.id]

        def on_exit_error(err):
            self.log.error("Guest {worker_id} exited with error {err.value}", worker_id=worker.id, err=err)
            del self._workers[worker.id]

        worker.exit.addCallbacks(on_exit_success, on_exit_error)

        # create a transport factory for talking WAMP to the native worker
        #
        transport_factory = create_guest_worker_client_factory(worker_config, worker.ready, worker.exit)
        transport_factory.noisy = False
        self._workers[worker_id].factory = transport_factory

        # now (immediately before actually forking) signal the starting of the worker
        #
        starting_info = {
            'id': worker_id,
            'status': worker.status,
            'created': utcstr(worker.created),
            'who': worker.who,
        }

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=details.caller))

        # now actually fork the worker ..
        #
        self.log.info('{worker_logname} "{worker_id}" process starting ..',
                      worker_logname=worker_logname,
                      worker_id=worker_id)
        self.log.debug('{worker_logname} "{worker_id}" process using command line "{cli}" ..',
                       worker_logname=worker_logname,
                       worker_id=worker_id,
                       cli=' '.join(args))

        d = ep.connect(transport_factory)

        def on_connect_success(proto):

            # this seems to be called immediately when the child process
            # has been forked. even if it then immediately fails because
            # e.g. the executable doesn't even exist. in other words,
            # I'm not sure under what conditions the deferred will
            # errback - probably only if the forking of a new process fails
            # at OS level due to out of memory conditions or such.
            self.log.debug('{worker_logname} "{worker_id}" connected',
                           worker_logname=worker_logname,
                           worker_id=worker_id)

            # do not comment this: it will lead to on_worker_started being called
            # _before_ on_worker_connected, and we don't need it!
            # worker.on_worker_connected(proto)

        def on_connect_error(err):

            # not sure when this errback is triggered at all .. see above.
            self.log.failure("Internal error: connection to forked guest worker failed ({log_failure.value})", )

            # in any case, forward the error ..
            worker.ready.errback(err)

        d.addCallbacks(on_connect_success, on_connect_error)

        return worker.ready

    def _stop_guest_worker(self, worker_id, kill=False, details=None):
        """
        Stops a currently running guest worker.

        :param worker_id: The ID of the guest worker to stop.
        :type worker_id: str
        """
        self.log.debug("stop_guest({worker_id}, kill={kill})", worker_id=worker_id, kill=kill)

        if worker_id not in self._workers or self._workers[worker_id].TYPE != 'guest':
            emsg = "Could not stop guest worker: no guest worker with ID '{}' currently running".format(worker_id)
            raise ApplicationError('crossbar.error.worker_not_running', emsg)

        worker = self._workers[worker_id]

        stop_info = {
            'id': worker.id,
            'type': 'guest',
            'kill': kill,
            'who': details.caller if details else None,
            'when': utcnow(),
        }

        try:
            if kill:
                self._workers[worker_id].proto.transport.signalProcess("KILL")
            else:
                self._workers[worker_id].proto.transport.loseConnection()
                self._workers[worker_id].proto.transport.signalProcess("TERM")
        except Exception as e:
            emsg = "Could not stop guest worker with ID '{}': {}".format(worker_id, e)
            raise ApplicationError('crossbar.error.stop_worker_failed', emsg)
        else:
            del self._workers[worker_id]

        return stop_info


def create_process_env(options):
    """
    Create worker process environment dictionary.
    """
    penv = {}

    # Usually, we want PYTHONUNBUFFERED set in child processes, *but*
    # if the user explicitly configures their environment we don't
    # stomp over it. So, a user wanting *buffered* output can set
    # PYTHONUNBUFFERED to the empty string in their config.
    saw_unbuff = False

    # by default, a worker/guest process inherits
    # complete environment
    inherit_all = True

    # check/inherit parent process environment
    if 'env' in options and 'inherit' in options['env']:
        inherit = options['env']['inherit']
        if isinstance(inherit, bool):
            inherit_all = inherit
        elif isinstance(inherit, list):
            inherit_all = False
            for v in inherit:
                if v in os.environ:
                    penv[v] = os.environ[v]
                    if v == 'PYTHONUNBUFFERED':
                        saw_unbuff = True

    if inherit_all:
        # must do deepcopy like this (os.environ is a "special" thing ..)
        for k, v in os.environ.items():
            penv[k] = v
            if k == 'PYTHONUNBUFFERED':
                saw_unbuff = True

    # explicit environment vars from config
    if 'env' in options and 'vars' in options['env']:
        for k, v in options['env']['vars'].items():
            penv[k] = v
            if k == 'PYTHONUNBUFFERED':
                saw_unbuff = True

    # if nothing so far has set PYTHONUNBUFFERED explicitly, we set it
    # ourselves.
    if not saw_unbuff:
        penv['PYTHONUNBUFFERED'] = '1'
    return penv
