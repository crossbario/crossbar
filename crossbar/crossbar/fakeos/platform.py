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


import os, sys, datetime, uuid

from distutils.sysconfig import get_python_lib # for site-packages directory

from twisted.python import log
from twisted.application import service

from autobahn.wamp import json_dumps


class PlatformService(service.Service):

   SERVICENAME = "Platform"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      self.isRunning = False


   def getHostId(self):
      return str(uuid.UUID(int = uuid.getnode()))


   def getHardwareModel(self):
      return "Fake-CPU 3.0 GHz"


   def getCoreCount(self):
      return 1


   def getCoreClock(self):
      return 3000


   def getMemory(self):
      return 1024


   def getPlatformInfo(self):
      return {'os': self.getOsVersion(),
              'appliance': self.getApplianceVersion(),
              'model': self.getHardwareModel(),
              'cores': self.getCoreCount(),
              'clock': self.getCoreClock(),
              'memory': self.getMemory()}


   def getSysctl(self, as_dict = False):
      if as_dict:
         return {}
      else:
         return []


   def getBoottime(self):
      return datetime.datetime.utcnow()


   def getNetworkConfig(self, ifc = "em0"):
      return {'mac': '01:12:34:56',
              'ip': '192.168.1.100',
              'netmask': '255.255.255.0',
              'broadcast': '255.255.255.255',
              'default_router': '192.168.1.1',
              'hostname': 'localhost',
              'nameserver': '192.168.1.1'}


   def getSystime(self):
      return datetime.datetime.utcnow()


   def getUptime(self):
      return '0 s'


   def getOsVersion(self):
      return "Fake OS 1.0"


   def getApplianceVersion(self):
      return "unknown"


   def getPythonVersion(self):
      return '.'.join([str(x) for x in list(sys.version_info[:3])])


   def getPythonVersionString(self):
      return sys.version.replace('\n', ' ')


   def getTwistedVersion(self):
      try:
         import pkg_resources
         version = pkg_resources.require("Twisted")[0].version
      except:
         ## i.e. no setuptools installed ..
         version = None
      return version


   def getDmesg(self):
      return []


   def getIfconfig(self):
      return []


   def getPkgInfo(self):
      return []


   def getSitePackages(self):
      res = sorted(os.listdir(get_python_lib()))
      return res


   def getDiagnostics(self, as_json = False):
      r = {}
      r['python-site-packages'] = self.getSitePackages()
      r['package-info'] = self.getPkgInfo()
      r['interface-config'] = self.getIfconfig()
      r['dmesg'] = self.getDmesg()
      r['twisted-version'] = self.getTwistedVersion()
      r['python-version'] = self.getPythonVersion()
      r['os-version'] = self.getOsVersion()
      r['host-id'] = self.getHostId()
      r['network-config'] = self.getNetworkConfig()
      r['sysctl'] = self.getSysctl()
      if as_json:
         return json_dumps(r, indent = 3)
      else:
         return r


   def applianceControl(self, cmd):
      if cmd == "restart":
         self.reactor.stop()
         sys.exit(0)
      elif cmd == "update":
         log.msg("ApplianceControl [FAKE]: update triggered .. will do nothing on FAKE platform")
         return "Update on FAKE platform: doing nothing!"
      else:
         raise Exception("ApplianceControl [FAKE]: skipping unknown command '%s'" % cmd)
