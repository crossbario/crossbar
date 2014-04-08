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


import random

from twisted.python import log
from twisted.internet import protocol
from twisted.application import service

from autobahn.util import utcnow

from crossbar.adminwebmodule.uris import URI_EVENT


class VmstatService(service.Service):

   SERVICENAME = "Memory monitoring"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.interval = 1
      self.isRunning = False

   def startService(self):
      log.msg("Starting %s service .." % self.SERVICENAME)
      self.current = {"timestamp": utcnow(),
                      "mem-used": 0,
                      "mem-free": 0,
                      "cpu-user": 0,
                      "cpu-system": 0,
                      "cpu-idle": 0}
      self.isRunning = True
      self.emitFake()

   def stopService(self):
      log.msg("Stopping %s service .." % self.SERVICENAME)
      self.isRunning = False

   def dispatchEvent(self, event):
      if self.services.has_key("adminws"):
         self.services["adminws"].dispatchAdminEvent(URI_EVENT + "on-vmstat", event)

   def getCurrent(self):
      return self.current

   def emitFake(self):
      m1 = random.randint(0, 100)
      m2 = 100 - m1

      c1 = random.randint(0, 100)
      c2 = random.randint(0, 100 - c1)
      c3 = 100 - c2 - c1
      self.processRecord(m1, m2, c1, c2, c3)
      if self.isRunning:
         self.reactor.callLater(self.interval, self.emitFake)

   def processRecord(self, memUsed, memFree, cpuUser, cpuSys, cpuIdle):
      evt = {"timestamp": utcnow(),
             "mem-used": memUsed,
             "mem-free": memFree,
             "cpu-user": cpuUser,
             "cpu-system": cpuSys,
             "cpu-idle": cpuIdle}
      self.current = evt
      self.dispatchEvent(evt)
