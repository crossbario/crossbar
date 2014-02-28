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

import os


class NodeSession(ApplicationSession):
   """
   """
   def __init__(self):
      ApplicationSession.__init__(self)


   def onConnect(self):
      self.join("crossbar")


   def onJoin(self, details):
      print "JOINED"



from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSessionFactory
from autobahn.twisted.websocket import WampWebSocketClientFactory
from twisted.internet.endpoints import ProcessEndpoint, StandardErrorBehavior
from crossbar.processproxy import ProcessProxy

import pkg_resources
from sys import argv, executable



class Node:

   def __init__(self, reactor, config):
      self._reactor = reactor
      self._config = config


   def start(self):
      router_factory = RouterFactory()

      session_factory = RouterSessionFactory(router_factory)
      session_factory.add(NodeSession())

      transport_factory = WampWebSocketClientFactory(session_factory, "ws://localhost", debug = False)
      transport_factory.setProtocolOptions(failByDrop = False)

      WORKER_MAP = {
         "router": "router/worker.py",
         "component.python": "router/worker.py"
      }

      config = self._config

      if 'processes' in config:
         for process in config['processes']:

            if not process['type'] in WORKER_MAP:
               #raise Exception("Illegal worker type '{}'".format(process['type']))
               pass

            else:

               filename = pkg_resources.resource_filename('crossbar', WORKER_MAP[process['type']])

               args = [executable, "-u", filename]

               ep = ProcessEndpoint(self._reactor,
                                    executable,
                                    args,
                                    childFDs = {0: 'w', 1: 'r', 2: 2},
                                    errFlag = StandardErrorBehavior.LOG,
                                    env = os.environ)

               d = ep.connect(transport_factory)

               def onconnect(res):
                  log.msg("Worker forked with PID {}".format(res.transport.pid))
                  #print process
                  session_factory.add(ProcessProxy(res.transport.pid, process))

               def onerror(err):
                  log.msg("Could not fork worker: {}".format(err.value))

               d.addCallback(onconnect)

      else:
         raise Exception("no processes configured")
