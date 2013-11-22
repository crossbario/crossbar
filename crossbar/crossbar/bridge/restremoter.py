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


import urlparse

from twisted.python import log
#from twisted.web.client import getPage
from crossbar.txutil import getPage, StringReceiver, StringProducer, getDomain

from twisted.internet import defer
from twisted.internet.defer import Deferred, succeed
from twisted.web.http_headers import Headers

from autobahn.wamp import json_loads, json_dumps

from crossbar.adminwebmodule.uris import URI_ERROR_REMOTING
from crossbar.adminwebmodule.uris import URI_EVENT, URI_RESTREMOTE

from remoter import Remoter



class RestRemote:
   """
   Model for a single REST Remote.
   """

   def __init__(self,
                id,
                appkey,
                rpcBaseUri,
                restBaseUrl,
                payloadFormat,
                forwardCookies,
                redirectLimit,
                connectionTimeout,
                requestTimeout,
                usePersistentConnections,
                maxPersistentConnections,
                persistentConnectionTimeout):
      self.id = id
      self.appkey = appkey
      self.rpcBaseUri = rpcBaseUri
      self.restBaseUrl = restBaseUrl
      self.restDomain = getDomain(unicode(restBaseUrl))
      self.payloadFormat = payloadFormat
      self.forwardCookies = forwardCookies
      self.redirectLimit = redirectLimit
      self.connectionTimeout = connectionTimeout
      self.requestTimeout = requestTimeout
      self.usePersistentConnections = usePersistentConnections
      self.maxPersistentConnections = maxPersistentConnections
      self.persistentConnectionTimeout = persistentConnectionTimeout


