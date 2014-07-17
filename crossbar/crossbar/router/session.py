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
           'CrossbarRouterFactory',
           'CrossbarRouterServiceSession']

import json
import datetime
from pytrie import StringTrie
from collections import namedtuple

from six.moves import urllib

from twisted.python import log
from twisted.internet.defer import Deferred, inlineCallbacks

from autobahn import util
from autobahn.websocket import http
from autobahn.websocket.compress import *

from autobahn import wamp
from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.interfaces import IRouter
from autobahn.wamp.router import Router, RouterFactory
from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.wamp import RouterSession, RouterSessionFactory

import crossbar



class PendingAuth:
   """
   Base class for pending WAMP authentications.
   """



class PendingAuthPersona(PendingAuth):
   """
   Pending Mozilla Persona authentication.
   """
   def __init__(self, provider, audience, role = None):
      self.provider = provider
      self.audience = audience
      self.role = role



class CrossbarRouterSession(RouterSession):
   """
   Router-side of (non-embedded) Crossbar.io WAMP sessions.
   """

   def onOpen(self, transport):
      """
      Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onOpen`
      """
      RouterSession.onOpen(self, transport)

      if hasattr(self._transport, 'factory') and hasattr(self._transport.factory, '_config'):
         self._transport_config = self._transport.factory._config
      else:
         self._transport_config = {}

      self._pending_auth = None
      self._session_details = None


   def onHello(self, realm, details):

      ## check if the realm the session wants to join actually exists
      ##
      if realm not in self._router_factory:
         return types.Deny(ApplicationError.NO_SUCH_REALM, message = "no realm '{}' exists on this router".format(realm))

      ## perform authentication
      ##
      if self._transport._authid is not None:

         ## already authenticated .. e.g. via cookie

         ## check if role still exists on realm
         ##
         allow = self._router_factory[realm].has_role(self._transport._authrole)

         if allow:
            return types.Accept(authid = self._transport._authid,
                                authrole = self._transport._authrole,
                                authmethod = self._transport._authmethod,
                                authprovider = 'transport')
         else:
            return types.Deny(ApplicationError.NO_SUCH_ROLE, message = "session was previously authenticated (via transport), but role '{}' no longer exists on realm '{}'".format(self._transport._authrole, realm))

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


                  ## "Mozilla Persona" authentication
                  ##
                  if authmethod == "mozilla_persona":
                     cfg = self._transport_config['auth']['mozilla_persona']

                     audience = cfg.get('audience', self._transport._origin)
                     provider = cfg.get('provider', "https://verifier.login.persona.org/verify")

                     ## authrole mapping
                     ##
                     authrole = cfg.get('role', 'anonymous')

                     ## check if role exists on realm anyway
                     ##
                     if not self._router_factory[realm].has_role(authrole):
                        return types.Deny(ApplicationError.NO_SUCH_ROLE, message = "authentication failed - realm '{}' has no role '{}'".format(realm, authrole))

                     ## ok, now challenge the client for doing Mozilla Persona auth.
                     ##
                     self._pending_auth = PendingAuthPersona(provider, audience, authrole)
                     return types.Challenge("mozilla-persona")


                  ## "Anonymous" authentication
                  ##
                  elif authmethod == "anonymous":
                     cfg = self._transport_config['auth']['anonymous']

                     ## authrole mapping
                     ##
                     authrole = cfg.get('role', 'anonymous')

                     ## check if role exists on realm anyway
                     ##
                     if not self._router_factory[realm].has_role(authrole):
                        return types.Deny(ApplicationError.NO_SUCH_ROLE, message = "authentication failed - realm '{}' has no role '{}'".format(realm, authrole))

                     ## authid generation
                     ##
                     if self._transport._cbtid:
                        ## if cookie tracking is enabled, set authid to cookie value
                        ##
                        authid = self._transport._cbtid
                     else:
                        ## if no cookie tracking, generate a random value for authid
                        ##
                        authid = util.newid(24)

                     self._transport._authid = authid
                     self._transport._authrole = authrole
                     self._transport._authmethod = authmethod

                     return types.Accept(authid = authid, authrole = authrole, authmethod = self._transport._authmethod)


                  ## "Cookie" authentication
                  ##
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
                     return types.Deny(message = "unknown authentication method {}".format(authmethod))


            ## if authentication is configured, by default, deny.
            ##
            return types.Deny(message = "authentication using method '{}' denied by configuration".format(authmethod))


         else:
            ## if authentication is _not_ configured, by default, allow anyone.
            ##

            ## authid generation
            ##
            if self._transport._cbtid:
               ## if cookie tracking is enabled, set authid to cookie value
               ##
               authid = self._transport._cbtid
            else:
               ## if no cookie tracking, generate a random value for authid
               ##
               authid = util.newid(24)


            return types.Accept(authid = authid, authrole = "anonymous", authmethod = "anonymous")


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
         'authprovider': details.authprovider,
         'realm': details.realm,
         'session': details.session
      }

      ## dispatch session metaevent from WAMP AP
      ##
      msg = message.Publish(0, u'wamp.metaevent.session.on_join', [self._session_details])
      self._router.process(self, msg)


   def onLeave(self, details):

      ## dispatch session metaevent from WAMP AP
      ##
      msg = message.Publish(0, u'wamp.metaevent.session.on_leave', [self._session_details])
      self._router.process(self, msg)
      self._session_details = None

      ## if asked to explicitly close the session ..
      if details.reason == u"wamp.close.logout":

         ## if cookie was set on transport ..
         if self._transport._cbtid and self._transport.factory._cookiestore:
            cs = self._transport.factory._cookiestore

            ## set cookie to "not authenticated"
            cs.setAuth(self._transport._cbtid, None, None, None)

            ## kick all session for the same auth cookie
            for proto in cs.getProtos(self._transport._cbtid):
               proto.sendClose()



