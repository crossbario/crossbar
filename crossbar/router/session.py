#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

import json
import traceback
import six

from six.moves import urllib

from twisted.python import log
from twisted.internet.defer import Deferred

from autobahn import util
from autobahn.websocket.compress import *  # noqa

from autobahn import wamp
from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.protocol import BaseSession
from autobahn.wamp.exception import ProtocolError, SessionNotReady
from autobahn.wamp.types import SessionDetails
from autobahn.wamp.interfaces import ITransportHandler

import txaio

from crossbar.router.auth import PendingAuthPersona, \
    PendingAuthWampCra, \
    PendingAuthTicket


__all__ = (
    'CrossbarRouterSessionFactory',
    'CrossbarRouterSession',
)


class RouterApplicationSession:

    """
    Wraps an application session to run directly attached to a WAMP router (broker+dealer).
    """

    def __init__(self, session, routerFactory, authid=None, authrole=None):
        """
        Wrap an application session and add it to the given broker and dealer.

        :param session: Application session to wrap.
        :type session: An instance that implements :class:`autobahn.wamp.interfaces.ISession`
        :param routerFactory: The router factory to associate this session with.
        :type routerFactory: An instance that implements :class:`autobahn.wamp.interfaces.IRouterFactory`
        :param authid: The fixed/trusted authentication ID under which the session will run.
        :type authid: str
        :param authrole: The fixed/trusted authentication role under which the session will run.
        :type authrole: str
        """

        assert(authid is None or isinstance(authid, six.text_type))
        assert(authrole is None or isinstance(authrole, six.text_type))

        # remember router we are wrapping the app session for
        #
        self._routerFactory = routerFactory
        self._router = None

        # remember wrapped app session
        #
        self._session = session

        # remember "trusted" authentication information
        #
        self._trusted_authid = authid
        self._trusted_authrole = authrole

        # set fake transport on session ("pass-through transport")
        #
        self._session._transport = self

        self._session.onConnect()

    def isOpen(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.isOpen`
        """

    def close(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.close`
        """
        if self._router:
            self._router.detach(self._session)

    def abort(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.abort`
        """

    def send(self, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.send`
        """
        if isinstance(msg, message.Hello):

            self._router = self._routerFactory.get(msg.realm)

            # fake session ID assignment (normally done in WAMP opening handshake)
            self._session._session_id = util.id()

            # set fixed/trusted authentication information
            self._session._authid = self._trusted_authid
            self._session._authrole = self._trusted_authrole
            self._session._authmethod = None
            # FIXME: the following does blow up
            # self._session._authmethod = u'trusted'
            self._session._authprovider = None

            # add app session to router
            self._router.attach(self._session)

            # fake app session open
            #
            details = SessionDetails(self._session._realm, self._session._session_id,
                                     self._session._authid, self._session._authrole, self._session._authmethod,
                                     self._session._authprovider)

            txaio.as_future(self._session.onJoin, details)
            # self._session.onJoin(details)

        # app-to-router
        #
        elif isinstance(msg, message.Publish) or \
            isinstance(msg, message.Subscribe) or \
            isinstance(msg, message.Unsubscribe) or \
            isinstance(msg, message.Call) or \
            isinstance(msg, message.Yield) or \
            isinstance(msg, message.Register) or \
            isinstance(msg, message.Unregister) or \
            isinstance(msg, message.Cancel) or \
            (isinstance(msg, message.Error) and
             msg.request_type == message.Invocation.MESSAGE_TYPE):

            # deliver message to router
            #
            self._router.process(self._session, msg)

        # router-to-app
        #
        elif isinstance(msg, message.Event) or \
            isinstance(msg, message.Invocation) or \
            isinstance(msg, message.Result) or \
            isinstance(msg, message.Published) or \
            isinstance(msg, message.Subscribed) or \
            isinstance(msg, message.Unsubscribed) or \
            isinstance(msg, message.Registered) or \
            isinstance(msg, message.Unregistered) or \
            (isinstance(msg, message.Error) and (
                msg.request_type == message.Call.MESSAGE_TYPE or
                msg.request_type == message.Cancel.MESSAGE_TYPE or
                msg.request_type == message.Register.MESSAGE_TYPE or
                msg.request_type == message.Unregister.MESSAGE_TYPE or
                msg.request_type == message.Publish.MESSAGE_TYPE or
                msg.request_type == message.Subscribe.MESSAGE_TYPE or
                msg.request_type == message.Unsubscribe.MESSAGE_TYPE)):

            # deliver message to app session
            #
            self._session.onMessage(msg)

        else:
            # should not arrive here
            #
            raise Exception("RouterApplicationSession.send: unhandled message {0}".format(msg))


class RouterSession(BaseSession):
    """
    WAMP router session. This class implements :class:`autobahn.wamp.interfaces.ITransportHandler`.
    """

    def __init__(self, routerFactory):
        """
        Constructor.
        """
        BaseSession.__init__(self)
        self._transport = None

        self._router_factory = routerFactory
        self._router = None
        self._realm = None

        self._goodbye_sent = False
        self._transport_is_closing = False

    def onOpen(self, transport):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onOpen`
        """
        self._transport = transport

        self._realm = None
        self._session_id = None
        self._pending_session_id = None
        self._session_roles = None

        # session authentication information
        #
        self._authid = None
        self._authrole = None
        self._authmethod = None
        self._authprovider = None

    def onHello(self, realm, details):
        return types.Accept()

    def onAuthenticate(self, signature, extra):
        return types.Accept()

    def onMessage(self, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onMessage`
        """
        if self._session_id is None:

            if not self._pending_session_id:
                self._pending_session_id = util.id()

            def welcome(realm, authid=None, authrole=None, authmethod=None, authprovider=None):
                self._session_id = self._pending_session_id
                self._pending_session_id = None
                self._goodbye_sent = False

                self._router = self._router_factory.get(realm)
                if not self._router:
                    raise Exception("no such realm")

                self._authid = authid
                self._authrole = authrole
                self._authmethod = authmethod
                self._authprovider = authprovider

                roles = self._router.attach(self)

                msg = message.Welcome(self._session_id, roles, authid=authid, authrole=authrole, authmethod=authmethod, authprovider=authprovider)
                self._transport.send(msg)

                self.onJoin(SessionDetails(self._realm, self._session_id, self._authid, self._authrole, self._authmethod, self._authprovider))

            # the first message MUST be HELLO
            if isinstance(msg, message.Hello):

                self._realm = msg.realm
                self._session_roles = msg.roles

                details = types.HelloDetails(msg.roles, msg.authmethods, msg.authid, self._pending_session_id)

                d = txaio.as_future(self.onHello, self._realm, details)

                def success(res):
                    msg = None

                    if isinstance(res, types.Accept):
                        welcome(self._realm, res.authid, res.authrole, res.authmethod, res.authprovider)

                    elif isinstance(res, types.Challenge):
                        msg = message.Challenge(res.method, res.extra)

                    elif isinstance(res, types.Deny):
                        msg = message.Abort(res.reason, res.message)

                    else:
                        pass

                    if msg:
                        self._transport.send(msg)

                txaio.add_callbacks(d, success, self._onError)

            elif isinstance(msg, message.Authenticate):

                d = txaio.as_future(self.onAuthenticate, msg.signature, {})

                def success(res):
                    msg = None

                    if isinstance(res, types.Accept):
                        welcome(self._realm, res.authid, res.authrole, res.authmethod, res.authprovider)

                    elif isinstance(res, types.Deny):
                        msg = message.Abort(res.reason, res.message)

                    else:
                        pass

                    if msg:
                        self._transport.send(msg)

                txaio.add_callbacks(d, success, self._onError)

            elif isinstance(msg, message.Abort):

                # fire callback and close the transport
                self.onLeave(types.CloseDetails(msg.reason, msg.message))

                self._session_id = None
                self._pending_session_id = None

                # self._transport.close()

            else:
                raise ProtocolError("Received {0} message, and session is not yet established".format(msg.__class__))

        else:

            if isinstance(msg, message.Hello):
                raise ProtocolError(u"HELLO message received, while session is already established")

            elif isinstance(msg, message.Goodbye):
                if not self._goodbye_sent:
                    # the peer wants to close: send GOODBYE reply
                    reply = message.Goodbye()
                    self._transport.send(reply)

                # fire callback and close the transport
                self.onLeave(types.CloseDetails(msg.reason, msg.message))

                self._router.detach(self)

                self._session_id = None
                self._pending_session_id = None

                # self._transport.close()

            else:

                self._router.process(self, msg)

    # noinspection PyUnusedLocal
    def onClose(self, wasClean):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onClose`
        """
        self._transport = None

        if self._session_id:

            # fire callback and close the transport
            try:
                self.onLeave(types.CloseDetails())
            except Exception as e:
                if self.debug:
                    print("exception raised in onLeave callback: {0}".format(e))

            self._router.detach(self)

            self._session_id = None

        self._pending_session_id = None

        self._authid = None
        self._authrole = None
        self._authmethod = None
        self._authprovider = None

    def onJoin(self, details):
        """
        Implements :func:`autobahn.wamp.interfaces.ISession.onJoin`
        """

    def onLeave(self, details):
        """
        Implements :func:`autobahn.wamp.interfaces.ISession.onLeave`
        """

    def leave(self, reason=None, message=None):
        """
        Implements :func:`autobahn.wamp.interfaces.ISession.leave`
        """
        if not self._goodbye_sent:
            if reason:
                msg = wamp.message.Goodbye(reason, message)
            else:
                msg = wamp.message.Goodbye(message=message)

            self._transport.send(msg)
            self._goodbye_sent = True
        else:
            raise SessionNotReady(u"Already requested to close the session")

    def _onError(self, err):
        try:
            self.onError(err)
        except Exception as e:
            if self.debug:
                print("exception raised in onError callback: {0}".format(e))

        reply = message.Abort(u"wamp.error.authorization_failed", u"Internal server error")
        self._transport.send(reply)

        self._router.detach(self)

        self._session_id = None
        self._pending_session_id = None

    def onError(self, err):
        """
        Overwride for custom error handling.
        """
        if self.debug:
            print("Catched exception during message processing: {0}".format(err.getTraceback()))  # replace with proper logging


ITransportHandler.register(RouterSession)


class RouterSessionFactory(object):
    """
    WAMP router session factory.
    """

    session = RouterSession
    """
   WAMP router session class to be used in this factory.
   """

    def __init__(self, routerFactory):
        """

        :param routerFactory: The router factory this session factory is working for.
        :type routerFactory: Instance of :class:`autobahn.wamp.router.RouterFactory`.
        """
        self._routerFactory = routerFactory
        self._app_sessions = {}

    def add(self, session, authid=None, authrole=None):
        """
        Adds a WAMP application session to run directly in this router.

        :param: session: A WAMP application session.
        :type session: A instance of a class that derives of :class:`autobahn.wamp.protocol.WampAppSession`
        """
        self._app_sessions[session] = RouterApplicationSession(session, self._routerFactory, authid, authrole)

    def remove(self, session):
        """
        Removes a WAMP application session running directly in this router.
        """
        if session in self._app_sessions:
            self._app_sessions[session]._session.disconnect()
            del self._app_sessions[session]

    def __call__(self):
        """
        Creates a new WAMP router session.

        :returns: -- An instance of the WAMP router session class as
                     given by `self.session`.
        """
        session = self.session(self._routerFactory)
        session.factory = self
        return session


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
        self._service_session = None

    def onHello(self, realm, details):

        try:

            # check if the realm the session wants to join actually exists
            #
            if realm not in self._router_factory:
                return types.Deny(ApplicationError.NO_SUCH_REALM, message="no realm '{}' exists on this router".format(realm))

            # perform authentication
            #
            if self._transport._authid is not None:

                # already authenticated .. e.g. via cookie

                # check if role still exists on realm
                #
                allow = self._router_factory[realm].has_role(self._transport._authrole)

                if allow:
                    return types.Accept(authid=self._transport._authid,
                                        authrole=self._transport._authrole,
                                        authmethod=self._transport._authmethod,
                                        authprovider='transport')
                else:
                    return types.Deny(ApplicationError.NO_SUCH_ROLE, message="session was previously authenticated (via transport), but role '{}' no longer exists on realm '{}'".format(self._transport._authrole, realm))

            else:
                # if authentication is enabled on the transport ..
                #
                if "auth" in self._transport_config:

                    # iterate over authentication methods announced by client ..
                    #
                    for authmethod in details.authmethods or ["anonymous"]:

                        # .. and if the configuration has an entry for the authmethod
                        # announced, process ..
                        if authmethod in self._transport_config["auth"]:

                            # "WAMP-Challenge-Response" authentication
                            #
                            if authmethod == u"wampcra":
                                cfg = self._transport_config['auth']['wampcra']

                                if cfg['type'] == 'static':

                                    if details.authid in cfg.get('users', {}):

                                        user = cfg['users'][details.authid]

                                        # the authid the session will be authenticated as is from the user data, or when
                                        # the user data doesn't contain an authid, from the HELLO message the client sent
                                        #
                                        authid = user.get("authid", details.authid)

                                        # construct a pending WAMP-CRA authentication
                                        #
                                        self._pending_auth = PendingAuthWampCra(details.pending_session,
                                                                                authid,
                                                                                user['role'],
                                                                                u'static',
                                                                                user['secret'].encode('utf8'))

                                        # send challenge to client
                                        #
                                        extra = {
                                            u'challenge': self._pending_auth.challenge
                                        }

                                        # when using salted passwords, provide the client with
                                        # the salt and then PBKDF2 parameters used
                                        #
                                        if 'salt' in user:
                                            extra[u'salt'] = user['salt']
                                            extra[u'iterations'] = user.get('iterations', 1000)
                                            extra[u'keylen'] = user.get('keylen', 32)

                                        return types.Challenge(u'wampcra', extra)

                                    else:
                                        return types.Deny(message="no user with authid '{}' in user database".format(details.authid))

                                elif cfg['type'] == 'dynamic':

                                    # call the configured dynamic authenticator procedure
                                    # via the router's service session
                                    #
                                    service_session = self._router_factory.get(realm)._realm.session
                                    session_details = {
                                        # forward transport level details of the WAMP session that
                                        # wishes to authenticate
                                        u'transport': self._transport._transport_info,

                                        # the following WAMP session ID will be assigned to the session
                                        # if (and only if) the subsequent authentication succeeds.
                                        u'session': self._pending_session_id
                                    }
                                    d = service_session.call(cfg['authenticator'], realm, details.authid, session_details)

                                    def on_authenticate_ok(user):

                                        # the authid the session will be authenticated as is from the dynamic
                                        # authenticator response, or when the response doesn't contain an authid,
                                        # from the HELLO message the client sent
                                        #
                                        authid = user.get("authid", details.authid)

                                        # construct a pending WAMP-CRA authentication
                                        #
                                        self._pending_auth = PendingAuthWampCra(details.pending_session,
                                                                                authid,
                                                                                user['role'],
                                                                                u'dynamic',
                                                                                user['secret'].encode('utf8'))

                                        # send challenge to client
                                        #
                                        extra = {
                                            u'challenge': self._pending_auth.challenge
                                        }

                                        # when using salted passwords, provide the client with
                                        # the salt and the PBKDF2 parameters used
                                        #
                                        if 'salt' in user:
                                            extra[u'salt'] = user['salt']
                                            extra[u'iterations'] = user.get('iterations', 1000)
                                            extra[u'keylen'] = user.get('keylen', 32)

                                        return types.Challenge(u'wampcra', extra)

                                    def on_authenticate_error(err):

                                        error = None
                                        message = "dynamic WAMP-CRA credential getter failed: {}".format(err)

                                        if isinstance(err.value, ApplicationError):
                                            error = err.value.error
                                            if err.value.args and len(err.value.args):
                                                message = str(err.value.args[0])  # exception does not need to contain a string

                                        return types.Deny(error, message)

                                    d.addCallbacks(on_authenticate_ok, on_authenticate_error)

                                    return d

                                else:

                                    return types.Deny(message="illegal WAMP-CRA authentication config (type '{0}' is unknown)".format(cfg['type']))

                            # WAMP-Ticket authentication
                            #
                            elif authmethod == u"ticket":
                                cfg = self._transport_config['auth']['ticket']

                                # use static principal database from configuration
                                #
                                if cfg['type'] == 'static':

                                    if details.authid in cfg.get('principals', {}):

                                        principal = cfg['principals'][details.authid]

                                        # the authid the session will be authenticated as is from the principal data, or when
                                        # the principal data doesn't contain an authid, from the HELLO message the client sent
                                        #
                                        authid = principal.get("authid", details.authid)

                                        self._pending_auth = PendingAuthTicket(realm,
                                                                               authid,
                                                                               principal['role'],
                                                                               u'static',
                                                                               principal['ticket'].encode('utf8'))

                                        return types.Challenge(u'ticket')
                                    else:
                                        return types.Deny(message="no principal with authid '{}' in principal database".format(details.authid))

                                # use configured procedure to dynamically get a ticket for the principal
                                #
                                elif cfg['type'] == 'dynamic':

                                    self._pending_auth = PendingAuthTicket(realm,
                                                                           details.authid,
                                                                           None,
                                                                           cfg['authenticator'],
                                                                           None)

                                    return types.Challenge(u'ticket')

                                else:
                                    return types.Deny(message="illegal WAMP-Ticket authentication config (type '{0}' is unknown)".format(cfg['type']))

                            # "Mozilla Persona" authentication
                            #
                            elif authmethod == u"mozilla_persona":
                                cfg = self._transport_config['auth']['mozilla_persona']

                                audience = cfg.get('audience', self._transport._origin)
                                provider = cfg.get('provider', "https://verifier.login.persona.org/verify")

                                # authrole mapping
                                #
                                authrole = cfg.get('role', 'anonymous')

                                # check if role exists on realm anyway
                                #
                                if not self._router_factory[realm].has_role(authrole):
                                    return types.Deny(ApplicationError.NO_SUCH_ROLE, message="authentication failed - realm '{}' has no role '{}'".format(realm, authrole))

                                # ok, now challenge the client for doing Mozilla Persona auth.
                                #
                                self._pending_auth = PendingAuthPersona(provider, audience, authrole)
                                return types.Challenge("mozilla-persona")

                            # "Anonymous" authentication
                            #
                            elif authmethod == u"anonymous":
                                cfg = self._transport_config['auth']['anonymous']

                                # authrole mapping
                                #
                                authrole = cfg.get('role', 'anonymous')

                                # check if role exists on realm anyway
                                #
                                if not self._router_factory[realm].has_role(authrole):
                                    return types.Deny(ApplicationError.NO_SUCH_ROLE, message="authentication failed - realm '{}' has no role '{}'".format(realm, authrole))

                                # authid generation
                                #
                                if self._transport._cbtid:
                                    # if cookie tracking is enabled, set authid to cookie value
                                    #
                                    authid = self._transport._cbtid
                                else:
                                    # if no cookie tracking, generate a random value for authid
                                    #
                                    authid = util.newid(24)

                                self._transport._authid = authid
                                self._transport._authrole = authrole
                                self._transport._authmethod = authmethod

                                return types.Accept(authid=authid, authrole=authrole, authmethod=self._transport._authmethod)

                            # "Cookie" authentication
                            #
                            elif authmethod == u"cookie":
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
                                return types.Deny(message="unknown authentication method {}".format(authmethod))

                    # if authentication is configured, by default, deny.
                    #
                    return types.Deny(message="authentication using method '{}' denied by configuration".format(authmethod))

                else:
                    # if authentication is _not_ configured, by default, allow anyone.
                    #

                    # authid generation
                    #
                    if self._transport._cbtid:
                        # if cookie tracking is enabled, set authid to cookie value
                        #
                        authid = self._transport._cbtid
                    else:
                        # if no cookie tracking, generate a random value for authid
                        #
                        authid = util.newid(24)

                    return types.Accept(authid=authid, authrole="anonymous", authmethod="anonymous")

        except Exception as e:
            traceback.print_exc()
            return types.Deny(message="internal error: {}".format(e))

    def onAuthenticate(self, signature, extra):
        """
        Callback fired when a client responds to an authentication challenge.
        """
        print("onAuthenticate: {} {}".format(signature, extra))

        # if there is a pending auth, check the challenge response. The specifics
        # of how to check depend on the authentication method
        #
        if self._pending_auth:

            # WAMP-CRA
            #
            if isinstance(self._pending_auth, PendingAuthWampCra):

                if signature == self._pending_auth.signature:
                    # WAMP-CRA authentication signature was valid: accept the client
                    #
                    return types.Accept(authid=self._pending_auth.authid,
                                        authrole=self._pending_auth.authrole,
                                        authmethod=self._pending_auth.authmethod,
                                        authprovider=self._pending_auth.authprovider)
                else:
                    # WAMP-CRA authentication signature was invalid: deny client
                    #
                    return types.Deny(message=u"signature is invalid")

            # WAMP-Ticket
            #
            elif isinstance(self._pending_auth, PendingAuthTicket):

                # when doing WAMP-Ticket from static configuration, the ticket we
                # expect was store on the pending authentication object and we just compare ..
                #
                if self._pending_auth.authprovider == 'static':
                    if signature == self._pending_auth.ticket:
                        # WAMP-Ticket authentication ticket was valid: accept the client
                        #
                        return types.Accept(authid=self._pending_auth.authid,
                                            authrole=self._pending_auth.authrole,
                                            authmethod=self._pending_auth.authmethod,
                                            authprovider=self._pending_auth.authprovider)
                    else:
                        # WAMP-Ticket authentication ticket was invalid: deny client
                        #
                        return types.Deny(message=u"ticket is invalid")

                # WAMP-Ticket dynamic ..
                #
                else:
                    # call the configured dynamic authenticator procedure
                    # via the router's service session
                    #
                    service_session = self._router_factory.get(self._pending_auth.realm)._realm.session

                    d = service_session.call(self._pending_auth.authprovider,
                                             self._pending_auth.realm,
                                             self._pending_auth.authid,
                                             signature)

                    def on_authenticate_ok(principal):

                        if isinstance(principal, dict):
                            # dynamic ticket authenticator returned a dictionary (new)
                            authid = principal.get("authid", self._pending_auth.authid)
                            authrole = principal["role"]
                        else:
                            # backwards compatibility: dynamic ticket authenticator
                            # was expected to return a role directly
                            authid = self._pending_auth.authid
                            authrole = principal

                        return types.Accept(authid=authid,
                                            authrole=authrole,
                                            authmethod=self._pending_auth.authmethod,
                                            authprovider=self._pending_auth.authprovider)

                    def on_authenticate_error(err):
                        error = None
                        message = "dynamic WAMP-Ticket credential getter failed: {}".format(err)

                        if isinstance(err.value, ApplicationError):
                            error = err.value.error
                            if err.value.args and len(err.value.args):
                                message = err.value.args[0]

                        return types.Deny(error, message)

                    d.addCallbacks(on_authenticate_ok, on_authenticate_error)

                    return d

            elif isinstance(self._pending_auth, PendingAuthPersona):

                dres = Deferred()

                # The client did it's Mozilla Persona authentication thing
                # and now wants to verify the authentication and login.
                assertion = signature
                audience = str(self._pending_auth.audience)  # eg "http://192.168.1.130:8080/"
                provider = str(self._pending_auth.provider)  # eg "https://verifier.login.persona.org/verify"

                # To verify the authentication, we need to send a HTTP/POST
                # to Mozilla Persona. When successful, Persona will send us
                # back something like:

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
                d = getPage(url=provider,
                            method='POST',
                            postdata=body,
                            headers=headers)

                log.msg("Authentication request sent.")

                def done(res):
                    res = json.loads(res)
                    try:
                        if res['status'] == 'okay':

                            # awesome: Mozilla Persona successfully authenticated the user
                            self._transport._authid = res['email']
                            self._transport._authrole = self._pending_auth.role
                            self._transport._authmethod = 'mozilla_persona'

                            log.msg("Authenticated user {} with role {}".format(self._transport._authid, self._transport._authrole))
                            dres.callback(types.Accept(authid=self._transport._authid, authrole=self._transport._authrole, authmethod=self._transport._authmethod))

                            # remember the user's auth info (this marks the cookie as authenticated)
                            if self._transport._cbtid and self._transport.factory._cookiestore:
                                cs = self._transport.factory._cookiestore
                                cs.setAuth(self._transport._cbtid, self._transport._authid, self._transport._authrole, self._transport._authmethod)

                                # kick all sessions using same cookie (but not _this_ connection)
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
                            dres.callback(types.Deny(reason="wamp.error.authorization_failed", message=res.get("reason", None)))
                    except Exception as e:
                        log.msg("internal error during authentication verification: {}".format(e))
                        dres.callback(types.Deny(reason="wamp.error.internal_error", message=str(e)))

                def error(err):
                    log.msg("Authentication request failed: {}".format(err.value))
                    dres.callback(types.Deny(reason="wamp.error.authorization_request_failed", message=str(err.value)))

                d.addCallbacks(done, error)

                return dres

            else:

                log.msg("don't know how to authenticate")

                return types.Deny()

        else:

            # deny client
            return types.Deny(message=u"no pending authentication")

    def onJoin(self, details):

        # Router/Realm service session
        #
        self._service_session = self._router._realm.session
        # self._router:                  crossbar.router.session.CrossbarRouter
        # self._router_factory:          crossbar.router.session.CrossbarRouterFactory
        # self._router._realm:           crossbar.worker.router.RouterRealm
        # self._router._realm.session:   crossbar.router.session.CrossbarRouterServiceSession

        self._session_details = {
            u'authid': details.authid,
            u'authrole': details.authrole,
            u'authmethod': details.authmethod,
            u'authprovider': details.authprovider,
            u'realm': details.realm,
            u'session': details.session,
            u'transport': self._transport._transport_info
        }

        # dispatch session metaevent from WAMP AP
        #
        self._service_session.publish(u'wamp.session.on_join', self._session_details)

    def onLeave(self, details):

        # dispatch session metaevent from WAMP AP
        #
        self._service_session.publish(u'wamp.session.on_leave', self._session_id)

        self._session_details = None

        # if asked to explicitly close the session ..
        if details.reason == u"wamp.close.logout":

            # if cookie was set on transport ..
            if self._transport._cbtid and self._transport.factory._cookiestore:
                cs = self._transport.factory._cookiestore

                # set cookie to "not authenticated"
                cs.setAuth(self._transport._cbtid, None, None, None)

                # kick all session for the same auth cookie
                for proto in cs.getProtos(self._transport._cbtid):
                    proto.sendClose()


class CrossbarRouterSessionFactory(RouterSessionFactory):

    """
    Factory creating the router side of (non-embedded) Crossbar.io WAMP sessions.
    This is the session factory that will given to router transports.
    """
    session = CrossbarRouterSession
