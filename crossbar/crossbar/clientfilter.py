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


import hmac, hashlib, base64, binascii, json

from twisted.python import log
from twisted.application import service
from twisted.enterprise import adbapi

from netaddr.ip import IPAddress, IPNetwork

from autobahn.wamp import WampServerProtocol


class ClientFilterPerm:

   def __init__(self,
                id,
                topicUri,
                matchByPrefix,
                filterExpr,
                allowPublish,
                allowSubscribe):
      self.id = id
      self.topicUri = topicUri
      self.matchByPrefix = matchByPrefix
      self.filterExpr = filterExpr
      self.allowPublish = allowPublish
      self.allowSubscribe = allowSubscribe



class ClientFilter(service.Service):

   SERVICENAME = "Client authentication"


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
      self.dbpool.runInteraction(self.recache)
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      self.isRunning = False


   def getAppSecret(self, appkey):
      """
      Get application secret for application key or None if application key does not exist.
      """
      return self.appcreds.get(appkey, None)


   def getPermissions(self, appkey, extra, skipOnErrs = False):
      """
      Return client permissions by application key.
      """
      ret = []
      if self.perms.has_key(appkey):
         for r in self.perms[appkey]:

            #print r.topicUri, r.allowPublish, r.allowSubscribe, r.filterExpr

            try:
               topic_uri = r.topicUri % extra
            except KeyError, e:
               emsg = "unbound variable in %s (%s)" % (r.topicUri, e)
               if skipOnErrs:
                  log.msg(emsg)
               else:
                  raise Exception(emsg)
            else:

               ## apply filter expression
               ##
               permit = False
               if r.filterExpr is not None and r.filterExpr.strip() != "":

                  try:
                     ## FIXME: make this more secure ..
                     ## => ast.literal_eval (but this does not allow for boolean expressions ..)
                     ##
                     a = eval(r.filterExpr, {'__builtins__': []}, extra)
                  except Exception, e:
                     emsg = "filter expression invalid or unbound variables (%s)" % e
                     if skipOnErrs:
                        log.msg(emsg)
                     else:
                        raise Exception(emsg)

                  if type(a) == bool:
                     permit = a
                  else:
                     emsg = "filter expression returned non-boolean type (%s)" % type(a)
                     if skipOnErrs:
                        log.msg(emsg)
                     else:
                        raise Exception(emsg)
               else:
                  permit = True

               ## append topic if not filtered
               ##
               if permit:
                  ret.append({"uri": topic_uri,
                              "prefix": r.matchByPrefix,
                              "pub": r.allowPublish,
                              "sub": r.allowSubscribe})
      return ret


   def _cachePerms(self, res):
      self.perms = {}
      n = 0
      for r in res:
         if not self.perms.has_key(r[0]):
            self.perms[r[0]] = []
         perm = ClientFilterPerm(id = r[1],
                                 topicUri = r[2],
                                 matchByPrefix = r[3] != 0,
                                 filterExpr = r[4],
                                 allowPublish = r[5] != 0,
                                 allowSubscribe = r[6] != 0)
         self.perms[r[0]].append(perm)
         n += 1
      log.msg("ClientFilter._cachePerms (%d)" % n)


   def _cacheAppCreds(self, res):
      self.appcreds = {}
      for r in res:
         self.appcreds[r[0]] = str(r[1])
      log.msg("ClientFilter._cacheAppCreds (%d)" % len(self.appcreds))


   def recache(self, txn):
      log.msg("ClientFilter.recache")

      txn.execute("SELECT a.key, r.id, r.topic_uri, r.match_by_prefix, r.filter_expr, r.allow_publish, r.allow_subscribe FROM clientperm r LEFT OUTER JOIN appcredential a ON r.require_appcred_id = a.id ORDER BY a.key ASC, LENGTH(r.topic_uri) ASC, r.topic_uri ASC")
      self._cachePerms(txn.fetchall())

      txn.execute("SELECT key, secret FROM appcredential ORDER BY key")
      self._cacheAppCreds(txn.fetchall())
