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


import uuid, binascii

from twisted.python import log
from twisted.internet.threads import deferToThread
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks

from netaddr.ip import IPAddress

from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

from crossbar.adminwebmodule.uris import *


class PgConnects:
   """
   PostgreSQL Connects model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _checkSpec(self, spec, errs):

      errcnt = 0

      if not errs["host"] and spec.has_key("host"):
         host = str(spec["host"])
         try:
            addr = IPAddress(host)
            spec["host"] = str(addr)
         except Exception, e:
            errs["host"].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"),
                                 "Illegal value '%s' for host (%s)." % (host, str(e))))
            errcnt += 1

      return errcnt


   def _createPgConnect(self, txn, spec):

      ## check arguments
      ##
      attrs = {"label": (False, [str, unicode], 3, 20),
               "host": (False, [str, unicode], 0, 20),
               "port": (False, [int], 1, 65535),
               "database": (False, [str, unicode], 0, 20),
               "user": (False, [str, unicode], 0, 20),
               "password": (False, [str, unicode], 0, 20),
               "connection-timeout": (False, [int], 2, 120)}

      errcnt, errs = self.proto.checkDictArg("pgconnect spec", spec, attrs)

      errcnt += self._checkSpec(spec, errs)

      self.proto.raiseDictArgException(errs)

      ## normalize args
      ##
      for p in ["label", "database", "user"]:
         if spec.has_key(p):
            spec[p] = spec[p].strip()

      ## insert new object into service database
      ##
      id = newid()
      uri = URI_PGCONNECT + id
      now = utcnow()

      txn.execute("INSERT INTO pgconnect (id, created, label, host, port, database, user, password, connection_timeout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  [id,
                   now,
                   spec["label"],
                   spec["host"],
                   spec["port"],
                   spec["database"],
                   spec["user"],
                   spec["password"],
                   spec["connection-timeout"]])

      ## recache in services if necessary
      ##
      services = self.proto.factory.services
      if services.has_key("pgpusher"):
         services["pgpusher"].recache(txn)
      if services.has_key("pgremoter"):
         services["pgremoter"].recache(txn)

      obj = {"uri": uri,
             "created": now,
             "label": spec["label"],
             "host": spec["host"],
             "port": spec["port"],
             "database": spec["database"],
             "user": spec["user"],
             "password": spec["password"],
             "connection-timeout": spec["connection-timeout"]}

      ## dispatch on-created event
      ##
      self.proto.dispatch(URI_EVENT + "on-pgconnect-created", obj, [self.proto])

      ## return complete object
      ##
      obj["uri"] = self.proto.shrink(uri)
      return obj


   @exportRpc("create-pgconnect")
   def createPgConnect(self, spec):
      """
      Create a new PostgreSQL database connect.
      """
      return self.proto.dbpool.runInteraction(self._createPgConnect, spec)


   def _deletePgConnect(self, txn, pgConnectUri, cascade):

      ## check arguments
      ##
      if type(pgConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument pgConnectUri, but got %s" % str(type(pgConnectUri)))

      if type(cascade) not in [bool]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type bool for agument cascade, but got %s" % str(type(cascade)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(pgConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM pgconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check for depending pgremotes
         ##
         txn.execute("SELECT id FROM pgremote WHERE pgconnect_id = ?", [id])
         dependingRemotes = []
         for r in txn.fetchall():
            dependingRemotes.append(r[0])

         ## check for depending pgpushrules
         ##
         txn.execute("SELECT id FROM pgpushrule WHERE pgconnect_id = ?", [id])
         dependingPushRules = []
         for r in txn.fetchall():
            dependingPushRules.append(r[0])

         ## delete depending objects and object
         ##
         if len(dependingRemotes) > 0 or len(dependingPushRules) > 0:
            if not cascade:
               raise Exception(URI_ERROR + "depending-objects",
                               "Cannot delete database connect: %d depending remotes, %d depending pushrules" % (len(dependingRemotes), len(dependingPushRules)),
                               ([self.proto.shrink(URI_PGREMOTE + id) for id in dependingRemotes],
                                [self.proto.shrink(URI_PGPUSHRULE + id) for id in dependingPushRules]))
            else:
               if len(dependingRemotes) > 0:
                  txn.execute("DELETE FROM pgremote WHERE pgconnect_id = ?", [id])
               if len(dependingPushRules) > 0:
                  txn.execute("DELETE FROM pgpushrule WHERE pgconnect_id = ?", [id])

         txn.execute("DELETE FROM pgconnect WHERE id = ?", [id])

         ## recache in services if necessary
         ##
         services = self.proto.factory.services
         if len(dependingRemotes) > 0 and services.has_key("pgremoter"):
            services["pgremoter"].recache(txn)

         if len(dependingPushRules) > 0 and services.has_key("pgpusher"):
            services["pgpusher"].recache(txn)

         ## dispatch on-deleted events
         ##
         for id in dependingRemotes:
            self.proto.dispatch(URI_EVENT + "on-pgremote-deleted", URI_PGREMOTE + id, [])

         for id in dependingPushRules:
            self.proto.dispatch(URI_EVENT + "on-pgpushrule-deleted", URI_PGPUSHRULE + id, [])

         self.proto.dispatch(URI_EVENT + "on-pgconnect-deleted", uri, [self.proto])

         ## return deleted object URI
         ##
         return self.proto.shrink(uri)

      else:
         raise Exception(URI_ERROR + "no-such-object", "No PostgreSQL connect with URI %s" % uri)


   @exportRpc("delete-pgconnect")
   def deletePgConnect(self, pgConnectUri, cascade = False):
      """
      Delete a PostgreSQL database connect.
      """
      return self.proto.dbpool.runInteraction(self._deletePgConnect, pgConnectUri, cascade)


   def _modifyPgConnect(self, txn, pgConnectUri, specDelta):

      ## check arguments
      ##
      if type(pgConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument pgConnectUri, but got %s" % str(type(pgConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(pgConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT label, host, port, database, user, password, connection_timeout FROM pgconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check arguments
         ##
         attrs = {"label": (False, [str, unicode], 3, 20),
                  "host": (False, [str, unicode], 0, 20),
                  "port": (False, [int], 1, 65535),
                  "database": (False, [str, unicode], 0, 20),
                  "user": (False, [str, unicode], 0, 20),
                  "password": (False, [str, unicode], 0, 20),
                  "connection-timeout": (False, [int], 2, 120)}

         errcnt, errs = self.proto.checkDictArg("pgconnect delta spec", specDelta, attrs)

         errcnt += self._checkSpec(specDelta, errs)

         self.proto.raiseDictArgException(errs)

         ## normalize args
         ##
         for p in ["label", "database", "user"]:
            if specDelta.has_key(p):
               specDelta[p] = specDelta[p].strip()

         ## compute delta and SQL
         ##
         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         # [(API attribute, DB column name, DB column index)]
         for p in [('label', 'label', 0),
                   ('host', 'host', 1),
                   ('port', 'port', 2),
                   ('database', 'database', 3),
                   ('user', 'user', 4),
                   ('password', 'password', 5),
                   ('connection-timeout', 'connection_timeout', 6)]:
            if specDelta.has_key(p[0]):
               newval = specDelta[p[0]]
               if newval != res[p[2]]:
                  delta[p[0]] = newval
                  sql += ", %s = ?" % p[1]
                  sql_vars.append(newval)

         ## proceed when there is an actual change in data
         ##
         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE pgconnect SET %s WHERE id = ?" % sql, sql_vars)

            ## recache in services if necessary
            ##
            services = self.proto.factory.services
            if services.has_key("pgpusher"):
               services["pgpusher"].recache(txn)
            if services.has_key("pgremoter"):
               services["pgremoter"].recache(txn)

            ## dispatch on-modified events
            ##
            self.proto.dispatch(URI_EVENT + "on-pgconnect-modified", delta, [self.proto])

            ## return object delta
            ##
            delta["uri"] = self.proto.shrink(uri)
            return delta
         else:
            ## object unchanged
            ##
            return {}

      else:
         raise Exception(URI_ERROR + "no-such-object", "No PostgreSQL connect with URI %s" % uri)


   @exportRpc("modify-pgconnect")
   def modifyPgConnect(self, pgConnectUri, specDelta):
      """
      Modify a PostgreSQL database connect.
      """
      return self.proto.dbpool.runInteraction(self._modifyPgConnect, pgConnectUri, specDelta)


   @exportRpc("get-pgconnects")
   def getPgConnects(self):
      """
      Return list of PostgreSQL database connects.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, label, host, port, database, user, password, connection_timeout FROM pgconnect ORDER BY label, user, database, id ASC")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_PGCONNECT + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "label": r[3],
                                  "host": r[4],
                                  "port": r[5],
                                  "database": r[6],
                                  "user": r[7],
                                  "password": r[8],
                                  "connection-timeout": r[9]} for r in res])
      return d


   def _getPgConnectPusherState(self, txn, pgConnectUri):

      ## check arguments
      ##
      if type(pgConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument pgConnectUri, but got %s" % str(type(pgConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(pgConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM pgconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         if self.proto.factory.services.has_key("pgpusher"):
            return self.proto.factory.services["pgpusher"].getPusherState(id)
         else:
            raise Exception("pgpusher not running")

      else:
         raise Exception(URI_ERROR + "no-such-object", "No PostgreSQL connect with URI %s" % uri)


   @exportRpc("get-pgconnect-pusherstate")
   def getPgConnectPusherState(self, pgConnectUri):
      """
      Retrieve the current state of database pusher associated with this connect (if any).
      """
      return self.proto.dbpool.runInteraction(self._getPgConnectPusherState, pgConnectUri)


   @exportRpc("test-pgconnect")
   def testPgConnect(self, pgConnectUri):
      """
      Test a PostgreSQL database connect.

      This is done on a completely new database connection run from a new, short-lived background thread.
      """

      ## check arguments
      ##
      if type(pgConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument pgConnectUri, but got %s" % str(type(pgConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(pgConnectUri)
      id = self.proto.uriToId(uri)

      ## get database connection definition and test ..
      ##
      d = self.proto.dbpool.runQuery("SELECT host, port, database, user, password, connection_timeout FROM pgconnect WHERE id = ?", [id])

      def dotest(res):
         if res is not None and len(res) > 0:

            res = res[0]

            host = str(res[0])
            port = int(res[1])
            database = str(res[2])
            user = str(res[3])
            password = str(res[4])
            connection_timeout = int(res[5])

            def test():
               import psycopg2
               conn = psycopg2.connect(host = host,
                                       port = port,
                                       database = database,
                                       user = user,
                                       password = password,
                                       connect_timeout = connection_timeout)
               conn.autocommit = True
               cur = conn.cursor()
               cur.execute("SELECT now() AS now, pg_postmaster_start_time() AS start_time, version() AS version_str, (SELECT setting FROM pg_settings WHERE name = 'server_version') AS version")

               rr = cur.fetchone()
               cur.close()
               conn.close()

               current_time = str(rr[0]).strip()
               start_time = str(rr[1]).strip()
               version_str = str(rr[2]).strip()
               version = str(rr[3]).strip()
               sysuuid = None # str(uuid.UUID(binascii.b2a_hex(rr[3])))

               r = {'current-time': current_time,
                    'start-time': start_time,
                    'version': version,
                    'version-string': version_str,
                    'uuid': sysuuid}
               return r

            return deferToThread(test)

         else:
            raise Exception(URI_ERROR + "no-such-object", "No PostgreSQL connect with URI %s" % uri)

      d.addCallback(dotest)
      return d
