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


class HanaRemotes:
   """
   SAP HANA Remotes model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _checkSpec(self, spec, specDelta, errs):

      errcnt = 0

      if not errs["schema-list"]:
         if specDelta.has_key('schema-list'):
            try:
               specDelta['schema-list'] = ','.join(sorted([x.strip().lower() for x in specDelta['schema-list'].split(',')]))
            except Exception, e:
               errs["schema-list"].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"), "Illegal value '%s' for schema list [%s]." % (spec["schema-list"], str(e))))
               errcnt += 1

      if not errs["connection-pool-min-size"] and not errs["connection-pool-max-size"]:
         if specDelta.has_key('connection-pool-min-size') or specDelta.has_key('connection-pool-max-size'):
            cpMinSize = specDelta.get('connection-pool-min-size', spec.get('connection-pool-min-size', None))
            cpMaxSize = specDelta.get('connection-pool-max-size', spec.get('connection-pool-max-size', None))
            if cpMinSize > cpMaxSize:
               if specDelta.has_key('connection-pool-min-size'):
                  errs["connection-pool-min-size"].append((self.proto.shrink(URI_ERROR + "invalid-range-value"),
                                                           "Illegal value '%s' for connection pool min size - must be smaller than or equal to max size." % specDelta['connection-pool-min-size']))
                  errcnt += 1
               if specDelta.has_key('connection-pool-max-size'):
                  errs["connection-pool-max-size"].append((self.proto.shrink(URI_ERROR + "invalid-range-value"),
                                                           "Illegal value '%s' for connection pool max size - must be larger than or equal to min size." % specDelta['connection-pool-max-size']))
                  errcnt += 1

      return errcnt


   def _createHanaRemote(self, txn, spec):

      ## check arguments
      ##
      attrs = {"require-appcred-uri": (False, [str, unicode, types.NoneType]),
               "hanaconnect-uri": (True, [str, unicode]),
               "schema-list": (True, [str, unicode], 0, 1000),
               "rpc-base-uri": (True, [str, unicode], 0, URI_MAXLEN),
               "connection-pool-min-size": (True, [int], 1, 30),
               "connection-pool-max-size": (True, [int], 1, 100),
               "connection-timeout": (True, [int], 0, 120),
               "request-timeout": (True, [int], 0, 120)}

      errcnt, errs = self.proto.checkDictArg("hanaremote spec", spec, attrs)

      if not errs["rpc-base-uri"]:
         rpcBaseUri, errs2 = self.proto.validateUri(spec["rpc-base-uri"])
         errs["rpc-base-uri"].extend(errs2)
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

      connect_id = None
      connect_uri = None
      if spec.has_key("hanaconnect-uri") and spec["hanaconnect-uri"] is not None and spec["hanaconnect-uri"].strip() != "":
         connect_uri = self.proto.resolveOrPass(spec["hanaconnect-uri"].strip())
         connect_id = self.proto.uriToId(connect_uri)
         txn.execute("SELECT created FROM hanaconnect WHERE id = ?", [connect_id])
         if txn.fetchone() is None:
            errs["hanaconnect-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No HANA connect URI %s" % connect_uri))

      errcnt += self._checkSpec({}, spec, errs)

      self.proto.raiseDictArgException(errs)

      ## insert new object into service database
      ##
      id = newid()
      hanaremote_uri = URI_HANAREMOTE + id
      now = utcnow()

      txn.execute("INSERT INTO hanaremote (id, created, require_appcred_id, hanaconnect_id, schema_list, rpc_base_uri, connection_pool_min_size, connection_pool_max_size, connection_timeout, request_timeout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       [id,
                                        now,
                                        appcred_id,
                                        connect_id,
                                        spec["schema-list"],
                                        rpcBaseUri,
                                        int(spec["connection-pool-min-size"]),
                                        int(spec["connection-pool-max-size"]),
                                        int(spec["connection-timeout"]),
                                        int(spec["request-timeout"])
                                        ])

      ## recache in services if necessary
      ##
      services = self.proto.factory.services
      if services.has_key("hanaremoter"):
         services["hanaremoter"].recache(txn)

      hanaremote = {"uri": hanaremote_uri,
                    "require-appcred-uri": appcred_uri,
                    "hanaconnect-uri": connect_uri,
                    "schema-list": spec["schema-list"],
                    "rpc-base-uri": rpcBaseUri,
                    "connection-pool-min-size": int(spec["connection-pool-min-size"]),
                    "connection-pool-max-size": int(spec["connection-pool-max-size"]),
                    "connection-timeout": int(spec["connection-timeout"]),
                    "request-timeout": int(spec["request-timeout"])}

      ## dispatch on-created event
      ##
      self.proto.dispatch(URI_EVENT + "on-hanaremote-created", hanaremote, [self.proto])

      ## return complete object
      ##
      hanaremote["uri"] = self.proto.shrink(hanaremote_uri)

      if hanaremote["require-appcred-uri"] is not None:
         hanaremote["require-appcred-uri"] = self.proto.shrink(appcred_uri)

      if hanaremote["hanaconnect-uri"] is not None:
         hanaremote["hanaconnect-uri"] = self.proto.shrink(connect_uri)

      return hanaremote


   @exportRpc("create-hanaremote")
   def createHanaRemote(self, spec):
      """
      Create a new SAP HANA remote.
      """
      return self.proto.dbpool.runInteraction(self._createHanaRemote, spec)


   def _modifyHanaRemote(self, txn, hanaRemoteUri, specDelta):

      ## check arguments
      ##
      if type(hanaRemoteUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument hanaRemoteUri, but got %s" % str(type(hanaRemoteUri)))

      attrs = {"require-appcred-uri": (False, [str, unicode, types.NoneType]),
               "hanaconnect-uri": (False, [str, unicode]),
               "schema-list": (False, [str, unicode], 0, 1000),
               "rpc-base-uri": (False, [str, unicode], 0, URI_MAXLEN),
               "connection-pool-min-size": (False, [int], 1, 30),
               "connection-pool-max-size": (False, [int], 1, 100),
               "connection-timeout": (False, [int], 0, 120),
               "request-timeout": (False, [int], 0, 120)}

      errcnt, errs = self.proto.checkDictArg("hanaremote delta spec", specDelta, attrs)

      if not errs["rpc-base-uri"] and specDelta.has_key("rpc-base-uri"):
         rpcBaseUri, errs2 = self.proto.validateUri(specDelta["rpc-base-uri"])
         errs["rpc-base-uri"].extend(errs2)
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

      connect_id = None
      connect_uri = None
      if specDelta.has_key("hanaconnect-uri") and specDelta["hanaconnect-uri"] is not None and specDelta["hanaconnect-uri"].strip() != "":
         connect_uri = self.proto.resolveOrPass(specDelta["hanaconnect-uri"].strip())
         connect_id = self.proto.uriToId(connect_uri)
         txn.execute("SELECT created FROM hanaconnect WHERE id = ?", [connect_id])
         if txn.fetchone() is None:
            errs["hanaconnect-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No HANA connect URI %s" % connect_uri))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(hanaRemoteUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT require_appcred_id, hanaconnect_id, schema_list, rpc_base_uri, connection_pool_min_size, connection_pool_max_size, connection_timeout, request_timeout FROM hanaremote WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check arguments
         ##
         spec = {}
         spec["require-appcred-uri"] = self.proto.shrink(URI_APPCRED + res[0]) if res[0] else None
         spec["hanaconnect-uri"] = self.proto.shrink(URI_HANACONNECT + res[1]) if res[1] else None
         spec["schema-list"] = res[2]
         spec["rpc-base-uri"] = res[3]
         spec["connection-pool-min-size"] = res[4]
         spec["connection-pool-max-size"] = res[5]
         spec["connection-timeout"] = res[6]
         spec["request-timeout"] = res[7]

         errcnt += self._checkSpec(spec, specDelta, errs)

         self.proto.raiseDictArgException(errs)

         ## compute delta and SQL
         ##
         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         if specDelta.has_key("require-appcred-uri"):
            if appcred_id != res[0]:
               delta["require-appcred-uri"] = appcred_uri
               sql += ", require_appcred_id = ?"
               sql_vars.append(appcred_id)

         if specDelta.has_key("hanaconnect-uri"):
            if connect_id != res[1]:
               delta["hanaconnect-uri"] = connect_uri
               sql += ", hanaconnect_id = ?"
               sql_vars.append(connect_id)

         if specDelta.has_key("schema-list"):
            newval = specDelta["schema-list"]
            if newval != "" and newval != res[2]:
               delta["schema-list"] = newval
               sql += ", schema_list = ?"
               sql_vars.append(newval)

         if specDelta.has_key("rpc-base-uri"):
            newval = rpcBaseUri
            if newval != "" and newval != res[3]:
               delta["rpc-base-uri"] = newval
               sql += ", rpc_base_uri = ?"
               sql_vars.append(newval)

         if specDelta.has_key("connection-pool-min-size"):
            newval = specDelta["connection-pool-min-size"]
            if newval != res[4]:
               delta["connection-pool-min-size"] = newval
               sql += ", connection_pool_min_size = ?"
               sql_vars.append(newval)

         if specDelta.has_key("connection-pool-max-size"):
            newval = specDelta["connection-pool-max-size"]
            if newval != res[5]:
               delta["connection-pool-max-size"] = newval
               sql += ", connection_pool_max_size = ?"
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

         ## proceed when there is an actual change in data
         ##
         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE hanaremote SET %s WHERE id = ?" % sql, sql_vars)

            ## recache in services if necessary
            ##
            services = self.proto.factory.services
            if services.has_key("hanaremoter"):
               services["hanaremoter"].recache(txn)

            ## dispatch on-modified events
            ##
            self.proto.dispatch(URI_EVENT + "on-hanaremote-modified", delta, [self.proto])

            ## return object delta
            ##
            delta["uri"] = self.proto.shrink(uri)

            if delta.has_key("require-appcred-uri") and delta["require-appcred-uri"] is not None:
               delta["require-appcred-uri"] = self.proto.shrink(appcred_uri)

            if delta.has_key("hanaconnect-uri") and delta["hanaconnect-uri"] is not None:
               delta["hanaconnect-uri"] = self.proto.shrink(connect_uri)

            return delta
         else:
            ## object unchanged
            ##
            return {}
      else:
         raise Exception(URI_ERROR + "no-such-object", "No HANA remote with URI %s" % uri)


   @exportRpc("modify-hanaremote")
   def modifyHanaRemote(self, hanaRemoteUri, specDelta):
      """
      Modify a SAP HANA remote.
      """
      return self.proto.dbpool.runInteraction(self._modifyHanaRemote, hanaRemoteUri, specDelta)


   def _deleteHanaRemote(self, txn, hanaRemoteUri):

      ## check arguments
      ##
      if type(hanaRemoteUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument hanaRemoteUri, but got %s" % str(type(hanaRemoteUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(hanaRemoteUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM hanaremote WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         txn.execute("DELETE FROM hanaremote WHERE id = ?", [id])

         ## recache in services if necessary
         ##
         services = self.proto.factory.services
         if services.has_key("hanaremoter"):
            services["hanaremoter"].recache(txn)

         ## dispatch on-deleted events
         ##
         self.proto.dispatch(URI_EVENT + "on-hanaremote-deleted", uri, [self.proto])

         return self.proto.shrink(uri)
      else:
         raise Exception(URI_ERROR + "no-such-object", "No HANA remote with URI %s" % uri)


   @exportRpc("delete-hanaremote")
   def deleteHanaRemote(self, hanaRemoteUri):
      """
      Delete a HANA remote.
      """
      return self.proto.dbpool.runInteraction(self._deleteHanaRemote, hanaRemoteUri)


   @exportRpc("get-hanaremotes")
   def getHanaRemotes(self):
      """
      Return HANA remotes list.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, require_appcred_id, hanaconnect_id, schema_list, rpc_base_uri, connection_pool_min_size, connection_pool_max_size, connection_timeout, request_timeout FROM hanaremote ORDER BY require_appcred_id, rpc_base_uri, created")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_HANAREMOTE + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "require-appcred-uri": self.proto.shrink(URI_APPCRED + r[3]) if r[3] else None,
                                  "hanaconnect-uri": self.proto.shrink(URI_APPCRED + r[4]) if r[4] else None,
                                  "schema-list": r[5],
                                  "rpc-base-uri": r[6],
                                  "connection-pool-min-size": r[7],
                                  "connection-pool-max-size": r[8],
                                  "connection-timeout": r[9],
                                  "request-timeout": r[10]} for r in res])
      return d


   @exportRpc("query-hanapool")
   def queryHanaPool(self, hanaRemoteUri):
      """
      Query current SAP HANA database connection pool for remote.
      """
      if type(hanaRemoteUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument hanaRemoteUri, but got %s" % str(type(hanaRemoteUri)))

      uri = self.proto.resolveOrPass(hanaRemoteUri)
      id = self.proto.uriToId(uri)

      if self.proto.factory.services.has_key("hanaremoter"):
         res = self.proto.factory.services["hanaremoter"].queryPool(id)
         if res is not None:
            r = []
            for c in sorted(res):
               r.append({'created': c[1], 'backend-pid': c[0]})
            return r
         else:
            raise Exception(URI_ERROR + "no-such-object", "No SAP HANA remote with URI %s" % uri)
      else:
         return []


   def _getHanaApiSorted(self, res):
      r = []
      for k in sorted(res.keys()):
         rr = res[k]
         r.append((k, rr[0], rr[1], rr[2]))
      return r


   @exportRpc("query-hanaapi")
   def queryHanaApi(self, hanaRemoteUri):
      """
      Query SAP HANA remoted API for this remote.
      """
      if type(hanaRemoteUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument hanaRemoteUri, but got %s" % str(type(hanaRemoteUri)))

      uri = self.proto.resolveOrPass(hanaRemoteUri)
      id = self.proto.uriToId(uri)

      if self.proto.factory.services.has_key("hanaremoter"):
         d = self.proto.factory.services["hanaremoter"].queryApi(id)
         if d is not None:
            d.addCallback(self._getHanaApiSorted)
            return d
         else:
            raise Exception(URI_ERROR + "no-such-object", "No SAP HANA remote with URI %s" % uri)
      else:
         return []


   @exportRpc("query-hanaapi-by-appkey")
   def queryHanaApiByAppKey(self, appkey):
      """
      Query SAP HANA remoted API by authentication key.
      """
      return self.proto.factory.services["hanaremoter"].getRemotes(appkey)
