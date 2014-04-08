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


import math, os, socket

from pprint import pformat, pprint

from twisted.python import log
from twisted.application import service
from twisted.internet.defer import gatherResults

from autobahn.compress import *

from autobahn.wamp import WampCraServerProtocol, WampServerFactory
from autobahn.wamp import exportRpc

import crossbar
from crossbar.tlsctx import TlsContextFactory

from crossbar.adminwebmodule.uris import *

from crossbar.bridge.extdirectremoter import ExtDirectRemoter
from crossbar.bridge.restremoter import RestRemoter

from crossbar.bridge.hanaremoter import HanaRemoter
from crossbar.bridge.pgremoter import PgRemoter
from crossbar.bridge.oraremoter import OraRemoter


import json
from crossbar.customjson import CustomJsonEncoder

from autobahn.util import newid, utcnow
import Cookie

import jinja2
import pkg_resources


class SessionInfo:
   def __init__(self, sessionId = None, authenticatedAs = None):
      self.sessionId = sessionId
      self.authenticatedAs = authenticatedAs
      self.data = {}


RPC_SUCCESS_TIMINGS = [('RECV', 'onMessageBegin', 'onBeforeCall'),
                       ('CALL', 'onBeforeCall', 'onAfterCallSuccess'),
                       ('RCLL', 'onBeforeRemoteCall', 'onAfterRemoteCallSuccess'),
                       ('SEND', 'onAfterCallSuccess', 'onAfterSendCallSuccess')]

RPC_ERROR_TIMINGS = [('RECV', 'onMessageBegin', 'onBeforeCall'),
                     ('CALL', 'onBeforeCall', 'onAfterCallError'),
                     ('RCLL', 'onBeforeRemoteCall', 'onAfterRemoteCallError'),
                     ('SEND', 'onAfterCallError', 'onAfterSendCallError')]


RPC_SUCCESS_TIMINGS = [('RECV', 'onMessageBegin', 'onBeforeCall'),
                       ('UMSH', 'onBeforeCall', 'onBeforeRemoteCall'),
                       ('RCLL', 'onBeforeRemoteCall', 'onAfterRemoteCallReceiveSuccess'),
                       ('RCLF', 'onAfterRemoteCallReceiveSuccess', 'onAfterRemoteCallSuccess'),
                       ('MRSH', 'onAfterRemoteCallSuccess', 'onAfterCallSuccess'),
                       ('SEND', 'onAfterCallSuccess', 'onAfterSendCallSuccess')]


