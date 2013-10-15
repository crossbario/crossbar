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


import datetime, isodate

from autobahn.wamp import json_loads, json_dumps

from autobahn.util import utcnow

from twisted.python import log
from twisted.python.failure import Failure

from crossbar.adminwebmodule.uris import URI_EVENT, URI_ORAREMOTE
from crossbar.adbapi import ConnectionPool

from dbremoter import DbRemoter, DbRemote, DbProcedureMeta

from crossbar.adminwebmodule.uris import URI_BASE, \
                                      URI_ERROR, \
                                      URI_ERROR_REMOTING, \
                                      URI_ERROR_SQL


class OraRemote(DbRemote):
   """
   Model for flattened Oracle database remotes.

   Objects of this class contain flattened information from the following
   service database entities:

     - oraremote
     - oraconnect
     - appcredential
   """

   def __init__(self,
                id,
                appkey,
                host,
                port,
                sid,
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
      self.sid = str(sid)
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
      if isinstance(other, OraRemote):
         return self.id == other.id and \
                self.appkey == other.appkey and \
                self.host == other.host and \
                self.port == other.port and \
                self.sid == other.sid and \
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
           'sid': self.sid,
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
      import os
      os.environ["NLS_LANG"] = "AMERICAN_AMERICA.UTF8"
      import cx_Oracle

      dsn = cx_Oracle.makedsn(self.host, self.port, self.sid)
      pool = ConnectionPool("cx_Oracle",
                            user = self.user,
                            password = self.password,
                            dsn = dsn,
                            threaded = True,
                            cp_min = self.connectionPoolMinSize,
                            cp_max = self.connectionPoolMaxSize,
                            cp_noisy = True,
                            cp_openfun = self._onPoolConnectionCreated,
                            cp_reconnect = True,
                            cp_good_sql = "SELECT 1 FROM dual")
      return pool


   def _onPoolConnectionCreated(self, conn):
      ## setup per connection settings

      conn.autocommit = True

      cur = conn.cursor()

      ## set session identifier to help DBAs
      cur.execute("""
                  BEGIN
                     DBMS_SESSION.SET_IDENTIFIER(:1);
                  END;
                  """, ['CROSSBAR_%s_REMOTER_%s' % (self.user.upper(), self.id)])

      ## set UTC for session
      cur.execute("ALTER SESSION SET TIME_ZONE='+00:00'")

      ## set ISO 8601 format for date/timestamp default to string conversion
      cur.execute("""
                  ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD"T"HH24:MI:SS"Z"'
                  """)
      cur.execute("""
                  ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD"T"HH24:MI:SS.FF"Z"'
                  """)
      cur.execute("""
                  ALTER SESSION SET NLS_TIMESTAMP_TZ_FORMAT = 'YYYY-MM-DD"T"HH24:MI:SS.FFTZH:TZM'
                  """)

      ## This work even when we don't have privileges on V$SESSION
      ## and returns the AUDSID
      ##
      cur.execute("SELECT sys_context('USERENV', 'SESSIONID') FROM dual")
      audsid = cur.fetchone()[0]

      ## Works only from 10g onwards
      ##
      try:
         cur.execute("SELECT sys_context('USERENV', 'SID') FROM dual")
         sid = cur.fetchone()[0]
      except:
         sid = None

      self.poolConnections.append((audsid, sid, utcnow(), conn))

      log.msg("Oracle pool connection for OraRemote %s created [AUDSID = %s, SID = %s]" % (self.id, audsid, sid))


class OraRemoter(DbRemoter):
   """
   Implements remoting of Oracle stored procedures.
   """

   SERVICENAME = "Oracle Remoter"

   LOGID = "OraRemoter"
   REMOTERID = "ora"

   REMOTE_ID_BASEURI = URI_ORAREMOTE

   REMOTER_STATE_CHANGE_EVENT_URI = URI_EVENT + "on-oraremoter-statechange"
   STATS_EVENT_URI = URI_EVENT + "on-oraremoterstat"


   def recache(self, txn):
      """
      Recache Oracle database remotes.

      Recaching is triggered from the following classes:

         - OraRemotes
         - OraConnects
         - AppCreds
      """
      log.msg("OraRemoter.recache")

      txn.execute("""
         SELECT
            r.id,
            a.key,
            b.host,
            b.port,
            b.sid,
            b.user,
            b.password,
            r.schema_list,
            r.rpc_base_uri,
            r.connection_pool_min_size,
            r.connection_pool_max_size,
            r.connection_timeout,
            r.request_timeout
         FROM
            oraremote r
            INNER JOIN
               oraconnect b ON r.oraconnect_id = b.id
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
      remote = OraRemote(id = r[0],
                         appkey = r[1],
                         host = r[2],
                         port = r[3],
                         sid = r[4],
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

      ## the procedures remoted (indexed by URI) we return
      ##
      procs = {}

      txn.execute("""
                  SELECT id,
                         schema,
                         package,
                         procedure,
                         object_id,
                         subprogram_id,
                         return_type,
                         args_cnt,
                         arg_types,
                         arg_inouts,
                         uri,
                         authkeys
                    FROM endpoint
                  """)

      res = txn.fetchall()
      if res is not None:
         for r in res:
            id = r[0]
            schema = r[1]
            package = r[2]
            procedure = r[3]
            return_type = r[6]
            args_cnt = r[7]
            arg_types = r[8]
            arg_inouts = r[9]
            uri = r[10]
            authkeys = r[11]

            meta = DbProcedureMeta(remote.id,
                                   "%s.%s.%s" % (schema, package, procedure),
                                   args_cnt)
            meta.id = id
            meta.uri = uri
            meta.return_type = return_type
            meta.arg_types = arg_types
            meta.arg_inouts = arg_inouts
            meta.arg_sess_inout = None
            for i in xrange(len(meta.arg_types)):
               if meta.arg_types[i] == 'CROSSBAR_SESSION':
                  meta.arg_sess_inout = meta.arg_inouts[i]
                  break
            procs[uri] = meta

      return procs


   def _callSp(self, conn, call):
      """
      Call a remoted stored procedure.

      This is called using ConnectionPool.runWithConnection on the
      Twisted main thread from within DbRemoter.remoteCall.

      :param conn: A database connection from the pool.
      :type conn: obj
      :param session: Information on calling WAMP session.
      :type session: Instance of SessionInfo
      :param meta: SP metadata.
      :type meta: tuple
      :param args: SP calling arguments.
      :type args: list
      :return obj -- Result from calling the SP.
      """

      session = call.proto.sessionInfo
      meta = call.extra
      args = call.args

      import cx_Oracle

      ## http://docs.oracle.com/cd/B28359_01/server.111/b28318/datatype.htm
      ## http://docs.oracle.com/cd/B28359_01/appdev.111/b28370/datatypes.htm

      ## Supported:
      ##
      ##   cx_Oracle.NUMBER
      ##   cx_Oracle.NATIVE_FLOAT
      ##   cx_Oracle.STRING
      ##   cx_Oracle.UNICODE
      ##   cx_Oracle.FIXED_CHAR
      ##   cx_Oracle.FIXED_UNICODE
      ##   cx_Oracle.DATETIME
      ##   cx_Oracle.TIMESTAMP
      ##   cx_Oracle.INTERVAL
      ##   cx_Oracle.CURSOR
      ##
      ## Unsupported:
      ##
      ##   cx_Oracle.OBJECT
      ##   cx_Oracle.ROWID
      ##   cx_Oracle.BINARY
      ##   cx_Oracle.BFILE
      ##   cx_Oracle.LOB
      ##   cx_Oracle.BLOB
      ##   cx_Oracle.CLOB
      ##   cx_Oracle.NCLOB
      ##   cx_Oracle.LONG_BINARY
      ##   cx_Oracle.LONG_STRING
      ##   cx_Oracle.LONG_UNICODE

      ## Issues:
      ##
      ##  INTERVAL YEAR TO MONTH Support
      ##    Python datetime.timedelta only supports periods up to 1 day.
      ##    isodate has it's own Duration class to represent longer periods,
      ##    but such objects can't be consumed by cx_Oracle.
      ##


      ## map of endpoint.return_type / endpoint.arg_types to
      ##
      ##    (cx_Oracle bind var type, PL/SQL type, PL/SQL caster)
      ##
      ## for input parameters
      ##
      TYPEMAP = {'NUMBER': (cx_Oracle.NUMBER, None, None),
                 'VARCHAR2': (cx_Oracle.STRING, None, None),
                 'NVARCHAR2': (cx_Oracle.UNICODE, None, None),
                 'CHAR': (cx_Oracle.FIXED_CHAR, None, None),
                 'NCHAR': (cx_Oracle.FIXED_UNICODE, None, None),
                 'BINARY_FLOAT': (cx_Oracle.NATIVE_FLOAT, None, None),
                 'BINARY_DOUBLE': (cx_Oracle.NATIVE_FLOAT, None, None),
                 'DATE': (cx_Oracle.DATETIME, None, None),
                 'TIMESTAMP': (cx_Oracle.TIMESTAMP, None, None),
                 'TIMESTAMP WITH TIME ZONE': (cx_Oracle.TIMESTAMP, None, None),
                 'TIMESTAMP WITH LOCAL TIME ZONE': (cx_Oracle.TIMESTAMP, None, None),
                 'INTERVAL DAY TO SECOND': (cx_Oracle.INTERVAL, None, None),
                 #'INTERVAL YEAR TO MONTH': (cx_Oracle.INTERVAL, None, None),
                 'REF CURSOR': (cx_Oracle.CURSOR, None, None),
                 'JSON': (cx_Oracle.CLOB, 'json', 'json'),
                 'JSON_VALUE': (cx_Oracle.CLOB, 'json_value', 'json_parser.parse_any'),
                 'JSON_LIST': (cx_Oracle.CLOB, 'json_list', 'json_list'),
                 'CROSSBAR_SESSION': (None, 'crossbar_session', 'crossbar_session')}

      ## these object types are treated specially
      ##
      JSONTYPES = ['JSON',
                   'JSON_VALUE',
                   'JSON_LIST']

      DATETIMETYPES = ['DATE', 'TIMESTAMP']

      INTERVALTYPES = ['INTERVAL DAY TO SECOND',
                       #'INTERVAL YEAR TO MONTH',
                       ]

      ## create or get prepared cursor for calling SP
      ##
      cur, extra = conn.getPrepared(meta.uri)

      if not cur:
         ## construct SQL statement for calling SP
         ##

         ## input parameters
         ##
         arg_types = []
         if len(meta.arg_types) > 0:
            ## SP takes at least 1 input parameters
            ##
            iargs = []
            i = 0
            j = 0
            while i < len(meta.arg_types):
               if meta.arg_types[i] == 'CROSSBAR_SESSION':
                  if meta.arg_inouts[i] in ['IN', 'IN/OUT']:
                     iargs.append('l_sess')
                  else:
                     raise Exception("invalid direction %s for session object parameter" % meta.arg_sess_inout)
               else:
                  cast = TYPEMAP[meta.arg_types[i]][2]
                  if cast:
                     ## parameter value is casted
                     iargs.append('%s(:in%d)' % (cast, j))
                  else:
                     ## plain parameter
                     iargs.append(':in%d' % j)
                  arg_types.append(meta.arg_types[i])
                  j += 1
               i += 1
            s_args = "(" + ','.join(iargs) + ")"
         else:
            ## SP takes no input parameters
            ##
            s_args = ""

         ## return value
         ##
         if meta.return_type is not None:
            if meta.return_type not in JSONTYPES:
               s_out = ":out := "
            else:
               s_out = ""
         else:
            s_out = ""

         ## anonymous PL/SQL block
         ##
         ## For MODIFY_PACKAGE_STATE, see:
         ##   - http://stackoverflow.com/questions/12688317/clear-oracle-session-state
         ##   - http://docs.oracle.com/cd/E11882_01/appdev.112/e25788/d_sessio.htm#CEGIICCC
         ##
         if meta.return_type in JSONTYPES:
            ## for JSON types the SQL is different since we need to cast from
            ## JSON object type to CLOB
            if meta.arg_sess_inout == "IN/OUT":
               sql = """
                     DECLARE
                        l_sess   crossbar_session := crossbar_session(:so1, :so2, JSON(:so3));
                        l_out    %s;
                     BEGIN
                        DBMS_SESSION.MODIFY_PACKAGE_STATE(DBMS_SESSION.REINITIALIZE);
                        l_out := %s%s;
                        l_out.to_clob(:out);
                        l_sess.data.to_clob(:sout);
                     END;
                     """ % (TYPEMAP[meta.return_type][1], meta.procedure, s_args)
            elif meta.arg_sess_inout == "IN":
               sql = """
                     DECLARE
                        l_sess   crossbar_session := crossbar_session(:so1, :so2, JSON(:so3));
                        l_out    %s;
                     BEGIN
                        DBMS_SESSION.MODIFY_PACKAGE_STATE(DBMS_SESSION.REINITIALIZE);
                        l_out := %s%s;
                        l_out.to_clob(:out);
                     END;
                     """ % (TYPEMAP[meta.return_type][1], meta.procedure, s_args)
            else:
               sql = """
                     DECLARE
                        l_out   %s;
                     BEGIN
                        DBMS_SESSION.MODIFY_PACKAGE_STATE(DBMS_SESSION.REINITIALIZE);
                        l_out := %s%s;
                        l_out.to_clob(:out);
                     END;
                     """ % (TYPEMAP[meta.return_type][1], meta.procedure, s_args)
         else:
            if meta.arg_sess_inout == "IN/OUT":
               sql = """
                     DECLARE
                        l_sess   crossbar_session := crossbar_session(:so1, :so2, JSON(:so3));
                     BEGIN
                        DBMS_SESSION.MODIFY_PACKAGE_STATE(DBMS_SESSION.REINITIALIZE);
                        %s%s%s;
                        l_sess.data.to_clob(:sout);
                     END;
                     """ % (s_out, meta.procedure, s_args)
            elif meta.arg_sess_inout == "IN":
               sql = """
                     DECLARE
                        l_sess   crossbar_session := crossbar_session(:so1, :so2, JSON(:so3));
                     BEGIN
                        DBMS_SESSION.MODIFY_PACKAGE_STATE(DBMS_SESSION.REINITIALIZE);
                        %s%s%s;
                     END;
                     """ % (s_out, meta.procedure, s_args)
            else:
               sql = """
                     BEGIN
                        DBMS_SESSION.MODIFY_PACKAGE_STATE(DBMS_SESSION.REINITIALIZE);
                        %s%s%s;
                     END;
                     """ % (s_out, meta.procedure, s_args)

         ## create fresh cursor and prepare SQL
         ##
         cur = conn.cursor()
         cur.prepare(sql)

         ## map var types to cx_Oracle types
         ##
         if meta.return_type in JSONTYPES:
            ## when calling a SP that returns a JSON type, the return bind var
            ## is the last, since we need to cast from JSON to CLOB/STRING
            ##
            ttypes = arg_types + [meta.return_type]
         elif meta.return_type is not None:
            ## otherwise if the SP returns something, the return bind var
            ## is the first
            ##
            ttypes = [meta.return_type] + arg_types
         else:
            ## otherwise when the SP does not return anything, bind vars
            ## are just input parameters
            ##
            ttypes = arg_types

         if meta.arg_sess_inout:
            ttypes = ['VARCHAR2', 'VARCHAR2', 'JSON'] + ttypes
            if meta.arg_sess_inout == "IN/OUT":
               ttypes.append('JSON')

         atypes = [TYPEMAP[x][0] for x in ttypes]

         ## setup cx_Oracle bind vars
         curvars = cur.setinputsizes(*atypes)

         ## save the prepared cursor and bindvars. we also save the SQL
         ## for debugging purposes
         ##
         conn.savePrepared(meta.uri, cur, (curvars, sql))

      else:
         ## cursor was saved previously - get the bind vars ..
         ##
         curvars, sql = extra


      ## set parameters and call SP
      ##

      ## indexes 'args'
      i = 0

      ## indexes 'curvars'
      if meta.return_type in JSONTYPES:
         ## json return value (needs to be unwrapped via local PL/SQL var)
         j = 0
      elif meta.return_type is not None:
         ## scalar/refcursor return
         j = 1
      else:
         ## no return value
         j = 0


      ## inject session information
      ##
      if meta.arg_sess_inout:
         curvars[0].setvalue(0, session.sessionId)
         curvars[1].setvalue(0, session.authenticatedAs)
         curvars[2].setvalue(0, json_dumps(session.data))
         j += 3

      ## indexes 'meta.arg_types'
      k = 0

      while k < len(meta.arg_types):
         if meta.arg_types[k] == 'CROSSBAR_SESSION':
            k += 1

         else:
            if meta.arg_types[k] in JSONTYPES:
               val = json_dumps(args[i])

            elif meta.arg_types[k] in DATETIMETYPES:
               ## Target argument is a DATE/TIMESTAMP. Need to convert
               ## to Python datetime.datetime from string. We use ISO 8601 format.
               ##
               if args[i] is not None:
                  try:
                     val = isodate.parse_datetime(args[i])
                  except Exception, e:
                     raise Exception("invalid value for datetime/timestamp - expected a string in ISO 8601 datetime format [%s]" % e)
               else:
                  val = None

            elif meta.arg_types[k] in INTERVALTYPES:
               ## Target argument is a INTERVAL. Need to convert
               ## to Python datetime.timedelta from string. We use ISO 8601 format.
               ##
               if args[i] is not None:
                  try:
                     val = isodate.parse_duration(args[i])
                     if not isinstance(val, datetime.timedelta):
                        ## val will be an instance of isodate.Duration, due to
                        ## limits of Python datetime.timedelta
                        raise Exception("invalid value for literal - ISO 8601 years/months currently unsupported")
                  except Exception, e:
                     raise Exception("invalid value for interval - expected a string in ISO 8601 period format [%s]" % e)
               else:
                  val = None

            else:
               val = args[i]

            curvars[j].setvalue(0, val)
            j += 1
            k += 1
            i += 1


      ## initialize CLOBs for unwrapping
      if meta.arg_sess_inout == "IN/OUT":
         curvars[-1].setvalue(0, '')
         if meta.return_type in JSONTYPES:
            curvars[-2].setvalue(0, '')
      else:
         if meta.return_type in JSONTYPES:
            curvars[-1].setvalue(0, '')


      ## run SP
      try:
         if call.timings:
            call.timings.track("onBeforeRemoteCall")

         cur.execute(None)

         if call.timings:
            call.timings.track("onAfterRemoteCallReceiveSuccess")

      except cx_Oracle.DatabaseError, e:

         if call.timings:
            call.timings.track("onAfterRemoteCallError")

         error, = e.args
         code = error.code
         offset = error.offset
         message = error.message
         context = error.context

         ## handle crossbar.io application errors
         ##
         if code == 20999:

            ## extract crossbar.io application error payload
            ##
            try:
               lines = message.splitlines()
               fl = lines[0]
               i = fl.find(':') + 2
               s = fl[i:].strip()
               o = json_loads(s)
               rest = '\n'.join(lines[1:])
            except:
               o = {}
               rest = message

            if o.has_key('uri'):
               uri = o['uri']
            else:
               uri = URI_ERROR_SQL + ("%d" % code)

            if o.has_key('desc'):
               #m = "%s\n%s" % (o['desc'], rest)
               m = o['desc']
            else:
               m = rest

            if o.has_key('detail'):
               detail = o['detail']
            elif o.has_key('callstack'):
               detail = o['callstack'].splitlines()
            else:
               detail = None

            if o.has_key('kill'):
               kill = o['kill']
            else:
               kill = False

            raise Failure(Exception(uri, m, detail, kill))

         else:
            ## => produce generic SQL error
            ##
            raise Failure(Exception(URI_ERROR_SQL + ("%d" % code), message))

      except Exception, e:

         if call.timings:
            call.timings.track("onAfterRemoteCallError")

         ## => produce generic error
         ##
         raise Failure(Exception(URI_ERROR, str(e)))


      ## get result
      if meta.arg_sess_inout == "IN/OUT":
         sessRes = json_loads(curvars[-1].getvalue().read())
         session.data = sessRes

      if meta.return_type in JSONTYPES:
         ## result needs to be extracted from JSON value
         ##
         if meta.arg_sess_inout == "IN/OUT":
            res = json_loads(curvars[-2].getvalue().read())
         else:
            res = json_loads(curvars[-1].getvalue().read())

      else:
         if meta.arg_sess_inout:
            ri = 3
         else:
            ri = 0

         if meta.return_type == 'REF CURSOR':
            ## result is a REFCURSOR: get and read from it
            ##
            refcur = curvars[ri].getvalue()
            if refcur is not None:
               res = refcur.fetchall()
            else:
               res = None

         elif meta.return_type in DATETIMETYPES:
            ## Result is a Python datetime.datetime object
            ##
            ## Need to convert to string for later serialization to JSON. We use ISO 8601 format.
            ##
            ## Note: we do not use isodate module currently (as we do for parsing),
            ## since "time formating does not allow to create fractional representations"
            ##
            res = curvars[ri].getvalue()
            if res is not None:
               res = res.isoformat()

         elif meta.return_type in INTERVALTYPES:
            ## Result is a Python datetime.timedelta object
            ##
            ## Need to convert to string for later serialization to JSON. We use ISO 8601 format.
            ##
            res = curvars[ri].getvalue()
            if res is not None:
               res = isodate.duration_isoformat(res)

         elif meta.return_type is not None:
            ## result is a scalar value
            ##
            res = curvars[ri].getvalue()

         else:
            ## no return value (a procedure)
            ##
            res = None

      if call.timings:
         call.timings.track("onAfterRemoteCallSuccess")

      return res
