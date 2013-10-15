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


from urlparse import urljoin

from autobahn.util import utcnow
from autobahn.wamp import json_dumps

from twisted.python import log
from twisted.enterprise import adbapi

from crossbar.adminwebmodule.uris import URI_EVENT, URI_PGREMOTE
from dbremoter import DbRemoter, DbRemote, DbProcedureMeta

#import json
#from decimal import Decimal
#
#class DecimalEncoder(json.JSONEncoder):
#   def default(self, obj):
#      if isinstance(obj, Decimal):
#         # print "%s" % Decimal.from_float(0.1)
#         #return "%.2f" % obj
#         return "%s" % obj
#      return json.JSONEncoder.default(self, obj)
#

## FIXME: load the following stuff dynamically, maybe at startup
#try:
#   import psycopg2
#   import psycopg2.extras
#except:
#   log.msg("psycopg2 not installed")
#else:
#   ## automatically adapt Python dictionaries to PostgreSQL JSON
#   ##
#   try:
#      ## Latest psycopg2 has builtin support
#      ##
#      psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
#   except:
#      ## PG 9.2 OIDs
#      ##
#      json_oid, jsonarray_oid = 114, 199
#
#      def cast_json(value, cur):
#         if value is None:
#            return None
#         try:
#            o = json.loads(value)
#            #o = simplejson.loads(value, use_decimal = True)
#            return o
#         except:
#            raise InterfaceError("bad JSON representation")
#
#      JSON = psycopg2.extensions.new_type((json_oid,), "JSON", cast_json)
#      psycopg2.extensions.register_type(JSON)
#      psycopg2.extensions.register_type(psycopg2.extensions.new_array_type((jsonarray_oid,), "JSON[]", JSON))



class PgRemote(DbRemote):
   """
   Model for flattened PostgreSQL database remotes.

   Objects of this class contain flattened information from the following
   service database entities:

     - pgremote
     - pgconnect
     - appcredential
   """

   def __init__(self,
                id,
                appkey,
                host,
                port,
                database,
                user,
                password,
                schemaList,
                rpcBaseUri,
                connectionPoolMinSize,
                connectionPoolMaxSize,
                connectionTimeout,
                requestTimeout):

      self.id = str(id)
      self.appkey = str(appkey) if appkey is not None else None

      self.host = str(host)
      self.port = int(port)
      self.database = str(database)
      self.user = str(user)
      self.password = str(password)

      self.schemaList = str(schemaList)
      self.rpcBaseUri = str(rpcBaseUri)

      self.connectionPoolMinSize = int(connectionPoolMinSize)
      self.connectionPoolMaxSize = int(connectionPoolMaxSize)
      self.connectionTimeout = int(connectionTimeout)
      self.requestTimeout = int(requestTimeout)

      self.pool = None
      self.poolConnections = []


   def __eq__(self, other):
      if isinstance(other, PgRemote):
         return self.id == other.id and \
                self.appkey == other.appkey and \
                self.host == other.host and \
                self.port == other.port and \
                self.database == other.database and \
                self.user == other.connectId and \
                self.password == other.password and \
                self.schemaList == other.schemaList and \
                self.rpcBaseUri == other.rpcBaseUri and \
                self.connectionPoolMinSize == other.connectionPoolMinSize and \
                self.connectionPoolMaxSize == other.connectionPoolMaxSize and \
                self.connectionTimeout == other.connectionTimeout and \
                self.requestTimeout == other.requestTimeout
      return NotImplemented


   def __repr__(self):
      r = {'id': self.id,
           'appkey': self.appkey,

           'host': self.host,
           'port': self.port,
           'database': self.database,
           'user': self.user,
           'password': self.password,

           'schemaList': self.schemaList,
           'rpcBaseUri': self.rpcBaseUri,
           'connectionPoolMinSize': self.connectionPoolMinSize,
           'connectionPoolMaxSize': self.connectionPoolMaxSize,
           'connectionTimeout': self.connectionTimeout,
           'requestTimeout': self.requestTimeout,
           }
      return json_dumps(r)


   def makePool(self):
      pool = adbapi.ConnectionPool("psycopg2",
                                    host = self.host,
                                    port = self.port,
                                    database = self.database,
                                    user = self.user,
                                    password = self.password,
                                    cp_min = self.connectionPoolMinSize,
                                    cp_max = self.connectionPoolMaxSize,
                                    cp_noisy = True,
                                    cp_openfun = self._onPoolConnectionCreated,
                                    cp_reconnect = True,
                                    cp_good_sql = "SELECT 1")
      return pool


   def _onPoolConnectionCreated(self, conn):
      ## per connection settings
      conn.autocommit = True

      ## get connection info and store that
      backendPid = conn.get_backend_pid()
      serverVersion = conn.server_version
      self.poolConnections.append((backendPid, utcnow(), serverVersion, conn))

      #log.msg("PostgreSQL pool connection for PgRemote %s created [backend PID = %s, PG version = %s]" % (self.id, backendPid, serverVersion))



