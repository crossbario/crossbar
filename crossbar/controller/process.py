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

import os
import sys
import signal
from datetime import datetime
# backport of shutil.which
import shutilwhich  # noqa
import shutil

from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks, returnValue
from twisted.internet.error import ProcessExitedAlready
from twisted.python.runtime import platform

from autobahn.util import utcnow, utcstr
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, RegisterOptions

import crossbar
from crossbar.common import checkconfig
from crossbar.twisted.processutil import WorkerProcessEndpoint
from crossbar.controller.native import create_native_worker_client_factory
from crossbar.controller.guest import create_guest_worker_client_factory
from crossbar.controller.processtypes import RouterWorkerProcess, \
    ContainerWorkerProcess, \
    GuestWorkerProcess, \
    WebSocketTesteeWorkerProcess
from crossbar.common.process import NativeProcessSession
from crossbar.common.fswatcher import HAS_FS_WATCHER, FilesystemWatcher

from txaio import make_logger, get_global_log_level


__all__ = ('NodeControllerSession', 'create_process_env')


def check_executable(fn):
    """
    Check whether the given path is an executable.
    """
    return os.path.exists(fn) and os.access(fn, os.F_OK | os.X_OK) and not os.path.isdir(fn)


class NodeControllerSession(NativeProcessSession):
    """
    Singleton node WAMP session hooked up to the node management router.

    This class exposes the node's management API.
    """

    log = make_logger()

    PROCS = [
        'get_info',
        'shutdown',
        'get_workers',
        'get_worker',
        'get_worker_log',

        'start_worker',
        # 'stop_worker',

        'start_router',
        'stop_router',
        'start_container',
        'stop_container',
        'start_guest',
        'stop_guest',
        'start_websocket_testee',
        'stop_websocket_testee',
    ]

    NATIVE_WORKER = {
        'router': {
            'class': RouterWorkerProcess,
            'checkconfig': checkconfig.check_router_options,
            'logname': 'Router',
            'topics': {
                'starting': u'crossbar.node.on_router_starting',
                'started': u'crossbar.node.on_router_started',
            }
        },
        'container': {
            'class': ContainerWorkerProcess,
            'checkconfig': checkconfig.check_container_options,
            'logname': 'Container',
            'topics': {
                'starting': u'crossbar.node.on_container_starting',
                'started': u'crossbar.node.on_container_started',
            }
        },
        'websocket-testee': {
            'class': WebSocketTesteeWorkerProcess,
            'checkconfig': checkconfig.check_websocket_testee_options,
            'logname': 'WebSocketTestee',
            'topics': {
                'starting': u'crossbar.node.on_websocket_testee_starting',
                'started': u'crossbar.node.on_websocket_testee_started',
            }
        },
    }

    def __init__(self, node):
        """
        :param node: The node singleton for this node controller session.
        :type node: obj
        """
        NativeProcessSession.__init__(self, reactor=node._reactor)

        # associated node
        self._node = node
        self._realm = node._realm

        self.cbdir = self._node._cbdir

        self._uri_prefix = u'crossbar'

        self._started = None
        self._pid = os.getpid()

        # map of worker processes: worker_id -> NativeWorkerProcess
        self._workers = {}

        self._shutdown_requested = False

    def onConnect(self):

        self.log.debug("Connected to node management router")

        NativeProcessSession.onConnect(self, False)

        # self.join(self.config.realm)
        self.join(self._realm)

    @inlineCallbacks
    def onJoin(self, details):

        from autobahn.wamp.types import SubscribeOptions

        self.log.debug("Joined realm '{realm}' on node management router", realm=details.realm)

        # When a (native) worker process has connected back to the router of
        # the node controller, the worker will publish this event
        # to signal it's readyness.
        #
        def on_worker_ready(res):
            id = res['id']
            if id in self._workers:
                ready = self._workers[id].ready
                if not ready.called:
                    # fire the Deferred previously stored for
                    # signaling "worker ready"
                    ready.callback(id)
                else:
                    self.log.error("Internal error: on_worker_ready() fired for process {process}, but already called earlier",
                                   process=id)
            else:
                self.log.error("Internal error: on_worker_ready() fired for process {process}, but no process with that ID",
                               process=id)

        self.subscribe(on_worker_ready, u'crossbar.worker..on_worker_ready', SubscribeOptions(match=u'wildcard'))

        yield NativeProcessSession.onJoin(self, details)

        # register node controller procedures: 'crossbar.node.<ID>.<PROCEDURE>'
        #
        dl = []
        for proc in self.PROCS:
            uri = u'{}.{}'.format(self._uri_prefix, proc)
            self.log.debug('Registering management API procedure "{proc}"', proc=uri)
            dl.append(self.register(getattr(self, proc), uri, options=RegisterOptions(details_arg='details')))

        regs = yield DeferredList(dl)

        self.log.debug("Registered {cnt} management API procedures", cnt=len(regs))

        # we need to catch SIGINT here to properly shutdown the
        # node explicitly (a Twisted system trigger wouldn't allow us to distinguish
        # different reasons/origins of exiting ..)
        def signal_handler(signal, frame):
            # the following will shutdown the Twisted reactor in the end
            self.shutdown()
        signal.signal(signal.SIGINT, signal_handler)

        self._started = utcnow()

        self.publish(u"crossbar.on_ready")

        self.log.debug("Node controller ready")

    def get_info(self, details=None):
        """
        Return basic information about this node.

        :returns: Information on the Crossbar.io node.
        :rtype: dict
        """
        return {
            # eg "Crossbar.io COMMUNITY"
            u'title': u'{} {}'.format(self._node.PERSONALITY, crossbar.__version__),

            # basic information about the node
            u'started': self._started,
            u'controller_pid': self._pid,
            u'running_workers': len(self._workers),
            u'directory': self.cbdir,
            u'pubkey': self._node._node_key.public_key(),

            # the following 3 come from CFC (and are only filled
            # when the node personality is FABRIC!)
            u'management_realm': self._node._management_realm,
            u'management_node_id': self._node._node_id,
            u'management_session_id': self._node._manager._session_id if self._node._manager else None,
            u'management_node_extra': self._node._node_extra,
        }

    @inlineCallbacks
    def shutdown(self, restart=False, mode=None, details=None):
        """
        Explicitly stop this node.
        """
        if self._shutdown_requested:
            # we're already shutting down .. ignore ..
            return

        self._shutdown_requested = True

        self.log.info('Node shutdown requested ..')

        # publish management API event
        shutdown_info = {
            u'restart': restart,
            u'mode': mode,
            u'who': details.caller if details else None,
            u'when': utcnow()
        }
        yield self.publish(
            u'{}.on_shutdown'.format(self._uri_prefix),
            shutdown_info,
            options=PublishOptions(exclude=details.caller if details else None, acknowledge=True)
        )

        def stop_reactor():
            try:
                self._reactor.stop()
            except ReactorNotRunning:
                pass

        self._reactor.callLater(0, stop_reactor)

        returnValue(shutdown_info)

    def get_workers(self, details=None):
        """
        Returns the list of workers currently running on this node.

        :returns: List of worker processes.
        :rtype: list of dicts
        """
        now = datetime.utcnow()
        res = []
        for worker in sorted(self._workers.values(), key=lambda w: w.created):
            res.append(
                {
                    u'id': worker.id,
                    u'pid': worker.pid,
                    u'type': worker.TYPE,
                    u'status': worker.status,
                    u'created': utcstr(worker.created),
                    u'started': utcstr(worker.started),
                    u'startup_time': (worker.started - worker.created).total_seconds() if worker.started else None,
                    u'uptime': (now - worker.started).total_seconds() if worker.started else None,
                }
            )
        return res

    def get_worker(self, id, details=None):
        if id not in self._workers:
            emsg = "No worker with ID '{}'".format(id)
            raise ApplicationError(u'crossbar.error.no_such_worker', emsg)

        now = datetime.utcnow()
        worker = self._workers[id]

        worker_info = {
            u'id': worker.id,
            u'pid': worker.pid,
            u'type': worker.TYPE,
            u'status': worker.status,
            u'created': utcstr(worker.created),
            u'started': utcstr(worker.started),
            u'startup_time': (worker.started - worker.created).total_seconds() if worker.started else None,
            u'uptime': (now - worker.started).total_seconds() if worker.started else None,
        }

        return worker_info

    def get_worker_log(self, id, limit=100, details=None):
        """
        Get buffered log for a worker.

        :param limit: Optionally, limit the amount of log entries returned
           to the last N entries.
        :type limit: None or int

        :return: Buffered log for worker.
        :rtype: list
        """
        if id not in self._workers:
            emsg = "No worker with ID '{}'".format(id)
            raise ApplicationError(u'crossbar.error.no_such_worker', emsg)

        return self._workers[id].getlog(limit)

    def start_worker(self, worker_id, worker_type, worker_options=None, details=None):
        if worker_type in [u'router', u'container', u'websocket-testee']:
            return self._start_native_worker(worker_type, worker_id, worker_options, details=details)

        elif worker_type in [u'guest']:
            return self.start_guest(worker_id, worker_options, details=details)

        else:
            raise Exception('invalid worker type "{}"'.format(worker_type))

    def start_router(self, id, options=None, details=None):
        """
        Start a new router worker: a Crossbar.io native worker process
        that runs a WAMP router.

        :param id: The worker ID to start this router with.
        :type id: str
        :param options: The router worker options.
        :type options: dict
        """
        self.log.debug("start_router({id}, options={options})",
                       id=id, options=options)

        return self._start_native_worker('router', id, options, details=details)

    def start_container(self, id, options=None, details=None):
        """
        Start a new container worker: a Crossbar.io native worker process
        that can host WAMP application components written in Python.

        :param id: The worker ID to start this container with.
        :type id: str
        :param options: The container worker options.
        :type options: dict
        """
        self.log.debug("start_container(id = {id}, options = {options})",
                       id=id, options=options)

        return self._start_native_worker('container', id, options, details=details)

    def start_websocket_testee(self, id, options=None, details=None):
        """
        Start a new websocket-testee worker: a Crossbar.io native worker process
        that runs a plain echo'ing WebSocket server.

        :param id: The worker ID to start this router with.
        :type id: str
        :param options: The worker options.
        :type options: dict
        """
        self.log.debug("start_websocket_testee({id}, options={options})",
                       id=id, options=options)

        return self._start_native_worker('websocket-testee', id, options, details=details)

    def _start_native_worker(self, worker_type, id, options=None, details=None):

        # prohibit starting a worker twice
        #
        if id in self._workers:
            emsg = "Could not start worker: a worker with ID '{}' is already running (or starting)".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.worker_already_running', emsg)

        # check worker options
        #
        options = options or {}
        try:
            if worker_type in self.NATIVE_WORKER:
                if self.NATIVE_WORKER[worker_type]['checkconfig']:
                    self.NATIVE_WORKER[worker_type]['checkconfig'](options)
                else:
                    self.log.warn('No checkconfig for worker type "{worker_type}" implemented!', worker_type=worker_type)
            else:
                raise Exception('invalid worker type "{}"'.format(worker_type))
        except Exception as e:
            emsg = "Could not start native worker: invalid configuration ({})".format(e)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.invalid_configuration', emsg)

        # allow override Python executable from options
        #
        if 'python' in options:
            exe = options['python']

            # the executable must be an absolute path, e.g. /home/oberstet/pypy-2.2.1-linux64/bin/pypy
            #
            if not os.path.isabs(exe):
                emsg = "Invalid worker configuration: python executable '{}' must be an absolute path".format(exe)
                self.log.error(emsg)
                raise ApplicationError(u'crossbar.error.invalid_configuration', emsg)

            # of course the path must exist and actually be executable
            #
            if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
                emsg = "Invalid worker configuration: python executable '{}' does not exist or isn't an executable".format(exe)
                self.log.error(emsg)
                raise ApplicationError(u'crossbar.error.invalid_configuration', emsg)
        else:
            exe = sys.executable

        # assemble command line for forking the worker
        #
        # all native workers (routers and containers for now) start
        # from the same script in crossbar/worker/process.py -- we're
        # invoking via "-m" so that .pyc files, __pycache__ etc work
        # properly.
        #
        args = [exe, "-u", "-m", "crossbar.worker.process"]
        args.extend(["--cbdir", self._node._cbdir])
        args.extend(["--worker", str(id)])
        args.extend(["--realm", self._realm])
        args.extend(["--type", worker_type])
        args.extend(["--loglevel", get_global_log_level()])

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
        worker_env["PYTHONPATH"] = os.pathsep.join(sys.path)

        # log name of worker
        #
        worker_logname = self.NATIVE_WORKER[worker_type]['logname']

        # each worker is run under its own dedicated WAMP auth role
        #
        worker_auth_role = u'crossbar.worker.{}'.format(id)

        # topic URIs used (later)
        #
        starting_topic = self.NATIVE_WORKER[worker_type]['topics']['starting']
        started_topic = self.NATIVE_WORKER[worker_type]['topics']['started']

        # add worker tracking instance to the worker map ..
        #
        WORKER = self.NATIVE_WORKER[worker_type]['class']
        worker = WORKER(self, id, details.caller, keeplog=options.get('traceback', None))
        self._workers[id] = worker

        # create a (custom) process endpoint.
        #
        if platform.isWindows():
            childFDs = None  # Use the default Twisted ones
        else:
            # The communication between controller and container workers is
            # using WAMP running over 2 pipes.
            # For controller->container traffic this runs over FD 0 (`stdin`)
            # and for the container->controller traffic, this runs over FD 3.
            #
            # Note: We use FD 3, not FD 1 (`stdout`) or FD 2 (`stderr`) for
            # container->controller traffic, so that components running in the
            # container which happen to write to `stdout` or `stderr` do not
            # interfere with the container-controller communication.
            childFDs = {0: "w", 1: "r", 2: "r", 3: "r"}

        ep = WorkerProcessEndpoint(
            self._node._reactor, exe, args, env=worker_env, worker=worker,
            childFDs=childFDs)

        # ready handling
        #
        def on_ready_success(id):
            self.log.info('{worker_type} worker "{worker_id}" process {pid} started',
                          worker_type=worker_logname, worker_id=worker.id, pid=worker.pid)

            self._node._reactor.addSystemEventTrigger(
                'before', 'shutdown',
                self._cleanup_worker, self._node._reactor, worker,
            )

            worker.status = 'started'
            worker.started = datetime.utcnow()

            started_info = {
                u'id': worker.id,
                u'status': worker.status,
                u'started': utcstr(worker.started),
                u'who': worker.who,
            }

            # FIXME: make start of stats printer dependent on log level ..
            worker.log_stats(5.)

            self.publish(started_topic, started_info, options=PublishOptions(exclude=details.caller))

            return started_info

        def on_ready_error(err):
            del self._workers[worker.id]
            emsg = 'Failed to start native worker: {}'.format(err.value)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.cannot_start", emsg, worker.getlog())

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
            self.log.info('Checking for node shutdown: worker_exit_success={worker_exit_success}, shutdown_requested={shutdown_requested}, node_shutdown_triggers={node_shutdown_triggers}', worker_exit_success=was_successful, shutdown_requested=self._shutdown_requested, node_shutdown_triggers=self._node._node_shutdown_triggers)

            shutdown = self._shutdown_requested

            # automatically shutdown node whenever a worker ended (successfully, or with error)
            #
            if checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT in self._node._node_shutdown_triggers:
                self.log.info("Node worker ended, and trigger '{trigger}' active", trigger=checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT)
                shutdown = True

            # automatically shutdown node when worker ended with error
            #
            if not was_successful and checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR in self._node._node_shutdown_triggers:
                self.log.info("Node worker ended with error, and trigger '{trigger}' active", trigger=checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR)
                shutdown = True

            # automatically shutdown node when no more workers are left
            #
            if len(self._workers) == 0 and checkconfig.NODE_SHUTDOWN_ON_LAST_WORKER_EXIT in self._node._node_shutdown_triggers:
                self.log.info("No more node workers running, and trigger '{trigger}' active", trigger=checkconfig.NODE_SHUTDOWN_ON_LAST_WORKER_EXIT)
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
        transport_factory = create_native_worker_client_factory(self._node._router_session_factory, worker_auth_role, worker.ready, worker.exit)
        transport_factory.noisy = False
        self._workers[id].factory = transport_factory

        # now (immediately before actually forking) signal the starting of the worker
        #
        starting_info = {
            u'id': id,
            u'status': worker.status,
            u'created': utcstr(worker.created),
            u'who': worker.who,
        }

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=details.caller))

        # now actually fork the worker ..
        #
        self.log.info('{worker_logname} worker "{worker_id}" starting ..',
                      worker_logname=worker_logname, worker_id=id)
        self.log.debug('{worker_logname} "{worker_id}" command line is "{cmdline}"',
                       worker_logname=worker_logname, worker_id=id, cmdline=' '.join(args))

        d = ep.connect(transport_factory)

        def on_connect_success(proto):

            # this seems to be called immediately when the child process
            # has been forked. even if it then immediately fails because
            # e.g. the executable doesn't even exist. in other words,
            # I'm not sure under what conditions the deferred will errback ..

            pid = proto.transport.pid
            self.log.debug("Native worker process connected with PID {pid}",
                           pid=pid)

            # note the PID of the worker
            worker.pid = pid

            # proto is an instance of NativeWorkerClientProtocol
            worker.proto = proto

            worker.status = 'connected'
            worker.connected = datetime.utcnow()

            # dynamically add a dedicated authrole to the router
            # for the worker we've just started
            self._node._add_worker_role(worker_auth_role, options)

        def on_connect_error(err):

            # not sure when this errback is triggered at all ..
            self.log.error("Interal error: connection to forked native worker failed ({err})", err=err)

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

    def stop_router(self, id, kill=False, details=None):
        """
        Stops a currently running router worker.

        :param id: The ID of the router worker to stop.
        :type id: str
        :param kill: If `True`, kill the process. Otherwise, gracefully
                     shut down the worker.
        :type kill: bool

        :returns: Stopping information from the worker.
        :rtype: dict
        """
        self.log.debug("stop_router({id}, kill={kill})",
                       id=id, kill=kill)

        return self._stop_native_worker('router', id, kill, details=details)

    def stop_container(self, id, kill=False, details=None):
        """
        Stops a currently running container worker.

        :param id: The ID of the container worker to stop.
        :type id: str
        :param kill: If `True`, kill the process. Otherwise, gracefully
                     shut down the worker.
        :type kill: bool

        :returns: Stopping information from the worker.
        :rtype: dict
        """
        self.log.debug("stop_container({id}, kill={kill})",
                       id=id, kill=kill)

        return self._stop_native_worker('container', id, kill, details=details)

    def stop_websocket_testee(self, id, kill=False, details=None):
        """
        Stops a currently running websocket-testee worker.

        :param id: The ID of the worker to stop.
        :type id: str
        :param kill: If `True`, kill the process. Otherwise, gracefully
                     shut down the worker.
        :type kill: bool

        :returns: Stopping information from the worker.
        :rtype: dict
        """
        self.log.debug("stop_websocket_testee({id}, kill={kill})",
                       id=id, kill=kill)

        return self._stop_native_worker('websocket-testee', id, kill, details=details)

    @inlineCallbacks
    def _stop_native_worker(self, worker_type, id, kill, details=None):

        if id not in self._workers or self._workers[id].TYPE != worker_type:
            emsg = "Could not stop native worker: no {} worker with ID '{}' currently running".format(worker_type, id)
            raise ApplicationError(u'crossbar.error.worker_not_running', emsg)

        worker = self._workers[id]

        if worker.status != 'started':
            emsg = "Could not stop native worker: worker with ID '{}' is not in status 'started', but status: '{}')".format(id, worker.status)
            raise ApplicationError(u'crossbar.error.worker_not_running', emsg)

        stop_info = {
            u'id': worker.id,
            u'type': worker_type,
            u'kill': kill,
            u'who': details.caller if details else None,
            u'when': utcnow(),
        }

        # publish management API event
        #
        yield self.publish(
            u'{}.on_stop_requested'.format(self._uri_prefix),
            stop_info,
            options=PublishOptions(exclude=details.caller if details else None, acknowledge=True)
        )

        # send SIGKILL or SIGTERM to worker
        #
        if kill:
            self.log.info("Killing {worker_type} worker with ID '{id}'",
                          worker_type=worker_type, id=id)
            self._workers[id].proto.transport.signalProcess("KILL")
        else:
            self.log.info("Stopping {worker_type} worker with ID '{id}'",
                          worker_type=worker_type, id=id)
            self._workers[id].factory.stopFactory()
            self._workers[id].proto.transport.signalProcess('TERM')

        returnValue(stop_info)

    def start_guest(self, id, config, details=None):
        """
        Start a new guest process on this node.

        :param config: The guest process configuration.
        :type config: obj

        :returns: int -- The PID of the new process.
        """
        # prohibit starting a worker twice
        #
        if id in self._workers:
            emsg = "Could not start worker: a worker with ID '{}' is already running (or starting)".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.worker_already_running', emsg)

        try:
            checkconfig.check_guest(config)
        except Exception as e:
            raise ApplicationError(u'crossbar.error.invalid_configuration', 'invalid guest worker configuration: {}'.format(e))

        options = config.get('options', {})

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
        exe = os.path.abspath(os.path.join(workdir, config['executable']))

        if check_executable(exe):
            self.log.info("Using guest worker executable '{exe}' (executable path taken from configuration)",
                          exe=exe)
        else:
            # try to detect the fully qualified path for the guest
            # executable by doing a "which" on the configured executable name
            exe = shutil.which(config['executable'])
            if exe is not None and check_executable(exe):
                self.log.info("Using guest worker executable '{exe}' (executable path detected from environment)",
                              exe=exe)
            else:
                emsg = "Could not start worker: could not find and executable for '{}'".format(config['executable'])
                self.log.error(emsg)
                raise ApplicationError(u'crossbar.error.invalid_configuration', emsg)

        # guest process command line arguments
        #
        args = [exe]
        args.extend(config.get('arguments', []))

        # guest process environment
        #
        worker_env = create_process_env(options)

        # log name of worker
        #
        worker_logname = 'Guest'

        # topic URIs used (later)
        #
        starting_topic = u'{}.on_guest_starting'.format(self._uri_prefix)
        started_topic = u'{}.on_guest_started'.format(self._uri_prefix)

        # add worker tracking instance to the worker map ..
        #
        worker = GuestWorkerProcess(self, id, details.caller, keeplog=options.get('traceback', None))

        self._workers[id] = worker

        # create a (custom) process endpoint
        #
        ep = WorkerProcessEndpoint(self._node._reactor, exe, args, path=workdir, env=worker_env, worker=worker)

        # ready handling
        #
        def on_ready_success(proto):

            worker.pid = proto.transport.pid
            worker.status = 'started'
            worker.started = datetime.utcnow()

            self.log.info('{worker_logname} worker "{worker_id}" process {pid} started',
                          worker_logname=worker_logname, worker_id=worker.id, pid=worker.pid)

            self._node._reactor.addSystemEventTrigger(
                'before', 'shutdown',
                self._cleanup_worker, self._node._reactor, worker,
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
                            self.log.info("Filesystem watcher detected change {fs_event} - restarting guest in {watch_timeout} seconds ..", fs_event=fs_event, watch_timeout=worker.watch_timeout)
                            # Add a timeout large enough (perhaps add a config option later)
                            self._node._reactor.callLater(worker.watch_timeout, self.start_guest, id, config, details)
                            # Shut the worker down, after the restart event is scheduled
                            # FIXME: all workers should have a stop() method ..
                            # -> 'GuestWorkerProcess' object has no attribute 'stop'
                            # worker.stop()
                        else:
                            self.log.info("Filesystem watcher detected change {fs_event} - no action taken!", fs_event=fs_event)

                    # now start watching ..
                    worker.watcher.start(on_filesystem_change)

                else:
                    self.log.warn("Cannot watch directories for changes - feature not available")

            # assemble guest worker startup information
            #
            started_info = {
                u'id': worker.id,
                u'status': worker.status,
                u'started': utcstr(worker.started),
                u'who': worker.who,
            }

            self.publish(started_topic, started_info, options=PublishOptions(exclude=details.caller))

            return started_info

        def on_ready_error(err):
            del self._workers[worker.id]

            emsg = 'Failed to start guest worker: {}'.format(err.value)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.cannot_start", emsg, ep.getlog())

        worker.ready.addCallbacks(on_ready_success, on_ready_error)

        def on_exit_success(res):
            self.log.info("Guest {id} exited with success", id=worker.id)
            del self._workers[worker.id]

        def on_exit_error(err):
            self.log.error("Guest {id} exited with error {err.value}",
                           id=worker.id, err=err)
            del self._workers[worker.id]

        worker.exit.addCallbacks(on_exit_success, on_exit_error)

        # create a transport factory for talking WAMP to the native worker
        #
        transport_factory = create_guest_worker_client_factory(config, worker.ready, worker.exit)
        transport_factory.noisy = False
        self._workers[id].factory = transport_factory

        # now (immediately before actually forking) signal the starting of the worker
        #
        starting_info = {
            u'id': id,
            u'status': worker.status,
            u'created': utcstr(worker.created),
            u'who': worker.who,
        }

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=details.caller))

        # now actually fork the worker ..
        #
        self.log.info('{worker_logname} "{worker_id}" process starting ..',
                      worker_logname=worker_logname, worker_id=id)
        self.log.debug('{worker_logname} "{worker_id}" process using command line "{cli}" ..',
                       worker_logname=worker_logname, worker_id=id, cli=' '.join(args))

        d = ep.connect(transport_factory)

        def on_connect_success(proto):

            # this seems to be called immediately when the child process
            # has been forked. even if it then immediately fails because
            # e.g. the executable doesn't even exist. in other words,
            # I'm not sure under what conditions the deferred will
            # errback - probably only if the forking of a new process fails
            # at OS level due to out of memory conditions or such.

            pid = proto.transport.pid
            self.log.debug("Guest worker process connected with PID {pid}",
                           pid=pid)

            worker.pid = pid

            # proto is an instance of GuestWorkerClientProtocol
            worker.proto = proto

            worker.status = 'connected'
            worker.connected = datetime.utcnow()

        def on_connect_error(err):

            # not sure when this errback is triggered at all .. see above.
            self.log.failure(
                "Internal error: connection to forked guest worker failed ({log_failure.value})",
            )

            # in any case, forward the error ..
            worker.ready.errback(err)

        d.addCallbacks(on_connect_success, on_connect_error)

        return worker.ready

    def stop_guest(self, id, kill=False, details=None):
        """
        Stops a currently running guest worker.

        :param id: The ID of the guest worker to stop.
        :type id: str
        """
        self.log.debug("stop_guest({id}, kill={kill})",
                       id=id, kill=kill)

        if id not in self._workers or self._workers[id].worker_type != 'guest':
            emsg = "Could not stop guest worker: no guest worker with ID '{}' currently running".format(id)
            raise ApplicationError(u'crossbar.error.worker_not_running', emsg)

        try:
            if kill:
                self._workers[id].proto.transport.signalProcess("KILL")
            else:
                self._workers[id].proto.transport.loseConnection()
        except Exception as e:
            emsg = "Could not stop guest worker with ID '{}': {}".format(id, e)
            raise ApplicationError(u'crossbar.error.stop_worker_failed', emsg)
        else:
            del self._workers[id]


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
