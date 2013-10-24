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


## We need to monkey patch in the new Python IO
## because of http://www.freebsd.org/cgi/query-pr.cgi?pr=148581
## when using the kqueue reactor and twistd.
##
import io, __builtin__
__builtin__.open = io.open

import os, datetime, sys, time

import OpenSSL
import twisted

from twisted.python import log, usage
from twisted.internet import reactor
from twisted.application import service
from twisted.application.service import Application, MultiService

from crossbar.logger import Logger
from crossbar.database import Database
from crossbar.config import Config

from crossbar.clientfilter import ClientFilter

from crossbar.bridge.extdirectremoter import ExtDirectRemoter

from crossbar.bridge.restpusher import RestPusher
from crossbar.bridge.restremoter import RestRemoter

from crossbar.bridge.hanaremoter import HanaRemoter
from crossbar.bridge.hanapusher import HanaPusher

from crossbar.bridge.pgremoter import PgRemoter
from crossbar.bridge.pgpusher import PgPusher

from crossbar.bridge.oraremoter import OraRemoter
from crossbar.bridge.orapusher import OraPusher

from crossbar.netservice.hubwebresource import HubWebService
from crossbar.netservice.hubwebsocket import HubWebSocketService
from crossbar.netservice.adminwebresource import AdminWebService
from crossbar.netservice.adminwebsocket import AdminWebSocketService

from crossbar.netservice.echowebsocket import EchoWebSocketService
from crossbar.netservice.flashpolicy import FlashPolicyService
from crossbar.netservice.ftpserver import FtpService

from crossbar.platform import PlatformService
from crossbar.platform import NetstatService
from crossbar.platform import VmstatService


class CrossbarService(MultiService):
   """
   Root service for Crossbar.io.

   Some notes on implementing twistd plugins:

      http://chrismiles.livejournal.com/23399.html
      https://bitbucket.org/jerub/twisted-plugin-example/src
      http://twistedmatrix.com/documents/current/core/howto/tap.html
      http://twistedmatrix.com/documents/current/core/howto/plugin.html
   """

   def startService(self):
      try:
         s = self._startService()
         return s
      except Exception, e:
         print
         es = " ERROR "
         l1 = (80 - len(es)) / 2
         l2 = 80 - l1 - len(es)
         print "*" * l1 + es  + "*" * l2
         print
         if isinstance(e, twisted.internet.error.CannotListenError):
            print "Could not listen on port %d. Is there another program listening on the port already?" % e.port
            print
            print "[%s]" % e.socketError
         else:
            print e
         print
         print "*" * 80
         print

         ## delay exit ..
         d = 5
         print "Exciting in %d seconds .." % d
         time.sleep(d)

         raise e

   def _startService(self):

      cfg = None
      dbpool = None
      services = {}

      ## Master Service and logger
      ##
      services["master"] = self
      services["logger"] = self.logger

      ## Log OpenSSL info
      ##
      log.msg("Using pyOpenSSL %s on OpenSSL %s") % (OpenSSL.__version__, OpenSSL.SSL.SSLeay_version(OpenSSL.SSL.SSLEAY_VERSION))

      ## remember service start time
      ##
      self.started = datetime.datetime.utcnow()

      ## make sure we have full absolute path to data dir
      ##
      self.appdata = os.path.abspath(self.appdata)

      ## initialize database
      ##
      db = Database(services)
      #db.setName("database")
      #db.setServiceParent(self)
      services["database"] = db
      db.startService()

      cfg = db.getConfig(includeTls = True)
      dbpool = db.createPool()

      ## License options
      ##
      self.licenseOptions = db.getLicenseOptions()

      ## Installed options
      ##
      self.installedOptions = db.getInstalledOptions()

      if self.webdata is None:
         self.webdata = os.path.join(self.appdata, db.getConfig('web-dir'))
         print "Crossbar.io Web directory unspecified - using %s." % self.webdata

      ## Print out core information to log
      ##
      log.msg("")
      log.msg('*' * 80)
      log.msg("")
      log.msg("  You can access the management console of crossbar.io at")
      log.msg("")
      log.msg("  >>>>>>>>>  %s" % db.getWebAdminURL())
      log.msg("")
      log.msg("  from your browser (Google Chrome, Mozilla Firefox or Microsoft IE10+)")
      log.msg("")
      log.msg("")
      log.msg("  You can access the static Web content served by crossbar.io at")
      log.msg("")
      log.msg("  >>>>>>>>>  %s" % self.webdata)
      log.msg("")
      log.msg("  on the filesystem of your instance.")
      log.msg("")
      log.msg('*' * 80)
      log.msg("")

      ## Setup services hierarchy
      ##
      SERVICES = [(None, None, [("config", Config)]),
                  (None, None, [("platform", PlatformService)]),
                  (None, None, [("netstat", NetstatService)]),
                  (None, None, [("vmstat", VmstatService)]),
                  (None, None, [("appws", HubWebSocketService)]),
                  (None, None, [("echows", EchoWebSocketService)]),
                  (None, None, [("flashpolicy", FlashPolicyService)]),
                  (None, None, [("ftp", FtpService)]),
                  (None, None, [("clientfilter", ClientFilter)]),
                  (None, None, [("hubweb", HubWebService)]),
                  (None, None, [("adminweb", AdminWebService)]),
                  (None, None, [("adminws", AdminWebSocketService)]),
                  (None, "rest", [("restpusher", RestPusher), ("restremoter", RestRemoter)]),
                  (None, "extdirect", [("extdirectremoter", ExtDirectRemoter)]),
                  ("postgresql", "postgresql", [("pgpusher", PgPusher), ("pgremoter", PgRemoter)]),
                  ("oracle", "oracle", [("orapusher", OraPusher), ("oraremoter", OraRemoter)]),
                  ("hana", "hana", [("hanapusher", HanaPusher), ("hanaremoter", HanaRemoter)])
                  ]

      for sdef in SERVICES:

         installedOptionName, licenseOptionName, serviceList = sdef
         installed = installedOptionName is None or self.installedOptions[installedOptionName]
         licensed = licenseOptionName is None or self.licenseOptions[licenseOptionName]

         for s in serviceList:
            if installed:
               if licensed:
                  enabled = cfg.get("service-enable-%s" % s[0], True)
                  if enabled:
                     svc = s[1](dbpool, services)
                     svc.setName(s[0])
                     svc.setServiceParent(self)
                     services[s[0]] = svc
                  else:
                     log.msg("Skipping %s (service disabled)!" % s[1].SERVICENAME)
               else:
                  log.msg("Skipping %s (service not licensed)!" % s[1].SERVICENAME)
            else:
               log.msg("Skipping %s (service not installed)!" % s[1].SERVICENAME)


      ## Start whole service hierarchy
      ##
      MultiService.startService(self)


