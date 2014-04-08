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


import types

from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

from crossbar.adminwebmodule.uris import *


class ExtDirectRemotes:
   """
   Ext.Direct Remotes model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def checkExtDirectRemotePermSpec(self, spec, specDelta, errs):
      return 0


   def _createExtDirectRemote(self, txn, spec):

      attrs = {"rpc-base-uri": (True, [str, unicode], 0, URI_MAXLEN),
               "router-url": (True, [str, unicode], 0, URI_MAXLEN),
               "api-url": (True, [str, unicode], 0, URI_MAXLEN),
               "api-object": (True, [str, unicode], 0, 100),
               "forward-cookies": (True, [bool]),
               "redirect-limit": (True, [int], 0, 10),
               "connection-timeout": (True, [int], 0, 120),
               "request-timeout": (True, [int], 0, 120),
               "max-persistent-connections": (True, [int], 0, 1000),
               "persistent-connection-timeout": (True, [int], 0, 60 * 60),
               "require-appcred-uri": (False, [str, unicode, types.NoneType])}

      errcnt, errs = self.proto.checkDictArg("extdirectremote spec", spec, attrs)

      if not errs["rpc-base-uri"]:
         rpcBaseUri, errs2 = self.proto.validateUri(spec["rpc-base-uri"])
         errs["rpc-base-uri"].extend(errs2)
         errcnt += len(errs2)

      if not errs["router-url"]:
         routerUrl, errs2 = self.proto.validateUri(spec["router-url"])
         errs["router-url"].extend(errs2)
         errcnt += len(errs2)

      if not errs["api-url"]:
         apiUrl, errs2 = self.proto.validateUri(spec["api-url"])
         errs["api-url"].extend(errs2)
         errcnt += len(errs2)

      ## convenience handling in JS
      if not errs["require-appcred-uri"] and spec.has_key("require-appcred-uri"):
         if spec["require-appcred-uri"] == "null" or spec["require-appcred-uri"] == "":
            spec["require-appcred-uri"] = None

      appcred_id = None
      appcred_uri = None
      if spec.has_key("require-appcred-uri") and spec["require-appcred-uri"] is not None and spec["require-appcred-uri"].strip() != "":
         appcred_uri = self.proto.resolveOrPass(spec["require-appcred-uri"].strip())
         appcred_id = self.proto.uriToId(appcred_uri)
         txn.execute("SELECT created FROM appcredential WHERE id = ?", [appcred_id])
         if txn.fetchone() is None:
            errs["require-appcred-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No application credentials with URI %s" % appcred_uri))

      errcnt += self.checkExtDirectRemotePermSpec({}, spec, errs)

      self.proto.raiseDictArgException(errs)

      id = newid()
      extdirectremote_uri = URI_EXTDIRECTREMOTE + id
      now = utcnow()

      txn.execute("INSERT INTO extdirectremote (id, created, require_appcred_id, rpc_base_uri, router_url, api_url, api_object, forward_cookies, redirect_limit, connection_timeout, request_timeout, max_persistent_conns, persistent_conn_timeout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       [id,
                                        now,
                                        appcred_id,
                                        rpcBaseUri,
                                        routerUrl,
                                        apiUrl,
                                        spec["api-object"],
                                        spec["forward-cookies"],
                                        int(spec["redirect-limit"]),
                                        int(spec["connection-timeout"]),
                                        int(spec["request-timeout"]),
                                        int(spec["max-persistent-connections"]),
                                        int(spec["persistent-connection-timeout"])
                                        ])

      services = self.proto.factory.services
      if services.has_key("extdirectremoter"):
         services["extdirectremoter"].recache(txn)

      extdirectremote = {"uri": extdirectremote_uri,
                         "require-appcred-uri": appcred_uri,
                         "rpc-base-uri": rpcBaseUri,
                         "router-url": routerUrl,
                         "api-url": apiUrl,
                         "api-object": spec["api-object"],
                         "forward-cookies": spec["forward-cookies"],
                         "redirect-limit": int(spec["redirect-limit"]),
                         "connection-timeout": int(spec["connection-timeout"]),
                         "request-timeout": int(spec["request-timeout"]),
                         "max-persistent-connections": int(spec["max-persistent-connections"]),
                         "persistent-connection-timeout": int(spec["persistent-connection-timeout"])}

      self.proto.dispatch(URI_EVENT + "on-extdirectremote-created", extdirectremote, [self.proto])

      extdirectremote["uri"] = self.proto.shrink(extdirectremote_uri)
      if extdirectremote["require-appcred-uri"] is not None:
         extdirectremote["require-appcred-uri"] = self.proto.shrink(appcred_uri)
      return extdirectremote


   @exportRpc("create-extdirectremote")
   def createExtDirectRemote(self, spec):
      return self.proto.dbpool.runInteraction(self._createExtDirectRemote, spec)


   def _modifyExtDirectRemote(self, txn, extDirectUri, specDelta):

      if type(extDirectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument extDirectUri, but got %s" % str(type(extDirectUri)))

      attrs = {"rpc-base-uri": (False, [str, unicode], 0, URI_MAXLEN),
               "router-url": (False, [str, unicode], 0, URI_MAXLEN),
               "api-url": (False, [str, unicode], 0, URI_MAXLEN),
               "api-object": (False, [str, unicode], 0, 100),
               "forward-cookies": (False, [bool]),
               "redirect-limit": (False, [int], 0, 10),
               "connection-timeout": (False, [int], 0, 120),
               "request-timeout": (False, [int], 0, 120),
               "max-persistent-connections": (False, [int], 0, 1000),
               "persistent-connection-timeout": (False, [int], 0, 60 * 60),
               "require-appcred-uri": (False, [str, unicode, types.NoneType])}

      errcnt, errs = self.proto.checkDictArg("extdirectremote delta spec", specDelta, attrs)

      if not errs["rpc-base-uri"] and specDelta.has_key("rpc-base-uri"):
         rpcBaseUri, errs2 = self.proto.validateUri(specDelta["rpc-base-uri"])
         errs["rpc-base-uri"].extend(errs2)
         errcnt += len(errs2)

      if not errs["router-url"] and specDelta.has_key("router-url"):
         routerUrl, errs2 = self.proto.validateUri(specDelta["router-url"])
         errs["router-url"].extend(errs2)
         errcnt += len(errs2)

      if not errs["api-url"] and specDelta.has_key("api-url"):
         apiUrl, errs2 = self.proto.validateUri(specDelta["api-url"])
         errs["api-url"].extend(errs2)
         errcnt += len(errs2)

      ## convenience handling in JS
      if not errs["require-appcred-uri"] and specDelta.has_key("require-appcred-uri"):
         if specDelta["require-appcred-uri"] == "null" or specDelta["require-appcred-uri"] == "":
            specDelta["require-appcred-uri"] = None

      appcred_id = None
      appcred_uri = None
      if specDelta.has_key("require-appcred-uri") and specDelta["require-appcred-uri"] is not None and specDelta["require-appcred-uri"].strip() != "":
         appcred_uri = self.proto.resolveOrPass(specDelta["require-appcred-uri"].strip())
         appcred_id = self.proto.uriToId(appcred_uri)
         txn.execute("SELECT created FROM appcredential WHERE id = ?", [appcred_id])
         if txn.fetchone() is None:
            errs["require-appcred-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No application credentials with URI %s" % appcred_uri))

      uri = self.proto.resolveOrPass(extDirectUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT require_appcred_id, rpc_base_uri, router_url, api_url, api_object, forward_cookies, redirect_limit, connection_timeout, request_timeout, max_persistent_conns, persistent_conn_timeout FROM extdirectremote WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         spec = {}
         spec["require-appcred-uri"] = self.proto.shrink(URI_APPCRED + res[0]) if res[0] else None
         spec["rpc-base-uri"] = res[1]
         spec["router-url"] = res[2]
         spec["api-url"] = res[3]
         spec["api-object"] = res[4]
         spec["forward-cookies"] = res[5] != 0
         spec["redirect-limit"] = res[6]
         spec["connection-timeout"] = res[7]
         spec["request-timeout"] = res[8]
         spec["max-persistent-connections"] = res[9]
         spec["persistent-connection-timeout"] = res[10]

         errcnt += self.checkExtDirectRemotePermSpec(spec, specDelta, errs)

         self.proto.raiseDictArgException(errs)

         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         if specDelta.has_key("require-appcred-uri"):
            if appcred_id != res[0]:
               delta["require-appcred-uri"] = appcred_uri
               sql += ", require_appcred_id = ?"
               sql_vars.append(appcred_id)

         if specDelta.has_key("rpc-base-uri"):
            newval = rpcBaseUri
            if newval != "" and newval != res[1]:
               delta["rpc-base-uri"] = newval
               sql += ", rpc_base_uri = ?"
               sql_vars.append(newval)

         if specDelta.has_key("router-url"):
            newval = routerUrl
            if newval != "" and newval != res[2]:
               delta["router-url"] = newval
               sql += ", router_url = ?"
               sql_vars.append(newval)

         if specDelta.has_key("api-url"):
            newval = apiUrl
            if newval != "" and newval != res[3]:
               delta["api-url"] = newval
               sql += ", api_url = ?"
               sql_vars.append(newval)

         if specDelta.has_key("api-object"):
            newval = specDelta["api-object"]
            if newval != "" and newval != res[4]:
               delta["api-object"] = newval
               sql += ", api_object = ?"
               sql_vars.append(newval)

         if specDelta.has_key("forward-cookies"):
            newval = specDelta["forward-cookies"]
            if newval != (res[5] != 0):
               delta["forward-cookies"] = newval
               sql += ", forward_cookies = ?"
               sql_vars.append(newval)

         if specDelta.has_key("redirect-limit"):
            newval = specDelta["redirect-limit"]
            if newval != res[6]:
               delta["redirect-limit"] = newval
               sql += ", redirect_limit = ?"
               sql_vars.append(newval)

         if specDelta.has_key("connection-timeout"):
            newval = specDelta["connection-timeout"]
            if newval != res[7]:
               delta["connection-timeout"] = newval
               sql += ", connection_timeout = ?"
               sql_vars.append(newval)

         if specDelta.has_key("request-timeout"):
            newval = specDelta["request-timeout"]
            if newval != res[8]:
               delta["request-timeout"] = newval
               sql += ", request_timeout = ?"
               sql_vars.append(newval)

         if specDelta.has_key("max-persistent-connections"):
            newval = specDelta["max-persistent-connections"]
            if newval != res[9]:
               delta["max-persistent-connections"] = newval
               sql += ", max_persistent_conns = ?"
               sql_vars.append(newval)

         if specDelta.has_key("persistent-connection-timeout"):
            newval = specDelta["persistent-connection-timeout"]
            if newval != res[10]:
               delta["persistent-connection-timeout"] = newval
               sql += ", persistent_conn_timeout = ?"
               sql_vars.append(newval)

         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE extdirectremote SET %s WHERE id = ?" % sql, sql_vars)

            services = self.proto.factory.services
            if services.has_key("extdirectremoter"):
               services["extdirectremoter"].recache(txn)

            self.proto.dispatch(URI_EVENT + "on-extdirectremote-modified", delta, [self.proto])

            delta["uri"] = self.proto.shrink(uri)
            if delta.has_key("require-appcred-uri") and delta["require-appcred-uri"] is not None:
               delta["require-appcred-uri"] = self.proto.shrink(appcred_uri)
            return delta
         else:
            return {}
      else:
         raise Exception(URI_ERROR + "no-such-object", "No Ext.Direct remote with URI %s" % uri)


   @exportRpc("modify-extdirectremote")
   def modifyExtDirectRemote(self, extDirectUri, specDelta):
      return self.proto.dbpool.runInteraction(self._modifyExtDirectRemote, extDirectUri, specDelta)


   def _deleteExtDirectRemote(self, txn, extDirectUri):

      if type(extDirectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument extDirectUri, but got %s" % str(type(extDirectUri)))

      uri = self.proto.resolveOrPass(extDirectUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT created FROM extdirectremote WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         txn.execute("DELETE FROM extdirectremote WHERE id = ?", [id])

         services = self.proto.factory.services
         if services.has_key("extdirectremoter"):
            services["extdirectremoter"].recache(txn)

         self.proto.dispatch(URI_EVENT + "on-extdirectremote-deleted", uri, [self.proto])

         return self.proto.shrink(uri)
      else:
         raise Exception(URI_ERROR + "no-such-object", "No Ext.Direct remote with URI %s" % uri)


   @exportRpc("delete-extdirectremote")
   def deleteExtDirectRemote(self, extDirectUri):
      """
      Delete an Ext.Direct remote.
      """
      return self.proto.dbpool.runInteraction(self._deleteExtDirectRemote, extDirectUri)


   @exportRpc("get-extdirectremotes")
   def getExtDirectRemotes(self):
      """
      Return Ext.Direct remotes list.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, require_appcred_id, rpc_base_uri, router_url, api_url, api_object, forward_cookies, redirect_limit, connection_timeout, request_timeout, max_persistent_conns, persistent_conn_timeout FROM extdirectremote ORDER BY require_appcred_id, rpc_base_uri, created")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_EXTDIRECTREMOTE + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "require-appcred-uri": self.proto.shrink(URI_APPCRED + r[3]) if r[3] else None,
                                  "rpc-base-uri": r[4],
                                  "router-url": r[5],
                                  "api-url": r[6],
                                  "api-object": r[7],
                                  "forward-cookies": r[8] != 0,
                                  "redirect-limit": r[9],
                                  "connection-timeout": r[10],
                                  "request-timeout": r[11],
                                  "max-persistent-connections": r[12],
                                  "persistent-connection-timeout": r[13]} for r in res])
      return d


   def _getExtDirectApiSorted(self, res):
      r = []
      for k in sorted(res.keys()):
         rr = res[k]
         r.append((k, rr[1], rr[2], rr[3]))
      return r


   @exportRpc("query-extdirectapi")
   def queryExtDirectApi(self, extDirectUri):

      if type(extDirectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument extDirectUri, but got %s" % str(type(extDirectUri)))

      uri = self.proto.resolveOrPass(extDirectUri)
      id = self.proto.uriToId(uri)
      d = self.proto.factory.services["extdirectremoter"].queryApi(id)
      if d:
         d.addCallback(self._getExtDirectApiSorted)
         return d
      else:
         raise Exception(URI_ERROR + "no-such-object", "No Ext.Direct remote with URI %s" % uri)


   @exportRpc("query-extdirectapi-by-appkey")
   def queryExtDirectApiByAppKey(self, appkey):
      return self.proto.factory.services["extdirectremoter"].getRemotes(appkey)
