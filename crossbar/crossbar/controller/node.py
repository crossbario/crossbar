###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

from __future__ import absolute_import

__all__ = ['Node']


from twisted.python import log
from twisted.internet import defer
from twisted.internet.defer import Deferred, DeferredList, returnValue, inlineCallbacks

from twisted.internet.error import ProcessDone, \
                                   ProcessTerminated, \
                                   ConnectionDone, \
                                   ConnectionClosed, \
                                   ConnectionLost, \
                                   ConnectionAborted


from autobahn.twisted.wamp import ApplicationSession

import os, sys
import json
import traceback

from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSessionFactory
from autobahn.twisted.websocket import WampWebSocketClientFactory, WampWebSocketClientProtocol
from twisted.internet.endpoints import ProcessEndpoint, StandardErrorBehavior

import pkg_resources
from sys import argv, executable

from autobahn.twisted.wamp import ApplicationSessionFactory
from twisted.internet.endpoints import clientFromString

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp import types

from autobahn.wamp.types import PublishOptions, \
                                RegisterOptions, \
                                CallDetails


import socket
import os

from twisted.internet.protocol import ProcessProtocol
from crossbar.twisted.process import CustomProcessEndpoint

from twisted.internet import protocol
import re, json

from crossbar import common
from crossbar.controller.types import *


from autobahn.util import utcnow, utcstr
from datetime import datetime, timedelta

from crossbar.controller.process import create_process_env
from crossbar.controller.native import create_native_worker_client_factory

from crossbar.controller.types import *



