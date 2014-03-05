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



class NodeControllerSession(ApplicationSession):
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
            print e
         else:
            log.msg("Log into https://console.crossbar.io to configure your instance using the activation code: {}".format(activation_code))

            reg = None

            def activate(node_id, certificate):
               ## check if certificate was issued by Tavendo
               ## check if certificate matches node key
               ## persist node_id
               ## persist certificate
               ## restart node
               print "Node activated", node_id, certificate
               reg.unregister()

               self.publish('crossbar.node.onactivate', node_id)

               log.msg("Restarting node in 5 seconds ...")
               reactor.callLater(5, self.factory.node_session.restart_node)

            reg = yield self.register(activate, 'crossbar.node.activate.{}'.format(activation_code))
      else:
         pass

      res = yield self.register(self.factory.node_session.get_node_processes, 'crossbar.node.get_node_processes')
      print "register", res

      self.publish('com.myapp.topic1', os.getpid())



class NodeSession(ApplicationSession):
   """
   """
   def __init__(self, node):
      ApplicationSession.__init__(self)
      self._node = node
      self._controller_session = None

   def restart_node(self):
      print "restarting node .."


   def setControllerSession(self, session):
      self._controller_session = session


   def onConnect(self):
      self.join("crossbar")


   def onJoin(self, details):
      #print self.factory.session
      #self.publish('com.myapp.topic1', os.getpid())
      pass

   def get_node_processes(self):
      return sorted(self._node._processes.keys())



from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSessionFactory
from autobahn.twisted.websocket import WampWebSocketClientFactory
from twisted.internet.endpoints import ProcessEndpoint, StandardErrorBehavior
from crossbar.processproxy import ProcessProxy

import pkg_resources
from sys import argv, executable

from autobahn.twisted.wamp import ApplicationSessionFactory
from twisted.internet.endpoints import clientFromString



class Node:
   """
   A Crossbar.io node is the running a controller process
   and one or multiple worker processes.

   A single Crossbar.io node runs exactly one instance of
   this class, hence this class can be considered a system
   singleton.
   """

   def __init__(self, reactor, cbdir):
      """
      Ctor.

      :param reactor: Reactor to run on.
      :type reactor: obj
      :param cbdir: Crossbar.io node directory to run from.
      :type cbdir: str
      """
      self._reactor = reactor
      self._cbdir = cbdir
      self._processes = {}

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
      node_session = NodeSession(self)

      if False:
         session_factory = ApplicationSessionFactory()
         session_factory.session = NodeControllerSession
         session_factory.node_session = node_session
         transport_factory = WampWebSocketClientFactory(session_factory, "ws://127.0.0.1:7000")
         transport_factory.setProtocolOptions(failByDrop = False)
         client = clientFromString(self._reactor, "tcp:127.0.0.1:7000")
         client.connect(transport_factory)

      ## router and factory that creates router sessions
      ##
      router_factory = RouterFactory()
      router_session_factory = RouterSessionFactory(router_factory)

      ## 
      router_session_factory.add(node_session)

      ## factory that creates router session transports. these are for clients
      ## that talk WAMP-WebSocket over pipes with spawned worker processes
      ##
      transport_factory = WampWebSocketClientFactory(router_session_factory, "ws://localhost", debug = False)
      transport_factory.setProtocolOptions(failByDrop = False)

      WORKER_MAP = {
         "router": "router/worker.py",
         "component.python": "router/worker.py"
      }

      ## for each "process" in the node configuration, spawn a new worker process
      ##
      if 'processes' in self._config:
         for process in self._config['processes']:

            if not process['type'] in WORKER_MAP:
               #raise Exception("Illegal worker type '{}'".format(process['type']))
               pass

            else:

               filename = pkg_resources.resource_filename('crossbar', WORKER_MAP[process['type']])

               args = [executable, "-u", filename]

               if process.get('debug', False):
                  args.append('--debug')

               if sys.platform == 'win32':
                  args.extend(['--logfile', 'test.log'])
                  ep = ProcessEndpoint(self._reactor,
                                       executable,
                                       args,
                                       errFlag = StandardErrorBehavior.DROP,
                                       env = os.environ)
               else:
                  ep = ProcessEndpoint(self._reactor,
                                       executable,
                                       args,
                                       childFDs = {0: 'w', 1: 'r', 2: 2}, # does not work on Windows
                                       errFlag = StandardErrorBehavior.LOG,
                                       env = os.environ)

               d = ep.connect(transport_factory)

               def onconnect(res):
                  pid = res.transport.pid
                  log.msg("Worker forked with PID {}".format(pid))
                  proxy = ProcessProxy(pid, process)
                  router_session_factory.add(proxy)
                  self._processes[pid] = proxy

               def onerror(err):
                  log.msg("Could not fork worker: {}".format(err.value))

               d.addCallback(onconnect)

      else:
         raise Exception("no processes configured")
