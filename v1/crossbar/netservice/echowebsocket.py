###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
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


import math

from twisted.python import log
from twisted.application import service

from autobahn.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS

from autobahn.compress import *

from crossbar.tlsctx import TlsContextFactory
from crossbar.adminwebmodule.uris import *



class EchoWebSocketProtocol(WebSocketServerProtocol):
   """
   Simple WebSocket echo service protocol.
   """

   def onMessage(self, msg, binary):
      self.sendMessage(msg, binary)
      self.factory.onEchoMessage(binary, len(msg))


   def connectionMade(self):
      WebSocketServerProtocol.connectionMade(self)
      self.factory.onConnectionCountChanged()


   def connectionLost(self, reason):
      WebSocketServerProtocol.connectionLost(self, reason)
      self.factory.onConnectionCountChanged()



class EchoWebSocketFactory(WebSocketServerFactory):
   """
   Simple WebSocket echo service protocol.
   """

   protocol = EchoWebSocketProtocol

   def __init__(self, url, dbpool, services, reactor = None):
      WebSocketServerFactory.__init__(self, url, debug = False, debugCodePaths = False, reactor = reactor)

      self.dbpool = dbpool
      self.services = services

      ## reset Echo endpoint stats
      ##
      self.stats = {'wsecho-connections': 0,
                    'wsecho-echos-text-count': 0,
                    'wsecho-echos-text-bytes': 0,
                    'wsecho-echos-binary-count': 0,
                    'wsecho-echos-binary-bytes': 0}
      self.statsChanged = False


   def setOptionsFromConfig(self):
      c = self.services["config"]

      versions = []
      if c.get("ws-allow-version-0"):
         versions.append(0)
      if c.get("ws-allow-version-8"):
         versions.append(8)
      if c.get("ws-allow-version-13"):
         versions.append(13)

      ## FIXME: enforce!!
      ##
      self.connectionCap = c.get("ws-max-connections")

      self.setProtocolOptions(versions = versions,
                              allowHixie76 = c.get("ws-allow-version-0"),
                              webStatus = c.get("ws-enable-webstatus"),
                              utf8validateIncoming = c.get("ws-validate-utf8"),
                              maskServerFrames = c.get("ws-mask-server-frames"),
                              requireMaskedClientFrames = c.get("ws-require-masked-client-frames"),
                              applyMask = c.get("ws-apply-mask"),
                              maxFramePayloadSize = c.get("ws-max-frame-size"),
                              maxMessagePayloadSize = c.get("ws-max-message-size"),
                              autoFragmentSize = c.get("ws-auto-fragment-size"),
                              failByDrop = c.get("ws-fail-by-drop"),
                              echoCloseCodeReason = c.get("ws-echo-close-codereason"),
                              openHandshakeTimeout = c.get("ws-open-handshake-timeout"),
                              closeHandshakeTimeout = c.get("ws-close-handshake-timeout"),
                              tcpNoDelay = c.get("ws-tcp-nodelay"))

      ## permessage-compression WS extension
      ##
      if c.get("ws-enable-permessage-deflate"):

         windowSize = c.get("ws-permessage-deflate-window-size")
         windowBits = int(math.log(windowSize, 2)) if windowSize != 0 else 0
         requireWindowSize = c.get("ws-permessage-deflate-require-window-size")

         def accept(offers):
            for offer in offers:
               if isinstance(offer, PerMessageDeflateOffer):
                  if windowBits != 0 and offer.acceptMaxWindowBits:
                     return PerMessageDeflateOfferAccept(offer,
                                                         requestMaxWindowBits = windowBits,
                                                         windowBits = windowBits)
                  elif windowBits == 0 or not requireWindowSize:
                     return PerMessageDeflateOfferAccept(offer)

         self.setProtocolOptions(perMessageCompressionAccept = accept)


   def startFactory(self):
      WebSocketServerFactory.startFactory(self)
      self.setOptionsFromConfig()
      log.msg("EchoWebSocketFactory started [speaking WebSocket versions %s]" % self.versions)
      self.publishStats()


   def getStats(self):
      return self.stats


   def publishStats(self):
      if self.statsChanged:
         self.services["adminws"].dispatchAdminEvent(URI_EVENT + "on-wsechostat", self.stats)
         self.statsChanged = False
      self.reactor.callLater(0.2, self.publishStats)


   def onConnectionCountChanged(self):
      self.stats["wsecho-connections"] = self.getConnectionCount()
      self.statsChanged = True


   def onEchoMessage(self, binary, length):
      if binary:
         self.stats['wsecho-echos-binary-count'] += 1
         self.stats['wsecho-echos-binary-bytes'] += length
      else:
         self.stats['wsecho-echos-text-count'] += 1
         self.stats['wsecho-echos-text-bytes'] += length
      self.statsChanged = True



class EchoWebSocketService(service.Service):

   SERVICENAME = "Echo WebSocket"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False
      self.factory = None
      self.listener = None


   def setOptionsFromConfig(self):
      if self.factory:
         self.factory.setOptionsFromConfig()


   def getStats(self):
      if self.isRunning and self.factory:
         return self.factory.getStats()


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)
      if self.services["config"]["echo-websocket-tls"]:
         contextFactory = TlsContextFactory(self.services["config"]["echo-websocket-tlskey-pem"],
                                            self.services["config"]["echo-websocket-tlscert-pem"],
                                            dhParamFilename = self.services['master'].dhParamFilename)

         uri = "wss://localhost:%d" % self.services["config"]["echo-websocket-port"]
      else:
         contextFactory = None

         uri = "ws://localhost:%d" % self.services["config"]["echo-websocket-port"]

      self.factory = EchoWebSocketFactory(uri, self.dbpool, self.services, self.reactor)
      self.listener = listenWS(self.factory,
                               contextFactory,
                               backlog = self.services["config"]["ws-accept-queue-size"])
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      if self.listener:
         self.listener.stopListening()
         self.listener = None
         self.factory = None
      self.isRunning = False