class NodeControllerSession(ApplicationSession):
   """
   Singleton node WAMP session hooked up to the node management router.

   This class exposes the node's management API.
   """

   def __init__(self, node):
      """
      :param node: The node singleton for this node controller session.
      :type node: obj
      """
      ApplicationSession.__init__(self)
      self.debug = node.debug
      self.debug_app = True

      ## associated node
      self._node = node
      self._node_id = node._node_id
      self._realm = node._realm

      self._created = utcnow()
      self._pid = os.getpid()

      ## map of worker processes: worker_id -> NativeWorkerProcess
      self._workers = {}

      exit = Deferred()


   def onConnect(self):
      ## join the node's controller realm
      self.join(self._realm)


   @inlineCallbacks
   def onJoin(self, details):

      ## When a (native) worker process has connected back to the router of
      ## the node controller, the worker will publish this event
      ## to signal it's readyness.
      ##
      def on_worker_ready(res):
         id = res['id']
         if id in self._workers:
            ready = self._workers[id].ready
            if not ready.called:
               ## fire the Deferred previously stored for
               ## signaling "worker ready"
               ready.callback(id)
            else:
               log.msg("INTERNAL ERROR: on_worker_ready() fired for process {} - ready already called".format(id))
         else:
            log.msg("INTERNAL ERROR: on_worker_ready() fired for process {} - no process with that ID".format(id))

      self.subscribe(on_worker_ready, 'crossbar.node.{}.on_worker_ready'.format(self._node_id))

      ## register node controller procedures: 'crossbar.node.<ID>.<PROCEDURE>'
      ##
      procs = [
         'get_workers',

         'start_router',
         'stop_router',

         'start_container',

         'start_guest',

         'get_info',
         'stop',
         'list_wamplets'
      ]

      dl = []

      for proc in procs:
         uri = 'crossbar.node.{}.{}'.format(self._node_id, proc)
         if True or self.debug:
            log.msg("Registering procedure '{}'".format(uri))
         dl.append(self.register(getattr(self, proc), uri, options = RegisterOptions(details_arg = 'details', discloseCaller = True)))

      yield DeferredList(dl)



   def get_info(self, details = None):
      """
      Return node information.
      """
      return {
         'created': self._created,
         'pid': self._pid,
         'workers': len(self._workers),
         'guests': len(self._guests),
         'directory': self._node._cbdir
      }



   def stop(self, restart = False, details = None):
      """
      Stop this node.
      """
      log.msg("Stopping node (restart = {}) ..".format(restart))
      self._node._reactor.stop()



   def get_workers(self, details = None):
      """
      Returns the list of processes currently running on this node.

      :returns: list -- List of worker processes.
      """
      now = datetime.utcnow()
      res = []
      for k in sorted(self._workers.keys()):
         p = self._workers[k]
         res.append({
            'id': p.id,
            'pid': p.pid,
            'type': p.TYPE,
            'status': p.status,
            'created': utcstr(p.created),
            'started': utcstr(p.started),
            'startup_time': (p.started - p.created).total_seconds() if p.started else None,
            'uptime': (now - p.started).total_seconds() if p.started else None,
         })
      return res


   def start_router(self, id, options = {}, details = None):
      """
      Start a new router worker: a Crossbar.io native worker process
      that runs a WAMP router.

      crossbar.node.<node_id>.on_router_starting
      crossbar.node.<node_id>.on_router_started

      crossbar.node.<node_id>.on_router_stopping
      crossbar.node.<node_id>.on_router_stopped

      :param id: The worker ID to start this router with.
      :type id: str
      :param options: The router worker options.
      :type options: dict
      """
      if self.debug:
         log.msg("NodeControllerSession.start_router", id, options)

      return self._start_native_worker('router', id, options, details = details)



   @inlineCallbacks
   def start_container(self, id, options = {}, details = None):
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

      return self._start_native_worker('router', id, options, details = details)



   def _start_native_worker(self, wtype, id, options, details = None):

      assert(wtype in ['router', 'container'])

      ## prohibit starting a worker twice
      ##
      if id in self._workers:
         emsg = "ERROR: could not start worker - a worker with ID {} is already running (or starting)".format(id)
         log.msg(emsg)
         raise ApplicationError('crossbar.error.worker_already_running', emsg)

      ## check worker options
      ##
      try:
         if wtype == 'router':
            common.config.check_router_options(options)
         elif wtype == 'container':
            common.config.check_container_options(options)
         else:
            raise Exception("logic error")
      except Exception as e:
         emsg = "ERROR: could not start router - invalid configuration ({})".format(e)
         log.msg(emsg)
         raise ApplicationError('crossbar.error.invalid_configuration', emsg)

      ## allow override Python executable from options
      ##
      if 'python' in options:
         exe = options['python']

         ## the executable must be an absolute path, e.g. /home/oberstet/pypy-2.2.1-linux64/bin/pypy
         ##
         if not os.path.isabs(exe):
            emsg = "ERROR: python '{}' from worker options must be an absolute path".format(exe)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.invalid_configuration', emsg)

         ## of course the path must exist and actually be executable
         ##
         if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
            emsg = "ERROR: python '{}' from worker options does not exist or isn't an executable".format(exe)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.invalid_configuration', emsg)
      else:
         exe = sys.executable

      ## all native workers (routers and containers for now) start from the same script
      ##
      filename = pkg_resources.resource_filename('crossbar', 'worker/process.py')

      ## assemble command line for forking the worker
      ##
      args = [exe, "-u", filename]
      args.extend(["--cbdir", self._node._cbdir])
      args.extend(["--node", str(self._node_id)])
      args.extend(["--worker", str(id)])
      args.extend(["--realm", self._realm])
      args.extend(["--type", wtype])

      ## allow override worker process title from options
      ##
      if options.get('title', None):
         args.extend(['--title', options['title']])

      ## allow overriding debug flag from options
      ##
      if options.get('debug', self.debug):
         args.append('--debug')

      ## forward explicit reactor selection
      ##
      if self._node._reactor_shortname:
         args.extend(['--reactor', self._node._reactor_shortname])

      ## create worker process environment
      ##
      penv = create_process_env(options)

      ## log name of worker
      ##
      worker_logname = {'router': 'Router', 'container': 'Container'}.get(wtype, 'Worker')

      ## create a (custom) process endpoint
      ##
      ep = CustomProcessEndpoint(self._node._reactor, exe, args, env = penv,
         name = worker_logname, keeplog = options.get('traceback', None))

      ## add worker tracking instance to the worker map ..
      ##
      worker = RouterWorkerProcess(id, details.authid)
      self._workers[id] = worker

      ## ready handling
      ##
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

         self.publish(started_topic, started_info, options = PublishOptions(exclude = [details.caller]))

         return started_info

      def on_ready_error(err):
         del self._workers[worker.id]

         emsg = 'ERROR: failed to start native worker - {}'.format(err.value)
         log.msg(emsg)
         raise ApplicationError("crossbar.error.cannot_start", emsg, ep.getlog())

      worker.ready.addCallbacks(on_ready_success, on_ready_error)


      def on_exit_success(res):
         del self._workers[worker.id]

      def on_exit_error(err):
         del self._workers[worker.id]

      worker.exit.addCallbacks(on_exit_success, on_exit_error)


      ## create a transport factory for talking WAMP to the native worker
      ##
      transport_factory = create_native_worker_client_factory(self._node._router_session_factory, worker.ready, worker.exit)
      transport_factory.noisy = False
      self._workers[id].factory = transport_factory

      ## now (immediately before actually forking) signal the starting of the worker
      ##
      if wtype == 'router':
         starting_topic = 'crossbar.node.{}.on_router_starting'.format(self._node_id)
         started_topic = 'crossbar.node.{}.on_router_started'.format(self._node_id)
      elif wtype == 'container':
         starting_topic = 'crossbar.node.{}.on_container_starting'.format(self._node_id)
         started_topic = 'crossbar.node.{}.on_container_started'.format(self._node_id)
      else:
         raise Exception("logic error")

      starting_info = {
         'id': id,
         'status': worker.status,
         'created': utcstr(worker.created),
         'who': worker.who
      }

      ## the caller gets a progressive result ..
      if details.progress:
         details.progress(starting_info)

      ## .. while all others get an event
      self.publish(starting_topic, starting_info, options = PublishOptions(exclude = [details.caller]))

      ## now actually fork the worker ..
      ##
      if self.debug:
         log.msg("Starting {} with ID '{}' using command line '{}' ..".format(worker_logname, id, ' '.join(args)))
      else:
         log.msg("Starting {} with ID '{}' ..".format(worker_logname, id))

      d = ep.connect(transport_factory)


      def on_connect_success(proto):

         ## this seems to be called immediately when the child process
         ## has been forked. even if it then immediately fails because
         ## e.g. the executable doesn't even exist. in other words,
         ## I'm not sure under what conditions the deferred will errback ..

         pid = proto.transport.pid
         if self.debug:
            log.msg("Native worker process connected with PID {}".format(pid))

         worker.pid = pid

         ## proto is an instance of NativeWorkerClientProtocol
         worker.proto = proto

         worker.status = 'connected'
         worker.connected = datetime.utcnow()


      def on_connect_error(err):

         ## not sure when this errback is triggered at all ..
         if self.debug:
            log.msg("ERROR: Connecting forked native worker failed - {}".format(err))

         ## in any case, forward the error ..
         worker.ready.errback(err)

      d.addCallbacks(on_connect_success, on_connect_error)

      return worker.ready



   def stop_router(self, id, details = None):
      """
      Stops a currently running router worker.

      :param id: The ID of the router worker to stop.
      :type id: str
      """
      if self.debug:
         log.msg("NodeControllerSession.stop_router", id)

      if id not in self._workers or self._workers[id].worker_type != 'router':
         emsg = "ERROR: no router worker with ID '{}' currently running".format(id)
         raise ApplicationError('crossbar.error.worker_not_running', emsg)

      self._workers[id].factory.stopFactory()
      #self._workers[id].proto._session.leave()
      #self._workers[id].proto.transport.signalProcess("KILL")




   def start_guest(self, id, config, details = None):
      """
      Start a new guest process on this node.

      :param config: The guest process configuration.
      :type config: obj

      :returns: int -- The PID of the new process.
      """
      try:
         common.config.check_guest(config)
      except Exception as e:
         raise ApplicationError('crossbar.error.invalid_configuration', 'invalid guest worker configuration: {}'.format(e))

      ## the following will be used to signal guest readiness
      ## and exit ..
      ##
      ready = Deferred()
      exit = Deferred()



      ## the guest process configured executable and
      ## command line arguments
      ##
      exe = config['executable']
      args = [exe]
      args.extend(config.get('arguments', []))

      ## guest process working directory
      ##
      workdir = self._node._cbdir
      if 'workdir' in config:
         workdir = os.path.join(workdir, config['workdir'])
      workdir = os.path.abspath(workdir)

      ## guest process environment
      ##
      penv = create_process_env(config.get('options', {}))


      if False:

         #factory = GuestClientFactory()
         from crossbar.controller.guest import create_guest_worker_client_factory

         factory = create_guest_worker_client_factory(config, ready, exit)

         #ep = CustomProcessEndpoint(self._node._reactor,
         #         exe,
         #         args,
         #         name = "Worker {}".format(id),
         #         env = penv)

         from twisted.internet.endpoints import ProcessEndpoint

         ep = ProcessEndpoint()

         ## now actually spawn the worker ..
         ##
         d = ep.connect(factory)

         def onconnect(proto):
            pid = proto.transport.pid
            proto._pid = pid
            self._workers[id] = NodeGuestWorkerProcess(pid, ready, exit, proto = proto)
            log.msg("Guest {}: Program started.".format(pid))
            ready.callback(None)

         def onerror(err):
            log.msg("Guest: Program could not be started - {}".format(err.value))
            ready.errback(err)

         d.addCallbacks(onconnect, onerror)

      else:

         #proto = GuestClientProtocol()

         from crossbar.controller.guest import create_guest_worker_client_factory

         factory = create_guest_worker_client_factory(config, ready, exit)
         proto = factory.buildProtocol(None)

         proto._name = "Worker {}".format(id)

         try:
            ## An object which provides IProcessTransport:
            ## https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IProcessTransport.html
            trnsp = self._node._reactor.spawnProcess(proto, exe, args, path = workdir, env = penv)
         except Exception as e:
            log.msg("Guest: Program could not be started - {}".format(e))
            ready.errback(e)
         else:
            pid = trnsp.pid
            proto._pid = pid

            self._workers[id] = NodeGuestWorkerProcess(id, pid, ready, exit, proto = proto)
            log.msg("Guest {}: Program started.".format(id))

            ready.callback(None)

            topic = 'crossbar.node.{}.on_process_start'.format(self._node._name)
            self.publish(topic, {'id': id, 'pid': pid})


            def on_guest_exit_success(_):
               print "on_guest_exit_success"
               p = self._workers[id]
               now = datetime.utcnow()
               topic = 'crossbar.node.{}.on_process_exit'.format(self._node._name)
               self.publish(topic, {
                  'id': id,
                  'pid': pid,
                  'exit_code': 0,
                  'uptime': (now - p.started).total_seconds()
               })
               del self._workers[id]

            def on_guest_exit_failed(reason):
               ## https://twistedmatrix.com/documents/current/api/twisted.internet.error.ProcessTerminated.html
               exit_code = reason.value.exitCode
               signal = reason.value.signal
               print "on_guest_exit_failed", id, pid, exit_code, type(exit_code)
               try:
                  p = self._workers[id]
                  now = datetime.utcnow()
                  topic = 'crossbar.node.{}.on_process_exit'.format(self._node._name)
                  self.publish(topic, {
                     'id': id,
                     'pid': pid,
                     'exit_code': exit_code,
                     'signal': signal,
                     'uptime': (now - p.started).total_seconds()
                  })
                  del self._workers[id]
               except Exception as e:
                  print "(8888", e

            exit.addCallbacks(on_guest_exit_success, on_guest_exit_failed)

      return ready




   def stop_guest(self, id, kill = False, details = None):
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



   def list_wamplets(self, details = None):
      """
      List installed WAMPlets.
      """
      res = []

      # pkg_resources.load_entry_point('wamplet1', 'autobahn.twisted.wamplet', 'component1')

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

      return res


   @inlineCallbacks
   def run_node_config(self, config):
      """
      Setup node according to config provided.
      """

      ## fake call details information when calling into
      ## remoted procedure locally
      ##
      call_details = CallDetails(caller = 0, authid = 'node')

      for worker in config.get('workers', []):

         id = worker['id']
         options = worker.get('options', {})

         ## router/container
         ##
         if worker['type'] in ['router', 'container']:

            ## start a new worker process ..
            ##
            try:
               if worker['type'] == 'router':
                  yield self.start_router(id, options, details = call_details)
               elif worker['type'] == 'container':
                  yield self.start_container(id, options, details = call_details)
               else:
                  raise Exception("logic error")
            except Exception as e:
               log.msg("Failed to start worker process: {}".format(e))
               raise e
            else:
               log.msg("Worker {}: Started {}.".format(id, worker['type']))

            ## setup worker generic stuff
            ##
            if 'pythonpath' in options:
               try:
                  added_paths = yield self.call('crossbar.node.{}.worker.{}.add_pythonpath'.format(self._node_id, id),
                     options['pythonpath'])

               except Exception as e:
                  log.msg("Worker {}: Failed to set PYTHONPATH - {}".format(id, e))
               else:
                  log.msg("Worker {}: PYTHONPATH extended for {}".format(id, added_paths))

            if 'cpu_affinity' in options:
               try:
                  yield self.call('crossbar.node.{}.worker.{}.set_cpu_affinity'.format(self._node_id, id),
                     options['cpu_affinity'])

               except Exception as e:
                  log.msg("Worker {}: Failed to set CPU affinity - {}".format(id, e))
               else:
                  log.msg("Worker {}: CPU affinity set.".format(id))

            try:
               cpu_affinity = yield self.call('crossbar.node.{}.worker.{}.get_cpu_affinity'.format(self._node_id, id))
            except Exception as e:
               log.msg("Worker {}: Failed to get CPU affinity - {}".format(id, e))
            else:
               log.msg("Worker {}: CPU affinity is {}".format(id, cpu_affinity))


            ## manhole within worker
            ##
            if 'manhole' in worker:
               yield self.call('crossbar.node.{}.worker.{}.start_manhole'.format(self._node_id, id), worker['manhole'])


            ## WAMP router process
            ##
            if worker['type'] == 'router':

               ## start realms
               ##
               for realm_name, realm_config in worker['realms'].items():

                  realm_index = yield self.call('crossbar.node.{}.worker.{}.router.start_realm'.format(self._node_id, id), realm_name, realm_config)

                  log.msg("Worker {}: Realm {} ({}) started on router".format(id, realm_name, realm_index))

                  ## start any application components to run embedded in the realm
                  ##
                  for component_config in realm_config.get('components', []):

                     component_index = yield self.call('crossbar.node.{}.worker.{}.router.start_component'.format(self._node_id, id), realm_name, component_config)

               ## start transports on router
               ##
               for transport in worker['transports']:
                  transport_index = yield self.call('crossbar.node.{}.worker.{}.router.start_transport'.format(self._node_id, id), transport)

                  log.msg("Worker {}: Transport {}/{} ({}) started on router".format(id, transport['type'], transport['endpoint']['type'], transport_index))

            ## Setup: Python component host process
            ##
            elif worker['type'] == 'container':

               for component_config in worker.get('components', []):

                  component_id = yield self.call('crossbar.node.{}.worker.{}.container.start_component'.format(self._node_id, id), component_config)

               #yield self.call('crossbar.node.{}.worker.{}.container.start_component'.format(self._node_id, pid), worker['component'], worker['router'])

            else:
               raise Exception("logic error")


         elif worker['type'] == 'guest':

            ## start a new worker process ..
            ##
            try:
               pid = yield self.start_guest(worker, details = call_details)
            except Exception as e:
               log.msg("Failed to start guest process: {}".format(e))
            else:
               log.msg("Guest {}: Started.".format(pid))

         else:
            raise Exception("unknown worker type '{}'".format(worker['type']))



