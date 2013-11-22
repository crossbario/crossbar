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


import json, re

from twisted.internet import defer
from twisted.python.failure import Failure
from twisted.python import log

import autobahn
from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

import crossbar
from crossbar.adminwebmodule.uris import *
from crossbar.dbexport import DbExportProtocol


class ServiceControl:
   """
   Service control model.
   """

   DBEXPORT_PASSWORD_PATTERN = "^[a-z0-9_\-]{3,10}$"

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   @exportRpc("scratch-webdir")
   def scratchWebDir(self, init = True):
      return self.proto.factory.services["database"].scratchWebDir(init = init)


   @exportRpc("get-log")
   def getLog(self, limit = None):
      return self.proto.factory.services["logger"].getLog(limit)


   @exportRpc("scratch-database")
   def scratchDatabase(self, restart = True):
      self.proto.factory.services["database"].scratchDatabase()
      if restart:
         self.restartHub()


   @exportRpc("check-for-updates")
   def checkForUpdates(self, forceCheckNow = False):
      """
      Online check for appliance updates. This requires an outgoing
      Internet connection from crossbar.io.

      Events:

         on-update-available
      """
      if forceCheckNow:
         ## force new check result
         return self.proto.factory.checkForUpdatesNow()
      else:
         ## return cached check result
         return self.proto.factory.updateAvailable


   @exportRpc("export-database")
   def exportDatabase(self, password = None):
      """
      Export the hub database.
      """
      if password is not None:
         if type(password) not in [str, unicode]:
            raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument password, but got %s" % str(type(password)))
         try:
            password = str(password)
         except:
            raise Exception(URI_ERROR + "illegal-argument", "Password contains non-ASCII characters (%s)" % password)
         else:
            if password.strip() == "":
               password = None
            else:
               pat = re.compile(ServiceControl.DBEXPORT_PASSWORD_PATTERN)
               if not pat.match(password):
                  raise Exception(URI_ERROR + "illegal-argument", "Password %s does not match pattern %s" % (password, AdminWebSocketProtocol.DBEXPORT_PASSWORD_PATTERN))
      d = defer.Deferred()
      cfg = self.proto.factory.services["config"]
      dbfile = self.proto.factory.services["database"].dbfile
      log.msg("Exporting service database from %s ..", dbfile)
      p = DbExportProtocol(d,
                           self.proto.factory.services,
                           str(dbfile),
                           str(cfg.get("database-version")),
                           str(cfg.get("export-dir")),
                           str(cfg.get("export-url")),
                           password = password)
      p.run()
      return d


   @exportRpc("create-diagnostics-file")
   def createDiagnosticsFiles(self):
      """
      Create a diagnostics file which contains non-sensitive database information export
      and log files as ZIP file.
      """
      d = defer.Deferred()
      cfg = self.proto.factory.services["config"]
      dbfile = self.proto.factory.services["database"].dbfile
      p = DbExportProtocol(d,
                           self.proto.factory.services,
                           str(dbfile),
                           str(cfg.get("database-version")),
                           str(cfg.get("export-dir")),
                           str(cfg.get("export-url")),
                           mode = DbExportProtocol.MODE_DIAGNOSTICS,
                           logsdir = str(cfg.get("log-dir")))
      p.run()
      return d


   @exportRpc("restart")
   def restartHub(self):
      """
      Restart all services.
      """
      log.msg("appliance service restart requested via admin console")
      return self.proto.factory.services["platform"].applianceControl("restart")


   @exportRpc("update")
   def updateAppliance(self):
      """
      Update appliance software.
      """
      log.msg("appliance software update requested via admin console")
      res = self.proto.factory.services["platform"].applianceControl("update")
      self.proto.factory.issueRestartRequired()
      return res