class CrossbarRouterSessionFactory(RouterSessionFactory):
   """
   Factory creating the router side of (non-embedded) Crossbar.io WAMP sessions.
   This is the session factory that will given to router transports.
   """
   session = CrossbarRouterSession



class CrossbarRouterServiceSession(ApplicationSession):
   """
   Router service session which is used internally by a router to
   issue WAMP calls or publish events.
   """

   def __init__(self, config, schemas = None):
      """
      Ctor.

      :param config: WAMP application component configuration.
      :type config: Instance of :class:`autobahn.wamp.types.ComponentConfig`.
      :param schemas: An (optional) initial schema dictionary to load.
      :type schemas: dict
      """
      ApplicationSession.__init__(self, config)
      self._schemas = {}
      if schemas:
         self._schemas.update(schemas)
         print("CrossbarRouterServiceSession: initialized schemas cache with {} entries".format(len(self._schemas)))


   @inlineCallbacks
   def onJoin(self, details):
      if self.debug:
         log.msg("CrossbarRouterServiceSession.onJoin({})".format(details))

      regs = yield self.register(self)
      if self.debug:
         log.msg("CrossbarRouterServiceSession: registered {} procedures".format(len(regs)))


   @wamp.register('wamp.reflect.describe')
   def describe(self, uri = None):
      """
      Describe a given URI or all URIs.

      :param uri: The URI to describe or `None` to retrieve all declarations.
      :type uri: str

      :returns: list -- A list of WAMP declarations.
      """
      if uri:
         return self._schemas.get(uri, None)
      else:
         return self._schemas


   @wamp.register('wamp.reflect.define')
   def define(self, uri, schema):
      """
      Declare metadata for a given URI.

      :param uri: The URI for which to declare metadata.
      :type uri: str
      :param decl: The WAMP schema declaration for
         the URI or `None` to remove any declarations for the URI.
      :type decl: dict

      :returns: bool -- `None` if declaration was unchanged, `True` if
         declaration was new, `False` if declaration existed, but was modified.
      """
      if not schema:
         if uri in self._schemas:
            del self._schemas
            self.publish('wamp.reflect.on_undefine', uri)
            return uri
         else:
            return None

      if uri not in self._schemas:
         was_new = True
         was_modified = False
      else:
         was_new = False
         if json.dumps(schema) != json.dumps(self._schemas[uri]):
            was_modified = True
         else:
            was_modified = False

      if was_new or was_modified:
         self._schemas[uri] = schema
         self.publish('wamp.reflect.on_define', uri, schema, was_new)
         return was_new
      else:
         return None



CrossbarRouterPermissions = namedtuple('CrossbarRouterPermissions', ['uri', 'match_by_prefix', 'call', 'register', 'publish', 'subscribe'])