LICENSE_ACTIVATION_SERVER_DEFAULT_URI = "http://store.tavendo.de/api/webmq/activationrequest"


class Options(usage.Options):
   """
   Crossbar.io command line options when run from twistd as plugin.
   """
   longdesc = """Crossbar.io - Multi-protocol application router"""

   optFlags = [['debug', 'd', 'Emit debug messages']]
   optParameters = [["appdata", "a", None, "Crossbar.io service data directory (overrides environment variable CROSSBAR_DATA)."],
                    ["webdata", "w", None, "Crossbar Web directory (overrides default CROSSBAR_DATA/web)."],
                    ["licenseserver", "l", None, "Crossbar.io License Activation Server URI [default: %s]." % LICENSE_ACTIVATION_SERVER_DEFAULT_URI]]

   def postOptions(self):
      if not self['appdata']:
         if os.environ.has_key("CROSSBAR_DATA"):
            self['appdata'] = os.environ["CROSSBAR_DATA"]
            print "Crossbar.io service data directory %s set from environment variable CROSSBAR_DATA." % self['appdata']
         else:
            self['appdata'] = os.path.join(os.getcwd(), 'appdata')
            print "Crossbar.io service directory unspecified - using %s." % self['appdata']
      else:
         print "Crossbar.io application data directory %s set via command line option." % self['appdata']

      if not self['webdata']:
         if os.environ.has_key("CROSSBAR_WEB"):
            self['webdata'] = os.environ["CROSSBAR_WEB"]
            print "Crossbar.io Web directory %s set from environment variable CROSSBAR_WEB." % self['webdata']
      else:
         print "Crossbar.io Web directory %s set via command line option." % self['webdata']

      if not self['licenseserver']:
         self['licenseserver'] = LICENSE_ACTIVATION_SERVER_DEFAULT_URI


def makeService(options):
   """
   Main entry point into Crossbar.io application. This is called from the Twisted
   plugin system to instantiate "crossbar".
   """

   ## install our log observer before anything else is done
   logger = Logger()
   twisted.python.log.addObserver(logger)

   ## import reactor here first and set some thread pool size
   from twisted.internet import reactor
   reactor.suggestThreadPoolSize(30)

   ## now actually create our top service and set the logger
   service = CrossbarService()
   service.logger = logger

   ## store user options set
   service.appdata = options['appdata']
   service.webdata = options['webdata']
   service.debug = True if options['debug'] else False
   service.licenseserver = options['licenseserver']
   service.isExe = False # will be set to true iff Crossbar is running from self-contained EXE

   return service


def runPlugin():
   ## not working .. quite!
   ## http://stackoverflow.com/a/10194756/884770
   ##
   import sys

   from twisted.application import app
   from twisted.scripts.twistd import runApp, ServerOptions

   from twisted.application.service import ServiceMaker

   serviceMaker = ServiceMaker('crossbar',
                               'crossbar.main',
                               'crossbar.io multi-protocol application router',
                               'crossbar')

   plug = serviceMaker


   class MyServerOptions(ServerOptions):
      """
      See twisted.application.app.ServerOptions.subCommands().
      Override to specify a single plugin subcommand and load the plugin
      explictly.
      """
      def subCommands(self):
         self.loadedPlugins = {plug.tapname:plug}
         yield (plug.tapname,
                None,
                # Avoid resolving the options attribute right away, in case
                # it's a property with a non-trivial getter (eg, one which
                # imports modules).
                lambda plug=plug: plug.options(),
                plug.description)

      subCommands = property(subCommands)


   def run():
      """
      Replace twisted.application.app.run()
      To use our ServerOptions.
      """
      app.run(runApp, MyServerOptions)


   sys.argv[1:] = [
      #'--pidfile', '/var/run/myapp.pid',
      #'--logfile', '/var/run/myapp.log',
      plug.tapname] + sys.argv[1:]

   run()


def runDirect(installSignalHandlers = False):
   """
   Start Crossbar.io when running from EXE bundled with Pyinstaller.
   """
   import sys
   from twisted.internet import reactor
   from twisted.python import usage, log

   log.startLogging(sys.stdout)

   o = Options()
   try:
      o.parseOptions()
   except usage.UsageError, errortext:
      print '%s %s' % (sys.argv[0], errortext)
      print 'Try %s --help for usage details' % sys.argv[0]
      sys.exit(1)

   service = makeService(o)
   service.isExe = True # we are running from self-contained EXE
   service.startService()
   reactor.run(installSignalHandlers)


if __name__ == '__main__':
   runDirect(True)
