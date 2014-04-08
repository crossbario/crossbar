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


import sqlite3

from twisted.python import log
from twisted.application import service

from autobahn.wamp import json_loads


class Config(service.Service):

   SERVICENAME = "Configuration cache"


   def __init__(self, dbpool, services):
      self.dbpool = dbpool
      self.services = services
      self.isRunning = False

      self._config = self.services["database"].getConfig(includeTls = True)
      return

      ## when instantiated, we do the caching synchronously!
      if True:
         db = sqlite3.connect(self.services["database"].dbfile)
         cur = db.cursor()
         cur.execute("SELECT key, value FROM config ORDER BY key")
         res = cur.fetchall()
         self._cacheConfig(res)
      else:
         self.dbpool.runInteraction(self.recache)


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      self.isRunning = False


   def get(self, key, default = None):
      return self._config.get(key, default)


   def __getitem__(self, key):
      return self._config.get(key, None)


   def _cacheConfig(self, res):
      self._config = {}
      for r in res:
         self._config[r[0]] = json_loads(r[1])
      log.msg("Config._cacheConfig (%d)" % len(self._config))


   def recache(self, txn):
      log.msg("Config.recache")

      txn.execute("SELECT key, value FROM config ORDER BY key")
      self._cacheConfig(txn.fetchall())
