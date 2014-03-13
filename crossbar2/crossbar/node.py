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

__all__ = ['NodeSession']


from twisted.python import log
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession

import os, sys
import json


from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSessionFactory
from autobahn.twisted.websocket import WampWebSocketClientFactory
from twisted.internet.endpoints import ProcessEndpoint, StandardErrorBehavior

import pkg_resources
from sys import argv, executable

from autobahn.twisted.wamp import ApplicationSessionFactory
from twisted.internet.endpoints import clientFromString

from autobahn.wamp.exception import ApplicationError

from autobahn.util import utcnow

import socket
import os


class NodeManagementSession(ApplicationSession):
   """
   """
   def __init__(self):
      ApplicationSession.__init__(self)


   def onConnect(self):
      self.join("crossbar.cloud")


   def is_paired(self):
      return False


   @inlineCallbacks
   def onJoin(self, details):
      log.msg("Connected to Crossbar.io Management Cloud.")

      from twisted.internet import reactor

      self.factory.node_session.setControllerSession(self)

      if not self.is_paired():
         try:
            node_info = {}
            node_publickey = "public key"
            activation_code = yield self.call('crossbar.cloud.get_activation_code', node_info, node_publickey)
         except Exception as e:
            log.msg("internal error: {}".format(e))
         else:
            log.msg("Log into https://console.crossbar.io to configure your instance using the activation code: {}".format(activation_code))

            reg = None

            def activate(node_id, certificate):
               ## check if certificate was issued by Tavendo
               ## check if certificate matches node key
               ## persist node_id
               ## persist certificate
               ## restart node
               reg.unregister()

               self.publish('crossbar.node.onactivate', node_id)

               log.msg("Restarting node in 5 seconds ...")
               reactor.callLater(5, self.factory.node_controller_session.restart_node)

            reg = yield self.register(activate, 'crossbar.node.activate.{}'.format(activation_code))
      else:
         pass

      res = yield self.register(self.factory.node_controller_session.get_node_worker_processes, 'crossbar.node.get_node_worker_processes')

      self.publish('com.myapp.topic1', os.getpid())



