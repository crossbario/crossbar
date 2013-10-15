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


import re

from twisted.python import log
from twisted.internet import reactor
from twisted.application.internet import TCPServer
from twisted.internet.protocol import Protocol, Factory


class FlashPolicyProtocol(Protocol):
   """
   Flash Player 9 (version 9.0.124.0 and above) implements a strict new access
   policy for Flash applications that make Socket or XMLSocket connections to
   a remote host. It now requires the presence of a socket policy file
   on the server.

   http://www.lightsphere.com/dev/articles/flash_socket_policy.html

   We want this to support the Flash WebSockets bridge which is needed for
   older browser, in particular MSIE9/8.
   """

   REQUESTPAT = re.compile("^\s*<policy-file-request\s*/>")
   REQUESTMAXLEN = 200
   REQUESTTIMEOUT = 5
   POLICYFILE = """<?xml version="1.0"?><cross-domain-policy><allow-access-from domain="*" to-ports="%d" /></cross-domain-policy>"""

   def __init__(self, allowedPort):
      self.allowedPort = allowedPort
      self.received = ""
      self.dropConnection = None


   def connectionMade(self):
      ## DoS protection
      ##
      def dropConnection():
         self.transport.abortConnection()
         self.dropConnection = None
      self.dropConnection = reactor.callLater(FlashPolicyProtocol.REQUESTTIMEOUT, dropConnection)


   def connectionLost(self, reason):
      if self.dropConnection:
         self.dropConnection.cancel()
         self.dropConnection = None


   def dataReceived(self, data):
      self.received += data
      if FlashPolicyProtocol.REQUESTPAT.match(self.received):
         ## got valid request: send policy file
         ##
         self.transport.write(FlashPolicyProtocol.POLICYFILE % self.allowedPort)
         self.transport.loseConnection()
      elif len(self.received) > FlashPolicyProtocol.REQUESTMAXLEN:
         ## possible DoS attack
         ##
         self.transport.abortConnection()
      else:
         ## need more data
         ##
         pass


class FlashPolicyFactory(Factory):

   def __init__(self, config):
      self.config = config

   def buildProtocol(self, addr):
      return FlashPolicyProtocol(self.config["hub-websocket-port"])


class FlashPolicyService(TCPServer):

   SERVICENAME = "Flash Policy File"

   def __init__(self, dbpool, services):
      self.dbpool = dbpool
      self.services = services
      self.isRunning = False

      port = services["config"]["flash-policy-port"]
      factory = FlashPolicyFactory(services["config"])
      TCPServer.__init__(self, port, factory)

   def startService(self):
      log.msg("Starting %s service .." % self.SERVICENAME)
      TCPServer.startService(self)
      self.isRunning = True

   def stopService(self):
      log.msg("Stopping %s service .." % self.SERVICENAME)
      TCPServer.stopService(self)
      self.isRunning = False
