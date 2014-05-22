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


import socket
import os

from twisted.internet.protocol import ProcessProtocol
from crossbar.twisted.process import CustomProcessEndpoint

from twisted.internet import protocol
import re, json

from crossbar import controller
from crossbar.controller.types import *


from autobahn.util import utcnow, utcstr
from datetime import datetime, timedelta



def _create_process_env(options):
   """
   Create worker/guest process environment dictionary.
   """
   penv = {}

   ## by default, a worker/guest process inherits
   ## complete environment
   inherit_all = True

   ## check/inherit parent process environment
   if 'env' in options and 'inherit' in options['env']:
      inherit = options['env']['inherit']
      if type(inherit) == bool:
         inherit_all = inherit
      elif type(inherit) == list:
         inherit_all = False
         for v in inherit:
            if v in os.environ:
               penv[v] = os.environ[v]

   if inherit_all:
      ## must do deepcopy like this (os.environ is a "special" thing ..)
      for k, v in os.environ.items():
         penv[k] = v

   ## explicit environment vars from config
   if 'env' in options and 'vars' in options['env']:
      for k, v in options['env']['vars'].items():
         penv[k] = v

   return penv



class NodeControllerSession(ApplicationSession):
   """
   Singleton node WAMP session hooked up to the node router.

   This class exposes the node's management API.
   """

   def __init__(self, node):
      """
      :param node: The node singleton for this node controller session.
      :type node: obj
      """
      ApplicationSession.__init__(self)
      self.debug = node.debug

      ## associated node
      self._node = node
      self._name = node._name
      self._realm = node._realm

      self._created = utcnow()
      self._pid = os.getpid()

      ## map of worker processes: PID -> NativeWorkerProcess
      self._processes = {}
      self._process_id = 0

      exit = Deferred()

      self._processes[0] = NodeControllerProcess(0, self._pid, defer.succeed(self._pid), exit)

      ## map of guest processes: PID -> GuestWorkerProcess
      #self._guests = {}
      #self._guest_no = 0


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
         if id in self._processes:
            ready = self._processes[id].ready
            if not ready.called:
               ## fire the Deferred previously stored for
               ## signaling "worker ready"
               ready.callback(id)
            else:
               log.msg("INTERNAL ERROR: on_worker_ready() fired for process {} - ready already called".format(id))
         else:
            log.msg("INTERNAL ERROR: on_worker_ready() fired for process {} - no process with that ID".format(id))

      self.subscribe(on_worker_ready, 'crossbar.node.{}.on_worker_ready'.format(self._node._name))

      ## register node controller procedures: 'crossbar.node.<ID>.<PROCEDURE>'
      ##
      procs = [
         'start_router',
         'start_container',
         'start_guest',
         'list_processes',
         'stop_process',
         'get_info',
         'stop',
         'list_wamplets'
      ]

      dl = []

      for proc in procs:
         uri = 'crossbar.node.{}.{}'.format(self._node._name, proc)
         dl.append(self.register(getattr(self, proc), uri))

      yield DeferredList(dl)



   def get_info(self):
      """
      Return node information.
      """
      return {
         'created': self._created,
         'pid': self._pid,
         'workers': len(self._processes),
         'guests': len(self._guests),
         'directory': self._node._cbdir
      }



   def stop(self, restart = False):
      """
      Stop this node.
      """
      log.msg("Stopping node (restart = {}) ..".format(restart))
      self._node._reactor.stop()



   def list_processes(self):
      """
      Returns the list of processes currently running on this node.
      """
      now = datetime.utcnow()
      res = []
      for k in sorted(self._processes.keys()):
         p = self._processes[k]
         #print p.process_type, p.pid, p.ready, p.exit, p.ready.called, p.exit.called
         res.append({
            'id': p.id,
            'pid': p.pid,
            'type': p.process_type,
            'started': utcstr(p.started),
            'uptime': (now - p.started).total_seconds(),
            #'ready': p.ready.called,
            #'exit': p.exit.called,
         })
      return res



   def start_router(self, options):
      return self.start_native_worker('router', options)



   def start_container(self, options):
      return self.start_native_worker('container', options)



   def start_native_worker(self, worker_type, options = {}):
      """
      Start a new Crossbar.io worker process.

      :param options: Worker options.
      :type options: dict

      :returns: int -- The PID of the new worker process.
      """
      self._process_id += 1
      process_id = self._process_id

      ## allow override Python executable from config
      exe = options.get('python', executable)


      ## all worker processes start "generic" (like stem cells) and
      ## are later configured via WAMP from the node controller session
      ##
      filename = pkg_resources.resource_filename('crossbar', 'worker/process.py')

      args = [exe, "-u", filename]
      args.extend(["--cbdir", self._node._cbdir])
      args.extend(["--node", self._node._name])
      args.extend(["--id", str(process_id)])
      args.extend(["--realm", self._node._realm])
      args.extend(["--type", worker_type])

      ## override worker process title from config
      ##
      if options.get('title', None):
         args.extend(['--title', options['title']])

      ## turn on debugging on worker process
      ##
      if options.get('debug', False):
         args.append('--debug')

      ## forward explicit reactor selection
      ##
      if self._node._reactor_shortname:
         args.extend(['--reactor', self._node._reactor_shortname])

      log.msg("Starting native worker: {}".format(' '.join(args)))

      ## worker process environment
      ##
      penv = _create_process_env(options)

      ep = CustomProcessEndpoint(self._node._reactor,
               executable,
               args,
               name = "Worker {}".format(process_id),
               env = penv)

      ## this will be resolved/rejected when the worker is actually
      ## ready to receive commands
      ready = Deferred()

      ## this will be resolved when the worker exits (after previously connected)
      exit = Deferred()



      from crossbar.controller.native import create_native_worker_client_factory
      transport_factory = create_native_worker_client_factory(self._node._router_session_factory, ready, exit)

      ## now actually spawn the worker ..
      ##
      d = ep.connect(transport_factory)

      def onconnect(proto):
         print "XXXXXXXXXXXx", proto
         pid = proto.transport.pid
         log.msg("Worker PID {} process connected".format(pid))

         ## remember the worker process, including "ready" deferred. this will later
         ## be fired upon the worker publishing to 'crossbar.node.{}.on_worker_ready'
         self._processes[process_id] = NodeNativeWorkerProcess(process_id, pid, ready, exit, worker_type, factory = transport_factory, proto = proto)

         topic = 'crossbar.node.{}.on_process_start'.format(self._node._name)
         self.publish(topic, {'id': process_id, 'pid': pid})


         def on_exit_success(_):
            del self._processes[process_id]

         def on_exit_failed(exit_code):
            del self._processes[process_id]

         exit.addCallbacks(on_exit_success, on_exit_failed)

      def onerror(err):
         log.msg("Could not start worker process with args '{}': {}".format(args, err.value))
         ready.errback(err)

      d.addCallbacks(onconnect, onerror)

      return ready



   def stop_process(self, id):
      """
      Stops a worker process.
      """
      print "stop_process", id
      if id in self._processes:
         process = self._processes[id]

         if process.process_type in ['router', 'container']:
            #self._processes[pid].factory.stopFactory()
            #self._processes[pid].proto.leave()
            self._processes[id].proto.transport.signalProcess("KILL")
         elif process.process_type == 'guest':
            pass
         else:
            pass

         # try:
         #    self._processes[pid].factory.stopFactory()
         # except Exception as e:
         #    log.msg("Could not stop worker {}: {}".format(pid, e))
         #    raise e
         # else:
         #    del self._processes[pid]
      else:
         raise ApplicationError("wamp.error.invalid_argument", "No worker with ID '{}'".format(id))



   def start_guest(self, config):
      """
      Start a new guest process on this node.

      :param config: The guest process configuration.
      :type config: obj

      :returns: int -- The PID of the new process.
      """
      try:
         controller.config.check_guest(config)
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
      penv = _create_process_env(config.get('options', {}))


      self._process_id += 1
      process_id = self._process_id

      if False:

         #factory = GuestClientFactory()
         from crossbar.controller.guest import create_guest_worker_client_factory

         factory = create_guest_worker_client_factory(config, ready, exit)

         #ep = CustomProcessEndpoint(self._node._reactor,
         #         exe,
         #         args,
         #         name = "Worker {}".format(process_id),
         #         env = penv)

         from twisted.internet.endpoints import ProcessEndpoint

         ep = ProcessEndpoint()

         ## now actually spawn the worker ..
         ##
         d = ep.connect(factory)

         def onconnect(proto):
            pid = proto.transport.pid
            proto._pid = pid
            self._processes[process_id] = NodeGuestWorkerProcess(pid, ready, exit, proto = proto)
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

         proto._name = "Worker {}".format(process_id)

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

            self._processes[process_id] = NodeGuestWorkerProcess(process_id, pid, ready, exit, proto = proto)
            log.msg("Guest {}: Program started.".format(process_id))

            ready.callback(None)

            topic = 'crossbar.node.{}.on_process_start'.format(self._node._name)
            self.publish(topic, {'id': process_id, 'pid': pid})


            def on_guest_exit_success(_):
               print "on_guest_exit_success"
               p = self._processes[process_id]
               now = datetime.utcnow()
               topic = 'crossbar.node.{}.on_process_exit'.format(self._node._name)
               self.publish(topic, {
                  'id': process_id,
                  'pid': pid,
                  'exit_code': 0,
                  'uptime': (now - p.started).total_seconds()
               })
               del self._processes[process_id]

            def on_guest_exit_failed(reason):
               ## https://twistedmatrix.com/documents/current/api/twisted.internet.error.ProcessTerminated.html
               exit_code = reason.value.exitCode
               signal = reason.value.signal
               print "on_guest_exit_failed", process_id, pid, exit_code, type(exit_code)
               try:
                  p = self._processes[process_id]
                  now = datetime.utcnow()
                  topic = 'crossbar.node.{}.on_process_exit'.format(self._node._name)
                  self.publish(topic, {
                     'id': process_id,
                     'pid': pid,
                     'exit_code': exit_code,
                     'signal': signal,
                     'uptime': (now - p.started).total_seconds()
                  })
                  del self._processes[process_id]
               except Exception as e:
                  print "(8888", e

            exit.addCallbacks(on_guest_exit_success, on_guest_exit_failed)

      return ready



   def stop_guest(self, id):
      """
      Stops a guest process.
      """
      if id in self._processes:
         try:
            self._processes[id].proto.transport.loseConnection()
         except Exception as e:
            log.msg("Could not stop guest {}: {}".format(id, e))
            raise e
         else:
            del self._processes[id]
      else:
         raise ApplicationError("wamp.error.invalid_argument", "No guest with ID '{}'".format(id))



   def list_wamplets(self):
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
      for worker in config.get('workers', []):

         worker_options = worker.get('options', {})

         ## router/container
         ##
         if worker['type'] in ['router', 'container']:

            ## start a new worker process ..
            ##
            try:
               if worker['type'] == 'router':
                  id = yield self.start_router(worker_options)
               elif worker['type'] == 'container':
                  id = yield self.start_container(worker_options)
               else:
                  raise Exception("logic error")
            except Exception as e:
               log.msg("Failed to start worker process: {}".format(e))
               raise e
            else:
               log.msg("Worker {}: Started {}.".format(id, worker['type']))

            ## setup worker generic stuff
            ##
            if 'pythonpath' in worker_options:
               try:
                  added_paths = yield self.call('crossbar.node.{}.process.{}.add_pythonpath'.format(self._name, id),
                     worker_options['pythonpath'])

               except Exception as e:
                  log.msg("Worker {}: Failed to set PYTHONPATH - {}".format(id, e))
               else:
                  log.msg("Worker {}: PYTHONPATH extended for {}".format(id, added_paths))

            if 'cpu_affinity' in worker_options:
               try:
                  yield self.call('crossbar.node.{}.process.{}.set_cpu_affinity'.format(self._name, id),
                     worker_options['cpu_affinity'])

               except Exception as e:
                  log.msg("Worker {}: Failed to set CPU affinity - {}".format(id, e))
               else:
                  log.msg("Worker {}: CPU affinity set.".format(id))

            try:
               cpu_affinity = yield self.call('crossbar.node.{}.process.{}.get_cpu_affinity'.format(self._name, id))
            except Exception as e:
               log.msg("Worker {}: Failed to get CPU affinity - {}".format(id, e))
            else:
               log.msg("Worker {}: CPU affinity is {}".format(id, cpu_affinity))


            ## manhole within worker
            ##
            if 'manhole' in worker:
               yield self.call('crossbar.node.{}.process.{}.start_manhole'.format(self._name, id), worker['manhole'])


            ## WAMP router process
            ##
            if worker['type'] == 'router':

               ## start realms
               ##
               for realm_name, realm_config in worker['realms'].items():

                  print "###", realm_name, realm_config

                  realm_index = yield self.call('crossbar.node.{}.process.{}.router.start_realm'.format(self._name, id), realm_name, realm_config)

                  log.msg("Worker {}: Realm {} ({}) started on router".format(id, realm_name, realm_index))

                  ## start any application components to run embedded in the realm
                  ##
                  for component_config in realm_config.get('components', []):

                     component_index = yield self.call('crossbar.node.{}.process.{}.router.start_component'.format(self._name, id), realm_name, component_config)

               ## start transports on router
               ##
               for transport in worker['transports']:
                  transport_index = yield self.call('crossbar.node.{}.process.{}.router.start_transport'.format(self._name, id), transport)

                  log.msg("Worker {}: Transport {}/{} ({}) started on router".format(id, transport['type'], transport['endpoint']['type'], transport_index))

            ## Setup: Python component host process
            ##
            elif worker['type'] == 'container':

               for component_config in worker.get('components', []):

                  component_id = yield self.call('crossbar.node.{}.process.{}.container.start_component'.format(self._name, id), component_config)

               #yield self.call('crossbar.node.{}.process.{}.container.start_component'.format(self._name, pid), worker['component'], worker['router'])

            else:
               raise Exception("logic error")


         elif worker['type'] == 'guest':

            ## start a new worker process ..
            ##
            try:
               pid = yield self.start_guest(worker)
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

      self._worker_processes = {}

      ## the node's name (must be unique within the management realm)
      self._name = self._config['controller']['node']

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


      ## start the WebSocket server from an endpoint
      ##
      self._router_server = serverFromString(self._reactor, endpoint_descriptor)
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
