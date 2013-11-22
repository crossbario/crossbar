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

from twisted.python import log
from twisted.application.internet import TCPServer

from autobahn.flashpolicy import FlashPolicyFactory



class FlashPolicyService(TCPServer):

   SERVICENAME = "Flash Policy File"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False

      port = services["config"]["flash-policy-port"]
      allowedPort = services["config"]["hub-websocket-port"]
      factory = FlashPolicyFactory(allowedPort, reactor)
      TCPServer.__init__(self, port, factory)

   def startService(self):
      log.msg("Starting %s service .." % self.SERVICENAME)
      TCPServer.startService(self)
      self.isRunning = True

   def stopService(self):
      log.msg("Stopping %s service .." % self.SERVICENAME)
      TCPServer.stopService(self)
      self.isRunning = False