class HubWebSocketProtocol(WampCraServerProtocol):
   """
   Autobahn WebSockets Hub Twisted/Protocol.

   Topic URIs in client permissions must have the following forms:

      http://example.com/simple
      http://example.com/foo/%(myattribute1)s/bar
      http://example.com/users/%(user)s/inbox

   and may have attached filter expression of the following form

      role == 'editor' or role == 'author'

   or

      role in ['editor', 'author'] or is_developer or age > 10
   """

   RPC_ECHO = True
   RPC_PING = True

   TESTEE_API = True


   def sendServerStatus(self, redirectUrl = None, redirectAfter = 0):
      """
      Used to send out server status/version upon receiving a HTTP/GET without
      upgrade to WebSocket header (and option serverStatus is True).
      """
      config = self.factory.services['config']
      #port = config.get('hub-websocket-port')
      #tls = config.get('hub-websocket-tls')
      wsUri = self.factory.url
      wsPath = config.get('ws-websocket-path')
      if wsPath:
         wsUri += "/" + wsPath

      try:
         page = self.factory.service.templates.get_template('cb_ws_status.html')
         self.sendHtml(page.render(redirectUrl = redirectUrl,
                                   redirectAfter = redirectAfter,
                                   cbVersion = crossbar.__version__,
                                   wsUri = wsUri))
      except Exception, e:
         log.msg("Error rendering WebSocket status page template: %s" % e)


   def testDispatch(self, topic, event, options):
      """
      Simulate a server initiated event controlled by the tester.
      """
      if options.has_key('exclude'):
         exclude = options['exclude']
      else:
         excludeMe = options.get('excludeMe', None)
         if excludeMe is None or excludeMe == True:
             exclude = [self.session_id]
         else:
             exclude = []

      exclude = self.factory.sessionIdsToProtos(exclude)

      eligible = options.get('eligible', None)
      if eligible:
         eligible = self.factory.sessionIdsToProtos(eligible)

      self.factory.dispatch(topic, event, exclude = exclude, eligible = eligible)


   def formatWiretapTimings(self, call, tdef):
      print call, tdef
      print call.timings
      print self.trackedTimings
      s = " %s | " % call.callid
      for t in tdef:
         s += t[0]
         s += ": "
         s += call.timings.diff(t[1], t[2])
         s += " | "
      s += "%s" % call.uri
      return s


   def onAfterSendCallSuccess(self, msg, call):
      if self.dispatchWiretap and call.timings:
         s = self.formatWiretapTimings(call, RPC_SUCCESS_TIMINGS)
         self.dispatchWiretap(s)


   def onAfterSendCallError(self, msg, call):
      if self.dispatchWiretap and call.timings:
         s = self.formatWiretapTimings(call, RPC_ERROR_TIMINGS)
         self.dispatchWiretap(s)


   def setWiretapMode(self, enable):
      if enable and self.factory.services.has_key("adminws"):
         def dispatchWiretap(event):
            self.factory.services["adminws"].dispatchAdminEvent(URI_WIRETAP_EVENT + self.session_id, event)
         self.dispatchWiretap = dispatchWiretap
         self.setTrackTimings(True)
         log.msg("Wiretap mode enabled on session %s" % self.session_id)
      else:
         self.dispatchWiretap = None
         self.setTrackTimings(False)
         log.msg("Wiretap mode disabled on session %s" % self.session_id)


   def getWiretapMode(self):
      return hasattr(self, 'dispatchWiretap') and self.dispatchWiretap is not None


   def onConnect(self, connectionRequest):
      protocol, headers = WampCraServerProtocol.onConnect(self, connectionRequest)
      #pprint(connectionRequest.headers)

      ua = connectionRequest.headers.get('user-agent', None)
      origin = connectionRequest.headers.get('origin', None)

      ## Crossbar.io Tracking ID
      ##
      cbtid = None
      if connectionRequest.headers.has_key('cookie'):
         try:
            cookie = Cookie.SimpleCookie()
            cookie.load(str(connectionRequest.headers['cookie']))
         except Cookie.CookieError:
            pass
         else:
            if cookie.has_key('cbtid'):
               _cbtid = cookie['cbtid'].value
               if self.factory.trackingCookies.has_key(_cbtid):
                  cbtid = _cbtid
                  #log.msg("Crossbar.io tracking ID already in cookie: %s" % cbtid)

      if cbtid is None:

         cbtid = newid()
         maxAge = 86400

         cbtData = {'created': utcnow(),
                    'maxAge': maxAge,
                    'sessions': []}

         self.factory.trackingCookies[cbtid] = cbtData

         ## do NOT add the "secure" cookie attribute! "secure" refers to the
         ## scheme of the Web page that triggered the WS, not WS itself!!
         ##
         headers['Set-Cookie'] = 'cbtid=%s;max-age=%d' % (cbtid, maxAge)
         #log.msg("Setting new Crossbar.io tracking ID in cookie: %s" % cbtid)

      self._cbtid = cbtid
      cbSessionData = {'cbtid': cbtid,
                       'ua': ua,
                       'origin': origin,
                       'connected': utcnow()}

      i = len(self.factory.trackingCookies[cbtid]['sessions'])

      self.factory.trackingCookies[cbtid]['sessions'].append(cbSessionData)
      self._cbSession = self.factory.trackingCookies[cbtid]['sessions'][i]

      return (protocol, headers)


   def onSessionOpen(self):

      self.includeTraceback = True
      self.setWiretapMode(False)
      self.sessionInfo = SessionInfo(self.session_id)

      self._cbSession['wampSessionId'] = self.session_id

      self.dbpool = self.factory.dbpool
      self.authenticatedAs = None

      if self.RPC_PING:
         self.registerForRpc(self, URI_WAMP_RPC, [HubWebSocketProtocol.ping])

      if self.RPC_ECHO:
         self.registerForRpc(self, URI_WAMP_RPC, [HubWebSocketProtocol.echo])

      if self.TESTEE_API:
         ##
         ## FIXME:
         ##   - let the user enable/disable the built-in testsuite API
         ##   - let this method be overidden, e.g. when testing Oracle integration (probably based on appkey?)
         ##
         TESTEE_CONTROL_DISPATCH = "http://api.testsuite.wamp.ws/autobahn/testee/control#dispatch"
         #TESTEE_CONTROL_DISPATCH = "http://api.testsuite.wamp.ws/testee/control#dispatch"

         self.registerMethodForRpc(TESTEE_CONTROL_DISPATCH, self, HubWebSocketProtocol.testDispatch)

      ## global client auth options
      ##
      self.clientAuthTimeout = self.factory.services["config"].get("client-auth-timeout", 0)
      self.clientAuthAllowAnonymous = self.factory.services["config"].get("client-auth-allow-anonymous", False)

      WampCraServerProtocol.onSessionOpen(self)


   def getAuthPermissions(self, authKey, authExtra):
      ## we fill in permissions here
      perms = {'permissions': {}}

      for k in ['cookies', 'referrer', 'href']:
         if authExtra.has_key(k):
            perms[k] = authExtra[k]

      ## PubSub permissions
      ##
      perms['permissions']['pubsub'] = self.factory.services["clientfilter"].getPermissions(authKey, authExtra)

      ## RPC permissions
      ##
      perms['permissions']['rpc'] = []

      if self.RPC_PING:
         perms['permissions']['rpc'].append({'uri': URI_WAMP_RPC + "ping", 'call': True})

      if self.RPC_ECHO:
         perms['permissions']['rpc'].append({'uri': URI_WAMP_RPC + "echo", 'call': True})


      remotes = []

      ## fill in REST, Ext.Direct, SAP HANA, PostgreSQL, Oracle Remoting
      ##
      for remoter in ["restremoter",
                      "extdirectremoter",
                      "hanaremoter",
                      "pgremoter",
                      "oraremoter"]:
         if self.factory.services.has_key(remoter):
            remotes.append(self.factory.services[remoter].getRemotes(authKey, authExtra))

      d = gatherResults(remotes)

      def processRemotes(rlist):
         for r in rlist:
            rtype = r[0]
            procs = r[1]
            perms[rtype] = procs
            for k in procs:
               perms['permissions']['rpc'].append({'uri': k, 'call': True})
         return perms

      d.addCallback(processRemotes)

      return d


   def getAuthSecret(self, authKey):
      return self.factory.services["clientfilter"].getAppSecret(authKey)


   def onAuthenticated(self, authKey, perms):
      """
      WAMP session authenticated. Register PubSub topics and RPC handlers.
      """
      self.authenticatedAs = authKey
      self.cookies = perms.get('cookies', None)

      self.sessionInfo.authenticatedAs = authKey

      self._cbSession['authenticated'] = utcnow()
      self._cbSession['href'] = perms.get('href', None)
      self._cbSession['referrer'] = perms.get('referrer', None)

      self.registerForPubSubFromPermissions(perms['permissions'])

      for remoter, key, method in [("restremoter", "rest", RestRemoter.remoteCall),
                                   ("extdirectremoter", "extdirect", ExtDirectRemoter.remoteCall),
                                   ("hanaremoter", "hana", HanaRemoter.remoteCall),
                                   ("pgremoter", "pg", PgRemoter.remoteCall),
                                   ("oraremoter", "ora", OraRemoter.remoteCall),
                                   ]:
         if self.factory.services.has_key(remoter):
            r = perms[key]
            for uri in r:
               self.registerHandlerMethodForRpc(uri,
                                                self.factory.services[remoter],
                                                method,
                                                r[uri])

      self.factory.dispatch("http://analytics.tavendo.de#enter", self._cbSession)


   @exportRpc("ping")
   def ping(self):
      """
      RPC call with no arguments returning nothing.
      This can be used even before session authentication to measure RTTs to servers.
      """
      return


   @exportRpc("echo")
   def echo(self, arg):
      """
      RPC call returning echo.
      This can be used even before session authentication to measure RTTs to servers.
      """
      return arg


   def connectionMade(self):
      """
      Client connected. Check connection cap, and if allowed update stats.
      """
      WampCraServerProtocol.connectionMade(self)
      self.factory.onConnectionCountChanged()


   def connectionLost(self, reason):
      """
      Client disconnected. Update stats.
      """
      WampCraServerProtocol.connectionLost(self, reason)
      self.factory.onConnectionCountChanged()

      self._cbSession['lost'] = utcnow()

      self.factory.dispatch("http://analytics.tavendo.de#leave", self._cbSession)

      #print
      #pprint(self._cbSession)
      #print
      #pprint(self.factory.trackingCookies)
      #print

      #log.msg("\n\nTraffic stats on closed connection:\n\n" + pformat(self.trafficStats.__json__()) + "\n")



