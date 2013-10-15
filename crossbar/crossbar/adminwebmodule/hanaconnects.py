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


class HanaConnects:
   """
   SAP HANA Connects model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def checkSpec(self, spec, errs):

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


   def _createHanaConnect(self, txn, spec):

      ## check arguments
      ##
      attrs = {"label": (False, [str, unicode], 3, 20),
               "driver": (False, [str, unicode], 0, 20),
               "host": (False, [str, unicode], 0, 20),
               "port": (False, [int], 1, 65535),
               "database": (False, [str, unicode], 0, 20),
               "user": (False, [str, unicode], 0, 20),
               "password": (False, [str, unicode], 0, 20)}

      errcnt, errs = self.proto.checkDictArg("hanaconnect spec", spec, attrs)

      errcnt += self.checkSpec(spec, errs)

      self.proto.raiseDictArgException(errs)

      ## normalize args
      ##
      for p in ["driver", "database", "user"]:
         if spec.has_key(p):
            spec[p] = spec[p].upper()
      spec["label"] = spec["label"].strip()

      ## insert new object into service database
      ##
      id = newid()
      uri = URI_HANACONNECT + id
      now = utcnow()

      txn.execute("INSERT INTO hanaconnect (id, created, label, driver, host, port, database, user, password) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  [id,
                   now,
                   spec["label"],
                   spec["driver"],
                   spec["host"],
                   spec["port"],
                   spec["database"],
                   spec["user"],
                   spec["password"]])

      ## recache in services if necessary
      ##
      services = self.proto.factory.services
      if services.has_key("hanapusher"):
         services["hanapusher"].recache(txn)
      if services.has_key("hanaremoter"):
         services["hanaremoter"].recache(txn)

      obj = {"uri": uri,
             "created": now,
             "label": spec["label"],
             "driver": spec["driver"],
             "host": spec["host"],
             "port": spec["port"],
             "database": spec["database"],
             "user": spec["user"],
             "password": spec["password"]}

      ## dispatch on-created event
      ##
      self.proto.dispatch(URI_EVENT + "on-hanaconnect-created", obj, [self.proto])

      ## return complete object
      ##
      obj["uri"] = self.proto.shrink(uri)
      return obj


   @exportRpc("create-hanaconnect")
   def createHanaConnect(self, spec):
      """
      Create a new SAP HANA database connect.
      """
      return self.proto.dbpool.runInteraction(self._createHanaConnect, spec)


   def _deleteHanaConnect(self, txn, hanaConnectUri, cascade):

      ## check arguments
      ##
      if type(hanaConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument hanaConnectUri, but got %s" % str(type(hanaConnectUri)))

      if type(cascade) not in [bool]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type bool for agument cascade, but got %s" % str(type(cascade)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(hanaConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM hanaconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check for depending hanaremotes
         ##
         txn.execute("SELECT id FROM hanaremote WHERE hanaconnect_id = ?", [id])
         dependingRemotes = []
         for r in txn.fetchall():
            dependingRemotes.append(r[0])

         ## check for depending hanapushrules
         ##
         txn.execute("SELECT id FROM hanapushrule WHERE hanaconnect_id = ?", [id])
         dependingPushRules = []
         for r in txn.fetchall():
            dependingPushRules.append(r[0])

         ## delete depending objects and object
         ##
         if len(dependingRemotes) > 0 or len(dependingPushRules) > 0:
            if not cascade:
               raise Exception(URI_ERROR + "depending-objects",
                               "Cannot delete database connect: %d depending remotes, %d depending pushrules" % (len(dependingRemotes), len(dependingPushRules)),
                               ([self.proto.shrink(URI_HANAREMOTE + id) for id in dependingRemotes],
                                [self.proto.shrink(URI_HANAPUSHRULE + id) for id in dependingPushRules]))
            else:
               if len(dependingRemotes) > 0:
                  txn.execute("DELETE FROM hanaremote WHERE hanaconnect_id = ?", [id])
               if len(dependingPushRules) > 0:
                  txn.execute("DELETE FROM hanapushrule WHERE hanaconnect_id = ?", [id])

         txn.execute("DELETE FROM hanaconnect WHERE id = ?", [id])

         ## recache in services if necessary
         ##
         services = self.proto.factory.services
         if len(dependingRemotes) > 0 and services.has_key("hanaremoter"):
            services["hanaremoter"].recache(txn)

         if len(dependingPushRules) > 0 and services.has_key("hanapusher"):
            services["hanapusher"].recache(txn)

         ## dispatch on-deleted events
         ##
         for id in dependingRemotes:
            self.proto.dispatch(URI_EVENT + "on-hanaremote-deleted", URI_HANAREMOTE + id, [])

         for id in dependingPushRules:
            self.proto.dispatch(URI_EVENT + "on-hanapushrule-deleted", URI_HANAPUSHRULE + id, [])

         self.proto.dispatch(URI_EVENT + "on-hanaconnect-deleted", uri, [self.proto])

         ## return deleted object URI
         ##
         return self.proto.shrink(uri)

      else:
         raise Exception(URI_ERROR + "no-such-object", "No HANA connect with URI %s" % uri)


   @exportRpc("delete-hanaconnect")
   def deleteHanaConnect(self, hanaConnectUri, cascade = False):
      """
      Delete a SAP HANA database connect.
      """
      return self.proto.dbpool.runInteraction(self._deleteHanaConnect, hanaConnectUri, cascade)


   def _modifyHanaConnect(self, txn, hanaConnectUri, specDelta):

      ## check arguments
      ##
      if type(hanaConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument hanaConnectUri, but got %s" % str(type(hanaConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(hanaConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT label, driver, host, port, database, user, password FROM hanaconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check arguments
         ##
         attrs = {"label": (False, [str, unicode], 3, 20),
                  "driver": (False, [str, unicode], 0, 20),
                  "host": (False, [str, unicode], 0, 20),
                  "port": (False, [int], 1, 65535),
                  "database": (False, [str, unicode], 0, 20),
                  "user": (False, [str, unicode], 0, 20),
                  "password": (False, [str, unicode], 0, 20)}

         errcnt, errs = self.proto.checkDictArg("hanaconnect delta spec", specDelta, attrs)

         errcnt += self.checkSpec(specDelta, errs)

         self.proto.raiseDictArgException(errs)

         ## normalize args
         ##
         for p in ["driver", "database", "user"]:
            if specDelta.has_key(p):
               specDelta[p] = specDelta[p].upper()
         if specDelta.has_key("label"):
            specDelta["label"] = specDelta["label"].strip()

         ## compute delta and SQL
         ##
         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         for p in [('label', 0),
                   ('driver', 1),
                   ('host', 2),
                   ('port', 3),
                   ('database', 4),
                   ('user', 5),
                   ('password', 6)]:
            if specDelta.has_key(p[0]):
               newval = specDelta[p[0]]
               if newval != res[p[1]]:
                  delta[p[0]] = newval
                  sql += ", %s = ?" % p[0]
                  sql_vars.append(newval)

         ## proceed when there is an actual change in data
         ##
         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE hanaconnect SET %s WHERE id = ?" % sql, sql_vars)

            ## recache in services if necessary
            ##
            services = self.proto.factory.services
            if services.has_key("hanapusher"):
               services["hanapusher"].recache(txn)
            if services.has_key("hanaremoter"):
               services["hanaremoter"].recache(txn)

            ## dispatch on-modified events
            ##
            self.proto.dispatch(URI_EVENT + "on-hanaconnect-modified", delta, [self.proto])

            ## return object delta
            ##
            delta["uri"] = self.proto.shrink(uri)
            return delta
         else:
            ## object unchanged
            ##
            return {}

      else:
         raise Exception(URI_ERROR + "no-such-object", "No HANA connect with URI %s" % uri)


   @exportRpc("modify-hanaconnect")
   def modifyHanaConnect(self, hanaConnectUri, specDelta):
      """
      Modify a SAP HANA database connect.
      """
      return self.proto.dbpool.runInteraction(self._modifyHanaConnect, hanaConnectUri, specDelta)


   @exportRpc("get-hanaconnects")
   def getHanaConnects(self):
      """
      Return list of SAP HANA database connects.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, label, driver, host, port, database, user, password FROM hanaconnect ORDER BY label, user, database, id ASC")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_HANACONNECT + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "label": r[3],
                                  "driver": r[4],
                                  "host": r[5],
                                  "port": r[6],
                                  "database": r[7],
                                  "user": r[8],
                                  "password": r[9]} for r in res])
      return d


   def _getHanaConnectPusherState(self, txn, hanaConnectUri):

      ## check arguments
      ##
      if type(hanaConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument hanaConnectUri, but got %s" % str(type(hanaConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(hanaConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM hanaconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         if self.proto.factory.services.has_key("hanapusher"):
            return self.proto.factory.services["hanapusher"].getPusherState(id)
         else:
            raise Exception("hanapusher not running")

      else:
         raise Exception(URI_ERROR + "no-such-object", "No SAP HANA connect with URI %s" % uri)


   @exportRpc("get-hanaconnect-pusherstate")
   def getHanaConnectPusherState(self, hanaConnectUri):
      """
      Retrieve the current state of database pusher associated with this connect (if any).
      """
      return self.proto.dbpool.runInteraction(self._getHanaConnectPusherState, hanaConnectUri)


   @exportRpc("test-hanaconnect")
   def testHanaConnect(self, hanaConnectUri):
      """
      Test a SAP HANA database connect.

      This is done on a completely new database connection run from a new, short-lived background thread.
      """

      ## check arguments
      ##
      if type(hanaConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument hanaConnectUri, but got %s" % str(type(hanaConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(hanaConnectUri)
      id = self.proto.uriToId(uri)

      ## get database connection definition and test ..
      ##
      d = self.proto.dbpool.runQuery("SELECT driver, host, port, database, user, password FROM hanaconnect WHERE id = ?", [id])

      def dotest(res):
         if res is not None and len(res) > 0:

            res = res[0]

            driver = str(res[0])
            host = str(res[1])
            port = str(res[2])
            database = str(res[3])
            user = str(res[4])
            password = str(res[5])
            connectstr = 'DRIVER={%s};SERVERNODE=%s:%s;SERVERDB=%s;UID=%s;PWD=%s' % (driver, host, port, database, user, password)
            log.msg("Testing HANA connect (%s)" % connectstr)

            def test():
               import pyodbc
               conn = pyodbc.connect(connectstr)
               #conn.timeout = 3 # raises ODBC error from HANA driver: "optional feature not implemented"
               cur = conn.cursor()
               #cur.execute("SELECT now() FROM dummy")
               cur.execute("SELECT now() AS now, start_time, version, sysuuid FROM sys.m_database")
               rr = cur.fetchone()
               current_time = str(rr[0]).strip()
               start_time = str(rr[1]).strip()
               version = str(rr[2]).strip()
               sysuuid = str(uuid.UUID(binascii.b2a_hex(rr[3])))
               r = {'current-time': current_time,
                    'start-time': start_time,
                    'version': version,
                    'uuid': sysuuid}
               print r
               return r

            return deferToThread(test)

         else:
            raise Exception(URI_ERROR + "no-such-object", "No HANA connect with URI %s" % uri)

      d.addCallback(dotest)
      return d
