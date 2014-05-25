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

__all__ = ['create_native_worker_client_factory']

from twisted.python import log

from autobahn.twisted.websocket import WampWebSocketClientFactory, \
                                       WampWebSocketClientProtocol

from twisted.internet.error import ProcessDone, \
                                   ProcessTerminated, \
                                   ConnectionDone, \
                                   ConnectionClosed, \
                                   ConnectionLost, \
                                   ConnectionAborted



class NativeWorkerClientProtocol(WampWebSocketClientProtocol):

   def connectionMade(self):
      WampWebSocketClientProtocol.connectionMade(self)
      self._pid = self.transport.pid
      self.factory.proto = self


   def connectionLost(self, reason):
      log.msg("Worker {}: Process connection gone ({})".format(self._pid, reason.value))

      WampWebSocketClientProtocol.connectionLost(self, reason)
      self.factory.proto = None


      if isinstance(reason.value, ProcessTerminated):
         if not self.factory._on_ready.called:
            ## the worker was never ready in the first place ..
            self.factory._on_ready.errback(reason)
         else:
            ## the worker _did_ run (was ready before), but now exited with error
            if not self.factory._on_exit.called:
               self.factory._on_exit.errback(reason)
            else:
               log.msg("FIXME: unhandled code path (1) in WorkerClientProtocol.connectionLost", reason.value)
      elif isinstance(reason.value, ProcessDone) or isinstance(reason.value, ConnectionDone):
         ## the worker exited cleanly
         if not self.factory._on_exit.called:
            self.factory._on_exit.callback(None)
         else:
            log.msg("FIXME: unhandled code path (2) in WorkerClientProtocol.connectionLost", reason.value)
      else:
         ## should not arrive here
         log.msg("FIXME: unhandled code path (3) in WorkerClientProtocol.connectionLost", reason.value)



class NativeWorkerClientFactory(WampWebSocketClientFactory):

   def __init__(self, *args, **kwargs):
      WampWebSocketClientFactory.__init__(self, *args, **kwargs)
      self.proto = None

   def buildProtocol(self, addr):
      self.proto = NativeWorkerClientProtocol()
      self.proto.factory = self
      return self.proto

   def stopFactory(self):
      WampWebSocketClientFactory.stopFactory(self)
      if self.proto:
         self.proto.close()
         #self.proto.transport.loseConnection()



def create_native_worker_client_factory(router_session_factory, on_ready, on_exit):
   """
   Create a transport factory for talking to native workers.

   The node controller talks WAMP-WebSocket-over-STDIO with spawned (native) workers.

   The node controller runs a client transport factory, and the native worker
   runs a server transport factory. This is a little non-intuitive, but just the
   way that Twisted works when using STDIO transports.

   :param router_session_factory: Router session factory to attach to.
   :type router_session_factory: obj
   """
   factory = NativeWorkerClientFactory(router_session_factory, "ws://localhost", debug = False)

   ## we need to increase the opening handshake timeout in particular, since starting up a worker
   ## on PyPy will take a little (due to JITting)
   factory.setProtocolOptions(failByDrop = False, openHandshakeTimeout = 30, closeHandshakeTimeout = 5)
   factory._on_ready = on_ready
   factory._on_exit = on_exit

   return factory
