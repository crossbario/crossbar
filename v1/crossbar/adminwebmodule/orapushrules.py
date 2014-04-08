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


class OraPushRules:
   """
   Oracle push rules.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _checkSpec(self, spec, specDelta, errs):

      errcnt = 0

      if not errs["user"]:
         if specDelta.has_key('user') and specDelta['user'] is not None:
            if specDelta['user'].strip() == "":
               specDelta['user'] = None
            else:
               try:
                  specDelta['user'] = ','.join(sorted([x.strip().upper() for x in specDelta['user'].split(',')]))
               except Exception, e:
                  errs["user"].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"), "Illegal value '%s' for schema list [%s]." % (spec["schema-list"], str(e))))
                  errcnt += 1

      return errcnt


   def _createOraPushRule(self, txn, spec):

      ## check arguments
      ##
      attrs = {"topic-uri": (True, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (True, [bool]),
               "user": (False, [str, unicode, types.NoneType], 30),
               "oraconnect-uri": (True, [str, unicode], 0, URI_MAXLEN)}

      errcnt, errs = self.proto.checkDictArg("orapushrule spec", spec, attrs)

      if not errs["topic-uri"]:
         topic_uri, errs2 = self.proto.validateUri(spec["topic-uri"])
         errs["topic-uri"].extend(errs2)
         errcnt += len(errs2)

      oraconnect_id = None
      oraconnect_uri = None
      if spec.has_key("oraconnect-uri") and spec["oraconnect-uri"] is not None and spec["oraconnect-uri"].strip() != "":
         oraconnect_uri = self.proto.resolveOrPass(spec["oraconnect-uri"].strip())
         oraconnect_id = self.proto.uriToId(oraconnect_uri)
         txn.execute("SELECT created FROM oraconnect WHERE id = ?", [oraconnect_id])
         if txn.fetchone() is None:
            errs["oraconnect-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No ORA connect with URI %s" % appcred_uri))

      errcnt += self._checkSpec({}, spec, errs)

      self.proto.raiseDictArgException(errs)


      ## insert new object into service database
      ##
      id = newid()
      uri = URI_ORAPUSHRULE + id
      now = utcnow()
      user = spec['user'] if spec.has_key('user') else None

      txn.execute("INSERT INTO orapushrule (id, created, modified, oraconnect_id, user, topic_uri, match_by_prefix) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  [id,
                   now,
                   None,
                   oraconnect_id,
                   user,
                   topic_uri,
                   int(spec["match-by-prefix"])])

      ## recache in services if necessary
      ##
      services = self.proto.factory.services
      if services.has_key("orapusher"):
         services["orapusher"].recache(txn)

      obj = {"uri": uri,
             "created": now,
             "modified": None,
             "oraconnect-uri": oraconnect_uri,
             "user": user,
             "topic-uri": topic_uri,
             "match-by-prefix": spec["match-by-prefix"]}

      ## dispatch on-created event
      ##
      self.proto.dispatch(URI_EVENT + "on-orapushrule-created", obj, [self.proto])

      ## return complete object
      ##
      obj["uri"] = self.proto.shrink(uri)
      if obj["oraconnect-uri"] is not None:
         obj["oraconnect-uri"] = self.proto.shrink(oraconnect_uri)

      return obj


   @exportRpc("create-orapushrule")
   def createOraPushRule(self, spec):
      """
      Create a new Oracle push rule.
      """
      return self.proto.dbpool.runInteraction(self._createOraPushRule, spec)


   def _deleteOraPushRule(self, txn, oraPushRuleUri):

      ## check arguments
      ##
      if type(oraPushRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument oraPushRuleUri, but got %s" % str(type(oraPushRuleUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(oraPushRuleUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM orapushrule WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         txn.execute("DELETE FROM orapushrule WHERE id = ?", [id])

         ## recache in services if necessary
         ##
         services = self.proto.factory.services
         if services.has_key("orapusher"):
            services["orapusher"].recache(txn)

         ## dispatch on-deleted events
         ##
         self.proto.dispatch(URI_EVENT + "on-orapushrule-deleted", uri, [self.proto])

         ## return deleted object URI
         ##
         return self.proto.shrink(uri)
      else:
         raise Exception(URI_ERROR + "no-such-object", "No ORA push rule with URI %s" % uri)


   @exportRpc("delete-orapushrule")
   def deleteOraPushRule(self, oraPushRuleUri):
      """
      Delete a Oracle push rule.
      """
      return self.proto.dbpool.runInteraction(self._deleteOraPushRule, oraPushRuleUri)


   def _modifyOraPushRule(self, txn, oraPushRuleUri, specDelta):

      ## check arguments
      ##
      if type(oraPushRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument oraPushRuleUri, but got %s" % str(type(oraPushRuleUri)))

      attrs = {"topic-uri": (False, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (False, [bool]),
               "user": (False, [str, unicode, types.NoneType], 0, 30),
               "oraconnect-uri": (False, [str, unicode], 0, URI_MAXLEN)}

      errcnt, errs = self.proto.checkDictArg("ORA pushrule delta spec", specDelta, attrs)

      if not errs["topic-uri"] and specDelta.has_key("topic-uri"):
         topic_uri, errs2 = self.proto.validateUri(specDelta["topic-uri"])
         errs["topic-uri"].extend(errs2)
         errcnt += len(errs2)

      oraconnect_id = None
      oraconnect_uri = None
      if specDelta.has_key("oraconnect-uri") and specDelta["oraconnect-uri"] is not None and specDelta["oraconnect-uri"].strip() != "":
         oraconnect_uri = self.proto.resolveOrPass(specDelta["oraconnect-uri"].strip())
         oraconnect_id = self.proto.uriToId(oraconnect_uri)
         txn.execute("SELECT created FROM oraconnect WHERE id = ?", [oraconnect_id])
         if txn.fetchone() is None:
            errs["oraconnect-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No ORA connect with URI %s" % oraconnect_uri))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(oraPushRuleUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT topic_uri, match_by_prefix, user, oraconnect_id FROM orapushrule WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check arguments
         ##
         spec = {}
         spec["topic-uri"] = res[0]
         spec["match-by-prefix"] = res[1] != 0
         spec["user"] = res[2]
         spec["oraconnect-uri"] = self.proto.shrink(URI_ORACONNECT + res[3]) if res[3] else None

         errcnt += self._checkSpec(spec, specDelta, errs)

         self.proto.raiseDictArgException(errs)

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

         if specDelta.has_key("oraconnect-uri"):
            if oraconnect_id != res[3]:
               delta["oraconnect-uri"] = oraconnect_uri
               sql += ", oraconnect_id = ?"
               sql_vars.append(oraconnect_id)

         ## proceed when there is an actual change in data
         ##
         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE orapushrule SET %s WHERE id = ?" % sql, sql_vars)

            ## recache in services if necessary
            ##
            services = self.proto.factory.services
            if services.has_key("orapusher"):
               services["orapusher"].recache(txn)

            ## dispatch on-modified events
            ##
            self.proto.dispatch(URI_EVENT + "on-orapushrule-modified", delta, [self.proto])

            ## return object delta
            ##
            delta["uri"] = self.proto.shrink(uri)
            if delta.has_key("oraconnect-uri") and delta["oraconnect-uri"] is not None:
               delta["oraconnect-uri"] = self.proto.shrink(oraconnect_uri)
            return delta
         else:
            ## object unchanged
            ##
            return {}
      else:
         raise Exception(URI_ERROR + "no-such-object", "No ORA push rule with URI %s" % uri)


   @exportRpc("modify-orapushrule")
   def modifyOraPushRule(self, oraPushRuleUri, specDelta):
      """
      Modify a Oracle push rule.
      """
      return self.proto.dbpool.runInteraction(self._modifyOraPushRule, oraPushRuleUri, specDelta)


   @exportRpc("get-orapushrules")
   def getOraPushRules(self):
      """
      Return list of Oracle push rules.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, oraconnect_id, user, topic_uri, match_by_prefix FROM orapushrule ORDER BY oraconnect_id, user, topic_uri")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_ORAPUSHRULE + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "oraconnect-uri": self.proto.shrink(URI_ORACONNECT + r[3]) if r[3] else None,
                                  "user": r[4],
                                  "topic-uri": r[5],
                                  "match-by-prefix": r[6] != 0} for r in res])
      return d
