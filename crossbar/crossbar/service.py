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


import os, datetime, sys, time

import OpenSSL
import twisted

from twisted.python import log, usage
from twisted.application.service import MultiService

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

   def __init__(self, logger, cbdata, webdata = None, debug = False, isExe = False):
      MultiService.__init__(self)
      self.logger = logger
      self.cbdata = cbdata
      self.webdata = webdata
      self.debug = debug
      self.isExe = isExe


   def startService(self):
      """
      Main entry point to startup the Crossbar.io service.
      """
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

      ## this is here, since it triggers a reactor import
      from crossbar.netservice.ftpserver import FtpService

      cfg = None
      dbpool = None
      services = {}

      ## Master Service and logger
      ##
      services["master"] = self
      services["logger"] = self.logger

      ## remember service start time
      ##
      self.started = datetime.datetime.utcnow()

      ## make sure we have full absolute path to data dir
      ##
      self.cbdata = os.path.abspath(self.cbdata)

      ## initialize database
      ##
      db = Database(services)
      #db.setName("database")
      #db.setServiceParent(self)
      services["database"] = db
      db.startService()

      cfg = db.getConfig(includeTls = True)
      dbpool = db.createPool()

      ## Log OpenSSL info
      ##
      log.msg("Using pyOpenSSL %s on OpenSSL %s" % (OpenSSL.__version__, OpenSSL.SSL.SSLeay_version(OpenSSL.SSL.SSLEAY_VERSION)))

      ## Generate DH param set (primes ..)
      ##
      ## http://linux.die.net/man/3/ssl_ctx_set_tmp_dh
      ## http://linux.die.net/man/1/dhparam
      ##
      self.dhParamFilename = os.path.join(self.cbdata, 'dh_param.pem')
      if not os.path.exists(self.dhParamFilename):
         os.system("openssl dhparam -out %s -2 1024" % self.dhParamFilename)
         log.msg("Generated DH param file %s" % self.dhParamFilename)
      else:
         log.msg("Using existing DH param file %s" % self.dhParamFilename)

      ## License options
      ##
      self.licenseOptions = db.getLicenseOptions()

      ## Installed options
      ##
      self.installedOptions = db.getInstalledOptions()

      if self.webdata is None:
         self.webdata = os.path.join(self.cbdata, db.getConfig('web-dir'))
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