class HubWebSocketFactory(WampServerFactory):
   """
   Autobahn WebSockets Hub Twisted/Factory.
   """

   protocol = HubWebSocketProtocol

   def __init__(self, url, dbpool, service, services):
      WampServerFactory.__init__(self, url, debug = False, debugWamp = False)
      self.dbpool = dbpool
      self.service = service
      self.services = services
      self.stats = {'ws-connections': 0,
                    'ws-publications': 0,
                    'ws-dispatched-success': 0,
                    'ws-dispatched-failed': 0}
      self.statsChanged = False

      self.trackingCookies = {}


   #def _serialize(self, obj):
   #   return json.dumps(obj, cls = CustomJsonEncoder)


   def setOptionsFromConfig(self):
      c = self.services["config"]

      versions = []
      if c.get("ws-allow-version-0"):
         versions.append(0)
      if c.get("ws-allow-version-8"):
         versions.append(8)
      if c.get("ws-allow-version-13"):
         versions.append(13)

      ## FIXME: enforce!!
      ##
      self.connectionCap = c.get("ws-max-connections")

      self.setProtocolOptions(versions = versions,
                              allowHixie76 = c.get("ws-allow-version-0"),
                              webStatus = c.get("ws-enable-webstatus"),
                              utf8validateIncoming = c.get("ws-validate-utf8"),
                              maskServerFrames = c.get("ws-mask-server-frames"),
                              requireMaskedClientFrames = c.get("ws-require-masked-client-frames"),
                              applyMask = c.get("ws-apply-mask"),
                              maxFramePayloadSize = c.get("ws-max-frame-size"),
                              maxMessagePayloadSize = c.get("ws-max-message-size"),
                              autoFragmentSize = c.get("ws-auto-fragment-size"),
                              failByDrop = c.get("ws-fail-by-drop"),
                              echoCloseCodeReason = c.get("ws-echo-close-codereason"),
                              openHandshakeTimeout = c.get("ws-open-handshake-timeout"),
                              closeHandshakeTimeout = c.get("ws-close-handshake-timeout"),
                              tcpNoDelay = c.get("ws-tcp-nodelay"))

      ## permessage-compression WS extension
      ##
      if c.get("ws-enable-permessage-deflate"):

         windowSize = c.get("ws-permessage-deflate-window-size")
         windowBits = int(math.log(windowSize, 2)) if windowSize != 0 else 0
         requireWindowSize = c.get("ws-permessage-deflate-require-window-size")

         def accept(offers):
            for offer in offers:
               if isinstance(offer, PerMessageDeflateOffer):
                  if windowBits != 0 and offer.acceptMaxWindowBits:
                     return PerMessageDeflateOfferAccept(offer,
                                                         requestMaxWindowBits = windowBits,
                                                         windowBits = windowBits)
                  elif windowBits == 0 or not requireWindowSize:
                     return PerMessageDeflateOfferAccept(offer)

         self.setProtocolOptions(perMessageCompressionAccept = accept)


   def startFactory(self):
      WampServerFactory.startFactory(self)
      self.setOptionsFromConfig()
      log.msg("HubWebSocketFactory started [speaking %s, %s]" % (self.protocols, self.versions))
      self.publishStats()


   def dispatchHubEvent(self, topicuri, event, exclude = [], eligible = None):
      """
      Dispatch from a REST API Push.
      """
      if exclude:
         exclude = self.sessionIdsToProtos(exclude)
      if eligible:
         eligible = self.sessionIdsToProtos(eligible)
      return WampServerFactory.dispatch(self, topicuri, event, exclude, eligible)


   def dispatch(self, topicUri, event, exclude = [], eligible = None):
      """
      Normal dispatch from a WAMP client publish.
      """
      d = WampServerFactory.dispatch(self, topicUri, event, exclude, eligible)
      d.addCallback(self.logNormalDispatch)
      return d


   def logNormalDispatch(self, r):
      delivered, requested = r
      self.stats['ws-publications'] += 1
      self.stats['ws-dispatched-success'] += delivered
      error_count = requested - delivered
      if error_count > 0:
         self.stats['ws-dispatched-failed'] += error_count
      self.statsChanged = True


   def getStats(self):
      return self.stats


   def publishStats(self):
      if self.statsChanged:
         self.services["adminws"].dispatchAdminEvent(URI_EVENT + "on-wsstat", self.stats)
         self.statsChanged = False
      self.reactor.callLater(0.2, self.publishStats)


   def onConnectionCountChanged(self):
      self.stats["ws-connections"] = self.getConnectionCount()
      self.statsChanged = True



