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


class RestRemotes:
   """
   REST Remotes model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def checkRestRemotePermSpec(self, spec, specDelta, errs):
      ## FIXME: check "payload-format"
      return 0


   def _createRestRemote(self, txn, spec):

      attrs = {"rpc-base-uri": (True, [str, unicode], 0, URI_MAXLEN),
               "rest-base-url": (True, [str, unicode], 0, URI_MAXLEN),
               "payload-format": (True, [str, unicode], ["json"]),
               "forward-cookies": (True, [bool]),
               "redirect-limit": (True, [int], 0, 10),
               "connection-timeout": (True, [int], 0, 120),
               "request-timeout": (True, [int], 0, 120),
               "max-persistent-connections": (True, [int], 0, 1000),
               "persistent-connection-timeout": (True, [int], 0, 60 * 60),
               "require-appcred-uri": (True, [str, unicode, types.NoneType])}

      errcnt, errs = self.proto.checkDictArg("restremote spec", spec, attrs)

      if not errs["rpc-base-uri"]:
         rpcBaseUri, errs2 = self.proto.validateUri(spec["rpc-base-uri"])
         errs["rpc-base-uri"].extend(errs2)
         errcnt += len(errs2)

      if not errs["rest-base-url"]:
         restBaseUrl, errs2 = self.proto.validateUri(spec["rest-base-url"])
         errs["rest-base-url"].extend(errs2)
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

      errcnt += self.checkRestRemotePermSpec({}, spec, errs)

      self.proto.raiseDictArgException(errs)

      id = newid()
      restremote_uri = URI_RESTREMOTE + id
      now = utcnow()

      txn.execute("INSERT INTO restremote (id, created, require_appcred_id, rpc_base_uri, rest_base_url, payload_format, forward_cookies, redirect_limit, connection_timeout, request_timeout, max_persistent_conns, persistent_conn_timeout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       [id,
                                        now,
                                        appcred_id,
                                        rpcBaseUri,
                                        restBaseUrl,
                                        str(spec["payload-format"]),
                                        spec["forward-cookies"],
                                        int(spec["redirect-limit"]),
                                        int(spec["connection-timeout"]),
                                        int(spec["request-timeout"]),
                                        int(spec["max-persistent-connections"]),
                                        int(spec["persistent-connection-timeout"])
                                        ])

      services = self.proto.factory.services
      if services.has_key("restremoter"):
        services["restremoter"].recache(txn)

      restremote = {"uri": restremote_uri,
                    "require-appcred-uri": appcred_uri,
                    "rpc-base-uri": rpcBaseUri,
                    "rest-base-url": restBaseUrl,
                    "payload-format": spec["payload-format"],
                    "forward-cookies": spec["forward-cookies"],
                    "redirect-limit": int(spec["redirect-limit"]),
                    "connection-timeout": int(spec["connection-timeout"]),
                    "request-timeout": int(spec["request-timeout"]),
                    "max-persistent-connections": int(spec["max-persistent-connections"]),
                    "persistent-connection-timeout": int(spec["persistent-connection-timeout"])}

      self.proto.dispatch(URI_EVENT + "on-restremote-created", restremote, [self.proto])

      restremote["uri"] = self.proto.shrink(restremote_uri)
      if restremote["require-appcred-uri"] is not None:
         restremote["require-appcred-uri"] = self.proto.shrink(appcred_uri)
      return restremote


   @exportRpc("create-restremote")
   def createRestRemote(self, spec):
      return self.proto.dbpool.runInteraction(self._createRestRemote, spec)


   def _modifyRestRemote(self, txn, restRemoteUri, specDelta):

      if type(restRemoteUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument restRemoteUri, but got %s" % str(type(restRemoteUri)))

      attrs = {"rpc-base-uri": (False, [str, unicode], 0, URI_MAXLEN),
               "rest-base-url": (False, [str, unicode], 0, URI_MAXLEN),
               "payload-format": (False, [str, unicode], ["json"]),
               "forward-cookies": (False, [bool]),
               "redirect-limit": (False, [int], 0, 10),
               "connection-timeout": (False, [int], 0, 120),
               "request-timeout": (False, [int], 0, 120),
               "max-persistent-connections": (False, [int], 0, 1000),
               "persistent-connection-timeout": (False, [int], 0, 60 * 60),
               "require-appcred-uri": (False, [str, unicode, types.NoneType])}

      errcnt, errs = self.proto.checkDictArg("restremote delta spec", specDelta, attrs)

      if not errs["rpc-base-uri"] and specDelta.has_key("rpc-base-uri"):
         rpcBaseUri, errs2 = self.proto.validateUri(specDelta["rpc-base-uri"])
         errs["rpc-base-uri"].extend(errs2)
         errcnt += len(errs2)

      if not errs["rest-base-url"] and specDelta.has_key("rest-base-url"):
         restBaseUrl, errs2 = self.proto.validateUri(specDelta["rest-base-url"])
         errs["rest-base-url"].extend(errs2)
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

      uri = self.proto.resolveOrPass(restRemoteUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT require_appcred_id, rpc_base_uri, rest_base_url, payload_format, forward_cookies, redirect_limit, connection_timeout, request_timeout, max_persistent_conns, persistent_conn_timeout FROM restremote WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         spec = {}
         spec["require-appcred-uri"] = self.proto.shrink(URI_APPCRED + res[0]) if res[0] else None
         spec["rpc-base-uri"] = res[1]
         spec["rest-base-url"] = res[2]
         spec["payload-format"] = res[3]
         spec["forward-cookies"] = res[4] != 0
         spec["redirect-limit"] = res[5]
         spec["connection-timeout"] = res[6]
         spec["request-timeout"] = res[7]
         spec["max-persistent-connections"] = res[8]
         spec["persistent-connection-timeout"] = res[9]

         errcnt += self.checkRestRemotePermSpec(spec, specDelta, errs)

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

         if specDelta.has_key("rest-base-url"):
            newval = restBaseUrl
            if newval != "" and newval != res[2]:
               delta["rest-base-url"] = newval
               sql += ", rest_base_url = ?"
               sql_vars.append(newval)

         if specDelta.has_key("payload-format"):
            newval = specDelta["payload-format"]
            if newval != "" and newval != res[3]:
               delta["payload-format"] = newval
               sql += ", payload_format = ?"
               sql_vars.append(newval)

         if specDelta.has_key("forward-cookies"):
            newval = specDelta["forward-cookies"]
            if newval != (res[4] != 0):
               delta["forward-cookies"] = newval
               sql += ", forward_cookies = ?"
               sql_vars.append(newval)

         if specDelta.has_key("redirect-limit"):
            newval = specDelta["redirect-limit"]
            if newval != res[5]:
               delta["redirect-limit"] = newval
               sql += ", redirect_limit = ?"
               sql_vars.append(newval)

         if specDelta.has_key("connection-timeout"):
            newval = specDelta["connection-timeout"]
            if newval != res[6]:
               delta["connection-timeout"] = newval
               sql += ", connection_timeout = ?"
               sql_vars.append(newval)

         if specDelta.has_key("request-timeout"):
            newval = specDelta["request-timeout"]
            if newval != res[7]:
               delta["request-timeout"] = newval
               sql += ", request_timeout = ?"
               sql_vars.append(newval)

         if specDelta.has_key("max-persistent-connections"):
            newval = specDelta["max-persistent-connections"]
            if newval != res[8]:
               delta["max-persistent-connections"] = newval
               sql += ", max_persistent_conns = ?"
               sql_vars.append(newval)

         if specDelta.has_key("persistent-connection-timeout"):
            newval = specDelta["persistent-connection-timeout"]
            if newval != res[9]:
               delta["persistent-connection-timeout"] = newval
               sql += ", persistent_conn_timeout = ?"
               sql_vars.append(newval)

         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE restremote SET %s WHERE id = ?" % sql, sql_vars)

            services = self.proto.factory.services
            if services.has_key("restremoter"):
              services["restremoter"].recache(txn)

            self.proto.dispatch(URI_EVENT + "on-restremote-modified", delta, [self.proto])

            delta["uri"] = self.proto.shrink(uri)
            if delta.has_key("require-appcred-uri") and delta["require-appcred-uri"] is not None:
               delta["require-appcred-uri"] = self.proto.shrink(appcred_uri)
            return delta
         else:
            return {}
      else:
         raise Exception(URI_ERROR + "no-such-object", "No REST remote with URI %s" % uri)


   @exportRpc("modify-restremote")
   def modifyRestRemote(self, restRemoteUri, specDelta):
      return self.proto.dbpool.runInteraction(self._modifyRestRemote, restRemoteUri, specDelta)


   def _deleteRestRemote(self, txn, restRemoteUri):

      if type(restRemoteUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument restRemoteUri, but got %s" % str(type(restRemoteUri)))

      uri = self.proto.resolveOrPass(restRemoteUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT created FROM restremote WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         txn.execute("DELETE FROM restremote WHERE id = ?", [id])

         services = self.proto.factory.services
         if services.has_key("restremoter"):
           services["restremoter"].recache(txn)

         self.proto.dispatch(URI_EVENT + "on-restremote-deleted", uri, [self.proto])

         return self.proto.shrink(uri)
      else:
         raise Exception(URI_ERROR + "no-such-object", "No REST remote with URI %s" % uri)


   @exportRpc("delete-restremote")
   def deleteRestRemote(self, restRemoteUri):
      """
      Delete a REST remote.
      """
      return self.proto.dbpool.runInteraction(self._deleteRestRemote, restRemoteUri)


   @exportRpc("get-restremotes")
   def getRestRemotes(self):
      """
      Return REST remotes list.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, require_appcred_id, rpc_base_uri, rest_base_url, payload_format, forward_cookies, redirect_limit, connection_timeout, request_timeout, max_persistent_conns, persistent_conn_timeout FROM restremote ORDER BY require_appcred_id, rpc_base_uri, created")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_RESTREMOTE + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "require-appcred-uri": self.proto.shrink(URI_APPCRED + r[3]) if r[3] else None,
                                  "rpc-base-uri": r[4],
                                  "rest-base-url": r[5],
                                  "payload-format": r[6],
                                  "forward-cookies": r[7] != 0,
                                  "redirect-limit": r[8],
                                  "connection-timeout": r[9],
                                  "request-timeout": r[10],
                                  "max-persistent-connections": r[11],
                                  "persistent-connection-timeout": r[12]} for r in res])
      return d


   @exportRpc("query-restapi")
   def queryRestApi(self, restRemoteUri):
      uri = self.proto.resolveOrPass(restRemoteUri)
      id = self.proto.uriToId(uri)
      res = self.proto.factory.services["restremoter"].queryApi(id)
      if res:
         r = []
         for k in sorted(res.keys()):
            r.append((k, res[k][1]))
         return r
      else:
         raise Exception(URI_ERROR + "no-such-object", "No REST remote with URI %s" % uri)


   @exportRpc("query-restapi-by-appkey")
   def queryRestApiByAppKey(self, appkey):
      return self.proto.factory.services["restremoter"].getRemotes(appkey)