class CrossbarRouterRole:
   """
   Base class for router roles.
   """

   def __init__(self, router, uri, debug = False):
      """
      Ctor.

      :param uri: The URI of the role.
      :type uri: str
      :param debug: Enable debug logging.
      :type debug: bool
      """
      self.router = router
      self.uri = uri
      self.debug = debug


   def authorize(self, session, uri, action):
      """
      Authorize a session connected under this role to perform the given action
      on the given URI.

      :param session: The WAMP session that requests the action.
      :type session: Instance of :class:`autobahn.wamp.protocol.ApplicationSession`
      :param uri: The URI on which to perform the action.
      :type uri: str
      :param action: The action to be performed.
      :type action: str

      :return: bool -- Flag indicating whether session is authorized or not.
      """
      if self.debug:
         log.msg("CrossbarRouterRole.authorize", uri, action)
      return False



class CrossbarRouterTrustedRole(CrossbarRouterRole):
   """
   A router role that is trusted to do anything. This is used e.g. for the
   service session run internally run by a router.
   """

   def authorize(self, session, uri, action):
      if self.debug:
         log.msg("CrossbarRouterTrustedRole.authorize", self.uri, uri, action)
      return True



class CrossbarRouterRoleStaticAuth(CrossbarRouterRole):
   """
   A role on a router realm that is authorized using a static configuration.
   """

   def __init__(self, router, uri, permissions, debug = False):
      """
      Ctor.

      :param uri: The URI of the role.
      :type uri: str
      :param permissions: A permissions configuration, e.g. a list
         of permission dicts like `{'uri': 'com.example.*', 'call': True}`
      :type permissions: list
      :param debug: Enable debug logging.
      :type debug: bool
      """
      CrossbarRouterRole.__init__(self, router, uri, debug)
      self.permissions = permissions

      self._urimap = StringTrie()
      self._default = CrossbarRouterPermissions('', True, False, False, False, False)

      for p in permissions:
         uri = p['uri']

         if len(uri) > 0 and uri[-1] == '*':
            match_by_prefix = True
            uri = uri[:-1]
         else:
            match_by_prefix = False

         perms = CrossbarRouterPermissions(uri, match_by_prefix,
            call = p.get('call', False),
            register = p.get('register', False),
            publish = p.get('publish', False),
            subscribe = p.get('subscribe', False))

         if len(uri) > 0:
            self._urimap[uri] = perms
         else:
            self._default = perms


   def authorize(self, session, uri, action):
      """
      Authorize a session connected under this role to perform the given action
      on the given URI.

      :param session: The WAMP session that requests the action.
      :type session: Instance of :class:`autobahn.wamp.protocol.ApplicationSession`
      :param uri: The URI on which to perform the action.
      :type uri: str
      :param action: The action to be performed.
      :type action: str

      :return: bool -- Flag indicating whether session is authorized or not.
      """
      if self.debug:
         log.msg("CrossbarRouterRoleStaticAuth.authorize", self.uri, uri, action)
      #if action == 'publish':
      #   f = 1/0
      try:
         permissions = self._urimap.longest_prefix_value(uri)
         if not permissions.match_by_prefix and uri != permissions.uri:
            return False
         return getattr(permissions, action)
      except KeyError:
         return getattr(self._default, action)



class CrossbarRouterRoleDynamicAuth(CrossbarRouterRole):
   """
   A role on a router realm that is authorized by calling (via WAMP RPC)
   an authorizer function provided by the app.
   """

   def __init__(self, router, uri, authorizer, debug = False):
      """
      Ctor.

      :param uri: The URI of the role.
      :type uri: str
      :param debug: Enable debug logging.
      :type debug: bool
      """
      CrossbarRouterRole.__init__(self, router, uri, debug)
      self._authorizer = authorizer
      self._session = router._realm.session


   def authorize(self, session, uri, action):
      """
      Authorize a session connected under this role to perform the given action
      on the given URI.

      :param session: The WAMP session that requests the action.
      :type session: Instance of :class:`autobahn.wamp.protocol.ApplicationSession`
      :param uri: The URI on which to perform the action.
      :type uri: str
      :param action: The action to be performed.
      :type action: str

      :return: bool -- Flag indicating whether session is authorized or not.
      """
      if self.debug:
         log.msg("CrossbarRouterRoleDynamicAuth.authorize", self.uri, uri, action)
      return self._session.call(self._authorizer, session._session_details, uri, action)



