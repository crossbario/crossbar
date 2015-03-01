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

import os
import sys
import pkg_resources

# backport of shutil.which
import shutilwhich  # noqa
import shutil

from datetime import datetime

from twisted.python import log
from twisted.internet.defer import DeferredList, returnValue, inlineCallbacks

from twisted.internet.threads import deferToThread

from autobahn.util import utcnow, utcstr
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, RegisterOptions
from autobahn.twisted.util import sleep

from crossbar.common import checkconfig
from crossbar.twisted.processutil import WorkerProcessEndpoint
from crossbar.controller.native import create_native_worker_client_factory
from crossbar.controller.guest import create_guest_worker_client_factory

from crossbar.controller.processtypes import RouterWorkerProcess, \
    ContainerWorkerProcess, \
    GuestWorkerProcess
from crossbar.common.process import NativeProcessSession


from twisted.internet import reactor
from crossbar.twisted.endpoint import create_listening_port_from_config
from autobahn.twisted.websocket import WampWebSocketServerFactory

from crossbar.platform import HAS_FSNOTIFY, DirWatcher


__all__ = ('NodeControllerSession', 'create_process_env')


def check_executable(fn):
    """
    Check whether the given path is an executable.
    """
    return os.path.exists(fn) and os.access(fn, os.F_OK | os.X_OK) and not os.path.isdir(fn)


