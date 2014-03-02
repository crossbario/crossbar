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
from autobahn.twisted.websocket import WampWebSocketServerProtocol, WampWebSocketServerFactory
from twisted.internet.defer import Deferred

import json
import urllib
import Cookie

from autobahn.util import newid, utcnow
from autobahn.websocket import http

from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSessionFactory
from autobahn.wamp.protocol import RouterSession
from autobahn.wamp import types



class CrossbarWampWebSocketServerProtocol(WampWebSocketServerProtocol):

   ## authid -> cookie -> set(connection)

   def onConnect(self, request):

      protocol, headers = WampWebSocketServerProtocol.onConnect(self, request)

      self._origin = request.origin

      ## indicates if this transport has been authenticated
      self._authid = None

      ## our cookie tracking ID
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

            self._cbtid = newid(cookie_id_field_length)

            ## http://tools.ietf.org/html/rfc6265#page-20
            ## 0: delete cookie
            ## -1: preserve cookie until browser is closed

            max_age = cookie_config.get('max_age', 86400 * 30 * 12)

            cbtData = {'created': utcnow(),
                       'authid': None,
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

         self._authid = self.factory._cookies[self._cbtid]['authid']

         log.msg("Cookie tracking enabled on WebSocket connection {}".format(self))

      else:

         log.msg("Cookie tracking disabled on WebSocket connection {}".format(self))

      ## accept the WebSocket connection, speaking subprotocol `protocol`
      ## and setting HTTP headers `headers`
      return (protocol, headers)



from autobahn.websocket.compress import *


class CrossbarWampWebSocketServerFactory(WampWebSocketServerFactory):

   protocol = CrossbarWampWebSocketServerProtocol

   def __init__(self, factory, config):
      """
      Ctor.

      :param factory: WAMP session factory.
      :type factory: An instance of ..
      :param config: Crossbar transport configuration.
      :type config: dict 
      """
      WampWebSocketServerFactory.__init__(self, factory, url = config['url'])

      ## transport configuration
      self._config = config

      if 'cookie' in config:
         self._cookies = {}

      self.setProtocolOptions(failByDrop = False)


      options = config.get('options', {})

      if 'compression' in options:
         if 'deflate' in options['compression']:

            log.msg("enabling WebSocket compression (permessage-deflate)")

            params = options['compression']['deflate']

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
   def __init__(self, provider, audience):
      self.provider = provider
      self.audience = audience


class CrossbarRouterSession(RouterSession):

   def onOpen(self, transport):
      RouterSession.onOpen(self, transport)

      if hasattr(self._transport.factory, '_config'):
         self._transport_config = self._transport.factory._config
      else:
         self._transport_config = {}

      print "0000000000000", self._transport
      print "transport authenticated: {}".format(self._transport._authid)

      self._pending_auth = None


   def onHello(self, realm, details):
      print "onHello: {} {}".format(realm, details)
      if self._transport._authid is not None:
         return types.Accept(authid = self._transport._authid)
      else:
         if "auth" in self._transport_config:
            if "mozilla_persona" in self._transport_config["auth"]:
               audience = self._transport_config['auth']['mozilla_persona'].get('audience', self._transport._origin)
               provider = self._transport_config['auth']['mozilla_persona'].get('provider', "https://verifier.login.persona.org/verify")
               self._pending_auth = PendingAuthPersona(provider, audience)
               return types.Challenge("mozilla-persona")


   def onAuthenticate(self, signature, extra):
      print "onAuthenticate: {} {}".format(signature, extra)

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
                  ## Mozilla Persona successfully authenticated the user

                  self._transport._authid = res['email']

                  ## remember the user's email address. this marks the cookie as authenticated
                  if self._transport._cbtid:
                     self._transport.factory._cookies[self._transport._cbtid]['authid'] = res['email']

                  log.msg("Authenticated user {}".format(res['email']))
                  dres.callback(types.Accept(authid = res['email']))
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


   def onLeave(self, details):
      if details.reason == "wamp.close.logout":
         if self._transport._cbtid:
            cookie = self._transport.factory._cookies[self._transport._cbtid]
            cookie['authid'] = None
            for proto in cookie['connections']:
               proto.sendClose()



class CrossbarRouterSessionFactory(RouterSessionFactory):

   session = CrossbarRouterSession



class CrossbarRouterFactory(RouterFactory):
   pass