class CrossbarRouter(Router):
   """
   Crossbar.io core router class.
   """

   RESERVED_ROLES = ["trusted"]
   """
   Roles with these URIs are built-in and cannot be added/dropped.
   """


   def __init__(self, factory, realm, options = None):
      """
      Ctor.
      """
      uri = realm.config['name']
      Router.__init__(self, factory, uri, options)
      self._roles = {
         "trusted": CrossbarRouterTrustedRole(self, "trusted", debug = self.debug)
      }
      self._realm = realm
      #self.debug = True


   def has_role(self, uri):
      """
      Check if a role with given URI exists on this router.

      :returns: bool - `True` if a role under the given URI exists on this router.
      """
      return uri in self._roles


   def add_role(self, role):
      """
      Adds a role to this router.

      :param role: The role to add.
      :type role: An instance of :class:`crossbar.router.session.CrossbarRouterRole`.

      :returns: bool -- `True` if a role under the given URI actually existed before and was overwritten.
      """
      if self.debug:
         log.msg("CrossbarRouter.add_role", role)

      if role.uri in self.RESERVED_ROLES:
         raise Exception("cannot add reserved role '{}'".format(role.uri))

      overwritten = role.uri in self._roles

      self._roles[role.uri] = role

      return overwritten


   def drop_role(self, uri):
      """
      Drops a role from this router.

      :param uri: The URI of the role to drop.
      :type uri: str

      :returns: bool -- `True` if a role under the given URI actually existed and was removed.
      """
      if self.debug:
         log.msg("CrossbarRouter.drop_role", role)

      if role.uri in self.RESERVED_ROLES:
         raise Exception("cannot drop reserved role '{}'".format(role.uri))

      if uri in self._roles:
         del self._roles[uri]
         return True
      else:
         return False


   def authorize(self, session, uri, action):
      """
      Authorizes a session for an action on an URI.

      Implements :func:`autobahn.wamp.interfaces.IRouter.authorize`
      """
      role = session._authrole
      action = IRouter.ACTION_TO_STRING[action]

      authorized = False
      if role in self._roles:
         authorized = self._roles[role].authorize(session, uri, action)

      if self.debug:
         log.msg("CrossbarRouter.authorize: {} {} {} {} {} {} {} -> {}".format(session._session_id, uri, action, session._authid, session._authrole, session._authmethod, session._authprovider, authorized))

      return authorized



class CrossbarRouterFactory(RouterFactory):
   """
   Crossbar.io core router factory.
   """

   def __init__(self, options = None, debug = False):
      """
      Ctor.
      """
      options = types.RouterOptions(uri_check = types.RouterOptions.URI_CHECK_LOOSE)
      RouterFactory.__init__(self, options, debug)


   def __getitem__(self, realm):
      return self._routers[realm]


   def __contains__(self, realm):
      return realm in self._routers


   def get(self, realm):
      """
      Implements :func:`autobahn.wamp.interfaces.IRouterFactory.get`
      """
      return self._routers[realm]


   def start_realm(self, realm):
      """
      Starts a realm on this router.

      :param realm: The realm to start.
      :type realm: instance of :class:`crossbar.worker.router.RouterRealm`.
      """
      if self.debug:
         log.msg("CrossbarRouterFactory.start_realm(realm = {})".format(realm))

      uri = realm.config['name']
      assert(uri not in self._routers)

      self._routers[uri] = CrossbarRouter(self, realm, self._options)
      if self.debug:
         log.msg("Router created for realm '{}'".format(uri))


   def stop_realm(self, realm):
      if self.debug:
         log.msg("CrossbarRouterFactory.stop_realm(realm = {})".format(realm))


   def add_role(self, realm, config):
      if self.debug:
         log.msg("CrossbarRouterFactory.add_role(realm = {}, config = {})".format(realm, config))

      assert(realm in self._routers)

      router = self._routers[realm]
      uri = config['name']

      if 'permissions' in config:
         role = CrossbarRouterRoleStaticAuth(router, uri, config['permissions'], debug = self.debug)
      elif 'authorizer' in config:
         role = CrossbarRouterRoleDynamicAuth(router, uri, config['authorizer'], debug = self.debug)
      else:
         role = CrossbarRouterRole(router, uri, debug = self.debug)

      router.add_role(role)


   def drop_role(self, realm, role):
      if self.debug:
         log.msg("CrossbarRouterFactory.drop_role(realm = {}, role = {})".format(realm, role))
