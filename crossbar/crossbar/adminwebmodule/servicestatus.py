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


import datetime

import autobahn
from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

import crossbar
from crossbar.adminwebmodule.uris import *


class ServiceStatus:
   """
   Service status model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto
      self.services = proto.factory.services
      self.publishSystemStatus()


   def publishSystemStatus(self):
      e = self.getSystemStatus()
      self.proto.dispatch(URI_EVENT + "on-system-status", e, [])
      self.proto.factory.reactor.callLater(1, self.publishSystemStatus)


   @exportRpc("get-restart-required")
   def getRestartRequired(self):
      """
      Check if a restart of the service is required to
      make changes effective.
      """
      return self.proto.factory.getRestartRequired()


   @exportRpc("get-system-info")
   def getSystemInfo(self):
      """
      Get system information.
      """
      p = self.services["platform"]
      i = {"memory": p.getMemory(),
           "model": p.getHardwareModel(),
           "cores": p.getCoreCount(),
           "clock": p.getCoreClock()}
      return i


   @exportRpc("get-system-status")
   def getSystemStatus(self):
      """
      Get system status.
      """
      now = datetime.datetime.utcnow()
      booted = self.services["platform"].getBoottime()
      started = self.services["master"].started
      r = {"booted": utcstr(booted),
           "booted-ago": int(round((now - booted).total_seconds())),
           "started": utcstr(started),
           "started-ago": int(round((now - started).total_seconds()))
           }
      return r


   @exportRpc("get-network-config")
   def getNetworkConfig(self):
      """
      Get appliance network configuration.
      """
      return self.services["platform"].getNetworkConfig()


   @exportRpc("get-software-versions")
   def getSoftwareVersions(self):
      """
      Get software versions running.
      """
      p = self.services["platform"]
      v = {"crossbar": crossbar.version,
           "autobahn": autobahn.version,
           "twisted": p.getTwistedVersion(),
           "python": p.getPythonVersion(),
           "python-versionstring": p.getPythonVersionString(),
           "os": p.getOsVersion()}

      if self.services["master"].isExe:
         v["appliance"] = "Self-contained Executable"
      else:
         v["appliance"] = p.getApplianceVersion()

      return v


   @exportRpc("get-database-info")
   def getDatabaseInfo(self):
      """
      Get database information.
      """
      return self.services["database"].getDatabaseInfo()


   @exportRpc("get-wsstats")
   def getWsStats(self):
      """
      Get WebSocket statistics.

      Events:

         on-wsstat
      """
      if self.services.has_key("appws"):
         return self.services["appws"].getStats()
      else:
         return {"ws-connections": 0,
                 "ws-dispatched-failed": 0,
                 "ws-dispatched-success": 0,
                 "ws-publications": 0}


   @exportRpc("set-wiretap-mode")
   def setWiretapMode(self, sessionid, enable):
      """
      Enable/disable wiretapping on WAMP session.
      """
      if self.services.has_key("appws"):
         return self.services["appws"].setWiretapMode(sessionid, enable)
      else:
         raise Exception("service not enabled")


   @exportRpc("get-wsechostats")
   def getWsEchoStats(self):
      """
      Get WebSocket echo endpoint statistics.

      Events:

         on-wsechostat
      """
      if self.services.has_key("echows"):
         return self.services["echows"].getStats()
      else:
         return {}



   @exportRpc("get-restremoterstats")
   def getRestRemoterStats(self):
      """
      Get REST remoter statistics.

      Events:

         on-restremoterstat
      """
      if self.services.has_key("restremoter"):
         return self.services["restremoter"].getRemoterStats()
      else:
         return [{'uri': None,
                  'call-allowed': 0,
                  'call-denied': 0,
                  'forward-success': 0,
                  'forward-failed': 0}]


   @exportRpc("get-extdirectremoterstats")
   def getExtDirectRemoterStats(self):
      """
      Get Ext.Direct remoter statistics.

      Events:

         on-extdirectremoterstat
      """
      if self.services.has_key("extdirectremoter"):
         return self.services["extdirectremoter"].getRemoterStats()
      else:
         return [{'uri': None,
                  'call-allowed': 0,
                  'call-denied': 0,
                  'forward-success': 0,
                  'forward-failed': 0}]


   @exportRpc("get-oraremoterstats")
   def getOraRemoterStats(self):
      """
      Get Oracle remoter statistics.

      Events:

         on-oraremoterstat
      """
      if self.services.has_key("oraremoter"):
         return self.services["oraremoter"].getRemoterStats()
      else:
         return [{'uri': None,
                  'call-allowed': 0,
                  'call-denied': 0,
                  'forward-success': 0,
                  'forward-failed': 0}]


   @exportRpc("get-pgremoterstats")
   def getPgRemoterStats(self):
      """
      Get PostgreSQL remoter statistics.

      Events:

         on-pgremoterstat
      """
      if self.services.has_key("pgremoter"):
         return self.services["pgremoter"].getRemoterStats()
      else:
         return [{'uri': None,
                  'call-allowed': 0,
                  'call-denied': 0,
                  'forward-success': 0,
                  'forward-failed': 0}]


   @exportRpc("get-hanaremoterstats")
   def getHanaRemoterStats(self):
      """
      Get SAP HANA remoter statistics.

      Events:

         on-hanaremoterstat
      """
      if self.services.has_key("hanaremoter"):
         return self.services["hanaremoter"].getRemoterStats()
      else:
         return [{'uri': None,
                  'call-allowed': 0,
                  'call-denied': 0,
                  'forward-success': 0,
                  'forward-failed': 0}]


   @exportRpc("get-restpusherstats")
   def getRestPusherStats(self):
      """
      Get REST pusher statistics.

      Events:

         on-restpusherstat
      """
      if self.services.has_key("hubweb"):
         return self.services["hubweb"].getStats()
      else:
         return [{'uri': None,
                  'publish-allowed': 0,
                  'publish-denied': 0,
                  'dispatch-success': 0,
                  'dispatch-failed': 0}]


   @exportRpc("get-orapusherstats")
   def getOraPusherStats(self):
      """
      Get Oracle pusher statistics.

      Events:

         on-orapusherstat
      """
      if self.services.has_key("orapusher"):
         return self.services["orapusher"].getPusherStats()
      else:
         return [{'uri': None,
                  'publish-allowed': 0,
                  'publish-denied': 0,
                  'dispatch-success': 0,
                  'dispatch-failed': 0}]


   @exportRpc("get-pgpusherstats")
   def getPgPusherStats(self):
      """
      Get PostgreSQL pusher statistics.

      Events:

         on-pgpusherstat
      """
      if self.services.has_key("pgpusher"):
         return self.services["pgpusher"].getPusherStats()
      else:
         return [{'uri': None,
                  'publish-allowed': 0,
                  'publish-denied': 0,
                  'dispatch-success': 0,
                  'dispatch-failed': 0}]


   @exportRpc("get-hanapusherstats")
   def getHanaPusherStats(self):
      """
      Get SAP HANA pusher statistics.

      Events:

         on-hanapusherstat
      """
      if self.services.has_key("hanapusher"):
         return self.services["hanapusher"].getPusherStats()
      else:
         return [{'uri': None,
                  'publish-allowed': 0,
                  'publish-denied': 0,
                  'dispatch-success': 0,
                  'dispatch-failed': 0}]


   @exportRpc("get-vmstats")
   def getVmStats(self):
      """
      Get current system load.

      Events:

         on-vmstat
      """
      return self.services["vmstat"].getCurrent()


   @exportRpc("get-netstats")
   def getNetStats(self):
      """
      Get current network load.

      Events:

         on-netstat
      """
      return self.services["netstat"].getCurrent()


   @exportRpc("get-service-status")
   def getServiceStatus(self):
      """
      """
      licenseOptions = self.services["master"].licenseOptions
      installedOptions = self.services["master"].installedOptions
      res = {}
      for s, l, i in [
                ("appws", None, None),

                ("flashpolicy", None, None),
                ("echows", None, None),
                ("ftp", None, None),

                ("netstat", None, None),
                ("vmstat", None, None),

                ("restpusher", "rest", None),
                ("restremoter", "rest", None),
                ("pgpusher", "postgresql", "postgresql"),
                ("pgremoter", "postgresql", "postgresql"),
                ("orapusher", "oracle", "oracle"),
                ("oraremoter", "oracle", "oracle"),
                ("hanapusher", "hana", "hana"),
                ("hanaremoter", "hana", "hana"),

                ("extdirectremoter", "extdirect", None),
                ]:
         if self.services.has_key(s):
            res[s] = self.services[s].isRunning
         else:
            if licenseOptions.has_key(l) and not licenseOptions[l]:
               ## service unavailable because not licensed
               res[s] = None
            elif installedOptions.has_key(i) and not installedOptions[i]:
               ## service unavailable because not installed
               res[s] = None
            else:
               ## service unavailable because disabled
               res[s] = False

      if self.services.has_key("adminweb") and self.services.has_key("adminws"):
         res["adminui"] = self.services["adminweb"].isRunning and self.services["adminws"].isRunning
      else:
         res["adminui"] = False

      if self.services.has_key("appws"):
         res["appweb"] = self.services["appws"].isRunning and self.services["appws"].enableAppWeb
      else:
         res["appweb"] = False

      if self.services["master"].isExe:
         # a self-contained EXE cannot be updated or automatically restarted
         #
         res["update"] = False
         res["autorestart"] = False
      else:
         res["update"] = True
         res["autorestart"] = True

      return res