class PgRemoter(DbRemoter):
   """
   Implements remoting of PostgreSQL stored procedures.
   """

   SERVICENAME = "PostgreSQL Remoter"

   LOGID = "PgRemoter"
   REMOTERID = "pg"

   REMOTE_ID_BASEURI = URI_PGREMOTE

   REMOTER_STATE_CHANGE_EVENT_URI = URI_EVENT + "on-pgremoter-statechange"
   STATS_EVENT_URI = URI_EVENT + "on-pgremoterstat"


   def recache(self, txn):
      """
      Recache PostgreSQL database remotes.

      Recaching is triggered from the following classes:

         - PgRemotes
         - PgConnects
         - AppCreds
      """
      log.msg("PgRemoter.recache")

      txn.execute("""
         SELECT
            r.id,
            a.key,
            b.host,
            b.port,
            b.database,
            b.user,
            b.password,
            r.schema_list,
            r.rpc_base_uri,
            r.connection_pool_min_size,
            r.connection_pool_max_size,
            r.connection_timeout,
            r.request_timeout
         FROM
            pgremote r
            INNER JOIN
               pgconnect b ON r.pgconnect_id = b.id
            LEFT OUTER JOIN
               appcredential a ON r.require_appcred_id = a.id
         ORDER BY
            a.key ASC,
            b.id ASC,
            r.created ASC
      """)
      remotes = txn.fetchall()
      self._cache(remotes)


   def makeRemote(self, r):
      remote = PgRemote(id = r[0],
                        appkey = r[1],
                        host = r[2],
                        port = r[3],
                        database = r[4],
                        user = r[5],
                        password = r[6],
                        schemaList = r[7],
                        rpcBaseUri = r[8],
                        connectionPoolMinSize = r[9],
                        connectionPoolMaxSize = r[10],
                        connectionTimeout = r[11],
                        requestTimeout = r[12])
      return remote


   def _getRemotes(self, txn, remote):

      ## FIXME: filter
      ##   - overloaded funs
      ##   - funs with default params
      ##   - funs with parameter types we cannot digest

      ## the procedures remoted (indexed by URI) we return
      ##
      procs = {}

      ## iterate over all Schemas defined in the remote
      ##
      for s in remote.schemaList.split(','):

         ## FIXME: are PG identifiers case-insensitive?
         ##
         schema = s.strip().lower()

         ## get info on all stored procedures in given schema for which
         ## we (the connection pool user connecting) have execute rights
         ##
         txn.execute("""
            SELECT
               n.nspname,
               p.proname,
               p.pronargs,
               p.pronargdefaults
            FROM
               pg_proc p
               INNER JOIN
                  pg_namespace n ON p.pronamespace = n.oid
            WHERE
               n.nspname = %s
               AND has_schema_privilege(current_user, n.oid, 'usage') = true
               AND has_function_privilege(current_user, p.oid, 'execute') = true
            ORDER BY
               n.nspname,
               p.proname
         """,
         [schema])

         res = txn.fetchall()
         if res is not None:
            for r in res:
               ## the RPC endpoint URI is constructed as:
               ## RPC Base URI + Schema Name + '#' + Function Name
               ##
               uri = urljoin(remote.rpcBaseUri, str(r[0]).lower() + "#" + str(r[1]).lower())

               ## the SQL statement used when calling the SP later
               ##
               statement = "SELECT %s.%s(%s)" % (str(r[0]), str(r[1]), ("%s," * r[2])[:-1])

               ## procs[uri] = (Schema Name,
               ##               Function Name,
               ##               Function Arity,
               ##               Remote ID,
               ##               SQL Statement)
               ##
               meta = DbProcedureMeta(remote.id, r[0] + '.' + r[1], r[2])
               meta.statement = statement
               procs[uri] = meta

      return procs


   def _callSp(self, txn, meta, args):

      print self.LOGID, meta.statement, args

      ## actually perform the stored procedure call and process it's result
      ##
      txn.execute(meta.statement, args)
      rr = txn.fetchall()
      res = None
      if rr is not None:
         if len(rr) > 1:
            res = []
            for r in rr:
               if len(r) > 1:
                  res.append(list(r))
               else:
                  res.append(r[0])
         else:
            if len(rr[0]) > 1:
               res = list(rr[0])
            else:
               res = rr[0][0]
      return res
