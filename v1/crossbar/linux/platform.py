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


import os, hmac, hashlib, base64, sys, crypt, getpass, pwd, \
       time, math, datetime, shutil, subprocess, uuid

from distutils.sysconfig import get_python_lib # for site-packages directory

from twisted.python import log
from twisted.internet import utils
from twisted.application import service

from autobahn.wamp import json_loads, json_dumps

from crossbar.database import Database



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

      self._BOOTED = None
      self._TIMEZONES = None


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      self.isRunning = False


   def getHostId(self):
      ## FIXME
      return str(uuid.UUID(int = uuid.getnode()))


   def getHardwareModel(self):
      try:
         s = os.popen('grep "model name" /proc/cpuinfo').read().strip()
         s = s[s.find(':')+1:].strip()
         model = ' '.join([x.strip() for x in s.split()])
         return model
      except:
         return None


   def getCoreCount(self):
      try:
         s = os.popen('grep "cpu cores" /proc/cpuinfo').read().strip().split()[-1]
         ncpu = int(s)
         return ncpu
      except:
         return None


   def getCoreClock(self):
      try:
         s = os.popen('grep "cpu MHz" /proc/cpuinfo').read().strip().split()[-1]
         mhz = int(round(float(s)))
         return mhz
      except:
         return None


   def getMemory(self):
      try:
         s = os.popen("grep MemTotal /proc/meminfo").read().strip().split()[1]
         return int(math.ceil(float(s)/1024.))
      except:
         return None


   def getPlatformInfo(self):
      return {'os': self.getOsVersion(),
              'appliance': self.getApplianceVersion(),
              'model': self.getHardwareModel(),
              'cores': self.getCoreCount(),
              'clock': self.getCoreClock(),
              'memory': self.getMemory()}


   def getSysctl(self, as_dict = False):
      # this could be done using the procinfo command which gathers
      # information from /proc, but for some reasons, the cmd is
      # unavailable on Amazon Linux
      # http://linux.die.net/man/8/procinfo
      if as_dict:
         return {}
      else:
         return []


   def getBoottime(self):
      """
      Get system boot time as UTC datetime.
      """
      if self._BOOTED is not None:
         return self._BOOTED
      else:
         try:
            s = os.popen("grep btime /proc/stat").read()
            self._BOOTED = datetime.datetime.utcfromtimestamp(float(s.split()[1].strip()))
            return self._BOOTED
         except:
            return None


   def getNetworkConfig(self, ifc = "eth0"):

      ## interface configuration
      mac = ""
      ip = ""
      netmask = ""
      broadcast = ""
      try:
         s = os.popen("/sbin/ifconfig %s" % ifc).read()
         for l in s.splitlines():
            ll = l.split()
            if len(ll) == 5 and ll[3] == 'HWaddr':
               mac = ll[4].strip()
            if len(ll) == 4 and ll[0] == 'inet':
               ip = ll[1].split(':')[1]
               broadcast = ll[2].split(':')[1]
               netmask = ll[3].split(':')[1]
      except:
         pass

      ## default router (gateway)
      try:
         s = os.popen("/bin/netstat -rn | /bin/grep UG").read()
         default_router = s.split()[1]
      except:
         default_router = ""

      ## nameserver
      try:
         s = os.popen("/bin/grep nameserver /etc/resolv.conf").read()
         nameserver = s.splitlines()[0].split()[1]
      except:
         nameserver = ""

      ## hostname
      hostname = os.popen("/bin/hostname").read().strip()

      return {'mac': mac, 'ip': ip, 'netmask': netmask, 'broadcast': broadcast, 'default_router': default_router, 'hostname': hostname, 'nameserver': nameserver}


   def getSystime(self):
      s = os.popen("/bin/date").read()
      return s.strip()


   def getUptime(self):
      s = os.popen("uptime").read()
      i1 = s.find("up")
      i2 = s.find(",", i1)
      return s[i1+2:i2].strip()


   def getOsVersion(self):
      s = os.popen("uname -sr").read()
      return s.strip()


   def getApplianceVersion(self):
      try:
         o = json_loads(open("/etc/appliance.json").read())
         return o["image"]
      except:
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
      s = os.popen("dmesg").read().splitlines()
      return [x.strip() for x in s]


   def getIfconfig(self):
      s = os.popen("ifconfig -a").read().splitlines()
      return [x.strip() for x in s]


   def getPkgInfo(self):
      s = os.popen("yum list installed").read()
      return [x.split() for x in s.splitlines()]


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
         ## for restarting, we just stop the reactor, exit and rely on being
         ## automatically restarted. this is most robust/clean way!
         self.reactor.stop()
         sys.exit(0)
      elif cmd == "update":
         #cmd = '/home/ec2-user/app/bin/easy_install'
         cmd = os.path.join(os.path.dirname(sys.executable), 'easy_install')
         args = ['-H', Database.CROSSBAR_UPDATE_HOST, '-U', '-v', '-f', Database.CROSSBAR_UPDATE_URL, 'crossbar']
         d = utils.getProcessOutput(cmd, args, errortoo = True)
         def logAndReturn(r):
            log.msg(r)
            return r
         d.addBoth(logAndReturn)
         return d
      else:
         raise Exception("ApplianceControl: skipping unknown command '%s'" % cmd)