class RestRemoter(Remoter):
   """
   Provides a model cache for REST remotes and actual RPC forwarding for REST.

   TODO: Cookies!
   """

   USER_AGENT = "crossbar.io"
   """
   User agent provided in HTTP header for requests issued.
   """

   SERVICENAME = "REST Remoter"

   REMOTE_ID_BASEURI = URI_RESTREMOTE

   REMOTER_STATE_CHANGE_EVENT_URI = URI_EVENT + "on-restremoter-statechange"
   STATS_EVENT_URI = URI_EVENT + "on-restremoterstat"


   def startService(self):
      Remoter.startService(self)

      ## HTTP connection pools indexed by Ext.Direct Remote ID.
      ## Note that we usually do NOT want to recreate those on mere recaches
      ## since that would unnecessarily drop all currently kept alive connections.
      self.httppools = {}

      ## immediately cache
      self.dbpool.runInteraction(self.recache)


   def recache(self, txn):
      """
      Recache REST Remotes.
      """
      log.msg("RestRemoter.recache")

      txn.execute("SELECT a.key, r.id, r.rpc_base_uri, r.rest_base_url, r.payload_format, r.forward_cookies, r.redirect_limit, r.connection_timeout, r.request_timeout, r.max_persistent_conns, r.persistent_conn_timeout FROM restremote r LEFT OUTER JOIN appcredential a ON r.require_appcred_id = a.id ORDER BY a.key ASC, r.created ASC")
      self._cacheRestRemotes(txn.fetchall())


   def _cacheRestRemotes(self, res):
      self.remotesByAppKey = {}
      self.remotesById = {}
      n = 0
      for r in res:
         appkey = str(r[0]) if r[0] is not None else None
         id = str(r[1])
         if not self.remotesByAppKey.has_key(appkey):
            self.remotesByAppKey[appkey] = []
         usePersistentConnections = int(r[7]) > 0
         remote = RestRemote(id = id,
                             appkey = appkey,
                             rpcBaseUri = str(r[2]),
                             restBaseUrl = str(r[3]),
                             payloadFormat = str(r[4]),
                             forwardCookies = r[5] != 0,
                             redirectLimit = int(r[6]),
                             connectionTimeout = int(r[7]),
                             requestTimeout = int(r[8]),
                             usePersistentConnections = usePersistentConnections,
                             maxPersistentConnections = int(r[9]),
                             persistentConnectionTimeout = int(r[10]))
         self.remotesByAppKey[appkey].append(remote)
         self.remotesById[id] = remote

         ## avoid module level reactor import
         from twisted.web.client import HTTPConnectionPool

         if usePersistentConnections:
            ## setup HTTP Connection Pool for remote
            if not self.httppools.has_key(id) or self.httppools[id] is None:
               self.httppools[id] = HTTPConnectionPool(self.reactor, persistent = True)
            self.httppools[id].maxPersistentPerHost = remote.maxPersistentConnections
            self.httppools[id].cachedConnectionTimeout = remote.persistentConnectionTimeout
            self.httppools[id].retryAutomatically = False
         else:
            ## make sure to GC existing pool (if any)
            self.httppools[id] = None

         n += 1
      log.msg("RestRemoter._cacheRestRemotes (%d)" % n)


   def getRemotes(self, authKey, authExtra):
      """
      Get remoted API calls. This is usually called within getAuthPermissions
      on a WAMP session.
      """
      d = {}
      for remote in self.remotesByAppKey.get(authKey, []):
         d.update(self.queryApi(remote.id))
      return succeed(('rest', d))


   def queryApi(self, remoteId):
      """
      Query REST API by remote ID.
      """
      remote = self.remotesById.get(remoteId, None)
      if remote is None:
         return None
      else:
         res = {remote.rpcBaseUri + "#create": [remote.id, 'PUT'],
                remote.rpcBaseUri + "#read": [remote.id, 'GET'],
                remote.rpcBaseUri + "#update": [remote.id, 'POST'],
                remote.rpcBaseUri + "#delete": [remote.id, 'DELETE']}
         return res


   def remoteCall(self, call):
      """
      RPC handler remoting to REST servers. This method is usually
      registered via registerHandlerMethodForRpc on a WAMP protocol.
      """
      proto = call.proto
      uri = call.uri
      args = call.args

      ## extract extra information from RPC call handler argument
      (id, method) = call.extra

      ## get the REST remote onto which we will forward the call
      remote = self.remotesById[id]

      body = None

      if method in ['GET', 'DELETE']:
         if len(args) != 1:
            raise Exception(URI_ERROR_REMOTING,
                            "Invalid number of arguments (expected 1, was %d)" % len(args))
      elif method in ['PUT', 'POST']:
         if len(args) != 2:
            raise Exception(URI_ERROR_REMOTING,
                            "Invalid number of arguments (expected 2, was %d)" % len(args))
         body = json_dumps(args[1])
      else:
         ## should not arrive here!
         raise Exception("logic error")

      if remote.forwardCookies and \
         proto.cookies and \
         proto.cookies.has_key(remote.restDomain) and \
         proto.cookies[remote.restDomain] != "":

         cookie = str(proto.cookies[remote.restDomain])
      else:
         cookie = None

      if type(args[0]) not in [str, unicode]:
         raise Exception(URI_ERROR_REMOTING,
                         "Invalid type for argument 1 (expected str, was %s)" % type(args[0]))

      url = urlparse.urljoin(str(remote.restBaseUrl), str(args[0]))

      if not remote.usePersistentConnections:
         ## Do HTTP/POST as individual request
         ##

         headers = {'Content-Type': 'application/json',
                    'User-Agent': RestRemoter.USER_AGENT}

         if cookie:
            headers['Cookie'] = cookie

         d = getPage(url = url,
                     method = method,
                     postdata = body,
                     headers = headers,
                     timeout = remote.requestTimeout,
                     connectionTimeout = remote.connectionTimeout,
                     followRedirect = remote.redirectLimit > 0)

      else:
         ## Do HTTP/POST via HTTP connection pool
         ##
         ## http://twistedmatrix.com/documents/12.1.0/web/howto/client.html
         ##

         ## avoid module level reactor import
         from twisted.web.client import Agent, RedirectAgent

         headers = {'Content-Type': ['application/json'],
                    'User-Agent': [RestRemoter.USER_AGENT]}

         if cookie:
            headers['Cookie'] = [cookie]

         agent = Agent(self.reactor,
                       pool = self.httppools[remote.id],
                       connectTimeout = remote.connectionTimeout)

         if remote.redirectLimit > 0:
            agent = RedirectAgent(agent, redirectLimit = remote.redirectLimit)

         ## FIXME: honor requestTimeout
         if body:
            d = agent.request(method,
                              url,
                              Headers(headers),
                              StringProducer(body))
         else:
            d = agent.request(method,
                              url,
                              Headers(headers))

         def onResponse(response):
            if response.code == 200:
               finished = Deferred()
               response.deliverBody(StringReceiver(finished))
               return finished
            else:
               return defer.fail("%s [%s]" % (response.code, response.phrase))

         d.addCallback(onResponse)

      ## request information provided as error detail in case of call fails
      remotingRequest = {'provider': 'rest',
                         'rest-base-url': remote.restBaseUrl,
                         'use-persistent-connections': remote.usePersistentConnections,
                         'request-timeout': remote.requestTimeout,
                         'connection-timeout': remote.connectionTimeout,
                         'method': method}

      d.addCallbacks(self._onRemoteCallResult,
                     self._onRemoteCallError,
                     callbackArgs = [remotingRequest],
                     errbackArgs = [remotingRequest])

      ## FIXME!
      d.addCallback(self.onAfterRemoteCallSuccess, id)
      d.addErrback(self.onAfterRemoteCallError, id)

      return d


   def _onRemoteCallResult(self, r, remotingRequest):
      """
      Consume REST remoting result. Note that this still can trigger a WAMP exception.
      """
      try:
         if len(r) > 0:
            res = json_loads(r)
            return res
         else:
            return None
      except Exception, e:
         raise Exception(URI_ERROR_REMOTING,
                         "response payload could not be decoded",
                        {'message': str(e),
                         'response': r,
                         'request': remotingRequest})


   def _onRemoteCallError(self, e, remotingRequest):
      """
      Consume REST remoting error.
      """
      raise Exception(URI_ERROR_REMOTING,
                      "RPC could not be remoted",
                      {'message': e.getErrorMessage(),
                       'request': remotingRequest})
