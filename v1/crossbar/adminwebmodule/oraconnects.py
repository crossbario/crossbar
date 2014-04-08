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


import uuid, binascii, socket, types

from twisted.python import log
from twisted.python.failure import Failure

from twisted.internet.threads import deferToThread
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks, CancelledError, succeed

from netaddr.ip import IPAddress

from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

from crossbar.txutil import isValidHostname

from crossbar.adminwebmodule.uris import *

from crossbar.bridge import oraschema
from crossbar.bridge import oraschemarepo
from crossbar.bridge import oraschemademo



class OraConnects:
   """
   Oracle connects.
   """

   # We use the same restrictions as for Oracle database name for SID, though
   # the rules for SID are actually platform dependent:
   #
   #  "Restrictions related to the valid characters in an ORACLE_SID are
   #   platform-specific. On some platforms, the SID is case-sensitive."
   #
   # http://docs.oracle.com/cd/E11882_01/server.112/e25513/initparams064.htm#REFRN10041
   # http://docs.oracle.com/cd/E11882_01/server.112/e10595/create003.htm#i1008816
   #
   ORACLE_SID_PATTERN = "^[a-zA-Z0-9_#\$]*$"
   ORACLE_SID_MIN_LENGTH = 1
   ORACLE_SID_MAX_LENGTH = 8

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _checkSpec(self, spec, specDelta, errs):

      errcnt = 0

      if not errs["host"] and specDelta.has_key("host"):
         host = str(specDelta["host"]).strip()
         try:
            addr = IPAddress(host)
            specDelta["host"] = str(addr) # return normalized IP
         except Exception, e:
            if not isValidHostname(host):
               errs["host"].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"),
                                    "Illegal value '%s' for host - not a hostname, and not a valid IP address (%s)." % (host, str(e))))
               errcnt += 1
            else:
               try:
                  a = socket.gethostbyname(host)
                  specDelta["host"] = host
               except Exception, e:
                  errs["host"].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"),
                                       "Illegal value '%s' for host - hostname could not be resolved (%s)." % (host, str(e))))
                  errcnt += 1

      if not errs['sid'] and specDelta.has_key('sid'):
         specDelta['sid'] = specDelta['sid'].strip().upper()

      if not errs['user'] and specDelta.has_key('user'):
         specDelta['user'] = specDelta['user'].strip().upper()

      if not errs['demo-user'] and specDelta.has_key('demo-user') and specDelta['demo-user'] is not None:
         specDelta['demo-user'] = specDelta['demo-user'].strip().upper()
         if specDelta['demo-user'] == "":
            specDelta['demo-user'] = None

      if not errs['demo-password'] and specDelta.has_key('demo-password') and specDelta['demo-password'] is not None:
         specDelta['demo-password'] = specDelta['demo-password'].strip()
         if specDelta['demo-password'] == "":
            specDelta['demo-password'] = None

      if not errs['label'] and specDelta.has_key('label'):
         specDelta['label'] = specDelta['label'].strip()

      return errcnt


   def _checkDupConnect2(self, txn, id, spec, specDelta, errs):
      ## check for duplicate (host, port, sid, user)
      ##
      errcnt = 0

      attrs = ['host', 'port', 'sid', 'user', 'demo-user']
      attrvals = {}
      for a in attrs:
         if not errs[a] and specDelta.has_key(a):
            attrvals[a] = specDelta[a]
         else:
            attrvals[a] = spec[a]

      if id is None:
         txn.execute("SELECT id FROM oraconnect WHERE host = ? AND port = ? AND sid = ? AND (user = ? OR demo_user = ?)",
                     [attrvals['host'], attrvals['port'], attrvals['sid'], attrvals['user'], attrvals['demo-user']])
      else:
         txn.execute("SELECT id FROM oraconnect WHERE host = ? AND port = ? AND sid = ? AND (user = ? OR demo_user = ?) AND id != ?",
                     [attrvals['host'], attrvals['port'], attrvals['sid'], attrvals['user'], attrvals['demo-user'], id])

      res = txn.fetchall()
      if res and len(res) > 0:
         for e in attrs:
            if specDelta.has_key(e):
               errs[e].append((self.proto.shrink(URI_ERROR + "duplicate-attribute-value"),
                               "%d database connect already exist for same Host, Port, SID, Repo-User/Demo-User" % len(res)))
               errcnt += 1

      return errcnt


   def _checkDupConnect(self, txn, id, spec, specDelta, errs):
      ## check for duplicate (host, port, sid)
      ##
      errcnt = 0

      attrs = ['host', 'port', 'sid']
      attrvals = {}
      for a in attrs:
         if not errs[a] and specDelta.has_key(a):
            attrvals[a] = specDelta[a]
         else:
            attrvals[a] = spec[a]

      if id is None:
         txn.execute("SELECT id FROM oraconnect WHERE host = ? AND port = ? AND sid = ?",
                     [attrvals['host'], attrvals['port'], attrvals['sid']])
      else:
         txn.execute("SELECT id FROM oraconnect WHERE host = ? AND port = ? AND sid = ? AND id != ?",
                     [attrvals['host'], attrvals['port'], attrvals['sid'], id])

      res = txn.fetchall()
      if res and len(res) > 0:
         for e in attrs:
            if specDelta.has_key(e):
               errs[e].append((self.proto.shrink(URI_ERROR + "duplicate-attribute-value"),
                               "%d database connect already exist for same Host/Port/SID" % len(res)))
               errcnt += 1

      return errcnt


   def _createOraConnect(self, txn, spec):

      ## check arguments
      ##
      attrs = {"label": (True, [str, unicode], 3, 20),
               "host": (True, [str, unicode], 0, 255),
               "port": (True, [int], 1, 65535),
               "sid": (True, [str, unicode], OraConnects.ORACLE_SID_MIN_LENGTH, OraConnects.ORACLE_SID_MAX_LENGTH, OraConnects.ORACLE_SID_PATTERN),
               "user": (True, [str, unicode], 1, 30),
               "password": (True, [str, unicode], 1, 30),
               "demo-user": (False, [str, unicode, types.NoneType], 0, 30),
               "demo-password": (False, [str, unicode, types.NoneType], 0, 30),
               "connection-timeout": (True, [int], 2, 120)}

      errcnt, errs = self.proto.checkDictArg("oraconnect spec", spec, attrs)

      errcnt += self._checkSpec({}, spec, errs)

      self.proto.raiseDictArgException(errs)

      errcnt += self._checkDupConnect(txn, None, {}, spec, errs)

      self.proto.raiseDictArgException(errs)

      if not spec.has_key("demo-user"):
         spec["demo-user"] = None

      if not spec.has_key("demo-password"):
         spec["demo-password"] = None

      ## insert new object into service database
      ##
      id = newid()
      uri = URI_ORACONNECT + id
      now = utcnow()

      txn.execute("INSERT INTO oraconnect (id, created, label, host, port, sid, user, password, demo_user, demo_password, connection_timeout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  [id,
                   now,
                   spec["label"],
                   spec["host"],
                   spec["port"],
                   spec["sid"],
                   spec["user"],
                   spec["password"],
                   spec["demo-user"],
                   spec["demo-password"],
                   spec["connection-timeout"]])

      ## recache in services if necessary
      ##
      services = self.proto.factory.services
      if services.has_key("orapusher"):
         services["orapusher"].recache(txn)
      if services.has_key("oraremoter"):
         services["oraremoter"].recache(txn)

      obj = {"uri": uri,
             "created": now,
             "label": spec["label"],
             "host": spec["host"],
             "port": spec["port"],
             "sid": spec["sid"],
             "user": spec["user"],
             "password": spec["password"],
             "demo-user": spec["demo-user"],
             "demo-password": spec["demo-password"],
             "connection-timeout": spec["connection-timeout"]}

      ## dispatch on-created event
      ##
      self.proto.dispatch(URI_EVENT + "on-oraconnect-created", obj, [self.proto])

      ## return complete object
      ##
      obj["uri"] = self.proto.shrink(uri)
      return obj


   @exportRpc("create-oraconnect")
   def createOraConnect(self, spec):
      """
      Create a new Oracle database connect.
      """
      return self.proto.dbpool.runInteraction(self._createOraConnect, spec)


   def _deleteOraConnect(self, txn, oraConnectUri, cascade):

      ## check arguments
      ##
      if type(oraConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument oraConnectUri, but got %s" % str(type(oraConnectUri)))

      if type(cascade) not in [bool]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type bool for agument cascade, but got %s" % str(type(cascade)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(oraConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM oraconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## check for depending oraremotes
         ##
         txn.execute("SELECT id FROM oraremote WHERE oraconnect_id = ?", [id])
         dependingRemotes = []
         for r in txn.fetchall():
            dependingRemotes.append(r[0])

         ## check for depending orapushrules
         ##
         txn.execute("SELECT id FROM orapushrule WHERE oraconnect_id = ?", [id])
         dependingPushRules = []
         for r in txn.fetchall():
            dependingPushRules.append(r[0])

         ## delete depending objects and object
         ##
         if len(dependingRemotes) > 0 or len(dependingPushRules) > 0:
            if not cascade:
               raise Exception(URI_ERROR + "depending-objects",
                               "Cannot delete database connect: %d depending remotes, %d depending pushrules" % (len(dependingRemotes), len(dependingPushRules)),
                               ([self.proto.shrink(URI_ORAREMOTE + id) for id in dependingRemotes],
                                [self.proto.shrink(URI_ORAPUSHRULE + id) for id in dependingPushRules]))
            else:
               if len(dependingRemotes) > 0:
                  txn.execute("DELETE FROM oraremote WHERE oraconnect_id = ?", [id])
               if len(dependingPushRules) > 0:
                  txn.execute("DELETE FROM orapushrule WHERE oraconnect_id = ?", [id])

         txn.execute("DELETE FROM oraconnect WHERE id = ?", [id])

         ## recache in services if necessary
         ##
         services = self.proto.factory.services
         if len(dependingRemotes) > 0 and services.has_key("oraremoter"):
            services["oraremoter"].recache(txn)

         if len(dependingPushRules) and services.has_key("orapusher"):
            services["orapusher"].recache(txn)

         ## dispatch on-deleted events
         ##
         for id in dependingRemotes:
            self.proto.dispatch(URI_EVENT + "on-oraremote-deleted", URI_ORAREMOTE + id, [])

         for id in dependingPushRules:
            self.proto.dispatch(URI_EVENT + "on-orapushrule-deleted", URI_ORAPUSHRULE + id, [])

         self.proto.dispatch(URI_EVENT + "on-oraconnect-deleted", uri, [self.proto])

         ## return deleted object URI
         ##
         return self.proto.shrink(uri)

      else:
         raise Exception(URI_ERROR + "no-such-object", "No Oracle connect with URI %s" % uri)


   @exportRpc("delete-oraconnect")
   def deleteOraConnect(self, oraConnectUri, cascade = False):
      """
      Delete an Oracle database connect.
      """
      return self.proto.dbpool.runInteraction(self._deleteOraConnect, oraConnectUri, cascade)


   def _modifyOraConnect(self, txn, oraConnectUri, specDelta):

      ## check arguments
      ##
      if type(oraConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument oraConnectUri, but got %s" % str(type(oraConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(oraConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT label, host, port, sid, user, password, demo_user, demo_password, connection_timeout FROM oraconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         ## existing definition
         ##
         spec = {}
         spec['label'] = res[0]
         spec['host'] = res[1]
         spec['port'] = int(res[2])
         spec['sid'] = res[3]
         spec['user'] = res[4]
         spec['password'] = res[5]
         spec['demo-user'] = res[6]
         spec['demo-password'] = res[7]
         spec['connection-timeout'] = int(res[8])

         ## check arguments
         ##
         attrs = {"label": (False, [str, unicode], 3, 20),
                  "host": (False, [str, unicode], 0, 255),
                  "port": (False, [int], 1, 65535),
                  "sid": (False, [str, unicode], OraConnects.ORACLE_SID_MIN_LENGTH, OraConnects.ORACLE_SID_MAX_LENGTH, OraConnects.ORACLE_SID_PATTERN),
                  "user": (False, [str, unicode], 1, 30),
                  "password": (False, [str, unicode], 1, 30),
                  "demo-user": (False, [str, unicode, types.NoneType], 0, 30),
                  "demo-password": (False, [str, unicode, types.NoneType], 0, 30),
                  "connection-timeout": (False, [int], 2, 120)}

         errcnt, errs = self.proto.checkDictArg("oraconnect delta spec", specDelta, attrs)

         errcnt += self._checkSpec(spec, specDelta, errs)

         errcnt += self._checkDupConnect(txn, id, spec, specDelta, errs)

         self.proto.raiseDictArgException(errs)

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
                   ('sid', 'sid', 3),
                   ('user', 'user', 4),
                   ('password', 'password', 5),
                   ('demo-user', 'demo_user', 6),
                   ('demo-password', 'demo_password', 7),
                   ('connection-timeout', 'connection_timeout', 8)]:
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
            txn.execute("UPDATE oraconnect SET %s WHERE id = ?" % sql, sql_vars)

            ## recache in services if necessary
            ##
            services = self.proto.factory.services
            if services.has_key("orapusher"):
               services["orapusher"].recache(txn)
            if services.has_key("oraremoter"):
               services["oraremoter"].recache(txn)

            ## dispatch on-modified events
            ##
            self.proto.dispatch(URI_EVENT + "on-oraconnect-modified", delta, [self.proto])

            ## return object delta
            ##
            delta["uri"] = self.proto.shrink(uri)
            return delta
         else:
            ## object unchanged
            ##
            return {}

      else:
         raise Exception(URI_ERROR + "no-such-object", "No Oracle connect with URI %s" % uri)


   @exportRpc("modify-oraconnect")
   def modifyOraConnect(self, oraConnectUri, specDelta):
      """
      Modify an Oracle database connect.
      """
      return self.proto.dbpool.runInteraction(self._modifyOraConnect, oraConnectUri, specDelta)


   @exportRpc("get-oraconnects")
   def getOraConnects(self):
      """
      Return list of Oracle database connects.
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, label, host, port, sid, user, password, demo_user, demo_password, connection_timeout FROM oraconnect ORDER BY label, user, sid, id ASC")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_ORACONNECT + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "label": r[3],
                                  "host": r[4],
                                  "port": r[5],
                                  "sid": r[6],
                                  "user": r[7],
                                  "password": r[8],
                                  "demo-user": r[9],
                                  "demo-password": r[10],
                                  "connection-timeout": r[11]} for r in res])
      return d


   def _getOraConnectPusherState(self, txn, oraConnectUri):

      ## check arguments
      ##
      if type(oraConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument oraConnectUri, but got %s" % str(type(oraConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(oraConnectUri)
      id = self.proto.uriToId(uri)

      ## only proceed when object actually exists
      ##
      txn.execute("SELECT created FROM oraconnect WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         if self.proto.factory.services.has_key("orapusher"):
            return self.proto.factory.services["orapusher"].getPusherState(id)
         else:
            raise Exception("orapusher not running")

      else:
         raise Exception(URI_ERROR + "no-such-object", "No Oracle connect with URI %s" % uri)


   @exportRpc("get-oraconnect-pusherstate")
   def getOraConnectPusherState(self, oraConnectUri):
      """
      Retrieve the current state of database pusher associated with this connect (if any).
      """
      return self.proto.dbpool.runInteraction(self._getOraConnectPusherState, oraConnectUri)


   @exportRpc("generate-ora-createschema-script")
   def generateOraCreateSchemaScript(self, user, userPassword, demoUser = None, demoPassword = None):
      """
      Generate script for creating repository schema/user.
      """
      return oraschema.getCreateUsersScript(user, userPassword, demoUser = demoUser, demoPassword = demoPassword)


   @exportRpc("generate-oraconnect-createschema-script")
   def generateOraConnectCreateSchemaScript(self, oraConnectUri = None):
      """
      Generate script for creating repository schema/user.
      """

      if oraConnectUri is not None:
         ## check arguments
         ##
         if type(oraConnectUri) not in [str, unicode]:
            raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument oraConnectUri, but got %s" % str(type(oraConnectUri)))

         ## resolve URI to database object ID
         ##
         uri = self.proto.resolveOrPass(oraConnectUri)
         id = self.proto.uriToId(uri)

         ## get database connection definition and test ..
         ##
         d = self.proto.dbpool.runQuery("SELECT user, password, demo_user, demo_password FROM oraconnect WHERE id = ?", [id])
      else:
         d = succeed([['CROSSBAR', 'crossbar', 'CROSSBARDEMO', 'crossbardemo']])

      def start(res):
         if res is not None and len(res) > 0:
            res = res[0]
            user = str(res[0])
            password = str(res[1])
            demoUser = str(res[2]) if res[2] is not None else None
            demoPassword = str(res[3]) if res[3] is not None else None
            return self.generateOraCreateSchemaScript(user, password, demoUser, demoPassword)
         else:
            raise Exception(URI_ERROR + "no-such-object", "No Oracle connect with URI %s" % uri)

      d.addCallback(start)
      return d


   @exportRpc("generate-ora-dropschema-script")
   def generateOraDropSchemaScript(self, user, demoUser = None):
      """
      Generate script for dropping repository schema/user.
      """
      return oraschema.getDropUsersScript(user, demoUser)


   @exportRpc("execute-ora-createschema-script")
   def executeOraCreateSchemaScript(self, connect, user, userPassword, demoUser = None, demoPassword = None):
      script = oraschema.getCreateUsersScript(user, userPassword, demoUser = demoUser, demoPassword = demoPassword)
      return self._dbExecuteImmediate(connect, script)


   @exportRpc("execute-ora-dropschema-script")
   def executeOraDropSchemaScript(self, connect, user, demoUser = None):
      script = oraschema.getDropUsersScript(user, demoUser)
      return self._dbExecuteImmediate(connect, script)




   @exportRpc("generate-oraconnect-dropschema-script")
   def generateOraConnectDropSchemaScript(self, oraConnectUri = None):
      """
      Generate script for dropping repository schema/user.
      """

      if oraConnectUri is not None:
         ## check arguments
         ##
         if type(oraConnectUri) not in [str, unicode]:
            raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument oraConnectUri, but got %s" % str(type(oraConnectUri)))

         ## resolve URI to database object ID
         ##
         uri = self.proto.resolveOrPass(oraConnectUri)
         id = self.proto.uriToId(uri)

         ## get database connection definition and test ..
         ##
         d = self.proto.dbpool.runQuery("SELECT user, demo_user FROM oraconnect WHERE id = ?", [id])
      else:
         d = succeed([['CROSSBAR', 'CROSSBARDEMO']])

      def start(res):
         if res is not None and len(res) > 0:
            res = res[0]
            user = str(res[0])
            demoUser = str(res[1]) if res[1] is not None else None
            return self.generateOraDropSchemaScript(user, demoUser)
         else:
            raise Exception(URI_ERROR + "no-such-object", "No Oracle connect with URI %s" % uri)

      d.addCallback(start)
      return d


   def _dbexecute(self, oraConnectUri, runme, category = "repository"):
      """
      Execute something on a fresh, short-lived database connection on a background thread.

      :param oraConnectUri: URI of Oracle connect.
      :type oraConnectUri: str
      :param runme: Callable that will get a database connection as argument and should return it's results.
      :type runme: callable
      """

      ## check arguments
      ##
      if type(oraConnectUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument oraConnectUri, but got %s" % str(type(oraConnectUri)))

      ## resolve URI to database object ID
      ##
      uri = self.proto.resolveOrPass(oraConnectUri)
      id = self.proto.uriToId(uri)

      ## get database connection definition and test ..
      ##
      d = self.proto.dbpool.runQuery("SELECT host, port, sid, user, password, demo_user, demo_password, connection_timeout FROM oraconnect WHERE id = ?", [id])

      def start(res):
         if res is not None and len(res) > 0:

            res = res[0]

            host = str(res[0])
            port = int(res[1])
            sid = str(res[2])
            user = str(res[3])
            password = str(res[4])
            demoUser = str(res[5]) if res[5] is not None else None
            demoPassword = str(res[6]) if res[6] is not None else None
            connection_timeout = int(res[7])

            if category == "demo":
               if demoUser is None or demoUser == "":
                  raise Exception(URI_ERROR + "illegal-argument", "Oracle connect with URI %s has no demo user configured" % uri)
               else:
                  user = demoUser
                  password = demoPassword
            elif category == "repository":
               pass
            else:
               raise Exception("logic error")

            def doit():
               import os
               #os.environ["NLS_LANG"] = "GERMAN_GERMANY.UTF8"
               os.environ["NLS_LANG"] = "AMERICAN_AMERICA.UTF8"
               import cx_Oracle

               try:
                  dsn = cx_Oracle.makedsn(host, port, sid)
                  conn = cx_Oracle.connect(user, password, dsn, threaded = True)

               except cx_Oracle.DatabaseError, e:
                  error, = e.args
                  code = error.code
                  offset = error.offset
                  message = error.message
                  context = error.context

                  log.msg("OraConnects._dbexecute [%s]" % str(e).strip())

                  if code == 1017:
                     ## ORA-01017: invalid username/password; logon denied
                     raise Failure(Exception(URI_ERROR + "invalid-user-or-password", "Invalid database username or password - login denied."))
                  else:
                     ## => produce generic SQL error
                     ##
                     raise Failure(Exception(URI_ERROR_SQL + ("%d" % code), message.strip()))

               except Exception, e:
                  ## => produce generic error
                  ##
                  log.msg("OraConnects._dbexecute [%s]" % str(e).strip())
                  raise Failure(Exception(URI_ERROR, str(e).strip()))

               app = self.proto.factory.services["master"]
               return runme(app, conn)

            d = deferToThread(doit)

            def onerror(failure):
               if failure.check(CancelledError):
                  raise Exception(URI_ERROR + "failure", "connection timeout")
               elif isinstance(failure, Failure):
                  raise failure
               else:
                  m = failure.getErrorMessage()
                  raise Exception(URI_ERROR + "failure", m)

            def onsuccess(r):
               r['uri'] = uri
               return r

            d.addCallback(onsuccess)
            d.addErrback(onerror)

            ## there seems to be no way of altering the connection timeout
            ## hardcoded into OCI (which when fires produces ORA-12170: TNS: Connect Timeout)
            #if connection_timeout > 0:
            #   reactor.callLater(connection_timeout, d.cancel)

            return d

         else:
            raise Exception(URI_ERROR + "no-such-object", "No Oracle connect with URI %s" % uri)

      d.addCallback(start)
      return d


   def _dbExecuteImmediate(self, connect, script):

      def doit():
         import os
         os.environ["NLS_LANG"] = "AMERICAN_AMERICA.UTF8"

         import cx_Oracle

         MODES = {'SYSDBA': cx_Oracle.SYSDBA,
                  'SYSOPER': cx_Oracle.SYSOPER}

         try:
            dsn = cx_Oracle.makedsn(connect['host'], connect['port'], connect['sid'])
            mode = connect.get('mode', 'normal').upper()
            if MODES.has_key(mode):
               conn = cx_Oracle.connect(connect['user'], connect['password'], dsn, mode = MODES[mode], threaded = True)
            else:
               conn = cx_Oracle.connect(connect['user'], connect['password'], dsn, threaded = True)

            cur = conn.cursor()
            blocks = script.split('/')
            n = 1
            for b in blocks:
               s = b.strip()
               if len(s) > 0:
                  log.msg("Executing block %d:\n%s" % (n, s))
                  cur.execute(s)
                  n += 1

         except cx_Oracle.DatabaseError, e:
            error, = e.args
            code = error.code
            offset = error.offset
            message = error.message
            context = error.context

            log.msg("Error - OraConnects._dbExecuteImmediate [%s]" % str(e).strip())

            if code == 1017:
               ## ORA-01017: invalid username/password; logon denied
               raise Failure(Exception(URI_ERROR + "invalid-user-or-password", "Invalid database username or password - login denied."))
            else:
               ## => produce generic SQL error
               ##
               raise Failure(Exception(URI_ERROR_SQL + ("%d" % code), message.strip()))

         except Exception, e:
            ## => produce generic error
            ##
            log.msg("OraConnects._dbexecute [%s]" % str(e).strip())
            raise Failure(Exception(URI_ERROR, str(e).strip()))

      d = deferToThread(doit)

      def onerror(failure):
         if failure.check(CancelledError):
            raise Exception(URI_ERROR + "failure", "connection timeout")
         elif isinstance(failure, Failure):
            raise failure
         else:
            m = failure.getErrorMessage()
            raise Exception(URI_ERROR + "failure", m)

      def onsuccess(r):
         return r

      d.addCallback(onsuccess)
      d.addErrback(onerror)

      ## there seems to be no way of altering the connection timeout
      ## hardcoded into OCI (which when fires produces ORA-12170: TNS: Connect Timeout)
      #if connection_timeout > 0:
      #   reactor.callLater(connection_timeout, d.cancel)

      return d


   @exportRpc("install-oraconnect-schema")
   def installOraConnectSchema(self, oraConnectUri, category = "repository"):
      """
      Setup schema in Oracle.
      """
      m = {'demo': oraschemademo.setupSchema,
           'repository': oraschemarepo.setupSchema}

      if m.has_key(category):
         d = self._dbexecute(oraConnectUri, m[category], category)
      else:
         raise Exception(URI_ERROR + "illegal-argument", "Invalid schema category '%s'" % category)

      def done(res):
         self.proto.dispatch(URI_EVENT + "on-oraconnect-schema-changed", res, [self.proto])
         res['uri'] = self.proto.shrink(res['uri'])
         return res

      d.addCallback(done)
      return d


   @exportRpc("reinstall-oraconnect-schema")
   def reinstallOraConnectSchema(self, oraConnectUri, category = "repository"):
      """
      Reinstall schema in Oracle.
      """
      m = {'demo': oraschemademo.reinstallSchema,
           'repository': oraschemarepo.reinstallSchema}

      if m.has_key(category):
         d = self._dbexecute(oraConnectUri, m[category], category)
      else:
         raise Exception(URI_ERROR + "illegal-argument", "Invalid schema category '%s'" % category)

      def done(res):
         self.proto.dispatch(URI_EVENT + "on-oraconnect-schema-changed", res, [self.proto])
         res['uri'] = self.proto.shrink(res['uri'])
         return res

      d.addCallback(done)
      return d


   @exportRpc("uninstall-oraconnect-schema")
   def uninstallOraConnectSchema(self, oraConnectUri, category = "repository"):
      """
      Uninstall schema from Oracle.
      """
      m = {'demo': oraschemademo.dropSchema,
           'repository': oraschemarepo.dropSchema}

      if m.has_key(category):
         d = self._dbexecute(oraConnectUri, m[category], category)
      else:
         raise Exception(URI_ERROR + "illegal-argument", "Invalid schema category '%s'" % category)

      def done(res):
         self.proto.dispatch(URI_EVENT + "on-oraconnect-schema-changed", res, [self.proto])
         res['uri'] = self.proto.shrink(res['uri'])
         return res

      d.addCallback(done)
      return d


   @exportRpc("upgrade-oraconnect-schema")
   def upgradeOraConnectSchema(self, oraConnectUri, category = "repository"):
      """
      Upgrade schema in Oracle.
      """
      m = {'demo': oraschemademo.upgradeSchema,
           'repository': oraschemarepo.upgradeSchema}

      if m.has_key(category):
         d = self._dbexecute(oraConnectUri, m[category], category)
      else:
         raise Exception(URI_ERROR + "illegal-argument", "Invalid schema category '%s'" % category)

      def done(res):
         self.proto.dispatch(URI_EVENT + "on-oraconnect-schema-changed", res, [self.proto])
         res['uri'] = self.proto.shrink(res['uri'])
         return res

      d.addCallback(done)
      return d


   @exportRpc("get-oraconnect-schema-version")
   def getOraConnectSchemaVersion(self, oraConnectUri, category = "repository"):
      """
      Get schema information from Oracle.
      """
      m = {'demo': oraschemademo.getSchemaVersion,
           'repository': oraschemarepo.getSchemaVersion}

      if m.has_key(category):
         return self._dbexecute(oraConnectUri, m[category], category)
      else:
         raise Exception(URI_ERROR + "illegal-argument", "Invalid schema category '%s'" % category)


   @exportRpc("test-oraconnect-schema")
   def testOraConnectSchema(self, oraConnectUri, category = "repository"):
      """
      Test an Oracle schema by retrieving some basic database information.
      """
      return self._dbexecute(oraConnectUri, oraschema.getDatabaseInfo, category)