class HubWebSocketService(service.Service):

   SERVICENAME = "App WebSocket/Web"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False
      self.factory = None
      self.wsfactory = None
      self.listener = None
      self.enableAppWeb = False

      ## Jinja2 templates for Web (like WS status page et al)
      ##
      templates_dir = os.path.abspath(pkg_resources.resource_filename("crossbar", "web/templates"))
      log.msg("Using Crossbar.io web templates from %s" % templates_dir)
      self.templates = jinja2.Environment(loader = jinja2.FileSystemLoader(templates_dir))


   def setOptionsFromConfig(self):
      if self.wsfactory:
         self.wsfactory.setOptionsFromConfig()


   def getStats(self):
      if self.isRunning and self.wsfactory:
         return self.wsfactory.getStats()


   def dispatchHubEvent(self, topicuri, event, exclude = [], eligible = None):
      if self.isRunning and self.wsfactory:
         return self.wsfactory.dispatchHubEvent(topicuri, event, exclude, eligible)


   def setWiretapMode(self, sessionid, enable):
      if self.wsfactory:
         proto = self.wsfactory.sessionIdToProto(sessionid)
         if proto:
            return proto.setWiretapMode(enable)
         else:
            raise Exception("no such session")
      else:
         raise Exception("WebSocket factory not running")


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)

      ## this is here to avoid module level reactor imports
      ## https://twistedmatrix.com/trac/ticket/6849
      ##
      from twisted.web.server import Site
      from twisted.web.static import File
      from twisted.web.resource import Resource

      from cgiresource import CgiDirectory
      from portconfigresource import addPortConfigResource

      issecure = self.services["config"]["hub-websocket-tls"]
      port = self.services["config"]["hub-websocket-port"]
      hostname = socket.getfqdn()

      ## hostname
      ## externalTls
      ## externalPort
      ## externalHostname

      acceptqueue = self.services["config"]["ws-accept-queue-size"]

      if issecure:
         contextFactory = TlsContextFactory(self.services["config"]["hub-websocket-tlskey-pem"],
                                            self.services["config"]["hub-websocket-tlscert-pem"],
                                            dhParamFilename = self.services['master'].dhParamFilename)

         uri = "wss://%s:%d" % (hostname, port)
      else:
         contextFactory = None

         uri = "ws://%s:%d" % (hostname, port)

      self.wsfactory = HubWebSocketFactory(uri, self.dbpool, self, self.services)
      #self.wsfactory.trackTimings = True

      self.enableAppWeb = self.services["config"]["service-enable-appweb"]

      if self.enableAppWeb:

         ## avoid module level reactor import
         from autobahn.resource import WebSocketResource

         ## FIXME: Site.start/stopFactory should start/stop factories wrapped as Resources
         self.wsfactory.startFactory()
         resource = WebSocketResource(self.wsfactory)
         appwebDir = self.services["master"].webdata

         templates = self.templates

         config = self.services['config']

         wsUri = uri
         wsPath = config.get('ws-websocket-path')
         if wsPath:
            wsUri += "/" + wsPath

         restUri = "dfs"
         if config.get('service-enable-restpusher'):
            restUri = ''.join(['https://' if config.get('hub-web-tls') else 'http://',
                               hostname,
                               ':',
                               str(config.get('hub-web-port'))])

         class Resource404(Resource):
            """
            Custom error page (404).
            """
            def render_GET(self, request):
               page = templates.get_template('cb_web_404.html')
               s = page.render(cbVersion = crossbar.__version__,
                               wsUri = wsUri,
                               restUri = restUri)
               return s.encode('utf8')

         ## Web directory static file serving
         ##
         root = File(appwebDir)

         ## render 404 page on any concrete path not found
         root.childNotFound = Resource404()

         ## disable directory listing and render 404
         root.directoryListing = lambda: root.childNotFound

         ## WebSocket/WAMP resource
         ##
         root.putChild(self.services["config"]["ws-websocket-path"], resource)

         ## CGI resource
         ##
         cgienable = self.services["config"]["appweb-cgi-enable"]
         cgipath = self.services["config"]["appweb-cgi-path"]
         cgiprocessor = self.services["config"]["appweb-cgi-processor"]
         if cgienable and cgipath is not None and cgipath.strip() != "" and cgiprocessor is not None and cgiprocessor.strip() != "":
            cgipath = cgipath.strip()
            cgidir = os.path.join(appwebDir, cgipath)
            cgiprocessor = cgiprocessor.strip()
            cgiresource = CgiDirectory(cgidir, cgiprocessor)
            root.putChild(cgipath, cgiresource)
            log.msg("CGI configured on path '%s' using processor '%s'" % (cgipath, cgiprocessor))
         else:
            log.msg("No CGI configured")


         ## void module level reactor import
         from autobahn.resource import HTTPChannelHixie76Aware

         factory = Site(root)
         factory.log = lambda _: None # disable any logging
         factory.protocol = HTTPChannelHixie76Aware # needed if Hixie76 is to be supported

         ## REST interface to get config values
         ##
         configPath = self.services["config"]["ws-websocket-path"] + "config"
         addPortConfigResource(self.services["config"], root, configPath)
      else:
         factory = self.wsfactory

      self.factory = factory

      if issecure:
         self.listener = self.reactor.listenSSL(port, factory, contextFactory, backlog = acceptqueue)
      else:
         self.listener = self.reactor.listenTCP(port, factory, backlog = acceptqueue)

      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      if self.listener:
         self.listener.stopListening()
         self.listener = None
         self.factory = None
         self.wsfactory = None
         self.enableAppWeb = False
      self.isRunning = False
