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
      try:
         s = open("/etc/hostid").read()
         return s.strip()
      except:
         return str(uuid.UUID(int = uuid.getnode()))


   def getHardwareModel(self):
      try:
         s = os.popen("sysctl hw.model").read()
         model = ' '.join(s.strip().split()[1:])
         return model
      except:
         return None


   def getCoreCount(self):
      try:
         s = os.popen("sysctl hw.ncpu").read().split()[1]
         ncpu = int(s)
         return ncpu
      except:
         return None


   def getCoreClock(self):
      try:
         s = os.popen("sysctl hw.clockrate").read().split()[1]
         mhz = int(s)
         return mhz
      except:
         return None


   def getMemory(self):
      try:
         s = os.popen("sysctl hw.realmem").read().strip().split()[1]
         return int(math.ceil(float(s)/1024./1024.))
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
      try:
         s = os.popen("sysctl -a").read().splitlines()
         if as_dict:
            r = {}
            for x in s:
               ss = x.strip()
               if ss != "":
                  i = ss.find(':')
                  if i >= 0:
                     key = ss[:i]
                     val = ss[i+1:].strip()
                     r[key] = val
            return r
         else:
            return [x.strip() for x in s]
      except:
         return None



   def getBoottime(self):
      """
      Get system boot time as UTC datetime.
      """
      if self._BOOTED is not None:
         return self._BOOTED
      else:
         try:
            s = os.popen("sysctl kern.boottime").read()
            i1 = s.find("sec")
            i2 = s.find(",", i1)
            s2 = s[i1:i2]
            i3 = s2.find("=")
            s3 = s2[i3+1:].strip()
            bt = int(s3)
            self._BOOTED = datetime.datetime.utcfromtimestamp(bt)
            return self._BOOTED
         except:
            return None


   def getNetworkConfig(self, ifc = "em0"):

      mac = ""
      ip = ""
      netmask = ""
      broadcast = ""
      default_router = ""
      nameserver = ""

      ## interface configuration
      try:
         s = os.popen("/sbin/ifconfig %s" % ifc).read()
         for l in s.replace('\t', '').splitlines():
            if l[0:5] == "ether":
               mac = l.split(' ')[1]
            if l[0:4] == 'inet':
               p = l.split(' ')
               ip = p[1]
               nm = p[3][2:]
               netmask = "%d.%d.%d.%d" % (int(nm[0:2], 16), int(nm[2:4], 16), int(nm[4:6], 16), int(nm[6:8], 16))
               broadcast = p[5]
      except:
         mac = ""
         ip = ""
         netmask = ""
         broadcast = ""

      ## default router (gateway)
      try:
         s = os.popen("/usr/bin/netstat -rn | /usr/bin/grep default").read()
         default_router = s.split()[1]
      except:
         default_router = ""

      ## nameserver
      try:
         s = os.popen("/usr/bin/grep nameserver /etc/resolv.conf").read()
         nameserver = s.splitlines()[0].split()[1]
      except:
         nameserver = ""

      ## hostname
      hostname = os.popen("hostname").read().strip()

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
         o = json_load(open("/etc/appliance.json"))
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
      s = os.popen("dmesg -a").read().splitlines()
      return [x.strip() for x in s]


   def getIfconfig(self):
      s = os.popen("ifconfig -a").read().splitlines()
      return [x.strip() for x in s]


   def getPkgInfo(self):
      s = os.popen("pkg_info").read()
      return [x.split()[0] for x in s.splitlines()]


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
         cmd = '/home/crossbar/app/bin/easy_install'
         args = ['-H', Database.CROSSBAR_UPDATE_HOST, '-U', '-v', '-f', Database.CROSSBAR_UPDATE_URL, 'crossbar']
         d = utils.getProcessOutput(cmd, args, errortoo = True)
         def logAndReturn(r):
            log.msg(r)
            return r
         d.addBoth(logAndReturn)
         return d
      else:
         raise Exception("ApplianceControl: skipping unknown command '%s'" % cmd)


   ############################################################################
   ## END OF COMMON INTERFACE!

   def getTimezones(self):
      if self._TIMEZONES is not None:
         return self._TIMEZONES
      else:
         tzr = open("/usr/share/zoneinfo/zone.tab").read().splitlines()
         tz = []
         for t in tzr:
            if len(t) > 0 and t[0] != '#':
               tt = t.split()
               tz.append(tt[2])
         tz = sorted(tz)
         self._TIMEZONES = tz
         return tz


   def getTimeInTimezone(self, tz = None):
      if tz is not None and tz not in self.getTimezones():
         return None
      else:
         if tz is None:
            s1 = os.popen("date").read()
            s2 = os.popen("date '+%Z %z'").read().split()
         else:
            s1 = os.popen("TZ=%s date" % tz).read()
            s2 = os.popen("TZ=%s date '+%%Z %%z'" % tz).read().split()
         return (s1.strip(), s2[0].strip(), s2[1].strip())


   def setTimezone(self, tz):
      if tz in self.getTimezones():
         src = os.path.join("/usr/share/zoneinfo", tz)
         dst = "/etc/localtime"
         if os.path.isfile(src):
            try:
               shutil.copy(src, dst)
               return True
            except:
               pass
      return False


   def login(self, username, cleartext):
      try:
         cryptedpasswd = pwd.getpwnam(username)[1]
      except:
         return -2
      if cryptedpasswd:
         if cryptedpasswd == 'x' or cryptedpasswd == '*':
            return -3 # currently no support for shadow passwords
         if crypt.crypt(cleartext, cryptedpasswd) == cryptedpasswd:
            return 0 # ok, correct password
         else:
            return -1 # wrong password
      else:
         return 0 # no password for user
