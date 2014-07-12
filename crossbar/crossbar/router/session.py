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

__all__ = ['CrossbarRouterSessionFactory',
           'CrossbarRouterFactory']

import datetime

from twisted.python import log
from twisted.internet.defer import Deferred

import json

from six.moves import urllib

from autobahn import util
from autobahn.websocket import http
from autobahn.websocket.compress import *

from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp.interfaces import IRouter
from autobahn.wamp.router import Router, RouterFactory
from autobahn.twisted.wamp import RouterSession, RouterSessionFactory

import crossbar



class PendingAuth:
   """
   Base class for pending WAMP authentications.
   """



class PendingAuthPersona(PendingAuth):
   def __init__(self, provider, audience, role = None):
      self.provider = provider
      self.audience = audience
      self.role = role



class CrossbarRouterSession(RouterSession):
   """
   Router-side of (non-embedded) Crossbar.io WAMP sessions.
   """

   def onOpen(self, transport):
      RouterSession.onOpen(self, transport)

      if hasattr(self._transport, 'factory') and hasattr(self._transport.factory, '_config'):
         self._transport_config = self._transport.factory._config
      else:
         self._transport_config = {}

      self._pending_auth = None
      self._session_details = None


   def onHello(self, realm, details):

      authorizer = self._router_factory._authorizer

      if self._transport._authid is not None:
         ## already authenticated .. e.g. via cookie
         ##
         allow = authorizer.authorize_join(realm, self._transport._authrole)

         if allow:
            return types.Accept(authid = self._transport._authid,
                                authrole = self._transport._authrole,
                                authmethod = self._transport._authmethod)
         else:
            return types.Deny()
      else:
         ## if authentication is enabled on the transport ..
         ##
         if "auth" in self._transport_config:

            ## iterate over authentication methods announced by client ..
            ##
            for authmethod in details.authmethods or ["anonymous"]:

               ## .. and if the configuration has an entry for the authmethod
               ## announced, process ..
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
                     self._transport._authmethod = authmethod

                     allow = authorizer.authorize_join(realm, self._transport._authrole)

                     if allow:
                        return types.Accept(authid = authid, authrole = authrole, authmethod = self._transport._authmethod)
                     else:
                        return Deny()

                  elif authmethod == "cookie":
                     pass
                     # if self._transport._cbtid:
                     #    cookie = self._transport.factory._cookies[self._transport._cbtid]
                     #    authid = cookie['authid']
                     #    authrole = cookie['authrole']
                     #    authmethod = "cookie.{}".format(cookie['authmethod'])
                     #    return types.Accept(authid = authid, authrole = authrole, authmethod = authmethod)
                     # else:
                     #    return types.Deny()
                  else:
                     log.msg("unknown authmethod '{}'".format(authmethod))


            ## if authentication is configured, by default, deny.
            ##
            return types.Deny()
         else:
            ## if authentication is not configured, by default, allow anyone.
            return types.Accept(authid = "anonymous", authrole = "anonymous", authmethod = "anonymous")


   def onAuthenticate(self, signature, extra):

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

                  log.msg("Authenticated user {} with role {}".format(self._transport._authid, self._transport._authrole))
                  dres.callback(types.Accept(authid = self._transport._authid, authrole = self._transport._authrole, authmethod = self._transport._authmethod))

                  ## remember the user's auth info (this marks the cookie as authenticated)
                  if self._transport._cbtid and self._transport.factory._cookiestore:
                     cs = self._transport.factory._cookiestore
                     cs.setAuth(self._transport._cbtid, self._transport._authid, self._transport._authrole, self._transport._authmethod)

                     ## kick all sessions using same cookie (but not _this_ connection)
                     if True:
                        for proto in cs.getProtos(self._transport._cbtid):
                           if proto and proto != self._transport:
                              try:
                                 proto.close()
                              except Exception as e:
                                 pass
               else:
                  log.msg("Authentication failed!")
                  log.msg(res)
                  dres.callback(types.Deny(reason = "wamp.error.authorization_failed", message = res.get("reason", None)))
            except Exception as e:
               log.msg("internal error during authentication verification: {}".format(e))
               dres.callback(types.Deny(reason = "wamp.error.internal_error", message = str(e)))

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

      msg = message.Publish(0, u'wamp.metaevent.session.on_join', [self._session_details])
      self._router.process(self, msg)


   def onLeave(self, details):

      ## FIXME: dispatch metaevent
      #self.publish('wamp.metaevent.session.on_join', evt)

      msg = message.Publish(0, u'wamp.metaevent.session.on_leave', [self._session_details])
      self._router.process(self, msg)
      self._session_details = None

      if details.reason == u"wamp.close.logout":
         if self._transport._cbtid and self._transport.factory._cookiestore:
            cs = self._transport.factory._cookiestore
            cs.setAuth(self._transport._cbtid, None, None, None)
            for proto in cs.getProtos(self._transport._cbtid):
               proto.sendClose()



