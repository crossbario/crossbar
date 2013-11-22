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
from twisted.internet.defer import Deferred
from twisted.web.http_headers import Headers

from autobahn.wamp import WampProtocol
from autobahn.wamp import json_loads, json_dumps

from crossbar.adminwebmodule.uris import URI_ERROR_REMOTING
from crossbar.adminwebmodule.uris import URI_EVENT, URI_EXTDIRECTREMOTE

from remoter import Remoter



class ExtDirectRemote:
   """
   Model for a single Ext.Direct Remote.
   """

   def __init__(self,
                id,
                appkey,
                rpcBaseUri,
                routerUrl,
                apiUrl,
                apiObject,
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
      self.routerUrl = routerUrl
      self.routerDomain = getDomain(unicode(routerUrl))
      self.apiUrl = apiUrl
      self.apiObject = apiObject
      self.forwardCookies = forwardCookies
      self.redirectLimit = redirectLimit
      self.connectionTimeout = connectionTimeout
      self.requestTimeout = requestTimeout
      self.usePersistentConnections = usePersistentConnections
      self.maxPersistentConnections = maxPersistentConnections
      self.persistentConnectionTimeout = persistentConnectionTimeout


class ExtDirectRemoter(Remoter):
   """
   Provides a model cache for Ext.Direct remotes and actual API query
   and RPC forwarding for Ext.Direct.

   TODO: Cookies!
   """

   USER_AGENT = "crossbar.io"
   """
   User agent provided in HTTP header for requests issued.
   """

   SERVICENAME = "Ext.Direct Remoter"

   REMOTE_ID_BASEURI = URI_EXTDIRECTREMOTE

   REMOTER_STATE_CHANGE_EVENT_URI = URI_EVENT + "on-extdirectremoter-statechange"
   STATS_EVENT_URI = URI_EVENT + "on-extdirectremoterstat"


   def startService(self):
      Remoter.startService(self)

      ## HTTP connection pools indexed by Ext.Direct Remote ID.
      ## Note that we usually do NOT want to recreate those on mere recaches
      ## since that would unnecessarily drop all currently kept alive connections.
      self.httppools = {}

      ## immedialy cache
      self.dbpool.runInteraction(self.recache)


   def recache(self, txn):
      """
      Recache Ext.Direct Remotes.
      """
      log.msg("ExtDirectRemoter.recache")

      txn.execute("SELECT a.key, r.id, r.rpc_base_uri, r.router_url, r.api_url, r.api_object, r.forward_cookies, r.redirect_limit, r.connection_timeout, r.request_timeout, r.max_persistent_conns, r.persistent_conn_timeout FROM extdirectremote r LEFT OUTER JOIN appcredential a ON r.require_appcred_id = a.id ORDER BY a.key ASC, r.created ASC")
      self._cacheExtDirectRemotes(txn.fetchall())


   def _cacheExtDirectRemotes(self, res):
      self.remotesByAppKey = {}
      self.remotesById = {}
      n = 0
      for r in res:
         appkey = str(r[0]) if r[0] is not None else None
         id = str(r[1])
         if not self.remotesByAppKey.has_key(appkey):
            self.remotesByAppKey[appkey] = []
         usePersistentConnections = int(r[8]) > 0
         remote = ExtDirectRemote(id = id,
                                  appkey = appkey,
                                  rpcBaseUri = str(r[2]),
                                  routerUrl = str(r[3]),
                                  apiUrl = str(r[4]),
                                  apiObject = str(r[5]),
                                  forwardCookies = r[6] != 0,
                                  redirectLimit = int(r[7]),
                                  connectionTimeout = int(r[8]),
                                  requestTimeout = int(r[9]),
                                  usePersistentConnections = usePersistentConnections,
                                  maxPersistentConnections = int(r[10]),
                                  persistentConnectionTimeout = int(r[11]))
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
      log.msg("ExtDirectRemoter._cacheExtDirectRemotes (%d)" % n)


   def getRemotes(self, authKey, authExtra):
      """
      Get remoted API calls. This is usually called within getAuthPermissions
      on a WAMP session.
      """
      d = []
      for remote in self.remotesByAppKey.get(authKey, []):
         d.append(self.queryApi(remote.id))
      rd = defer.gatherResults(d, consumeErrors = True)
      def process(res):
         l = {}
         for k in res:
            for p in k:
               l[p] = k[p]
         return ('extdirect', l)
      rd.addCallback(process)
      return rd


   def queryApi(self, remoteId):
      """
      Query Ext.Direct API by remote ID.
      """
      remote = self.remotesById.get(remoteId, None)
      if remote is None:
         return None

      if not remote.usePersistentConnections:
         ## Do HTTP/POST as individual request
         ##
         d = getPage(url = remote.apiUrl,
                     method = 'GET',
                     headers = {'User-Agent': ExtDirectRemoter.USER_AGENT},
                     timeout = remote.requestTimeout,
                     connectionTimeout = remote.connectionTimeout,
                     followRedirect = remote.redirectLimit > 0)

      else:
         ## Do HTTP/POST via HTTP connection pool
         ##

         ## avoid module level reactor import
         from twisted.web.client import Agent, RedirectAgent

         agent = Agent(self.reactor,
                       pool = self.httppools[remote.id],
                       connectTimeout = remote.connectionTimeout)

         if remote.redirectLimit > 0:
            agent = RedirectAgent(agent, redirectLimit = remote.redirectLimit)

         ## FIXME: honor requestTimeout
         d = agent.request('GET',
                           remote.apiUrl,
                           Headers({'User-Agent': [ExtDirectRemoter.USER_AGENT]}))

         def onResponse(response):
            if response.code == 200:
               finished = Deferred()
               response.deliverBody(StringReceiver(finished))
               return finished
            else:
               return defer.fail("%s [%s]" % (response.code, response.phrase))

         d.addCallback(onResponse)

      apiRequest = {'provider': 'extdirect',
                    'api-url': remote.apiUrl,
                    'use-persistent-connections': remote.usePersistentConnections,
                    'request-timeout': remote.requestTimeout,
                    'connection-timeout': remote.connectionTimeout}

      d.addCallbacks(self._onQueryApiResult,
                     self._onQueryApiError,
                     callbackArgs = [remote, apiRequest],
                     errbackArgs = [apiRequest])

      return d


   def _onQueryApiResult(self, res, remote, apiRequest):
      """
      Consume Ext.Direct API request result.
      """
      ## cut out JSON with API definition
      ## FIXME: make this more robust!
      i1 = res.find(remote.apiObject)
      if i1 < 0:
         raise Exception(URI_ERROR_REMOTING,
                         "API object could not be found in response payload",
                        {'message': "The API object %s could not be found in the response payload" % remote.apiObject,
                         'response': res,
                         'request': apiRequest})
      i2 = res.find("=", i1) + 1
      r = res[i2:len(res) - 1].strip()

      ## parse JSON API definition
      try:
         o = json_loads(r)
      except Exception, e:
         raise Exception(URI_ERROR_REMOTING,
                         "remoting API response payload could not be decoded",
                        {'message': str(e),
                         'response': res,
                         'json': r,
                         'request': apiRequest})

      ## result set is dictionary indexed by RPC URI containing tuples: (Remote ID, Action, Name, ArgsCount)
      procs = {}
      for c in o['actions']:
         for p in o['actions'][c]:
            if p.has_key('len'):
               ## FIXME? We map to a fixed format URI = <RPC Base URI>/<Action>#<Name>
               procUri = urlparse.urljoin(remote.rpcBaseUri, str(c)) + "#%s" % str(p['name'])
               procs[procUri] = [remote.id, str(c), str(p['name']), int(p['len'])]
            else:
               ## FIXME: handle procedures with named arguments
               pass
      return procs


   def _onQueryApiError(self, e, apiRequest):
      """
      Consume Ext.Direct API request error.
      """
      raise Exception(URI_ERROR_REMOTING,
                      "remoting API could not be queried",
                      {'message': e.getErrorMessage(),
                       'request': apiRequest})


   def remoteCall(self, call):
      """
      RPC handler remoting to Ext.Direct servers. This method is usually
      registered via registerHandlerMethodForRpc on a WAMP protocol.
      """
      proto = call.proto
      uri = call.uri
      args = call.args

      ## extract extra information from RPC call handler argument
      (id, action, method, _) = call.extra

      ## get the Ext.Direct remote onto which we will forward the call
      remote = self.remotesById[id]

      ## construct the POST body
      d = {'action': action,
           'method': method,
           'data': args,
           'type': 'rpc',
           'tid': 1}
      body = json_dumps(d)

      if remote.forwardCookies and \
         proto.cookies and \
         proto.cookies.has_key(remote.routerDomain) and \
         proto.cookies[remote.routerDomain] != "":

         cookie = str(proto.cookies[remote.routerDomain])
      else:
         cookie = None

      if not remote.usePersistentConnections:
         ## Do HTTP/POST as individual request
         ##

         headers = {'Content-Type': 'application/json',
                    'User-Agent': ExtDirectRemoter.USER_AGENT}

         if cookie:
            headers['Cookie'] = cookie

         d = getPage(url = remote.routerUrl,
                     method = 'POST',
                     postdata = body,
                     headers = headers,
                     timeout = remote.requestTimeout,
                     connectionTimeout = remote.connectionTimeout,
                     followRedirect = remote.redirectLimit > 0)

      else:
         ## Do HTTP/POST via HTTP connection pool
         ##

         headers = {'Content-Type': ['application/json'],
                    'User-Agent': [ExtDirectRemoter.USER_AGENT]}

         if cookie:
            headers['Cookie'] = [cookie]

         agent = Agent(self.reactor,
                       pool = self.httppools[remote.id],
                       connectTimeout = remote.connectionTimeout)

         if remote.redirectLimit > 0:
            agent = RedirectAgent(agent, redirectLimit = remote.redirectLimit)

         ## FIXME: honor requestTimeout
         d = agent.request('POST',
                           remote.routerUrl,
                           Headers(headers),
                           StringProducer(body))

         def onResponse(response):
            if response.code == 200:
               finished = Deferred()
               response.deliverBody(StringReceiver(finished))
               return finished
            else:
               return defer.fail("%s [%s]" % (response.code, response.phrase))

         d.addCallback(onResponse)

      ## request information provided as error detail in case of call fails
      remotingRequest = {'provider': 'extdirect',
                         'router-url': remote.routerUrl,
                         'use-persistent-connections': remote.usePersistentConnections,
                         'request-timeout': remote.requestTimeout,
                         'connection-timeout': remote.connectionTimeout,
                         'action': action,
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
      Consume Ext.Direct remoting result. Note that this still can trigger a WAMP exception.
      """
      try:
         res = json_loads(r)
      except Exception, e:
         raise Exception(URI_ERROR_REMOTING,
                         "response payload could not be decoded",
                        {'message': str(e),
                         'response': r,
                         'request': remotingRequest})
      if type(res) != dict:
         raise Exception(URI_ERROR_REMOTING,
                         "invalid response (Ext.Direct response not a dict (was %s)" % type(res),
                         {'response': res,
                          'request': remotingRequest})
      if res.has_key('type'):
         if res['type'] == 'rpc':
            if res.has_key('result'):
               return res['result']
            else:
               raise Exception(URI_ERROR_REMOTING,
                               "invalid response (Ext.Direct response missing field 'result')",
                               {'response': res,
                                'request': remotingRequest})
         elif res['type'] == 'exception':
            details = {}
            details['request'] = remotingRequest
            details['where'] = res.get('where', None)
            raise Exception(WampProtocol.ERROR_URI_GENERIC,
                            res.get('message', None),
                            details)
         else:
            raise Exception(URI_ERROR_REMOTING,
                            "invalid response (Ext.Direct response field 'type' unknown value '%s')" % res['type'],
                            {'response': res,
                             'request': remotingRequest})
      else:
         raise Exception(URI_ERROR_REMOTING,
                         "invalid response (Ext.Direct response missing field 'type')",
                         {'response': res,
                          'request': remotingRequest})


   def _onRemoteCallError(self, e, remotingRequest):
      """
      Consume Ext.Direct remoting error.
      """
      raise Exception(URI_ERROR_REMOTING,
                      "RPC could not be remoted",
                      {'message': e.getErrorMessage(),
                       'request': remotingRequest})
