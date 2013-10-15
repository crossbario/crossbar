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
from twisted.internet import defer
from twisted.internet.defer import succeed
from twisted.internet.defer import Deferred, DeferredList

from remoter import Remoter


class DbRemote:

   # http://jcalderone.livejournal.com/32837.html !!
   def __ne__(self, other):
      result = self.__eq__(other)
      if result is NotImplemented:
         return result
      return not result


   def getPool(self):
      """
      Get the database connection pool associated with this remote. This
      will create a pool if there isn't one, and merely return the
      created one when one already exists.
      """
      if self.pool is None:
         self.pool = self.makePool()
      return self.pool


   def destroyPool(self):
      """
      Destroy the database connection pool associated with this remote - if any.
      This will release all database connections.
      """
      if self.pool is not None:
         self.pool.close()
         self.pool = None
         self.poolConnections = []


class DbProcedureMeta:
   def __init__(self,
                remoteId,
                procedure,
                cargs):
      self.remoteId = remoteId
      self.procedure = procedure
      self.cargs = cargs



class DbRemoter(Remoter):

   def __init__(self, dbpool, services):
      Remoter.__init__(self, dbpool, services)


   def startService(self):
      Remoter.startService(self)

      self.connects = {}
      self.remotesByAuthKey = {}
      self.remotesById = {}

      self.dbpool.runInteraction(self.recache)


   def stopService(self):
      Remoter.stopService(self)


   def _cache(self, res):
      for remote in self.remotesById.values():
         remote.destroyPool()

      self.remotesByAuthKey = {}
      self.remotesById = {}

      n = 0
      for r in res:

         remote = self.makeRemote(r)

         if not self.remotesByAuthKey.has_key(remote.appkey):
            self.remotesByAuthKey[remote.appkey] = []

         self.remotesByAuthKey[remote.appkey].append(remote)
         self.remotesById[remote.id] = remote

         n += 1

      log.msg("%s._cache (%d)" % (self.LOGID, n))


   def queryPool(self, remoteId):
      """
      Query the current database connection pool associated with the
      given remote.

      Returns a list of [(PostgreSQL Backend PID, Connection Creation Time: UTC as String)]
      or None if the remoteId does not exist.
      """
      remote = self.remotesById.get(remoteId, None)
      if remote:
         #return [(c[0], c[1]) for c in remote.poolConnections]
         return [c[:-1] for c in remote.poolConnections]
      else:
         return None


   def queryApi(self, remoteId):
      """
      Query the API provided by the given remote.
      """
      remote = self.remotesById.get(remoteId, None)
      if remote:
         pool = remote.getPool()
         if pool:
            return pool.runInteraction(self._getRemotes, remote)
         else:
            ## should not arrive here (that is, we should have a db connection pool setup for every remote)
            return None
      else:
         return None


   def getRemotes(self, authKey, authExtra):
      """
      Get remoted procedures.

      This will return a Twisted Deferred that yields

        ('pg', {'http://example.com/myschema#myfun': ('myschema', 'myfun', 2, pool, 'SELECT myschema.myfun(%s,%s)')})

      for a 2-ary stored procedure myschema.myfun. The dictionary is indexed by RPC endpoint URI with
      values being 5-tuples containing schema, function, arity, database connection pool and SQL statement.

      This will be called in WampCraServerProtocol.getAuthPermissions().
      """

      ## we need to collect all remoted stored procedures from all remotes
      d = []
      for remote in self.remotesByAuthKey.get(authKey, []):
         ## get the database connection pool for the authKey
         pool = remote.getPool()
         if pool:
            d.append(pool.runInteraction(self._getRemotes, remote))
         else:
            ## should not arrive here (that is, we should have
            ## a db connection pool setup for every remote)
            pass
      rd = defer.gatherResults(d, consumeErrors = True)
      def process(res):
         procs = {}
         for r in res:
            procs.update(r)
         return (self.REMOTERID, procs)
      rd.addCallback(process)
      return rd


   def remoteCall(self, call):
      """
      This method will get registered as an RPC handler via registerHandlerMethodForRpc
      within a WampCraServerProtocol instance after successful authentication.
      """
      proto = call.proto
      uri = call.uri
      args = call.args

      ## extract extra information from RPC call handler argument
      meta = call.extra

      if len(args) != meta.cargs:
         m = "stored procedure %s expects %d arguments, but received %d" % (meta.procedure, meta.cargs, len(args))
         raise Exception(m)

      remote = self.remotesById.get(meta.remoteId, None)
      if remote:
         pool = remote.getPool()
         if pool and pool.running:
            d = pool.runWithConnection(self._callSp, call)
            d.addCallback(self.onAfterRemoteCallSuccess, meta.remoteId)
            d.addErrback(self.onAfterRemoteCallError, meta.remoteId)
            return d
         else:
            raise Exception("pool disappeared or shut down")
      else:
         raise Exception("remote disappeared")