class ManagementTransport:

    """
    Local management service running inside node controller.
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


class NodeControllerSession(NativeProcessSession):

    """
    Singleton node WAMP session hooked up to the node management router.

    This class exposes the node's management API.
    """

    def __init__(self, node):
        """
        :param node: The node singleton for this node controller session.
        :type node: obj
        """
        NativeProcessSession.__init__(self)
        # self.debug = node.debug
        self.debug = False
        self.debug_app = False

        # associated node
        self._node = node
        self._node_id = node._node_id
        self._realm = node._realm

        self.cbdir = self._node._cbdir

        self._created = utcnow()
        self._pid = os.getpid()

        # map of worker processes: worker_id -> NativeWorkerProcess
        self._workers = {}

        self._management_transport = None

    def onConnect(self):
        # self._uri_prefix = 'crossbar.node.{}'.format(self.config.extra.node)
        self._uri_prefix = 'crossbar.node.{}'.format(self._node_id)

        NativeProcessSession.onConnect(self, False)

        # self.join(self.config.realm)
        self.join(self._realm)

    @inlineCallbacks
    def onJoin(self, details):

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
                    log.msg("INTERNAL ERROR: on_worker_ready() fired for process {} - ready already called".format(id))
            else:
                log.msg("INTERNAL ERROR: on_worker_ready() fired for process {} - no process with that ID".format(id))

        self.subscribe(on_worker_ready, 'crossbar.node.{}.on_worker_ready'.format(self._node_id))

        yield NativeProcessSession.onJoin(self, details)

        # register node controller procedures: 'crossbar.node.<ID>.<PROCEDURE>'
        #
        procs = [
            'shutdown',
            'start_management_transport',
            'get_info',
            'get_workers',
            'get_worker_log',
            'start_router',
            'stop_router',
            'start_container',
            'stop_container',
            'start_guest',
            'stop_guest',
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

        # FIXME: publish node ready event

    @inlineCallbacks
    def shutdown(self, restart=False, details=None):
        """
        Stop this node.
        """
        log.msg("Shutting down node ..")

        shutdown_topic = 'crossbar.node.{}.on_shutdown'.format(self._node_id)

        shutdown_info = {
        }

        yield self.publish(shutdown_topic, shutdown_info, options=PublishOptions(acknowledge=True))
        yield sleep(3)

        self._node._reactor.stop()

    @inlineCallbacks
    def start_management_transport(self, config, details=None):
        """
        Start transport for local management router.

        :param config: Transport configuration.
        :type config: obj
        """
        if self.debug:
            log.msg("{}.start_management_transport".format(self.__class__.__name__), config)

        if self._management_transport:
            emsg = "ERROR: could not start management transport - already running (or starting)"
            log.msg(emsg)
            raise ApplicationError("crossbar.error.already_started", emsg)

        try:
            checkconfig.check_listening_transport_websocket(config)
        except Exception as e:
            emsg = "ERROR: could not start management transport - invalid configuration ({})".format(e)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.invalid_configuration', emsg)

        self._management_transport = ManagementTransport(config, details.caller)

        factory = WampWebSocketServerFactory(self._node._router_session_factory, debug=False)
        factory.setProtocolOptions(failByDrop=False)
        factory.noisy = False

        starting_topic = '{}.on_management_transport_starting'.format(self._uri_prefix)
        starting_info = self._management_transport.marshal()

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=[details.caller]))

        try:
            self._management_transport.port = yield create_listening_port_from_config(config['endpoint'], factory, self.cbdir, reactor)
        except Exception as e:
            self._management_transport = None
            emsg = "ERROR: local management service endpoint cannot listen - {}".format(e)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.cannot_listen", emsg)

        # alright, manhole has started
        self._management_transport.started = datetime.utcnow()
        self._management_transport.status = 'started'

        started_topic = '{}.on_management_transport_started'.format(self._uri_prefix)
        started_info = self._management_transport.marshal()
        self.publish(started_topic, started_info, options=PublishOptions(exclude=[details.caller]))

        returnValue(started_info)

    def get_info(self, details=None):
        """
        Return node information.
        """
        return {
            'created': self._created,
            'pid': self._pid,
            'workers': len(self._workers),
            'directory': self.cbdir,
            'wamplets': self._get_wamplets()
        }

    def _get_wamplets(self):
        """
        List installed WAMPlets.
        """
        res = []

        for entrypoint in pkg_resources.iter_entry_points('autobahn.twisted.wamplet'):
            try:
                e = entrypoint.load()
            except Exception as e:
                pass
            else:
                ep = {}
                ep['dist'] = entrypoint.dist.key
                ep['version'] = entrypoint.dist.version
                ep['location'] = entrypoint.dist.location
                ep['name'] = entrypoint.name
                ep['module_name'] = entrypoint.module_name
                ep['entry_point'] = str(entrypoint)

                if hasattr(e, '__doc__') and e.__doc__:
                    ep['doc'] = e.__doc__.strip()
                else:
                    ep['doc'] = None

                ep['meta'] = e(None)

                res.append(ep)

        return sorted(res)

    def get_workers(self, details=None):
        """
        Returns the list of processes currently running on this node.

        :returns: list -- List of worker processes.
        """
        now = datetime.utcnow()
        res = []
        for worker in sorted(self._workers.values(), key=lambda w: w.created):
            res.append({
                'id': worker.id,
                'pid': worker.pid,
                'type': worker.TYPE,
                'status': worker.status,
                'created': utcstr(worker.created),
                'started': utcstr(worker.started),
                'startup_time': (worker.started - worker.created).total_seconds() if worker.started else None,
                'uptime': (now - worker.started).total_seconds() if worker.started else None,
            })
        return res

    def get_worker_log(self, id, limit=None, details=None):
        """
        Get buffered worker log.

        :param limit: Optionally, limit the amount of log entries returned
           to the last N entries.
        :type limit: None or int

        :returns: list -- Buffered log.
        """
        if id not in self._workers:
            emsg = "ERROR: no worker with ID '{}'".format(id)
            raise ApplicationError('crossbar.error.no_such_worker', emsg)

        return self._workers[id].getlog(limit)

    def start_router(self, id, options=None, details=None):
        """
        Start a new router worker: a Crossbar.io native worker process
        that runs a WAMP router.

        :param id: The worker ID to start this router with.
        :type id: str
        :param options: The router worker options.
        :type options: dict
        """
        if self.debug:
            log.msg("NodeControllerSession.start_router", id, options)

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
        if self.debug:
            log.msg("NodeControllerSession.start_container", id, options)

        return self._start_native_worker('container', id, options, details=details)

    def _start_native_worker(self, wtype, id, options=None, details=None):

        assert(wtype in ['router', 'container'])

        # prohibit starting a worker twice
        #
        if id in self._workers:
            emsg = "ERROR: could not start worker - a worker with ID '{}'' is already running (or starting)".format(id)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.worker_already_running', emsg)

        # check worker options
        #
        options = options or {}
        try:
            if wtype == 'router':
                checkconfig.check_router_options(options)
            elif wtype == 'container':
                checkconfig.check_container_options(options)
            else:
                raise Exception("logic error")
        except Exception as e:
            emsg = "ERROR: could not start native worker - invalid configuration ({})".format(e)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.invalid_configuration', emsg)

        # allow override Python executable from options
        #
        if 'python' in options:
            exe = options['python']

            # the executable must be an absolute path, e.g. /home/oberstet/pypy-2.2.1-linux64/bin/pypy
            #
            if not os.path.isabs(exe):
                emsg = "ERROR: python '{}' from worker options must be an absolute path".format(exe)
                log.msg(emsg)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)

            # of course the path must exist and actually be executable
            #
            if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
                emsg = "ERROR: python '{}' from worker options does not exist or isn't an executable".format(exe)
                log.msg(emsg)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)
        else:
            exe = sys.executable

        # all native workers (routers and containers for now) start from the same script
        #
        filename = pkg_resources.resource_filename('crossbar', 'worker/process.py')

        # assemble command line for forking the worker
        #
        args = [exe, "-u", filename]
        args.extend(["--cbdir", self._node._cbdir])
        args.extend(["--node", str(self._node_id)])
        args.extend(["--worker", str(id)])
        args.extend(["--realm", self._realm])
        args.extend(["--type", wtype])

        # allow override worker process title from options
        #
        if options.get('title', None):
            args.extend(['--title', options['title']])

        # allow overriding debug flag from options
        #
        if options.get('debug', self.debug):
            args.append('--debug')

        # forward explicit reactor selection
        #
        if 'reactor' in options and sys.platform in options['reactor']:
            args.extend(['--reactor', options['reactor'][sys.platform]])
        elif self._node.options.reactor:
            args.extend(['--reactor', self._node.options.reactor])

        # create worker process environment
        #
        worker_env = create_process_env(options)

        # log name of worker
        #
        worker_logname = {'router': 'Router', 'container': 'Container'}.get(wtype, 'Worker')

        # topic URIs used (later)
        #
        if wtype == 'router':
            starting_topic = 'crossbar.node.{}.on_router_starting'.format(self._node_id)
            started_topic = 'crossbar.node.{}.on_router_started'.format(self._node_id)
        elif wtype == 'container':
            starting_topic = 'crossbar.node.{}.on_container_starting'.format(self._node_id)
            started_topic = 'crossbar.node.{}.on_container_started'.format(self._node_id)
        else:
            raise Exception("logic error")

        # add worker tracking instance to the worker map ..
        #
        if wtype == 'router':
            worker = RouterWorkerProcess(self, id, details.caller, keeplog=options.get('traceback', None))
        elif wtype == 'container':
            worker = ContainerWorkerProcess(self, id, details.caller, keeplog=options.get('traceback', None))
        else:
            raise Exception("logic error")

        self._workers[id] = worker

        # create a (custom) process endpoint
        #
        ep = WorkerProcessEndpoint(self._node._reactor, exe, args, env=worker_env, worker=worker)

        # ready handling
        #
        def on_ready_success(id):
            log.msg("{} with ID '{}' and PID {} started".format(worker_logname, worker.id, worker.pid))

            worker.status = 'started'
            worker.started = datetime.utcnow()

            started_info = {
                'id': worker.id,
                'status': worker.status,
                'started': utcstr(worker.started),
                'who': worker.who
            }

            self.publish(started_topic, started_info, options=PublishOptions(exclude=[details.caller]))

            return started_info

        def on_ready_error(err):
            del self._workers[worker.id]

            emsg = 'ERROR: failed to start native worker - {}'.format(err.value)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.cannot_start", emsg, worker.getlog())

        worker.ready.addCallbacks(on_ready_success, on_ready_error)

        def on_exit_success(res):
            del self._workers[worker.id]

        def on_exit_error(err):
            del self._workers[worker.id]

        worker.exit.addCallbacks(on_exit_success, on_exit_error)

        # create a transport factory for talking WAMP to the native worker
        #
        transport_factory = create_native_worker_client_factory(self._node._router_session_factory, worker.ready, worker.exit)
        transport_factory.noisy = False
        self._workers[id].factory = transport_factory

        # now (immediately before actually forking) signal the starting of the worker
        #
        starting_info = {
            'id': id,
            'status': worker.status,
            'created': utcstr(worker.created),
            'who': worker.who
        }

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=[details.caller]))

        # now actually fork the worker ..
        #
        if self.debug:
            log.msg("Starting {} with ID '{}' using command line '{}' ..".format(worker_logname, id, ' '.join(args)))
        else:
            log.msg("Starting {} with ID '{}' ..".format(worker_logname, id))

        d = ep.connect(transport_factory)

        def on_connect_success(proto):

            # this seems to be called immediately when the child process
            # has been forked. even if it then immediately fails because
            # e.g. the executable doesn't even exist. in other words,
            # I'm not sure under what conditions the deferred will errback ..

            pid = proto.transport.pid
            if self.debug:
                log.msg("Native worker process connected with PID {}".format(pid))

            # note the PID of the worker
            worker.pid = pid

            # proto is an instance of NativeWorkerClientProtocol
            worker.proto = proto

            worker.status = 'connected'
            worker.connected = datetime.utcnow()

        def on_connect_error(err):

            # not sure when this errback is triggered at all ..
            if self.debug:
                log.msg("ERROR: Connecting forked native worker failed - {}".format(err))

            # in any case, forward the error ..
            worker.ready.errback(err)

        d.addCallbacks(on_connect_success, on_connect_error)

        return worker.ready

    def stop_router(self, id, kill=False, details=None):
        """
        Stops a currently running router worker.

        :param id: The ID of the router worker to stop.
        :type id: str
        :param kill: If `True`, kill the process. Otherwise, gracefully
                     shut down the worker.
        :type kill: bool
        """
        if self.debug:
            log.msg("NodeControllerSession.start_router", id, kill)

        return self._stop_native_worker('router', id, kill, details=details)

    def stop_container(self, id, kill=False, details=None):
        """
        Stops a currently running container worker.

        :param id: The ID of the container worker to stop.
        :type id: str
        :param kill: If `True`, kill the process. Otherwise, gracefully
                     shut down the worker.
        :type kill: bool
        """
        if self.debug:
            log.msg("NodeControllerSession.stop_container", id, kill)

        return self._stop_native_worker('container', id, kill, details=details)

    def _stop_native_worker(self, wtype, id, kill, details=None):

        assert(wtype in ['router', 'container'])

        if id not in self._workers or self._workers[id].TYPE != wtype:
            emsg = "ERROR: no {} worker with ID '{}' currently running".format(wtype, id)
            raise ApplicationError('crossbar.error.worker_not_running', emsg)

        worker = self._workers[id]

        if worker.status != 'started':
            emsg = "ERROR: worker with ID '{}' is not in 'started' status (current status: '{}')".format(id, worker.status)
            raise ApplicationError('crossbar.error.worker_not_running', emsg)

        if kill:
            log.msg("Killing {} worker with ID '{}'".format(wtype, id))
            self._workers[id].proto.transport.signalProcess("KILL")
        else:
            log.msg("Stopping {} worker with ID '{}'".format(wtype, id))
            self._workers[id].factory.stopFactory()
            # self._workers[id].proto._session.leave()

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
            emsg = "ERROR: could not start worker - a worker with ID '{}' is already running (or starting)".format(id)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.worker_already_running', emsg)

        try:
            checkconfig.check_guest(config)
        except Exception as e:
            raise ApplicationError('crossbar.error.invalid_configuration', 'invalid guest worker configuration: {}'.format(e))

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
            log.msg("Using guest worker executable '{}' (executable path taken from configuration)".format(exe))
        else:
            # try to detect the fully qualified path for the guest
            # executable by doing a "which" on the configured executable name
            exe = shutil.which(config['executable'])
            if exe is not None and check_executable(exe):
                log.msg("Using guest worker executable '{}' (executable path detected from environment)".format(exe))
            else:
                emsg = "ERROR: could not start worker - could not find and executable for '{}'".format(config['executable'])
                log.msg(emsg)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)

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
        starting_topic = 'crossbar.node.{}.on_guest_starting'.format(self._node_id)
        started_topic = 'crossbar.node.{}.on_guest_started'.format(self._node_id)

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

            log.msg("{} with ID '{}' and PID {} started".format(worker_logname, worker.id, worker.pid))

            # directory watcher
            #
            if 'watch' in options:

                if HAS_FSNOTIFY:

                    # assemble list of watched directories
                    watched_dirs = []
                    for d in options['watch'].get('directories', []):
                        watched_dirs.append(os.path.abspath(os.path.join(self._node._cbdir, d)))

                    # create a directory watcher
                    worker.watcher = DirWatcher(dirs=watched_dirs, notify_once=True)

                    # make sure to stop the background thread running inside the
                    # watcher upon Twisted being shut down
                    def on_shutdown():
                        worker.watcher.stop()

                    reactor.addSystemEventTrigger('before', 'shutdown', on_shutdown)

                    # this handler will get fired by the watcher upon detecting an FS event
                    def on_fsevent(evt):
                        worker.watcher.stop()
                        proto.signal('TERM')

                        if options['watch'].get('action', None) == 'restart':
                            log.msg("Restarting guest ..")
                            reactor.callLater(0.1, self.start_guest, id, config, details)

                    # now run the watcher on a background thread
                    deferToThread(worker.watcher.loop, on_fsevent)

                else:
                    log.msg("Warning: cannot watch directory for changes - feature DirWatcher unavailable")

            # assemble guest worker startup information
            #
            started_info = {
                'id': worker.id,
                'status': worker.status,
                'started': utcstr(worker.started),
                'who': worker.who
            }

            self.publish(started_topic, started_info, options=PublishOptions(exclude=[details.caller]))

            return started_info

        def on_ready_error(err):
            del self._workers[worker.id]

            emsg = 'ERROR: failed to start guest worker - {}'.format(err.value)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.cannot_start", emsg, ep.getlog())

        worker.ready.addCallbacks(on_ready_success, on_ready_error)

        def on_exit_success(res):
            log.msg("Guest excited with success")
            del self._workers[worker.id]

        def on_exit_error(err):
            log.msg("Guest excited with error", err)
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
            'id': id,
            'status': worker.status,
            'created': utcstr(worker.created),
            'who': worker.who
        }

        # the caller gets a progressive result ..
        if details.progress:
            details.progress(starting_info)

        # .. while all others get an event
        self.publish(starting_topic, starting_info, options=PublishOptions(exclude=[details.caller]))

        # now actually fork the worker ..
        #
        if self.debug:
            log.msg("Starting {} with ID '{}' using command line '{}' ..".format(worker_logname, id, ' '.join(args)))
        else:
            log.msg("Starting {} with ID '{}' ..".format(worker_logname, id))

        d = ep.connect(transport_factory)

        def on_connect_success(proto):

            # this seems to be called immediately when the child process
            # has been forked. even if it then immediately fails because
            # e.g. the executable doesn't even exist. in other words,
            # I'm not sure under what conditions the deferred will
            # errback - probably only if the forking of a new process fails
            # at OS level due to out of memory conditions or such.

            pid = proto.transport.pid
            if self.debug:
                log.msg("Guest worker process connected with PID {}".format(pid))

            worker.pid = pid

            # proto is an instance of GuestWorkerClientProtocol
            worker.proto = proto

            worker.status = 'connected'
            worker.connected = datetime.utcnow()

        def on_connect_error(err):

            # not sure when this errback is triggered at all .. see above.
            if self.debug:
                log.msg("ERROR: Connecting forked guest worker failed - {}".format(err))

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
        if self.debug:
            log.msg("NodeControllerSession.stop_guest", id, kill)

        if id not in self._workers or self._workers[id].worker_type != 'guest':
            emsg = "ERROR: no guest worker with ID '{}' currently running".format(id)
            raise ApplicationError('crossbar.error.worker_not_running', emsg)

        try:
            if kill:
                self._workers[id].proto.transport.signalProcess("KILL")
            else:
                self._workers[id].proto.transport.loseConnection()
        except Exception as e:
            emsg = "ERROR: could not stop guest worker '{}' - {}".format(id, e)
            raise ApplicationError('crossbar.error.stop_worker_failed', emsg)
        else:
            del self._workers[id]


def create_process_env(options):
    """
    Create worker process environment dictionary.
    """
    penv = {}

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

    if inherit_all:
        # must do deepcopy like this (os.environ is a "special" thing ..)
        for k, v in os.environ.items():
            penv[k] = v

    # explicit environment vars from config
    if 'env' in options and 'vars' in options['env']:
        for k, v in options['env']['vars'].items():
            penv[k] = v

    return penv
