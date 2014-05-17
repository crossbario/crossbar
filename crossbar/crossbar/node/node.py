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

from autobahn.util import utcnow

import socket
import os

from twisted.internet.protocol import ProcessProtocol
from crossbar.twisted.process import CustomProcessEndpoint

from twisted.internet import protocol
import re, json

from crossbar.node.config import check_config_file




class WorkerProcess:
   """
   Internal run-time representation of a running node worker process.
   """
   def __init__(self, pid, ready = None, exit = None, factory = None):
      """
      Ctor.

      :param pid: The worker process PID.
      :type pid: int
      :param ready: A deferred that resolves when the worker is ready.
      :type ready: instance of Deferred
      :param exit: A deferred that resolves when the worker has exited.
      :type exit: instance of Deferred
      :param factory: The WAMP client factory that connects to the worker.
      :type factory: instance of WorkerClientFactory
      """
      self.pid = pid
      self.ready = ready
      self.exit = exit
      self.factory = factory
      self.created = utcnow()



class GuestProcess:
   """
   Internal run-time representation of a running node guest process.
   """

   def __init__(self, pid, ready = None, exit = None, proto = None):
      """
      Ctor.

      :param pid: The worker process PID.
      :type pid: int
      :param ready: A deferred that resolves when the worker is ready.
      :type ready: instance of Deferred
      :param exit: A deferred that resolves when the worker has exited.
      :type exit: instance of Deferred
      :param proto: The WAMP client protocol that connects to the worker.
      :type proto: instance of GuestClientProtocol
      """
      self.pid = pid
      self.ready = ready
      self.exit = exit
      self.proto = proto
      self.created = utcnow()



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
      self._node_name = node._node_name
      self._node_realm = node._node_realm

      self._created = utcnow()
      self._pid = os.getpid()

      ## map of worker processes: PID -> WorkerProcess
      self._workers = {}
      self._worker_no = 0

      ## map of guest processes: PID -> GuestProcess
      self._guests = {}
      self._guest_no = 0


   def onConnect(self):
      ## join the node's controller realm
      self.join(self._node_realm)


   @inlineCallbacks
   def onJoin(self, details):

      dl = []

      ## when a worker process has connected back to the router of
      ## the node controller, the worker will publish this event
      ## to signal it's readyness ..
      ##
      def on_worker_ready(res):
         ## fire the Deferred previously stored for signaling "worker ready"
         pid = res['pid']
         r = self._workers.get(pid, None)
         if r and r.ready:
            r.ready.callback(pid)
            r.ready = None

      dl.append(self.subscribe(on_worker_ready, 'crossbar.node.{}.on_worker_ready'.format(self._node._node_name)))

      ## node global procedures: 'crossbar.node.<PID>.<PROCEDURE>'
      ##
      procs = [
         'get_info',
         'stop',
         'list_workers',
         'start_worker',
         'start_guest',
         'list_wamplets'
      ]
      for proc in procs:
         uri = 'crossbar.node.{}.{}'.format(self._node._node_name, proc)
         dl.append(self.register(getattr(self, proc), uri))

      yield DeferredList(dl)



   def get_info(self):
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



   def stop(self, restart = False):
      """
      Stop this node.
      """
      log.msg("Stopping node (restart = {}) ..".format(restart))
      self._node._reactor.stop()



   def list_workers(self):
      """
      Returns a list of worker processes currently running on this node.
      """
      res = []
      for k in sorted(self._workers.keys()):
         p = self._workers[k]
         res.append({'pid': p.pid, 'created': p.created, 'is_ready': p.ready is None})
      return res



   def start_worker(self, options = {}):
      """
      Start a new Crossbar.io worker process.

      :param options: Worker options.
      :type options: dict

      :returns: int -- The PID of the new worker process.
      """
      ## allow override Python executable from config
      exe = options.get('python', executable)


      ## all worker processes start "generic" (like stem cells) and
      ## are later configured via WAMP from the node controller session
      ##
      filename = pkg_resources.resource_filename('crossbar', 'worker/process.py')

      args = [exe, "-u", filename]
      args.extend(["--cbdir", self._node._cbdir])

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
      if self._node._options.reactor:
         args.extend(['--reactor', self._node._options.reactor])

      ## worker process environment
      ##
      penv = {}
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


      self._worker_no += 1

      ep = CustomProcessEndpoint(self._node._reactor,
               executable,
               args,
               name = "Worker {}".format(self._worker_no),
               env = penv)

      ## this will be resolved/rejected when the worker is actually
      ## ready to receive commands
      ready = Deferred()

      ## this will be resolved when the worker exits (after previously connected)
      exit = Deferred()


      class WorkerClientProtocol(WampWebSocketClientProtocol):

         def connectionMade(self):
            WampWebSocketClientProtocol.connectionMade(self)
            self._pid = self.transport.pid
            self.factory.proto = self


         def connectionLost(self, reason):
            WampWebSocketClientProtocol.connectionLost(self, reason)
            self.factory.proto = None

            log.msg("Worker {}: Process connection gone ({})".format(self._pid, reason.value))

            if isinstance(reason.value, ProcessTerminated):
               if not ready.called:
                  ## the worker was never ready in the first place ..
                  ready.errback(reason)
               else:
                  ## the worker _did_ run (was ready before), but now exited with error
                  if not exit.called:
                     exit.errback(reason)
                  else:
                     log.msg("FIXME: unhandled code path (1) in WorkerClientProtocol.connectionLost", reason.value)
            elif isinstance(reason.value, ProcessDone) or isinstance(reason.value, ConnectionDone):
               ## the worker exited cleanly
               if not exit.called:
                  exit.callback()
               else:
                  log.msg("FIXME: unhandled code path (2) in WorkerClientProtocol.connectionLost", reason.value)
            else:
               ## should not arrive here
               log.msg("FIXME: unhandled code path (3) in WorkerClientProtocol.connectionLost", reason.value)


      class WorkerClientFactory(WampWebSocketClientFactory):

         def __init__(self, *args, **kwargs):
            WampWebSocketClientFactory.__init__(self, *args, **kwargs)
            self.proto = None

         def buildProtocol(self, addr):
            self.proto = WorkerClientProtocol()
            self.proto.factory = self
            return self.proto

         def stopFactory(self):
            WampWebSocketClientFactory.stopFactory(self)
            if self.proto:
               self.proto.close()
               #self.proto.transport.loseConnection()


      ## factory that creates router session transports. these are for clients
      ## that talk WAMP-WebSocket over pipes with spawned worker processes and
      ## for any uplink session to a management service
      ##
      factory = WorkerClientFactory(self._node._router_session_factory, "ws://localhost", debug = self.debug)

      ## we need to increase the opening handshake timeout in particular, since starting up a worker
      ## on PyPy will take a little (due to JITting)
      factory.setProtocolOptions(failByDrop = False, openHandshakeTimeout = 30, closeHandshakeTimeout = 5)

      ## now actually spawn the worker ..
      ##
      d = ep.connect(factory)

      def onconnect(res):
         pid = res.transport.pid
         log.msg("Worker PID {} process connected".format(pid))

         ## remember the worker process, including "ready" deferred. this will later
         ## be fired upon the worker publishing to 'crossbar.node.{}.on_worker_ready'
         self._workers[pid] = WorkerProcess(pid, ready, exit, factory = factory)

      def onerror(err):
         log.msg("Could not start worker process with args '{}': {}".format(args, err.value))
         ready.errback(err)

      d.addCallbacks(onconnect, onerror)

      return ready



   def stop_worker(self, pid):
      """
      Stops a worker process.
      """
      if pid in self._workers:
         try:
            self._workers[pid].factory.stopFactory()
         except Exception as e:
            log.msg("Could not stop worker {}: {}".format(pid, e))
            raise e
         else:
            del self._processes[pid]
      else:
         raise ApplicationError("wamp.error.invalid_argument", "No worker with PID '{}'".format(pid))



   def start_guest(self, config):
      """
      Start a new guest process on this node.

      :param config: The guest process configuration.
      :type config: obj

      :returns: int -- The PID of the new process.
      """

      class GuestClientProtocol(protocol.ProcessProtocol):

         def __init__(self):
            self._pid = None
            self._name = None

         def _log(self, data):
            for msg in data.split('\n'):
               msg = msg.strip()
               if msg != "":
                  log.msg(msg, system = "{:<10} {:>6}".format(self._name, self._pid))

         def connectionMade(self):
            if 'stdout' in config and config['stdout'] == 'close':
               self.transport.closeStdout()

            if 'stderr' in config and config['stderr'] == 'close':
               self.transport.closeStderr()

            if 'stdin' in config:
               if config['stdin'] == 'close':
                  self.transport.closeStdin()
               else:
                  if config['stdin']['type'] == 'json':
                     self.transport.write(json.dumps(config['stdin']['value']))
                  elif config['stdin']['type'] == 'msgpack':
                     pass ## FIXME
                  else:
                     raise Exception("logic error")

                  if config['stdin'].get('close', True):
                     self.transport.closeStdin()

         def outReceived(self, data):
            if config.get('stdout', None) == 'log':
               self._log(data)

         def errReceived(self, data):
            if config.get('stderr', None) == 'log':
               self._log(data)

         def inConnectionLost(self):
            pass

         def outConnectionLost(self):
            pass

         def errConnectionLost(self):
            pass

         def processExited(self, reason):
            pass

         def processEnded(self, reason):
            if isinstance(reason.value,  ProcessDone):
               log.msg("Guest {}: Ended cleanly.".format(self._pid))
            elif isinstance(reason.value, ProcessTerminated):
               log.msg("Guest {}: Ended with error {}".format(self._pid, reason.value.exitCode))
            else:
               ## should not arrive here
               pass


      class GuestClientFactory(protocol.Factory):

         protocol = GuestClientProtocol


      exe = config['executable']

      args = [exe]
      args.extend(config.get('arguments', []))

      workdir = self._node._cbdir
      if 'workdir' in config:
         workdir = os.path.join(workdir, config['workdir'])
      workdir = os.path.abspath(workdir)

      ready = Deferred()
      exit = Deferred()


      if False:
         self._guest_no += 1

         factory = GuestClientFactory()

         ep = CustomProcessEndpoint(self._node._reactor,
                  exe,
                  args,
                  name = "Guest {}".format(self._guest_no),
                  env = os.environ)

         ## now actually spawn the worker ..
         ##
         d = ep.connect(factory)

         def onconnect(proto):
            pid = proto.transport.pid
            proto._pid = pid
            self._guests[pid] = GuestProcess(pid, ready, exit, proto = proto)
            log.msg("Guest {}: Program started.".format(pid))
            ready.callback(pid)

         def onerror(err):
            log.msg("Guest: Program could not be started - {}".format(err.value))
            ready.errback(err)

         d.addCallbacks(onconnect, onerror)

      else:
         self._guest_no += 1

         proto = GuestClientProtocol()
         proto._name = "Guest {}".format(self._guest_no)

         try:
            trnsp = self._node._reactor.spawnProcess(proto, exe, args, path = workdir, env = os.environ)
         except Exception as e:
            log.msg("Guest: Program could not be started - {}".format(e))
            ready.errback(e)
         else:
            pid = trnsp.pid
            proto._pid = pid
            self._guests[pid] = GuestProcess(pid, ready, exit, proto = proto)
            log.msg("Guest {}: Program started.".format(pid))
            ready.callback(pid)

      return ready



   def stop_guest(self, pid):
      """
      Stops a guest process.
      """
      if pid in self._guests:
         try:
            self._guests[pid].proto.transport.loseConnection()
         except Exception as e:
            log.msg("Could not stop guest {}: {}".format(pid, e))
            raise e
         else:
            del self._guests[pid]
      else:
         raise ApplicationError("wamp.error.invalid_argument", "No guest with PID '{}'".format(pid))



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
      for process in config['processes']:

         process_options = process.get('options', {})

         ## worker
         ##
         if process['type'] == 'worker':

            ## start a new worker process ..
            ##
            try:
               pid = yield self.start_worker(process_options)
            except Exception as e:
               log.msg("Failed to start worker process: {}".format(e))
            else:
               log.msg("Worker {}: Started.".format(pid))

            ## setup worker generic stuff
            ##
            if 'pythonpath' in process_options:
               try:
                  added_paths = yield self.call('crossbar.node.{}.worker.{}.add_pythonpath'.format(self._node_name, pid),
                     process_options['pythonpath'])

               except Exception as e:
                  log.msg("Worker {}: Failed to set PYTHONPATH - {}".format(pid, e))
               else:
                  log.msg("Worker {}: PYTHONPATH extended for {}".format(pid, added_paths))

            if 'cpu_affinity' in process_options:
               try:
                  yield self.call('crossbar.node.{}.worker.{}.set_cpu_affinity'.format(self._node_name, pid),
                     process_options['cpu_affinity'])

               except Exception as e:
                  log.msg("Worker {}: Failed to set CPU affinity - {}".format(pid, e))
               else:
                  log.msg("Worker {}: CPU affinity set.".format(pid))

            try:
               cpu_affinity = yield self.call('crossbar.node.{}.worker.{}.get_cpu_affinity'.format(self._node_name, pid))
            except Exception as e:
               log.msg("Worker {}: Failed to get CPU affinity - {}".format(pid, e))
            else:
               log.msg("Worker {}: CPU affinity is {}".format(pid, cpu_affinity))

            ## manhole within worker
            ##
            if 'manhole' in process:
               yield self.call('crossbar.node.{}.worker.{}.start_manhole'.format(self._node_name, pid), process['manhole'])

            ## setup modules
            ##
            for module in process['modules']:

               ## Setup: WAMP router process
               ##
               if module['type'] == 'router':

                  ## start new router
                  ##
                  router_index = yield self.call('crossbar.node.{}.worker.{}.router.start'.format(self._node_name, pid))
                  log.msg("Worker {}: Router started ({})".format(pid, router_index))

                  ## start realms
                  ##
                  for realm_name in module['realms']:

                     realm_config = module['realms'][realm_name]
                     realm_index = yield self.call('crossbar.node.{}.worker.{}.router.start_realm'.format(self._node_name, pid),
                        router_index, realm_name, realm_config)

                     log.msg("Worker {}: Realm started on router {} ({})".format(pid, router_index, realm_index))

                     ## start any application components to run embedded in the realm
                     ##
                     for component_config in realm_config.get('components', []):

                        id = yield self.call('crossbar.node.{}.worker.{}.router.start_component'.format(self._node_name, pid),
                           router_index, realm_name, component_config)

                  ## start transports on router
                  ##
                  for transport in module['transports']:
                     id = yield self.call('crossbar.node.{}.worker.{}.router.start_transport'.format(self._node_name, pid),
                        router_index, transport)

                     log.msg("Worker {}: Transport {}/{} ({}) started on router {}".format(pid, transport['type'], transport['endpoint']['type'], id, router_index))

               ## Setup: Python component host process
               ##
               elif module['type'] == 'container':

                  log.msg("Worker {}: Component container started.".format(pid))

                  yield self.call('crossbar.node.{}.worker.{}.container.start_component'.format(self._node_name, pid),
                     module['component'], module['router'])

               else:
                  raise Exception("logic error")


         elif process['type'] == 'guest':

            ## start a new worker process ..
            ##
            try:
               pid = yield self.start_guest(process)
            except Exception as e:
               log.msg("Failed to start guest process: {}".format(e))
            else:
               log.msg("Guest {}: Started.".format(pid))

         else:
            raise Exception("unknown process type '{}'".format(process['type']))



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
      :param cbdir: Crossbar.io node directory to run from.
      :type cbdir: str
      """
      self._options = options

      self.debug = options.debug
      self._cbdir = options.cbdir

      self._reactor = reactor
      self._worker_processes = {}

      ## node name: FIXME
      self._node_name = "{}-{}".format(socket.getfqdn(), os.getpid())
      self._node_name.replace('-', '_')
      self._node_name = '918234'
      self._node_realm = 'crossbar'

      self._node_controller_session = None

      ## node management
      self._management_url = "ws://127.0.0.1:7000"
      #self._management_url = "wss://cloud.crossbar.io"
      self._management_realm = "crossbar.cloud.aliceblue"



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
         setproctitle.setproctitle("Crossbar.io Node Controller")

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
      log.msg("Detected {} WAMPlets in environment:".format(len(wamplets)))
      for wpl in wamplets:
         log.msg("WAMPlet {}.{}".format(wpl['dist'], wpl['name']))


      self._start_from_local_config(configfile = os.path.join(self._cbdir, self._options.config))

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
         config = check_config_file(configfile, silence = True)
      except Exception as e:
         log.msg("Fatal: {}".format(e))
         sys.exit(1)
      else:
         self._node_controller_session.run_node_config(config)
