###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
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

from __future__ import absolute_import

import datetime

from autobahn.twisted.wamp import ApplicationSession

from twisted.python import log
from autobahn.twisted.websocket import WampWebSocketServerProtocol, \
                                       WampWebSocketServerFactory, \
                                       WampWebSocketClientProtocol, \
                                       WampWebSocketClientFactory

from twisted.internet.defer import Deferred

import json
import urllib
import Cookie

from autobahn import util
from autobahn.websocket import http
from autobahn.websocket.compress import *

from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSessionFactory
from autobahn.wamp.protocol import RouterSession
from autobahn.wamp import types
from autobahn.wamp import message

import crossbar



class CrossbarWampWebSocketServerProtocol(WampWebSocketServerProtocol):

   ## authid -> cookie -> set(connection)

   def onConnect(self, request):

      protocol, headers = WampWebSocketServerProtocol.onConnect(self, request)

      self._origin = request.origin

      ## transport authentication
      ##
      self._authid = None
      self._authrole = None
      self._authmethod = None

      ## cookie tracking
      ##
      self._cbtid = None
      if 'cookie' in self.factory._config:

         cookie_config = self.factory._config['cookie']
         cookie_id_field = cookie_config.get('name', 'cbtid')
         cookie_id_field_length = int(cookie_config.get('length', 24))

         ## see if there already is a cookie set ..
         if request.headers.has_key('cookie'):
            try:
               cookie = Cookie.SimpleCookie()
               cookie.load(str(request.headers['cookie']))
            except Cookie.CookieError:
               pass
            else:
               if cookie.has_key(cookie_id_field):
                  cbtid = cookie[cookie_id_field].value
                  if self.factory._cookies.has_key(cbtid):
                     self._cbtid = cbtid
                     log.msg("Cookie already set: %s" % self._cbtid)

         ## if no cookie is set, create a new one ..
         if self._cbtid is None:

            self._cbtid = util.newid(cookie_id_field_length)

            ## http://tools.ietf.org/html/rfc6265#page-20
            ## 0: delete cookie
            ## -1: preserve cookie until browser is closed

            max_age = cookie_config.get('max_age', 86400 * 30 * 12)

            cbtData = {'created': util.utcnow(),
                       'authid': None,
                       'authrole': None,
                       'authmethod': None,
                       'max_age': max_age,
                       'connections': set()}

            self.factory._cookies[self._cbtid] = cbtData

            ## do NOT add the "secure" cookie attribute! "secure" refers to the
            ## scheme of the Web page that triggered the WS, not WS itself!!
            ##
            headers['Set-Cookie'] = '%s=%s;max-age=%d' % (cookie_id_field, self._cbtid, max_age)
            log.msg("Setting new cookie: %s" % headers['Set-Cookie'])

         ## add this WebSocket connection to the set of connections
         ## associated with the same cookie
         self.factory._cookies[self._cbtid]['connections'].add(self)

         if self.debug:
            log.msg("Cookie tracking enabled on WebSocket connection {}".format(self))

         ## if cookie-based authentication is enabled, set auth info from cookie store
         ##
         if 'auth' in self.factory._config and 'cookie' in self.factory._config['auth']:
            self._authid = self.factory._cookies[self._cbtid]['authid']
            self._authrole = self.factory._cookies[self._cbtid]['authrole']
            self._authmethod = "cookie.{}".format(self.factory._cookies[self._cbtid]['authmethod'])

      else:

         if self.debug:
            log.msg("Cookie tracking disabled on WebSocket connection {}".format(self))

      ## accept the WebSocket connection, speaking subprotocol `protocol`
      ## and setting HTTP headers `headers`
      return (protocol, headers)


   def sendServerStatus(self, redirectUrl = None, redirectAfter = 0):
      """
      Used to send out server status/version upon receiving a HTTP/GET without
      upgrade to WebSocket header (and option serverStatus is True).
      """
      try:
         page = self.factory._templates.get_template('cb_ws_status.html')
         self.sendHtml(page.render(redirectUrl = redirectUrl,
                                   redirectAfter = redirectAfter,
                                   cbVersion = crossbar.__version__,
                                   wsUri = self.factory.url))
      except Exception as e:         
         log.msg("Error rendering WebSocket status page template: %s" % e)