class Node:
   """
   A Crossbar.io node is the running a controller process
   and one or multiple worker processes.

   A single Crossbar.io node runs exactly one instance of
   this class, hence this class can be considered a system
   singleton.
   """

   def __init__(self, reactor, options):
      """
      Ctor.

      :param reactor: Reactor to run on.
      :type reactor: obj
      :param options: Options from command line.
      :type options: obj
      """
      self._reactor = reactor

      self._cbdir = options.cbdir
      self._config = json.loads(open(options.config, 'rb').read())
      self._reactor_shortname = options.reactor

      self.debug = False

      self._worker_workers = {}

      ## the node's name (must be unique within the management realm)
      self._node_id = self._config['controller']['id']

      ## the node's management realm
      self._realm = self._config['controller']['realm']

      ## node controller session (a singleton ApplicationSession embedded
      ## in the node's management router)
      self._node_controller_session = None




   #@inlineCallbacks
   def start(self):
      """
      Starts this node. This will start a node controller
      and then spawn new worker processes as needed.

      The node controller will watch spawned processes,
      communicate via stdio with the worker, and start
      and restart the worker processes as needed.
      """
      try:
         import setproctitle
      except ImportError:
         log.msg("Warning, could not set process title (setproctitle not installed)")
      else:
         setproctitle.setproctitle("crossbar-controller")

      ## the node controller singleton WAMP application session
      ##
      self._node_controller_session = NodeControllerSession(self)

      ## router and factory that creates router sessions
      ##
      self._router_factory = RouterFactory(
         options = types.RouterOptions(uri_check = types.RouterOptions.URI_CHECK_LOOSE),
         debug = False)
      self._router_session_factory = RouterSessionFactory(self._router_factory)

      ## add the node controller singleton session to the router
      ##
      self._router_session_factory.add(self._node_controller_session)

      ## Detect WAMPlets
      ##
      wamplets = sorted(self._node_controller_session.list_wamplets())
      if len(wamplets) > 0:
         log.msg("Detected {} WAMPlets in environment:".format(len(wamplets)))
         for wpl in wamplets:
            log.msg("WAMPlet {}.{}".format(wpl['dist'], wpl['name']))
      else:
         log.msg("No WAMPlets detected in enviroment.")