class NodeControllerSession(ApplicationSession):
   """
   Singleton node WAMP session hooked up to the node router.

   This class exposes the node's management API.
   """
   class NodeProcess:
      def __init__(self, ptype, pid, ready = None):
         assert(ptype in ['worker', 'program'])
         self.ptype = ptype
         self.pid = pid
         self.ready = ready
         self.created = utcnow()


   def __init__(self, node):
      ApplicationSession.__init__(self)
      self.debug = False
      self._node = node
      self._node_name = node._node_name
      self._management_session = None
      self._processes = {}


   def onConnect(self):
      self.join("crossbar")


   def onJoin(self, details):

      def on_worker_ready(res):
         ## fire the Deferred previously stored for signaling "worker ready"
         pid = res['pid']
         r = self._processes.get(pid, None)
         if r and r.ready:
            r.ready.callback(pid)
            r.ready = None

      dl = []
      dl.append(self.subscribe(on_worker_ready, 'crossbar.node.{}.on_worker_ready'.format(self._node._node_name)))

      dl.append(self.register(self.start_process, 'crossbar.node.{}.start_process'.format(self._node._node_name)))
      dl.append(self.register(self.get_processes, 'crossbar.node.{}.get_processes'.format(self._node._node_name)))


   def stop_node(self):
      pass


   def restart_node(self):
      log.msg("restarting node ..")


   @inlineCallbacks
   def run_node_config(self, config):

      options = config.get('options', {})

      for process in config['processes']:

         process_options = process.get('options', {})

         if process['type'] in ['router', 'component.python']:

            ## start a new worker process ..
            pid = yield self.start_process(process)

            ## .. and orchestrate the startup of the worker
            if 'classpaths' in process_options:
               yield self.call('crossbar.node.{}.process.{}.add_classpaths'.format(self._node_name, pid), process_options['classpaths'])

            if process['type'] == 'router':

               router_index = yield self.call('crossbar.node.{}.process.{}.start_router'.format(self._node_name, pid))
               log.msg("Worker {}: Router started ({})".format(pid, router_index))

               for realm_name in process['realms']:
                  realm_config = process['realms'][realm_name]
                  realm_index = yield self.call('crossbar.node.{}.process.{}.router.{}.start_realm'.format(self._node_name, pid, router_index), realm_name, realm_config)
                  log.msg("Worker {}: Realm started on router {} ({})".format(pid, router_index, realm_index))

                  try:
                     for klassname in realm_config.get('classes', []):
                        id = yield self.call('crossbar.node.{}.process.{}.router.{}.start_class'.format(self._node_name, pid, router_index), klassname, realm_name)
                        log.msg("Worker {}: Class '{}' ({}) started in realm '{}' on router {}".format(pid, klassname, id, realm_name, router_index))
                  except Exception as e:
                     log.msg("internal error: {} {}".format(e, e.args))

               for transport in process['transports']:
                  id = yield self.call('crossbar.node.{}.process.{}.router.{}.start_transport'.format(self._node_name, pid, router_index), transport)
                  log.msg("Worker {}: Transport {}/{} ({}) started on router {}".format(pid, transport['type'], transport['endpoint']['type'], id, router_index))

            elif process['type'] == 'component.python':

               klassname, realm_name = process['class'], process['router']['realm']

               yield self.call('crossbar.node.module.{}.component.start'.format(pid), process['router'], klassname, realm_name)
               log.msg("Worker {}: Component container started ().".format(pid))
               log.msg("Worker {}: Class '{}' started in realm '{}'".format(pid, klassname, realm_name))

            else:
               raise Exception("logic error")

         elif process['type'] == 'component.program':

            pid = yield self.start_process(process)

         else:
            raise ApplicationError("wamp.error.invalid_argument", "Invalid process type '{}'".format(process['type']))


   def start_process(self, config):
      """
      Management API for starting a new process on this node.

      :param config: The process configuration.
      :type config: dict

      :returns: int -- The PID of the new process.
      """
      if config['type'] in ['router', 'component.python']:

         ##
         ## start a Crossbar.io worker process
         ##
         filename = pkg_resources.resource_filename('crossbar', 'worker.py')

         args = [executable, "-u", filename]

         if self.debug:
            args.append('--debug')

         if sys.platform == 'win32':
            args.extend(['--logfile', 'test.log'])
            ep = ProcessEndpoint(self._node._reactor,
                                 executable,
                                 args,
                                 errFlag = StandardErrorBehavior.DROP,
                                 env = os.environ)
         else:
            ep = ProcessEndpoint(self._node._reactor,
                                 executable,
                                 args,
                                 childFDs = {0: 'w', 1: 'r', 2: 2}, # does not work on Windows
                                 errFlag = StandardErrorBehavior.LOG,
                                 env = os.environ)

         ready = Deferred()

         d = ep.connect(self._node._router_client_transport_factory)

         def onconnect(res):
            pid = res.transport.pid
            self._processes[pid] = NodeControllerSession.NodeProcess('worker', pid, ready)

         def onerror(err):
            ready.errback(err)

         d.addCallbacks(onconnect, onerror)

         return ready

      elif config['type'] == 'component.program':

         ##
         ## start a program process
         ##
         from twisted.internet import protocol
         from twisted.internet import reactor
         from twisted.internet.error import ProcessDone, ProcessTerminated
         import re, json

         class ProgramWorkerProcess(protocol.ProcessProtocol):

            def __init__(self):
               self._pid = None

            def connectionMade(self):
               if 'stdin' in config and config['stdin'] == 'config' and 'config' in config:
                  ## write process config from configuration to stdin
                  ## of the forked process and close stdin
                  self.transport.write(json.dumps(config['config']))
                  self.transport.closeStdin()

            def outReceived(self, data):
               if 'stdout' in config and config['stdout'] == 'log':
                  try:
                     data = str(data).strip()
                  except:
                     data = "{} bytes".format(len(data))
                  log.msg("Worker {} (stdout): {}".format(self._pid, data))

            def errReceived(self, data):
               if 'stderr' in config and config['stderr'] == 'log':
                  try:
                     data = str(data).strip()
                  except:
                     data = "{} bytes".format(len(data))
                  log.msg("Worker {} (stderr): {}".format(self._pid, data))

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
                  log.msg("Worker {}: Ended cleanly.".format(self._pid))
               elif isinstance(reason.value, ProcessTerminated):
                  log.msg("Worker {}: Ended with error {}".format(self._pid, reason.value.exitCode))
               else:
                  ## should not arrive here
                  pass

         exe = config['executable']

         args = [exe]
         args.extend(config.get('arguments', []))

         workdir = self._node._cbdir
         if 'workdir' in config:
            workdir = os.path.join(workdir, config['workdir'])
         workdir = os.path.abspath(workdir)

         ready = Deferred()

         proto = ProgramWorkerProcess()
         try:
            trnsp = reactor.spawnProcess(proto, exe, args, path = workdir, env = os.environ)
         except Exception as e:
            log.msg("Worker: Program could not be started - {}".format(e))
            ready.errback(e)
         else:
            pid = trnsp.pid
            proto._pid = pid
            self._processes[pid] = NodeControllerSession.NodeProcess('program', pid, ready)
            log.msg("Worker {}: Program started.".format(pid))
            ready.callback(pid)

         return ready

      else:

         raise ApplicationError("wamp.error.invalid_argument", "Invalid process type '{}'".format(config['type']))


   def stop_process(self, pid):
      pass


   def get_processes(self):
      """
      Returns a list of PIDs of worker processes.
      """
      res = []
      for k in sorted(self._processes.keys()):
         p = self._processes[k]
         res.append({'pid': p.pid, 'created': p.created, 'type': p.ptype, 'is_ready': p.ready is None})
      return res