class CrossbarWampWebSocketServerFactory(WampWebSocketServerFactory):

   protocol = CrossbarWampWebSocketServerProtocol

   def __init__(self, factory, config, templates):
      """
      Ctor.

      :param factory: WAMP session factory.
      :type factory: An instance of ..
      :param config: Crossbar transport configuration.
      :type config: dict 
      """
      options = config.get('options', {})

      server = "Crossbar/{}".format(crossbar.__version__)
      externalPort = options.get('external_port', None)

      WampWebSocketServerFactory.__init__(self,
                                          factory,
                                          url = config['url'],
                                          server = server,
                                          externalPort = externalPort,
                                          debug = False)

      ## transport configuration
      self._config = config

      self._templates = templates

      if 'cookie' in config:
         self._cookies = {}

      c = options

      versions = []
      if c.get("enable_hixie76", True):
         versions.append(0)
      if c.get("enable_hybi10", True):
         versions.append(8)
      if c.get("enable_rfc6455", True):
         versions.append(13)

      ## FIXME: enforce!!
      ##
      #self.connectionCap = c.get("max_connections")

      ## convert to seconds
      ##
      openHandshakeTimeout = c.get("open_handshake_timeout", 0)
      if openHandshakeTimeout:
         openHandshakeTimeout = float(openHandshakeTimeout) / 1000.

      closeHandshakeTimeout = c.get("close_handshake_timeout", 0)
      if closeHandshakeTimeout:
         closeHandshakeTimeout = float(closeHandshakeTimeout) / 1000.

      self.setProtocolOptions(versions = versions,
                              allowHixie76 = c.get("enable_hixie76", True),
                              webStatus = c.get("enable_webstatus", True),
                              utf8validateIncoming = c.get("validate_utf8", True),
                              maskServerFrames = c.get("mask_server_frames", False),
                              requireMaskedClientFrames = c.get("require_masked_client_frames", True),
                              applyMask = c.get("apply_mask", True),
                              maxFramePayloadSize = c.get("max_frame_size", 0),
                              maxMessagePayloadSize = c.get("max_message_size", 0),
                              autoFragmentSize = c.get("auto_fragment_size", 0),
                              failByDrop = c.get("fail_by_drop", False),
                              echoCloseCodeReason = c.get("echo_close_codereason", False),
                              openHandshakeTimeout = openHandshakeTimeout,
                              closeHandshakeTimeout = closeHandshakeTimeout,
                              tcpNoDelay = c.get("tcp_nodelay", True))

      ## WebSocket compression
      ##
      self.setProtocolOptions(perMessageCompressionAccept = lambda _: None)
      if 'compression' in c:

         ## permessage-deflate
         ##
         if 'deflate' in c['compression']:

            log.msg("enabling WebSocket compression (permessage-deflate)")

            params = c['compression']['deflate']

            requestNoContextTakeover   = params.get('request_no_context_takeover', False)
            requestMaxWindowBits       = params.get('request_max_window_bits', 0)
            noContextTakeover          = params.get('no_context_takeover', None)
            windowBits                 = params.get('max_window_bits', None)
            memLevel                   = params.get('memory_level', None)

            def accept(offers):
               for offer in offers:
                  if isinstance(offer, PerMessageDeflateOffer):
                     if (requestMaxWindowBits == 0 or offer.acceptMaxWindowBits) and \
                        (not requestNoContextTakeover or offer.acceptNoContextTakeover):
                        return PerMessageDeflateOfferAccept(offer,
                                                            requestMaxWindowBits = requestMaxWindowBits,
                                                            requestNoContextTakeover = requestNoContextTakeover,
                                                            noContextTakeover = noContextTakeover,
                                                            windowBits = windowBits,
                                                            memLevel = memLevel)

            self.setProtocolOptions(perMessageCompressionAccept = accept)



class PendingAuth:
   pass



class PendingAuthPersona(PendingAuth):
   def __init__(self, provider, audience, role = None):
      self.provider = provider
      self.audience = audience
      self.role = role



