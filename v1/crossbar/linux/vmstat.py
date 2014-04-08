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


import os

from twisted.python import log
from twisted.internet import protocol
from twisted.application import service

from autobahn.util import utcnow

from crossbar.adminwebmodule.uris import URI_EVENT


class VmstatProtocol(protocol.ProcessProtocol):
   """
   Protocol to continuously consume output from FreeBSD vmstat command.
   """

   def __init__(self, service = None):
      self.service = service

      s = os.popen("grep MemTotal /proc/meminfo").read().strip().split()[1]
      self.totalMemKB = int(s)

      self.current = {"timestamp": utcnow(),
                      "mem-used": 0,
                      "mem-free": 0,
                      "cpu-user": 0,
                      "cpu-system": 0,
                      "cpu-idle": 0}

   def connectionMade(self):
      self.line = ""
      self.transport.closeStdin()

   def processEnded(self, reason):
      pass

   def outReceived(self, data):
      if len(data) > 0:
         e = data.find('\n')
         if e >= 0:
            self.line += data[:e]
            self.processLine()
            self.line = ""
            self.outReceived(data[e + 1:])
         else:
            self.line += data

   def processLine(self):
      s = self.line.split()
      if len(s) == 17:
         try:
            d = [int(x) for x in s]
         except:
            pass
         else:
            (_r, _b, _swpd, _free, _buff, _cache, _si, _so, _bi, _bo, _in, _cs, _us, _sy, _id, _wa, _st) = d
            memUsed = int(round(100. * float(self.totalMemKB - _free) / float(self.totalMemKB)))
            memFree = 100 - memUsed
            self.processRecord(memUsed, memFree, _us, _sy, _id)

   def processRecord(self, memUsed, memFree, cpuUser, cpuSys, cpuIdle):
      evt = {"timestamp": utcnow(),
             "mem-used": memUsed,
             "mem-free": memFree,
             "cpu-user": cpuUser,
             "cpu-system": cpuSys,
             "cpu-idle": cpuIdle}
      self.current = evt
      if self.service:
         self.service.dispatchEvent(evt)
      else:
         log.msg(evt)


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
      self.vmstat = VmstatProtocol(self)
      self.reactor.spawnProcess(self.vmstat, 'vmstat', ['vmstat', '-n', str(self.interval)])
      self.isRunning = True

   def stopService(self):
      log.msg("Stopping %s service .." % self.SERVICENAME)
      self.vmstat.transport.signalProcess('KILL')
      self.isRunning = False

   def dispatchEvent(self, event):
      if self.services.has_key("adminws"):
         self.services["adminws"].dispatchAdminEvent(URI_EVENT + "on-vmstat", event)

   def getCurrent(self):
      return self.vmstat.current
