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


class ClientPerms:
   """
   Client permissions model.
   """

   DOCNAME = "Client Permissions"

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def checkClientPermSpec(self, spec, specDelta, errs):

      ## default client permission flags
      ##
      flags = ["allow-publish", "allow-subscribe"]

      ## check that at least one of the flags is True (after an update with spec)
      ##
      flags_current = {}
      any = False
      for f in flags:
         if errs[f]:
            return 0
         if specDelta.has_key(f):
            flags_current[f] = specDelta[f]
         else:
            flags_current[f] = spec[f]
         any = any or flags_current[f]
      errcnt = 0
      if not any:
         for f in flags:
            if specDelta.has_key(f):
               errs[f].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"), "At least on of allow-* must be true"))
               errcnt += 2

      return errcnt


   def _createClientPerm(self, txn, spec):

      attrs = {"topic-uri": (True, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (True, [bool]),
               "filter-expression": (False, [str, unicode, types.NoneType], 0, 2000),
               "allow-publish": (True, [bool]),
               "allow-subscribe": (True, [bool]),
               "require-appcred-uri": (False, [str, unicode, types.NoneType])}

      errcnt, errs = self.proto.checkDictArg("clientperm spec", spec, attrs)

      if not errs["topic-uri"]:
         topic_uri, errs2 = self.proto.validateUri(spec["topic-uri"])
         errs["topic-uri"].extend(errs2)
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

      filter_expr = None
      if spec.has_key("filter-expression") and spec["filter-expression"] is not None and spec["filter-expression"].strip() != "":
         filter_expr = spec["filter-expression"].strip()

      errcnt += self.checkClientPermSpec({}, spec, errs)

      self.proto.raiseDictArgException(errs)

      id = newid()
      clientperm_uri = URI_CLIENTPERM + id
      now = utcnow()

      txn.execute("INSERT INTO clientperm (id, created, topic_uri, match_by_prefix, require_appcred_id, filter_expr, allow_publish, allow_subscribe) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                       [id,
                                        now,
                                        topic_uri,
                                        int(spec["match-by-prefix"]),
                                        appcred_id,
                                        filter_expr,
                                        int(spec["allow-publish"]),
                                        int(spec["allow-subscribe"])
                                        ])

      services = self.proto.factory.services
      if services.has_key("clientfilter"):
         self.proto.factory.services["clientfilter"].recache(txn)

      clientperm = {"uri": clientperm_uri,
                    "topic-uri": topic_uri,
                    "match-by-prefix": spec["match-by-prefix"],
                    "require-appcred-uri": appcred_uri,
                    "filter-expression": filter_expr,
                    "allow-publish": spec["allow-publish"],
                    "allow-subscribe": spec["allow-subscribe"]}

      self.proto.dispatch(URI_EVENT + "on-clientperm-created", clientperm, [self.proto])

      clientperm["uri"] = self.proto.shrink(clientperm_uri)
      if clientperm["require-appcred-uri"] is not None:
         clientperm["require-appcred-uri"] = self.proto.shrink(appcred_uri)
      return clientperm


   @exportRpc("create-clientperm")
   def createClientPerm(self, spec):
      return self.proto.dbpool.runInteraction(self._createClientPerm, spec)


   def _modifyClientPerm(self, txn, clientPermUri, specDelta):

      if type(clientPermUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument clientPermUri, but got %s" % str(type(clientPermUri)))

      attrs = {"topic-uri": (False, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (False, [bool]),
               "filter-expression": (False, [str, unicode], 0, 2000),
               "allow-publish": (False, [bool]),
               "allow-subscribe": (False, [bool]),
               "require-appcred-uri": (False, [str, unicode, types.NoneType])}

      errcnt, errs = self.proto.checkDictArg("clientperm delta spec", specDelta, attrs)

      if not errs["topic-uri"] and specDelta.has_key("topic-uri"):
         normalizedUri, errs2 = self.proto.validateUri(specDelta["topic-uri"])
         errs["topic-uri"].extend(errs2)
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

      uri = self.proto.resolveOrPass(clientPermUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT topic_uri, match_by_prefix, filter_expr, require_appcred_id, allow_publish, allow_subscribe FROM clientperm WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         spec = {}
         spec["topic-uri"] = res[0]
         spec["match-by-prefix"] = res[1] != 0
         spec["filter-expression"] = res[2]
         spec["require-appcred-uri"] = self.proto.shrink(URI_APPCRED + res[3]) if res[3] else None
         spec["allow-publish"] = res[4] != 0
         spec["allow-subscribe"] = res[5] != 0

         errcnt += self.checkClientPermSpec(spec, specDelta, errs)

         self.proto.raiseDictArgException(errs)

         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         if specDelta.has_key("topic-uri"): # and specDelta["topic-uri"] is not None:
            #newval = self.proto.resolveOrPass(specDelta["topic-uri"].strip())
            newval = normalizedUri
            if newval != "" and newval != res[0]:
               delta["topic-uri"] = newval
               sql += ", topic_uri = ?"
               sql_vars.append(newval)

         if specDelta.has_key("match-by-prefix"): # and specDelta["match-by-prefix"] is not None:
            newval = specDelta["match-by-prefix"]
            if newval != (res[1] != 0):
               delta["match-by-prefix"] = newval
               sql += ", match_by_prefix = ?"
               sql_vars.append(newval)

         if specDelta.has_key("filter-expression"): # and specDelta["filter-expression"] is not None:
            newval = specDelta["filter-expression"]
            if newval != res[2]:
               delta["filter-expression"] = newval
               sql += ", filter_expr = ?"
               sql_vars.append(newval)

#         if specDelta.has_key("require-appcred-uri") and specDelta["require-appcred-uri"] is not None and specDelta["require-appcred-uri"].strip() != "":
         if specDelta.has_key("require-appcred-uri"):
            if appcred_id != res[3]:
               delta["require-appcred-uri"] = appcred_uri
               sql += ", require_appcred_id = ?"
               sql_vars.append(appcred_id)

         if specDelta.has_key("allow-publish"): # and specDelta["allow-publish"] is not None:
            newval = specDelta["allow-publish"]
            if newval != (res[4] != 0):
               delta["allow-publish"] = newval
               sql += ", allow_publish = ?"
               sql_vars.append(newval)

         if specDelta.has_key("allow-subscribe"): # and specDelta["allow-subscribe"] is not None:
            newval = specDelta["allow-subscribe"]
            if newval != (res[5] != 0):
               delta["allow-subscribe"] = newval
               sql += ", allow_subscribe = ?"
               sql_vars.append(newval)

         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE clientperm SET %s WHERE id = ?" % sql, sql_vars)

            services = self.proto.factory.services
            if services.has_key("clientfilter"):
               services["clientfilter"].recache(txn)

            self.proto.dispatch(URI_EVENT + "on-clientperm-modified", delta, [self.proto])

            delta["uri"] = self.proto.shrink(uri)
            if delta.has_key("require-appcred-uri") and delta["require-appcred-uri"] is not None:
               delta["require-appcred-uri"] = self.proto.shrink(appcred_uri)
            return delta
         else:
            return {}
      else:
         raise Exception(URI_ERROR + "no-such-object", "No client permission with URI %s" % uri)


   @exportRpc("modify-clientperm")
   def modifyClientPerm(self, clientPermUri, specDelta):
      return self.proto.dbpool.runInteraction(self._modifyClientPerm, clientPermUri, specDelta)


   def _deleteClientPerm(self, txn, clientPermUri):

      if type(clientPermUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument clientPermUri, but got %s" % str(type(clientPermUri)))

      uri = self.proto.resolveOrPass(clientPermUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT created FROM clientperm WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         txn.execute("DELETE FROM clientperm WHERE id = ?", [id])

         services = self.proto.factory.services
         if services.has_key("clientfilter"):
            services["clientfilter"].recache(txn)

         self.proto.dispatch(URI_EVENT + "on-clientperm-deleted", uri, [self.proto])

         return self.proto.shrink(uri)
      else:
         raise Exception(URI_ERROR + "no-such-object", "No client permission with URI %s" % uri)


   @exportRpc("delete-clientperm")
   def deleteClientPerm(self, clientPermUri):
      return self.proto.dbpool.runInteraction(self._deleteClientPerm, clientPermUri)


   @exportRpc("get-clientperms")
   def getClientPerms(self):
      """
      Return client permissions list.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, topic_uri, match_by_prefix, require_appcred_id, filter_expr, allow_publish, allow_subscribe FROM clientperm ORDER BY LENGTH(topic_uri) ASC, topic_uri")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_CLIENTPERM + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "topic-uri": r[3],
                                  "match-by-prefix": r[4] != 0,
                                  "require-appcred-uri": self.proto.shrink(URI_APPCRED + r[5]) if r[5] else None,
                                  "filter-expression": r[6],
                                  "allow-publish": r[7] != 0,
                                  "allow-subscribe": r[8] != 0} for r in res])
      return d