class Node:
   """
   A Crossbar.io node is the running a controller process
   and one or multiple worker processes.

   A single Crossbar.io node runs exactly one instance of
   this class, hence this class can be considered a system
   singleton.
   """

   def __init__(self, reactor, cbdir, debug = False):
      """
      Ctor.

      :param reactor: Reactor to run on.
      :type reactor: obj
      :param cbdir: Crossbar.io node directory to run from.
      :type cbdir: str
      """
      self.debug = debug

      self._reactor = reactor
      self._cbdir = cbdir
      self._worker_processes = {}

      ## node name: FIXME
      self._node_name = "{}-{}".format(socket.getfqdn(), os.getpid())
      self._node_name.replace('-', '_')
      self._node_name = '918234'

      ## node management
      self._management_url = "ws://127.0.0.1:7000"
      #self._management_url = "wss://cloud.crossbar.io"
      self._management_realm = "crossbar.cloud.aliceblue"

      ## load Crossbar.io node configuration
      ##
      cf = os.path.join(self._cbdir, 'config.json')
      with open(cf, 'rb') as infile:
         self._config = json.load(infile)


   def start(self):
      """
      Starts this node. This will start a node controller
      and then spawn new worker processes as needed.

      The node controller will watch spawned processes,
      communicate via stdio with the worker, and start
      and restart the worker processes as needed.
      """
      ## the node controller singleton WAMP application session
      ##
      self._node_controller_session = NodeControllerSession(self)

      ## router and factory that creates router sessions
      ##
      self._router_factory = RouterFactory()
      self._router_session_factory = RouterSessionFactory(self._router_factory)

      ## add the node controller singleton session to the router
      ##
      self._router_session_factory.add(self._node_controller_session)

      if True:
         ## create a WAMP-over-WebSocket transport server factory
         ##
         from autobahn.twisted.websocket import WampWebSocketServerFactory
         from twisted.internet.endpoints import serverFromString

         self._router_server_transport_factory = WampWebSocketServerFactory(self._router_session_factory, "ws://localhost:9000", debug = False)
         self._router_server_transport_factory.setProtocolOptions(failByDrop = False)


         ## start the WebSocket server from an endpoint
         ##
         self._router_server = serverFromString(self._reactor, "tcp:9000")
         self._router_server.listen(self._router_server_transport_factory)

      ## factory that creates router session transports. these are for clients
      ## that talk WAMP-WebSocket over pipes with spawned worker processes and
      ## for any uplink session to a management service
      ##
      self._router_client_transport_factory = WampWebSocketClientFactory(self._router_session_factory, "ws://localhost", debug = False)
      self._router_client_transport_factory.setProtocolOptions(failByDrop = False)

      if False:
         management_session_factory = ApplicationSessionFactory()
         management_session_factory.session = NodeManagementSession
         management_session_factory.node_controller_session = node_controller_session
         management_transport_factory = WampWebSocketClientFactory(management_session_factory, "ws://127.0.0.1:7000")
         management_transport_factory.setProtocolOptions(failByDrop = False)
         management_client = clientFromString(self._reactor, "tcp:127.0.0.1:7000")
         management_client.connect(management_transport_factory)


      ## startup the node from configuration file
      ##
      self._node_controller_session.run_node_config(self._config)