class CrossbarRouterSession(RouterSession):

   def onOpen(self, transport):
      RouterSession.onOpen(self, transport)

      if hasattr(self._transport.factory, '_config'):
         self._transport_config = self._transport.factory._config
      else:
         self._transport_config = {}

      self._pending_auth = None
      self._session_details = None


   def onHello(self, realm, details):

      if self._transport._authid is not None:
         ## already authenticated ..
         ##
         return types.Accept(authid = self._transport._authid,
                             authrole = self._transport._authrole,
                             authmethod = self._transport._authmethod)
      else:
         if "auth" in self._transport_config:
            ## iterate over authentication methods announced by client
            ##
            for authmethod in details.authmethods:

               if authmethod in self._transport_config["auth"]:

                  ## Mozilla Persona
                  ##
                  if authmethod == "mozilla_persona":
                     cfg = self._transport_config['auth']['mozilla_persona']

                     audience = cfg.get('audience', self._transport._origin)
                     provider = cfg.get('provider', "https://verifier.login.persona.org/verify")

                     ## authrole mapping
                     ##
                     authrole = None
                     try:
                        if 'role' in cfg:
                           if cfg['role']['type'] == 'static':
                              authrole = cfg['role']['value']
                     except Exception as e:
                        log.msg("error processing 'role' part of 'auth' config: {}".format(e))

                     self._pending_auth = PendingAuthPersona(provider, audience, authrole)
                     return types.Challenge("mozilla-persona")

                  ## Anonymous
                  ##
                  elif authmethod == "anonymous":
                     cfg = self._transport_config['auth']['anonymous']

                     ## authrole mapping
                     ##
                     authrole = "anonymous"
                     try:
                        if 'role' in cfg:
                           if cfg['role']['type'] == 'static':
                              authrole = cfg['role']['value']
                     except Exception as e:
                        log.msg("error processing 'role' part of 'auth' config: {}".format(e))

                     ## authid generation
                     ##
                     if self._transport._cbtid:
                        ## set authid to cookie value
                        authid = self._transport._cbtid
                     else:
                        authid = util.newid(24)

                     self._transport._authid = authid
                     self._transport._authrole = authrole
                     self._transport._authmethod = "anonymous"

                     # # remember the user's auth info (this marks the cookie as authenticated)
                     # if self._transport._cbtid:
                     #    self._transport.factory._cookies[self._transport._cbtid]['authid'] = "anonymous"
                     #    self._transport.factory._cookies[self._transport._cbtid]['authrole'] = "anonymous"
                     #    self._transport.factory._cookies[self._transport._cbtid]['authmethod'] = "anonymous"

                     return types.Accept(authid = authid, authrole = authrole, authmethod = self._transport._authmethod)

                  else:
                     log.msg("unknown authmethod '{}'".format(authmethod))

         else:
            ## FIXME: if not "auth" key present, allow anyone
            return types.Accept(authid = "anonymous", authrole = "anonymous", authmethod = "anonymous")


   def onAuthenticate(self, signature, extra):
      #print "onAuthenticate: {} {}".format(signature, extra)

      if isinstance(self._pending_auth, PendingAuthPersona):

         dres = Deferred()

         ## The client did it's Mozilla Persona authentication thing
         ## and now wants to verify the authentication and login.
         assertion = signature
         audience = str(self._pending_auth.audience) # eg "http://192.168.1.130:8080/"
         provider = str(self._pending_auth.provider) # eg "https://verifier.login.persona.org/verify"

         ## To verify the authentication, we need to send a HTTP/POST
         ## to Mozilla Persona. When successful, Persona will send us
         ## back something like:

         # {
         #    "audience": "http://192.168.1.130:8080/",
         #    "expires": 1393681951257,
         #    "issuer": "gmail.login.persona.org",
         #    "email": "tobias.oberstein@gmail.com",
         #    "status": "okay"
         # }

         headers = {'Content-Type': 'application/x-www-form-urlencoded'}
         body = urllib.urlencode({'audience': audience, 'assertion': assertion})

         from twisted.web.client import getPage
         d = getPage(url = provider,
                     method = 'POST',
                     postdata = body,
                     headers = headers)

         log.msg("Authentication request sent.")

         def done(res):
            res = json.loads(res)
            try:
               if res['status'] == 'okay':

                  ## awesome: Mozilla Persona successfully authenticated the user
                  self._transport._authid = res['email']
                  self._transport._authrole = self._pending_auth.role
                  self._transport._authmethod = 'mozilla_persona'

                  ## remember the user's auth info (this marks the cookie as authenticated)
                  if self._transport._cbtid:
                     self._transport.factory._cookies[self._transport._cbtid]['authid'] = self._transport._authid
                     self._transport.factory._cookies[self._transport._cbtid]['authrole'] = self._transport._authrole
                     self._transport.factory._cookies[self._transport._cbtid]['authmethod'] = self._transport._authmethod

                  log.msg("Authenticated user {} with role {}".format(self._transport._authid, self._transport._authrole))
                  dres.callback(types.Accept(authid = self._transport._authid, authrole = self._transport._authrole, authmethod = self._transport._authmethod))
               else:
                  log.msg("Authentication failed!")
                  log.msg(res)
                  dres.callback(types.Deny(reason = "wamp.error.authorization_failed", message = res.get("reason", None)))
            except Exception as e:
               print "ERRR", e

         def error(err):
            log.msg("Authentication request failed: {}".format(err.value))
            dres.callback(types.Deny(reason = "wamp.error.authorization_request_failed", message = str(err.value)))

         d.addCallbacks(done, error)

         return dres

      else:

         log.msg("don't know how to authenticate")

         return types.Deny()


   def onJoin(self, details):

      self._session_details = {
         'authid': details.authid,
         'authrole': details.authrole,
         'authmethod': details.authmethod,
         'realm': details.realm,
         'session': details.session
      }

      ## FIXME: dispatch metaevent
      #self.publish('wamp.metaevent.session.on_join', evt)

      msg = message.Publish(0, 'wamp.metaevent.session.on_join', [self._session_details])
      self._router.process(self, msg)


   def onLeave(self, details):

      ## FIXME: dispatch metaevent
      #self.publish('wamp.metaevent.session.on_join', evt)

      msg = message.Publish(0, 'wamp.metaevent.session.on_leave', [self._session_details])
      self._router.process(self, msg)
      self._session_details = None


      if details.reason == "wamp.close.logout":
         if self._transport._cbtid:
            cookie = self._transport.factory._cookies[self._transport._cbtid]
            cookie['authid'] = None
            cookie['authrole'] = None
            cookie['authmethod'] = None
            for proto in cookie['connections']:
               proto.sendClose()



class CrossbarRouterSessionFactory(RouterSessionFactory):

   session = CrossbarRouterSession



class CrossbarRouterFactory(RouterFactory):
   def __init__(self, options = None, debug = False):
      options = types.RouterOptions(uri_check = types.RouterOptions.URI_CHECK_LOOSE)
      RouterFactory.__init__(self, options, debug)
