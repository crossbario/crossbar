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


from twisted.python import log
from twisted.application import service
from twisted.enterprise import adbapi
from twisted.internet.defer import succeed


#CONNECTSTR = 'DRIVER={HANA};SERVERNODE=10.231.17.219:30015;SERVERDB=HDB;UID=TEST;PWD=Abcd2366'
CONNECTSTR = 'DRIVER={HDBODBC32};SERVERNODE=54.247.126.11:30015;SERVERDB=HDB;UID=TEST;PWD=Abcd2366'


class HanaRemoter(service.Service):
   """

   Restrictions:
   HanaRemoter is currently only able for forward RPCs to SQLScript stored procedures that:

      - have only IN parameters (no OUT, no INOUT)
      - have only primitive types for parameters
      - return a single result set (have single SELECT statement at the end of the SP body)
   """

   SERVICENAME = "SAP HANA Remoter"

   def __init__(self, dbpool, services):
      self.dbpool = dbpool
      self.services = services
      self.enabled = False

      if False and services["database"].getLicenseOptions()["hana"]:
         try:
            import pyodbc
            self.enabled = True
            self.pool1 = adbapi.ConnectionPool("pyodbc",
                                               CONNECTSTR,
                                               cp_min = 3,
                                               cp_max = 10,
                                               cp_noisy = True,
                                               cp_openfun = self.onDbConnect,
                                               cp_reconnect = True,
                                               cp_good_sql = "SELECT 1 FROM dummy")
         except Exception, e:
            log.msg("no pyodbc module")


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      self.isRunning = False


   def getRemoterStats(self):
      return [{'uri': None,
               'call-allowed': 0,
               'call-denied': 0,
               'forward-success': 0,
               'forward-failed': 0}]


   def onDbConnect(self, conn):
      log.msg("SAP HANA database connection opened")


   def _getRemotes(self, txn):
      PREFIX = "http://example.com/"
      txn.execute("SELECT schema_name, procedure_name, input_parameter_count FROM sys.PROCEDURES WHERE schema_name = 'TEST' AND output_parameter_count = 0 AND inout_parameter_count = 0 AND result_set_count = 0")
      procs = {}
      res = txn.fetchall()
      if res is not None:
         for r in res:
            uri = PREFIX + str(r[0]).lower() + "#" + str(r[1]).lower()
            statement = "{call %s.%s(%s)}" % (str(r[0]), str(r[1]), ("?," * r[2])[:-1])
            procs[uri] = (r[0], r[1], r[2], statement)
      return ('hana', procs)


   def getRemotes(self, authKey, authExtra):
      if self.enabled:
         return self.pool1.runInteraction(self._getRemotes)
      else:
         return succeed(('hana', {}))


   def _callSp(self, txn, statement, args):
      #txn.execute("{call test.echo(?)}", [args[0]])
      txn.execute(statement, args)
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


   def remoteCall(self, uri, args, extra):

      ## get protocol we are remoting for
      proto = extra[0]

      ## extract extra information from RPC call handler argument
      (schema, proc, cargs, statement) = extra[1]

      if len(args) != cargs:
         raise Exception("stored procedure %s expects %d arguments, but received %d" % (schema.upper() + "." + proc.upper(), cargs, len(args)))

      return self.pool1.runInteraction(self._callSp, statement, args)
