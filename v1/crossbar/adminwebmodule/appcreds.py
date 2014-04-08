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


from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

from crossbar.adminwebmodule.uris import *


class AppCreds:
   """
   Application credentials model.
   """

   APPCRED_KEY_PATTERN = "^[a-z0-9_\-]*$"
   APPCRED_KEY_MIN_LENGTH = 3
   APPCRED_KEY_MAX_LENGTH = 15

   APPCRED_SECRET_PATTERN = "^[a-zA-Z0-9_\-!$%&/=]*$"
   APPCRED_SECRET_MIN_LENGTH = 6
   APPCRED_SECRET_MAX_LENGTH = 20

   APPCRED_LABEL_MIN_LENGTH = 3
   APPCRED_LABEL_MAX_LENGTH = 20


   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _createAppCred(self, txn, spec):
      """
      Create new application credential, runs in database transaction.
      """
      attrs = {"label": (True,
                         [str, unicode],
                         AppCreds.APPCRED_LABEL_MIN_LENGTH,
                         AppCreds.APPCRED_LABEL_MAX_LENGTH,
                         None),
               "key": (True,
                       [str, unicode],
                       AppCreds.APPCRED_KEY_MIN_LENGTH,
                       AppCreds.APPCRED_KEY_MAX_LENGTH,
                       AppCreds.APPCRED_KEY_PATTERN),
               "secret": (True,
                          [str, unicode],
                          AppCreds.APPCRED_SECRET_MIN_LENGTH,
                          AppCreds.APPCRED_SECRET_MAX_LENGTH,
                          AppCreds.APPCRED_SECRET_PATTERN)}

      errcnt, errs = self.proto.checkDictArg("appcred spec", spec, attrs)

      txn.execute("SELECT created FROM appcredential WHERE key = ?", [spec["key"]])
      if txn.fetchone() is not None:
         errs["key"].append((self.proto.shrink(URI_ERROR + "duplicate-value"), "Application key '%s' already exists" % spec["key"]))
         errcnt += 1

      if errcnt:
         raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)

      id = newid()
      appcred_uri = URI_APPCRED + id
      label = spec["label"].strip()
      now = utcnow()
      txn.execute("INSERT INTO appcredential (id, label, key, created, secret) VALUES (?, ?, ?, ?, ?)",
                  [id,
                   label,
                   spec["key"],
                   now,
                   spec["secret"]])

      services = self.proto.factory.services
      if services.has_key("restpusher"):
         services["restpusher"].recache(txn)
      if services.has_key("clientfilter"):
         services["clientfilter"].recache(txn)

      appcred = {"uri": appcred_uri,
                 "created": now,
                 "label": label,
                 "key": spec["key"],
                 "secret": spec["secret"]}

      self.proto.dispatch(URI_EVENT + "on-appcred-created", appcred, [self.proto])

      appcred["uri"] = self.proto.shrink(appcred_uri)
      return appcred


   @exportRpc("create-appcred")
   def createAppCred(self, spec):
      """
      Create new application credential.

      Parameters:

         spec:             Application credential specification, a dictionary.
         spec[]
            label:         Label, a string, not necessarily unique.
            key:           Key, a string, must be unique.
            secret:        Secret, a string.

      Result:

         {"uri":        <Appcred URI>,
          "created":    <Appcred creation timestamp>,
          "label":      <Appcred label>,
          "key":        <Appcred key>,
          "secret":     <Appcred secret>}

      Events:

         on-appcred-created

      Errors:

         spec:                   illegal-argument

         spec[]:

            *:                   illegal-attribute-type,
                                 missing-attribute

            label,
            key,
            secret:              attribute-value-too-short,
                                 attribute-value-too-long

            key,
            secret:              attribute-value-invalid-characters

            key:                 duplicate-value

            ?:                   unknown-attribute
      """
      return self.proto.dbpool.runInteraction(self._createAppCred, spec)


   def _deleteAppCred(self, txn, appCredUri, cascade):

      ## check arguments
      ##
      if type(appCredUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument appCredUri, but got %s" % str(type(appCredUri)))

      if type(cascade) not in [bool]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type bool for agument cascade, but got %s" % str(type(cascade)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(appCredUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM appcredential WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check for depending pgremotes
         ##
         txn.execute("SELECT id FROM pgremote WHERE require_appcred_id = ?", [id])
         dependingPgRemotes = []
         for r in txn.fetchall():
            dependingPgRemotes.append(r[0])

         ## check for depending oraremotes
         ##
         txn.execute("SELECT id FROM oraremote WHERE require_appcred_id = ?", [id])
         dependingOraRemotes = []
         for r in txn.fetchall():
            dependingOraRemotes.append(r[0])

         ## check for depending hanaremotes
         ##
         txn.execute("SELECT id FROM hanaremote WHERE require_appcred_id = ?", [id])
         dependingHanaRemotes = []
         for r in txn.fetchall():
            dependingHanaRemotes.append(r[0])

         ## check for depending postrules
         ##
         txn.execute("SELECT id FROM postrule WHERE require_appcred_id = ?", [id])
         dependingPostrules = []
         for r in txn.fetchall():
            dependingPostrules.append(r[0])

         ## check for depending clientperms
         ##
         txn.execute("SELECT id FROM clientperm WHERE require_appcred_id = ?", [id])
         dependingClientperms = []
         for r in txn.fetchall():
            dependingClientperms.append(r[0])

         ## delete depending objects and object
         ##
         if len(dependingPostrules) > 0 or len(dependingClientperms) > 0 or len(dependingPgRemotes) > 0:
            if not cascade:
               raise Exception(URI_ERROR + "depending-objects",
                               "Cannot delete application credential: %d depending postules, %d depending clientperms, %d depending PG remotes" % (len(dependingPostrules), len(dependingClientperms), len(dependingPgRemotes)),
                               ([self.proto.shrink(URI_POSTRULE + id) for id in dependingPostrules],
                                [self.proto.shrink(URI_CLIENTPERM + id) for id in dependingClientperms],
                                [self.proto.shrink(URI_PGREMOTE + id) for id in dependingPgRemotes]))
            else:
               if len(dependingPostrules) > 0:
                  txn.execute("DELETE FROM postrule WHERE require_appcred_id = ?", [id])
               if len(dependingClientperms) > 0:
                  txn.execute("DELETE FROM clientperm WHERE require_appcred_id = ?", [id])

               if len(dependingPgRemotes) > 0:
                  txn.execute("DELETE FROM pgremote WHERE require_appcred_id = ?", [id])
               if len(dependingOraRemotes) > 0:
                  txn.execute("DELETE FROM oraremote WHERE require_appcred_id = ?", [id])
               if len(dependingHanaRemotes) > 0:
                  txn.execute("DELETE FROM hanaremote WHERE require_appcred_id = ?", [id])

         txn.execute("DELETE FROM appcredential WHERE id = ?", [id])

         ## recache in services if necessary
         ##
         services = self.proto.factory.services
         if services.has_key("restpusher"):
            services["restpusher"].recache(txn)
         if services.has_key("clientfilter"):
            services["clientfilter"].recache(txn)

         if len(dependingPgRemotes) > 0 and services.has_key("pgremoter"):
            services["pgremoter"].recache(txn)
         if len(dependingOraRemotes) > 0 and services.has_key("oraremoter"):
            services["oraremoter"].recache(txn)
         if len(dependingHanaRemotes) > 0 and services.has_key("hanaremoter"):
            services["hanaremoter"].recache(txn)

         ## dispatch on-deleted events
         ##
         for id in dependingPostrules:
            self.proto.dispatch(URI_EVENT + "on-postrule-deleted", URI_POSTRULE + id, [])

         for id in dependingClientperms:
            self.proto.dispatch(URI_EVENT + "on-clientperm-deleted", URI_CLIENTPERM + id, [])

         for id in dependingPgRemotes:
            self.proto.dispatch(URI_EVENT + "on-pgremote-deleted", URI_PGREMOTE + id, [])

         for id in dependingOraRemotes:
            self.proto.dispatch(URI_EVENT + "on-oraremote-deleted", URI_ORAREMOTE + id, [])

         for id in dependingHanaRemotes:
            self.proto.dispatch(URI_EVENT + "on-hanaremote-deleted", URI_HANAREMOTE + id, [])

         self.proto.dispatch(URI_EVENT + "on-appcred-deleted", uri, [self.proto])

         ## return deleted object URI
         ##
         return self.proto.shrink(uri)

      else:
         raise Exception(URI_ERROR + "no-such-object", "No application credentials with URI %s" % uri)


   @exportRpc("delete-appcred")
   def deleteAppCred(self, appCredUri, cascade = False):
      """
      Delete application credential, and optionally delete all depending objects.

      Parameters:

         appCredUri:          URI or CURIE of application credential to modify.
         cascade:             True/False to cascade the delete to depending post-/client rules.

      Result:

         <Application credential URI>

      Events:

         on-appcred-deleted
         on-postrule-deleted

      Errors:

         appCredUri,
         cascade:                illegal-argument

         appCredUri:             no-such-object,
                                 depending-objects
      """
      return self.proto.dbpool.runInteraction(self._deleteAppCred, appCredUri, cascade)


   def _modifyAppCred(self, txn, appCredUri, specDelta):

      ## check arguments
      ##
      if type(appCredUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument appCredUri, but got %s" % str(type(appCredUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(appCredUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT label, key, secret FROM appcredential WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check arguments
         ##
         attrs = {"label": (False,
                            [str, unicode],
                            AppCreds.APPCRED_LABEL_MIN_LENGTH,
                            AppCreds.APPCRED_LABEL_MAX_LENGTH,
                            None),
                  "key": (False,
                          [str, unicode],
                          AppCreds.APPCRED_KEY_MIN_LENGTH,
                          AppCreds.APPCRED_KEY_MAX_LENGTH,
                          AppCreds.APPCRED_KEY_PATTERN),
                  "secret": (False,
                             [str, unicode],
                             AppCreds.APPCRED_SECRET_MIN_LENGTH,
                             AppCreds.APPCRED_SECRET_MAX_LENGTH,
                             AppCreds.APPCRED_SECRET_PATTERN)}

         errcnt, errs = self.proto.checkDictArg("appcred delta spec", specDelta, attrs)

         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         if specDelta.has_key("label"):
            newval = specDelta["label"].strip()
            if newval != res[0]:
               delta["label"] = newval
               sql += ", label = ?"
               sql_vars.append(newval)

         if specDelta.has_key("key"):
            newval = specDelta["key"]
            if newval != res[1]:
               txn.execute("SELECT created FROM appcredential WHERE key = ?", [newval])
               if txn.fetchone() is not None:
                  errs["key"].append((self.proto.shrink(URI_ERROR + "duplicate-value"), "application key '%s' already exists" % newval))
               delta["key"] = newval
               sql += ", key = ?"
               sql_vars.append(newval)

         if specDelta.has_key("secret"):
            newval = specDelta["secret"]
            if newval != res[2]:
               delta["secret"] = newval
               sql += ", secret = ?"
               sql_vars.append(newval)

         if errcnt:
            raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)

         ## proceed when there is an actual change in data
         ##
         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE appcredential SET %s WHERE id = ?" % sql, sql_vars)

            ## recache in services if necessary
            ##
            services = self.proto.factory.services
            if services.has_key("restpusher"):
               services["restpusher"].recache(txn)
            if services.has_key("clientfilter"):
               services["clientfilter"].recache(txn)

            ## database remoters only care about "key" field
            if delta.has_key("key"):
               if services.has_key("pgremoter"):
                  services["pgremoter"].recache(txn)
               if services.has_key("oraremoter"):
                  services["oraremoter"].recache(txn)
               if services.has_key("hanaremoter"):
                  services["hanaremoter"].recache(txn)

            ## dispatch on-modified events
            ##
            self.proto.dispatch(URI_EVENT + "on-appcred-modified", delta, [self.proto])

            ## return object delta
            ##
            delta["uri"] = self.proto.shrink(uri)
            return delta
         else:
            ## object unchanged
            ##
            return {}

      else:
         raise Exception(URI_ERROR + "no-such-object", "No application credentials with URI %s" % uri)


   @exportRpc("modify-appcred")
   def modifyAppCred(self, appCredUri, specDelta):
      """
      Modify existing application credential.

      Parameters:

         appCredUri:          URI or CURIE of application credential to modify.
         specDelta:           Application credential change specification, a dictionary.
         specDelta[]:
            label:            Label, a string, not necessarily unique.
            key:              Key, a string, must be unique.
            secret:           Secret, a string.

      Result:

         {"uri":           <Appcred URI>,
          "modified":      <Appcred modification timestamp>,
          "label":         <Appcred label>,
          "key":           <Appcred key>,
          "secret":        <Appcred secret>}

      Events:

         on-appcred-modified

      Errors:

         appCredUri,
         specDelta:              illegal-argument

         appCredUri:             no-such-object

         specDelta[]:

            *:                   illegal-attribute-type,
                                 missing-attribute

            label,
            key,
            secret:              attribute-value-too-short,
                                 attribute-value-too-long

            key,
            secret:              attribute-value-invalid-characters

            key:                 duplicate-value

            ?:                   unknown-attribute
      """
      return self.proto.dbpool.runInteraction(self._modifyAppCred, appCredUri, specDelta)


   @exportRpc("get-appcreds")
   def getAppCreds(self):
      """
      Return list of application credentials (ordered by label/key ascending).
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, label, key, secret FROM appcredential ORDER BY label, key ASC")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_APPCRED + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "label": r[3],
                                  "key": r[4],
                                  "secret": r[5]} for r in res])
      return d