#      self._start_from_local_config(configfile = os.path.join(self._cbdir, self._options.config))
      self._node_controller_session.run_node_config(self._config)

      self.start_local_management_transport(endpoint_descriptor = "tcp:9000")



   def start_remote_management_client(self):
      from crossbar.management import NodeManagementSession

      management_session_factory = ApplicationSessionFactory()
      management_session_factory.session = NodeManagementSession
      management_session_factory.node_controller_session = node_controller_session
      management_transport_factory = WampWebSocketClientFactory(management_session_factory, "ws://127.0.0.1:7000")
      management_transport_factory.setProtocolOptions(failByDrop = False)
      management_client = clientFromString(self._reactor, "tcp:127.0.0.1:7000")
      management_client.connect(management_transport_factory)



   def start_local_management_transport(self, endpoint_descriptor):
      ## create a WAMP-over-WebSocket transport server factory
      ##
      from autobahn.twisted.websocket import WampWebSocketServerFactory
      from twisted.internet.endpoints import serverFromString

      self._router_server_transport_factory = WampWebSocketServerFactory(self._router_session_factory, debug = self.debug)
      self._router_server_transport_factory.setProtocolOptions(failByDrop = False)
      self._router_server_transport_factory.noisy = False


      ## start the WebSocket server from an endpoint
      ##
      self._router_server = serverFromString(self._reactor, endpoint_descriptor)
      ## FIXME: the following spills out log noise: "WampWebSocketServerFactory starting on 9000"
      self._router_server.listen(self._router_server_transport_factory)



   def _start_from_local_config(self, configfile):
      """
      Start Crossbar.io node from local configuration file.
      """
      configfile = os.path.abspath(configfile)
      log.msg("Starting from local config file '{}'".format(configfile))

      try:
         #config = controller.config.check_config_file(configfile, silence = True)
         config = json.loads(open(configfile, 'rb').read())
      except Exception as e:
         log.msg("Fatal: {}".format(e))
         sys.exit(1)
      else:
         self._node_controller_session.run_node_config(config)
