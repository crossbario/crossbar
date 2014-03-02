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

      ## our cookie tracking ID
      self._cbtid = None

      ## see if there already is a cookie set ..
      if request.headers.has_key('cookie'):
         try:
            cookie = Cookie.SimpleCookie()
            cookie.load(str(request.headers['cookie']))
         except Cookie.CookieError:
            pass
         else:
            if cookie.has_key('cbtid'):
               cbtid = cookie['cbtid'].value
               if self.factory._cookies.has_key(cbtid):
                  self._cbtid = cbtid
                  log.msg("Cookie already set: %s" % self._cbtid)

      ## if no cookie is set, create a new one ..
      if self._cbtid is None:

         self._cbtid = newid()
         maxAge = 86400

         cbtData = {'created': utcnow(),
                    'authenticated': None,
                    'maxAge': maxAge,
                    'connections': set()}

         self.factory._cookies[self._cbtid] = cbtData

         ## do NOT add the "secure" cookie attribute! "secure" refers to the
         ## scheme of the Web page that triggered the WS, not WS itself!!
         ##
         headers['Set-Cookie'] = 'cbtid=%s;max-age=%d' % (self._cbtid, maxAge)
         log.msg("Setting new cookie: %s" % self._cbtid)

      ## add this WebSocket connection to the set of connections
      ## associated with the same cookie
      self.factory._cookies[self._cbtid]['connections'].add(self)

      self._authenticated = self.factory._cookies[self._cbtid]['authenticated']

      ## accept the WebSocket connection, speaking subprotocol `protocol`
      ## and setting HTTP headers `headers`
      return (protocol, headers)




class CrossbarWampWebSocketServerFactory(WampWebSocketServerFactory):

   protocol = CrossbarWampWebSocketServerProtocol

   def __init__(self, *args, **kwargs):
      WampWebSocketServerFactory.__init__(self, *args, **kwargs)
      self._cookies = {}
      self.setProtocolOptions(failByDrop = False)



class CrossbarRouterSession(RouterSession):

   def onOpen(self, transport):
      RouterSession.onOpen(self, transport)
      print "transport authenticated: {}".format(self._transport._authenticated)


   def onHello(self, realm, details):
      print "onHello: {} {}".format(realm, details)
      if self._transport._authenticated is not None:
         return types.Accept(authid = self._transport._authenticated)
      else:
         return types.Challenge("mozilla-persona")
      return accept


   def onLeave(self, details):
      if details.reason == "wamp.close.logout":
         cookie = self._transport.factory._cookies[self._transport._cbtid]
         cookie['authenticated'] = None
         for proto in cookie['connections']:
            proto.sendClose()


   def onAuthenticate(self, signature, extra):
      return types.Deny(error = "wamp.error.special", message = "hlleoo")
      print "onAuthenticate: {} {}".format(signature, extra)

      dres = Deferred()

      ## The client did it's Mozilla Persona authentication thing
      ## and now wants to verify the authentication and login.
      assertion = signature
      audience = 'http://localhost:8080/'
      #audience = 'http://192.168.1.130:8080/'

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
      d = getPage(url = "https://verifier.login.persona.org/verify",
                  method = 'POST',
                  postdata = body,
                  headers = headers)

      log.msg("Authentication request sent.")

      def done(res):
         res = json.loads(res)
         try:
            if res['status'] == 'okay':
               ## Mozilla Persona successfully authenticated the user

               ## remember the user's email address. this marks the cookie as
               ## authenticated
               self._transport.factory._cookies[self._transport._cbtid]['authenticated'] = res['email']

               log.msg("Authenticated user {}".format(res['email']))
               dres.callback(types.Accept(authid = res['email']))
            else:
               log.msg("Authentication failed!")
               dres.callback(types.Deny(reason = "wamp.error.authorization_failed", message = json.dumps(res)))
         except Exception as e:
            print "ERRR", e

      def error(err):
         log.msg("Authentication request failed: {}".format(err.value))
         dres.callback(types.Deny(reason = "wamp.error.authorization_request_failed", message = str(err.value)))

      d.addCallbacks(done, error)

      return dres



class CrossbarRouterSessionFactory(RouterSessionFactory):

   session = CrossbarRouterSession



class CrossbarRouterFactory(RouterFactory):
   pass