class CrossbarRouterSessionFactory(RouterSessionFactory):
   """
   Factory creating the router side of (non-embedded) Crossbar.io WAMP sessions.
   This is the session factory that will given to router transports.
   """
   session = CrossbarRouterSession


from collections import namedtuple

#AuthorizationInfo = namedtuple('AuthorizationInfo', ['session', 'authid', 'authrole', 'authmethod', 'authprovider', 'uri', 'action'])


class CrossbarRouterAuthorizer:

   def authorize_join(self, realm, authrole):
      return True

   def authorize_action(self, realm, authrole, uri, action):
      return True



class CrossbarRouterRole:

   def __init__(self, uri):
      self.uri = uri

   def authorize(self, uri, action):
      print("CrossbarRouterRole.authorize", uri, action)
      return True


class CrossbarRouterRoleStaticAuth(CrossbarRouterRole):

   def __init__(self, uri, permissions):
      CrossbarRouterRole.__init__(self, uri)
      self.permissions = permissions



class CrossbarRouter(Router):

   def __init__(self, *args, **kwargs):
      Router.__init__(self, *args, **kwargs)
      self._roles = {}


   def add_role(self, role):
      print("CrossbarRouter.add_role", role)
      self._roles[role.uri] = role


   def authorize(self, session, uri, action):
      role = session._authrole
      action = IRouter.ACTION_TO_STRING[action]

      authorized = False
      if role in self._roles:
         #authorized = self.factory._authorizer.authorize_action(self.realm, role, uri, action)
         authorized = self._roles[role].authorize(uri, action)

      if True or self.debug:
         print("CrossbarRouter.authorize: {} {} {} {} {} {} {} -> {}".format(session._session_id, uri, action, session._authid, session._authrole, session._authmethod, session._authprovider, authorized))

      return authorized



class CrossbarRouterFactory(RouterFactory):

   router = CrossbarRouter

   def __init__(self, options = None, debug = False):
      options = types.RouterOptions(uri_check = types.RouterOptions.URI_CHECK_LOOSE)
      RouterFactory.__init__(self, options, debug)

      self._authorizer = CrossbarRouterAuthorizer()


   def get(self, realm):
      """
      Implements :func:`autobahn.wamp.interfaces.IRouterFactory.get`
      """
      return self._routers[realm]


   def start_realm(self, realm):
      print("CrossbarRouterFactory.start_realm", realm)
      try:
         assert(realm not in self._routers)

         self._routers[realm] = self.router(self, realm, self._options)
         if self.debug:
            print("Router created for realm '{}'".format(realm))
      except Exception as e:
         print "YYYYY", e


   def stop_realm(self, realm):
      print("CrossbarRouterFactory.stop_realm", realm)


   def add_role(self, realm, config):
      print("CrossbarRouterFactory.add_role", realm, config)
      assert(realm in self._routers)

      if 'permissions' in config:
         role = CrossbarRouterRoleStaticAuth(config['name'], config['permissions'])
      else:
         role = CrossbarRouterRole(config['name'])

      self._routers[realm].add_role(role)



   def drop_role(self, realm, role):
      print("CrossbarRouterFactory.drop_role", realm, role)
