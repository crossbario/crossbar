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


class PgPushRules:
   """
   PostgreSQL Push Rules model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _checkSpec(self, spec, errs):

      errcnt = 0
      return errcnt


   def _createPgPushRule(self, txn, spec):

      ## check arguments
      ##
      attrs = {"topic-uri": (True, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (True, [bool]),
               "user": (False, [str, unicode, types.NoneType], 0, 30),
               "pgconnect-uri": (True, [str, unicode], 0, URI_MAXLEN)}

      errcnt, errs = self.proto.checkDictArg("PG pushrule spec", spec, attrs)

      if not errs["topic-uri"]:
         topic_uri, errs2 = self.proto.validateUri(spec["topic-uri"])
         errs["topic-uri"].extend(errs2)
         errcnt += len(errs2)

      errcnt += self._checkSpec(spec, errs)

      pgconnect_id = None
      pgconnect_uri = None
      if spec.has_key("pgconnect-uri") and spec["pgconnect-uri"] is not None and spec["pgconnect-uri"].strip() != "":
         pgconnect_uri = self.proto.resolveOrPass(spec["pgconnect-uri"].strip())
         pgconnect_id = self.proto.uriToId(pgconnect_uri)
         txn.execute("SELECT created FROM pgconnect WHERE id = ?", [pgconnect_id])
         if txn.fetchone() is None:
            errs["pgconnect-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No PG connect with URI %s" % appcred_uri))

      self.proto.raiseDictArgException(errs)


      ## insert new object into service database
      ##
      id = newid()
      uri = URI_PGPUSHRULE + id
      now = utcnow()
      user = spec['user'].strip() if spec.has_key('user') else None

      txn.execute("INSERT INTO pgpushrule (id, created, modified, pgconnect_id, user, topic_uri, match_by_prefix) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  [id,
                   now,
                   None,
                   pgconnect_id,
                   user,
                   topic_uri,
                   int(spec["match-by-prefix"])])

      ## recache in services if necessary
      ##
      services = self.proto.factory.services
      if services.has_key("pgpusher"):
         services["pgpusher"].recache(txn)

      obj = {"uri": uri,
             "created": now,
             "modified": None,
             "pgconnect-uri": pgconnect_uri,
             "user": user,
             "topic-uri": topic_uri,
             "match-by-prefix": spec["match-by-prefix"]}

      ## dispatch on-created event
      ##
      self.proto.dispatch(URI_EVENT + "on-pgpushrule-created", obj, [self.proto])

      ## return complete object
      ##
      obj["uri"] = self.proto.shrink(uri)
      if obj["pgconnect-uri"] is not None:
         obj["pgconnect-uri"] = self.proto.shrink(pgconnect_uri)
      return obj


   @exportRpc("create-pgpushrule")
   def createPgPushRule(self, spec):
      """
      Create a new PostgreSQL push rule.
      """
      return self.proto.dbpool.runInteraction(self._createPgPushRule, spec)


   def _deletePgPushRule(self, txn, pgPushRuleUri):

      ## check arguments
      ##
      if type(pgPushRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument pgPushRuleUri, but got %s" % str(type(pgPushRuleUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(pgPushRuleUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM pgpushrule WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         txn.execute("DELETE FROM pgpushrule WHERE id = ?", [id])

         ## recache in services if necessary
         ##
         services = self.proto.factory.services
         if services.has_key("pgpusher"):
            services["pgpusher"].recache(txn)

         ## dispatch on-deleted events
         ##
         self.proto.dispatch(URI_EVENT + "on-pgpushrule-deleted", uri, [self.proto])

         ## return deleted object URI
         ##
         return self.proto.shrink(uri)
      else:
         raise Exception(URI_ERROR + "no-such-object", "No PG push rule with URI %s" % uri)


   @exportRpc("delete-pgpushrule")
   def deletePgPushRule(self, pgPushRuleUri):
      """
      Delete a PostgreSQL push rule.
      """
      return self.proto.dbpool.runInteraction(self._deletePgPushRule, pgPushRuleUri)


   def _modifyPgPushRule(self, txn, pgPushRuleUri, specDelta):

      ## check arguments
      ##
      if type(pgPushRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument pgPushRuleUri, but got %s" % str(type(pgPushRuleUri)))

      attrs = {"topic-uri": (False, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (False, [bool]),
               "user": (False, [str, unicode, types.NoneType], 0, 30),
               "pgconnect-uri": (False, [str, unicode], 0, URI_MAXLEN)}

      errcnt, errs = self.proto.checkDictArg("PG pushrule delta spec", specDelta, attrs)

      if not errs["topic-uri"] and specDelta.has_key("topic-uri"):
         topic_uri, errs2 = self.proto.validateUri(specDelta["topic-uri"])
         errs["topic-uri"].extend(errs2)
         errcnt += len(errs2)

      errcnt += self._checkSpec(specDelta, errs)

      pgconnect_id = None
      pgconnect_uri = None
      if specDelta.has_key("pgconnect-uri") and specDelta["pgconnect-uri"] is not None and specDelta["pgconnect-uri"].strip() != "":
         pgconnect_uri = self.proto.resolveOrPass(specDelta["pgconnect-uri"].strip())
         pgconnect_id = self.proto.uriToId(pgconnect_uri)
         txn.execute("SELECT created FROM pgconnect WHERE id = ?", [pgconnect_id])
         if txn.fetchone() is None:
            errs["pgconnect-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No PG connect with URI %s" % pgconnect_uri))

      self.proto.raiseDictArgException(errs)

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(pgPushRuleUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT topic_uri, match_by_prefix, user, pgconnect_id FROM pgpushrule WHERE id = ?", [id])
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

         if specDelta.has_key("pgconnect-uri"):
            if pgconnect_id != res[3]:
               delta["pgconnect-uri"] = pgconnect_uri
               sql += ", pgconnect_id = ?"
               sql_vars.append(pgconnect_id)

         ## proceed when there is an actual change in data
         ##
         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE pgpushrule SET %s WHERE id = ?" % sql, sql_vars)

            ## recache in services if necessary
            ##
            services = self.proto.factory.services
            if services.has_key("pgpusher"):
               services["pgpusher"].recache(txn)

            ## dispatch on-modified events
            ##
            self.proto.dispatch(URI_EVENT + "on-pgpushrule-modified", delta, [self.proto])

            ## return object delta
            ##
            delta["uri"] = self.proto.shrink(uri)
            if delta.has_key("pgconnect-uri") and delta["pgconnect-uri"] is not None:
               delta["pgconnect-uri"] = self.proto.shrink(pgconnect_uri)
            return delta
         else:
            ## object unchanged
            ##
            return {}
      else:
         raise Exception(URI_ERROR + "no-such-object", "No PG push rule with URI %s" % uri)


   @exportRpc("modify-pgpushrule")
   def modifyPgPushRule(self, pgPushRuleUri, specDelta):
      """
      Modify a PostgreSQL push rule.
      """
      return self.proto.dbpool.runInteraction(self._modifyPgPushRule, pgPushRuleUri, specDelta)


   @exportRpc("get-pgpushrules")
   def getPgPushRules(self):
      """
      Return list of PostgreSQL push rules.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, pgconnect_id, user, topic_uri, match_by_prefix FROM pgpushrule ORDER BY pgconnect_id, user, topic_uri")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_PGPUSHRULE + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "pgconnect-uri": self.proto.shrink(URI_PGCONNECT + r[3]) if r[3] else None,
                                  "user": r[4],
                                  "topic-uri": r[5],
                                  "match-by-prefix": r[6] != 0} for r in res])
      return d
