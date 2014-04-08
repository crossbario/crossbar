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


class HanaPushRules:
   """
   SAP HANA Push Rules model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def checkSpec(self, spec, errs):

      errcnt = 0
      return errcnt


   def _createHanaPushRule(self, txn, spec):

      ## check arguments
      ##
      attrs = {"topic-uri": (True, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (True, [bool]),
               "user": (False, [str, unicode, types.NoneType], 0, 30),
               "hanaconnect-uri": (True, [str, unicode], 0, URI_MAXLEN)}

      errcnt, errs = self.proto.checkDictArg("HANA pushrule spec", spec, attrs)

      if not errs["topic-uri"]:
         topic_uri, errs2 = self.proto.validateUri(spec["topic-uri"])
         errs["topic-uri"].extend(errs2)
         errcnt += len(errs2)

      errcnt += self.checkSpec(spec, errs)

      hanaconnect_id = None
      hanaconnect_uri = None
      if spec.has_key("hanaconnect-uri") and spec["hanaconnect-uri"] is not None and spec["hanaconnect-uri"].strip() != "":
         hanaconnect_uri = self.proto.resolveOrPass(spec["hanaconnect-uri"].strip())
         hanaconnect_id = self.proto.uriToId(hanaconnect_uri)
         txn.execute("SELECT created FROM hanaconnect WHERE id = ?", [hanaconnect_id])
         if txn.fetchone() is None:
            errs["hanaconnect-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No HANA connect with URI %s" % appcred_uri))

      self.proto.raiseDictArgException(errs)


      ## insert new object into service database
      ##
      id = newid()
      uri = URI_HANAPUSHRULE + id
      now = utcnow()
      user = spec['user'].strip() if spec.has_key('user') else None

      txn.execute("INSERT INTO hanapushrule (id, created, modified, hanaconnect_id, user, topic_uri, match_by_prefix) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  [id,
                   now,
                   None,
                   hanaconnect_id,
                   user,
                   topic_uri,
                   int(spec["match-by-prefix"])])

      ## recache in services if necessary
      ##
      services = self.proto.factory.services
      if services.has_key("hanapusher"):
         services["hanapusher"].recache(txn)

      obj = {"uri": uri,
             "created": now,
             "modified": None,
             "hanaconnect-uri": hanaconnect_uri,
             "user": user,
             "topic-uri": topic_uri,
             "match-by-prefix": spec["match-by-prefix"]}

      ## dispatch on-created event
      ##
      self.proto.dispatch(URI_EVENT + "on-hanapushrule-created", obj, [self.proto])

      ## return complete object
      ##
      obj["uri"] = self.proto.shrink(uri)
      if obj["hanaconnect-uri"] is not None:
         obj["hanaconnect-uri"] = self.proto.shrink(hanaconnect_uri)
      return obj


   @exportRpc("create-hanapushrule")
   def createHanaPushRule(self, spec):
      """
      Create a new SAP HANA push rule.
      """
      return self.proto.dbpool.runInteraction(self._createHanaPushRule, spec)


   def _deleteHanaPushRule(self, txn, hanaPushRuleUri):

      ## check arguments
      ##
      if type(hanaPushRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument hanaPushRuleUri, but got %s" % str(type(hanaPushRuleUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(hanaPushRuleUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM hanapushrule WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         txn.execute("DELETE FROM hanapushrule WHERE id = ?", [id])

         ## recache in services if necessary
         ##
         services = self.proto.factory.services
         if services.has_key("hanapusher"):
            services["hanapusher"].recache(txn)

         ## dispatch on-deleted events
         ##
         self.proto.dispatch(URI_EVENT + "on-hanapushrule-deleted", uri, [self.proto])

         ## return deleted object URI
         ##
         return self.proto.shrink(uri)
      else:
         raise Exception(URI_ERROR + "no-such-object", "No HANA push rule with URI %s" % uri)


   @exportRpc("delete-hanapushrule")
   def deleteHanaPushRule(self, hanaPushRuleUri):
      """
      Delete a SAP HANA push rule.
      """
      return self.proto.dbpool.runInteraction(self._deleteHanaPushRule, hanaPushRuleUri)


   def _modifyHanaPushRule(self, txn, hanaPushRuleUri, specDelta):

      ## check arguments
      ##
      if type(hanaPushRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument hanaPushRuleUri, but got %s" % str(type(hanaPushRuleUri)))

      attrs = {"topic-uri": (False, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (False, [bool]),
               "user": (False, [str, unicode, types.NoneType], 0, 30),
               "hanaconnect-uri": (False, [str, unicode], 0, URI_MAXLEN)}

      errcnt, errs = self.proto.checkDictArg("HANA pushrule delta spec", specDelta, attrs)

      if not errs["topic-uri"] and specDelta.has_key("topic-uri"):
         topic_uri, errs2 = self.proto.validateUri(specDelta["topic-uri"])
         errs["topic-uri"].extend(errs2)
         errcnt += len(errs2)

      errcnt += self.checkSpec(specDelta, errs)

      hanaconnect_id = None
      hanaconnect_uri = None
      if specDelta.has_key("hanaconnect-uri") and specDelta["hanaconnect-uri"] is not None and specDelta["hanaconnect-uri"].strip() != "":
         hanaconnect_uri = self.proto.resolveOrPass(specDelta["hanaconnect-uri"].strip())
         hanaconnect_id = self.proto.uriToId(hanaconnect_uri)
         txn.execute("SELECT created FROM hanaconnect WHERE id = ?", [hanaconnect_id])
         if txn.fetchone() is None:
            errs["hanaconnect-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No HANA connect with URI %s" % hanaconnect_uri))

      self.proto.raiseDictArgException(errs)

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(hanaPushRuleUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT topic_uri, match_by_prefix, user, hanaconnect_id FROM hanapushrule WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## compute delta and SQL
         ##
         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         if specDelta.has_key("topic-uri"):
            newval = topic_uri
            if newval != "" and newval != res[0]:
               delta["topic-uri"] = newval
               sql += ", topic_uri = ?"
               sql_vars.append(newval)

         if specDelta.has_key("match-by-prefix"):
            newval = specDelta["match-by-prefix"]
            if newval != (res[1] != 0):
               delta["match-by-prefix"] = newval
               sql += ", match_by_prefix = ?"
               sql_vars.append(newval)

         if specDelta.has_key("user"):
            newval = specDelta["user"]
            if newval != res[2]:
               delta["user"] = newval
               sql += ", user = ?"
               sql_vars.append(newval)

         if specDelta.has_key("hanaconnect-uri"):
            if hanaconnect_id != res[3]:
               delta["hanaconnect-uri"] = hanaconnect_uri
               sql += ", hanaconnect_id = ?"
               sql_vars.append(hanaconnect_id)

         ## proceed when there is an actual change in data
         ##
         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE hanapushrule SET %s WHERE id = ?" % sql, sql_vars)

            ## recache in services if necessary
            ##
            services = self.proto.factory.services
            if services.has_key("hanapusher"):
               services["hanapusher"].recache(txn)

            ## dispatch on-modified events
            ##
            self.proto.dispatch(URI_EVENT + "on-hanapushrule-modified", delta, [self.proto])

            ## return object delta
            ##
            delta["uri"] = self.proto.shrink(uri)
            if delta.has_key("hanaconnect-uri") and delta["hanaconnect-uri"] is not None:
               delta["hanaconnect-uri"] = self.proto.shrink(hanaconnect_uri)
            return delta
         else:
            ## object unchanged
            ##
            return {}
      else:
         raise Exception(URI_ERROR + "no-such-object", "No HANA push rule with URI %s" % uri)


   @exportRpc("modify-hanapushrule")
   def modifyHanaPushRule(self, hanaPushRuleUri, specDelta):
      """
      Modify a SAP HANA push rule.
      """
      return self.proto.dbpool.runInteraction(self._modifyHanaPushRule, hanaPushRuleUri, specDelta)


   @exportRpc("get-hanapushrules")
   def getHanaPushRules(self):
      """
      Return list of SAP HANA push rules.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, hanaconnect_id, user, topic_uri, match_by_prefix FROM hanapushrule ORDER BY hanaconnect_id, user, topic_uri")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_HANAPUSHRULE + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "hanaconnect-uri": self.proto.shrink(URI_HANACONNECT + r[3]) if r[3] else None,
                                  "user": r[4],
                                  "topic-uri": r[5],
                                  "match-by-prefix": r[6] != 0} for r in res])
      return d
