#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
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

from __future__ import absolute_import, division

import os
import binascii

import txaio

from txaio import make_logger

from autobahn import util

from autobahn import wamp
from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.protocol import BaseSession
from autobahn.wamp.exception import ProtocolError, SessionNotReady
from autobahn.wamp.types import SessionDetails
from autobahn.wamp.interfaces import ITransportHandler

from crossbar.common.twisted.endpoint import extract_peer_certificate
from crossbar.router.auth import PendingAuthWampCra, PendingAuthTicket, PendingAuthScram
from crossbar.router.auth import AUTHMETHODS, AUTHMETHOD_MAP

from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure

try:
    from crossbar.router.auth import PendingAuthCryptosign
except ImportError:
    PendingAuthCryptosign = None


__all__ = ('RouterSessionFactory',)


class RouterApplicationSession(object):
    """
    Wraps an application session to run directly attached to a WAMP router (broker+dealer).
    """

    log = make_logger()

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

        assert(authid is None or isinstance(authid, str))
        assert(authrole is None or isinstance(authrole, str))

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

        self._session.fire('connect', self._session, self)
        self._session.onConnect()

    def _swallow_error(self, fail, msg):
        try:
            if self._session:
                self._session.onUserError(fail, msg)
        except:
            pass
        return None

    def _log_error(self, fail, msg):
        self.log.failure(msg, failure=fail)
        return None

    def isOpen(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.isOpen`
        """

    @property
    def is_closed(self):
        return txaio.create_future(result=self)

    def close(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.close`
        """
        if self._router:
            # See also #578; this is to prevent the set() of observers
            # shrinking while itering in broker.py:329 since the
            # send() call happens synchronously because this class is
            # acting as ITransport and the send() can result in an
            # immediate disconnect which winds up right here...so we
            # take at trip through the reactor loop.
            from twisted.internet import reactor

            def detach(sess):
                try:
                    self._router.detach(sess)
                except Exception:
                    pass
            reactor.callLater(0, detach, self._session)

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
            self._session._authextra = None

            # add app session to router
            self._router.attach(self._session)

            # fake app session open
            details = SessionDetails(self._session._realm,
                                     self._session._session_id,
                                     self._session._authid,
                                     self._session._authrole,
                                     self._session._authmethod,
                                     self._session._authprovider,
                                     self._session._authextra)

            # have to fire the 'join' notification ourselves, as we're
            # faking out what the protocol usually does.
            d = self._session.fire('join', self._session, details)
            d.addErrback(lambda fail: self._log_error(fail, "While notifying 'join'"))
            # now fire onJoin (since _log_error returns None, we'll be
            # back in the callback chain even on errors from 'join'
            d.addCallback(lambda _: txaio.as_future(self._session.onJoin, details))
            d.addErrback(lambda fail: self._swallow_error(fail, "While firing onJoin"))
            d.addCallback(lambda _: self._session.fire('ready', self._session))
            d.addErrback(lambda fail: self._log_error(fail, "While notifying 'ready'"))

        # app-to-router
        #
        elif isinstance(msg, (message.Publish,
                              message.Subscribe,
                              message.Unsubscribe,
                              message.Call,
                              message.Yield,
                              message.Register,
                              message.Unregister,
                              message.Cancel)) or (isinstance(msg, message.Error) and msg.request_type == message.Invocation.MESSAGE_TYPE):

            # deliver message to router
            #
            self._router.process(self._session, msg)

        # router-to-app
        #
        elif isinstance(msg, (message.Event,
                              message.Invocation,
                              message.Result,
                              message.Published,
                              message.Subscribed,
                              message.Unsubscribed,
                              message.Registered,
                              message.Unregistered)) or \
            (isinstance(msg, message.Error) and (msg.request_type in {
                message.Call.MESSAGE_TYPE,
                message.Cancel.MESSAGE_TYPE,
                message.Register.MESSAGE_TYPE,
                message.Unregister.MESSAGE_TYPE,
                message.Publish.MESSAGE_TYPE,
                message.Subscribe.MESSAGE_TYPE,
                message.Unsubscribe.MESSAGE_TYPE})):

            # deliver message to app session
            #
            self._session.onMessage(msg)

        # ignore messages
        #
        elif isinstance(msg, message.Goodbye):
            details = types.CloseDetails(msg.reason, msg.message)
            session = self._session

            @inlineCallbacks
            def do_goodbye():
                try:
                    yield session.onLeave(details)
                except Exception:
                    self._log_error(Failure(), "While firing onLeave")

                if session._transport:
                    session._transport.close()

                try:
                    yield session.fire('leave', session, details)
                except Exception:
                    self._log_error(Failure(), "While notifying 'leave'")

                try:
                    yield session.fire('disconnect', session)
                except Exception:
                    self._log_error(Failure(), "While notifying 'disconnect'")

                if self._router._realm.session:
                    yield self._router._realm.session.publish(
                        u'wamp.session.on_leave',
                        session._session_id,
                    )
            d = do_goodbye()
            d.addErrback(lambda fail: self._log_error(fail, "Internal error"))

        else:
            # should not arrive here
            #
            raise Exception("RouterApplicationSession.send: unhandled message {0}".format(msg))


class RouterSession(BaseSession):
    """
    WAMP router session. This class implements :class:`autobahn.wamp.interfaces.ITransportHandler`.
    """

    log = make_logger()

    def __init__(self, router_factory):
        """
        Constructor.
        """
        super(RouterSession, self).__init__()
        self._transport = None

        self._router_factory = router_factory
        self._router = None
        self._realm = None
        self._testaments = {u"destroyed": [], u"detached": []}

        self._goodbye_sent = False
        self._transport_is_closing = False
        self._session_details = None

    def onOpen(self, transport):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onOpen`
        """
        # this is a WAMP transport instance
        self._transport = transport

        # WampLongPollResourceSession instance has no attribute '_transport_info'
        if not hasattr(self._transport, '_transport_info'):
            self._transport._transport_info = {}

        # transport configuration
        if hasattr(self._transport, 'factory') and hasattr(self._transport.factory, '_config'):
            self._transport_config = self._transport.factory._config
        else:
            self._transport_config = {}

        # a dict with x509 TLS client certificate information (if the client provided a cert)
        # constructed from information from the Twisted stream transport underlying the WAMP transport
        client_cert = None
        # eg LongPoll transports lack underlying Twisted stream transport, since LongPoll is
        # implemented at the Twisted Web layer. But we should nevertheless be able to
        # extract the HTTP client cert! <= FIXME
        if hasattr(self._transport, 'transport'):
            client_cert = extract_peer_certificate(self._transport.transport)
        if client_cert:
            self._transport._transport_info[u'client_cert'] = client_cert
            self.log.debug("Client connecting with TLS certificate {client_cert}", client_cert=client_cert)

        # forward the transport channel ID (if any) on transport details
        channel_id = None
        if hasattr(self._transport, 'get_channel_id'):
            # channel ID isn't implemented for LongPolL!
            channel_id = self._transport.get_channel_id()
        if channel_id:
            self._transport._transport_info[u'channel_id'] = binascii.b2a_hex(channel_id).decode('ascii')

        self.log.debug("Client session connected - transport: {transport_info}", transport_info=self._transport._transport_info)

        # basic session information
        self._pending_session_id = None
        self._realm = None
        self._session_id = None
        self._session_roles = None
        self._session_details = None

        # session authentication information
        self._pending_auth = None
        self._authid = None
        self._authrole = None
        self._authmethod = None
        self._authprovider = None
        self._authextra = None

        # the service session to be used eg for WAMP metaevents
        self._service_session = None

    def onMessage(self, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onMessage`
        """
        if self._session_id is None:

            if not self._pending_session_id:
                self._pending_session_id = util.id()

            def welcome(realm, authid=None, authrole=None, authmethod=None, authprovider=None, authextra=None, custom=None):
                self._realm = realm
                self._session_id = self._pending_session_id
                self._pending_session_id = None
                self._goodbye_sent = False

                self._router = self._router_factory.get(realm)
                if not self._router:
                    # should not arrive here
                    raise Exception("logic error (no realm at a stage were we should have one)")

                self._authid = authid
                self._authrole = authrole
                self._authmethod = authmethod
                self._authprovider = authprovider
                self._authextra = authextra or {}

                self._authextra[u'x_cb_node_id'] = self._router_factory._node_id
                self._authextra[u'x_cb_peer'] = str(self._transport.peer)
                self._authextra[u'x_cb_pid'] = os.getpid()

                roles = self._router.attach(self)

                msg = message.Welcome(self._session_id,
                                      roles,
                                      realm=realm,
                                      authid=authid,
                                      authrole=authrole,
                                      authmethod=authmethod,
                                      authprovider=authprovider,
                                      authextra=self._authextra,
                                      custom=custom)
                self._transport.send(msg)

                self.onJoin(SessionDetails(self._realm, self._session_id, self._authid, self._authrole, self._authmethod, self._authprovider, self._authextra))

            # the first message MUST be HELLO
            if isinstance(msg, message.Hello):

                self._session_roles = msg.roles

                details = types.HelloDetails(realm=msg.realm,
                                             authmethods=msg.authmethods,
                                             authid=msg.authid,
                                             authrole=msg.authrole,
                                             authextra=msg.authextra,
                                             session_roles=msg.roles,
                                             pending_session=self._pending_session_id)

                d = txaio.as_future(self.onHello, msg.realm, details)

                def success(res):
                    msg = None
                    if isinstance(res, types.Accept):
                        custom = {
                            u'x_cb_node_id': self._router_factory._node_id
                        }
                        welcome(res.realm, res.authid, res.authrole, res.authmethod, res.authprovider, res.authextra, custom)

                    elif isinstance(res, types.Challenge):
                        msg = message.Challenge(res.method, res.extra)

                    elif isinstance(res, types.Deny):
                        msg = message.Abort(res.reason, res.message)

                    else:
                        pass

                    if msg:
                        self._transport.send(msg)

                txaio.add_callbacks(d, success, self._swallow_error_and_abort)

            elif isinstance(msg, message.Authenticate):

                d = txaio.as_future(self.onAuthenticate, msg.signature, {})

                def success(res):
                    msg = None
                    if isinstance(res, types.Accept):
                        custom = {
                            u'x_cb_node_id': self._router_factory._node_id
                        }
                        welcome(res.realm, res.authid, res.authrole, res.authmethod, res.authprovider, res.authextra, custom)

                    elif isinstance(res, types.Deny):
                        msg = message.Abort(res.reason, res.message)

                    else:
                        pass

                    if msg:
                        self._transport.send(msg)

                txaio.add_callbacks(d, success, self._swallow_error_and_abort)

            elif isinstance(msg, message.Abort):

                # fire callback and close the transport
                self.onLeave(types.CloseDetails(msg.reason, msg.message))

                self._session_id = None
                self._pending_session_id = None

                # self._transport.close()

            else:
                # raise ProtocolError(u"PReceived {0} message while session is not joined".format(msg.__class__))
                # self.log.warn('Protocol state error - received {message} while session is not joined')
                # swallow all noise like still getting PUBLISH messages from log event forwarding - maybe FIXME
                pass

        else:

            if isinstance(msg, message.Hello):
                raise ProtocolError(u"HELLO message received, while session is already established")

            elif isinstance(msg, message.Goodbye):
                if not self._goodbye_sent:
                    # The peer wants to close: answer with GOODBYE reply.
                    # Note: We MUST NOT send any WAMP message _after_ GOODBYE
                    reply = message.Goodbye()
                    self._transport.send(reply)
                    self._goodbye_sent = True
                else:
                    # This is the peer's GOODBYE reply to our own earlier GOODBYE
                    pass

                # We need to first detach the session from the router before
                # erasing the session ID below ..
                try:
                    self._router.detach(self)
                except Exception:
                    self.log.failure("Internal error")

                # In order to send wamp.session.on_leave properly
                # (i.e. *with* the proper session_id) we save it
                previous_session_id = self._session_id

                # At this point, we've either sent GOODBYE already earlier,
                # or we have just responded with GOODBYE. In any case, we MUST NOT
                # send any WAMP message from now on:
                # clear out session ID, so that anything that might be triggered
                # in the onLeave below is prohibited from sending WAMP stuff.
                # E.g. the client might have been subscribed to meta events like
                # wamp.session.on_leave - and we must not send that client's own
                # leave to itself!
                self._session_id = None
                self._pending_session_id = None

                # publish event, *after* self._session_id is None so
                # that we don't publish to ourselves as well (if this
                # session happens to be subscribed to wamp.session.on_leave)
                if self._service_session:
                    self._service_session.publish(
                        u'wamp.session.on_leave',
                        previous_session_id,
                    )

                # fire callback and close the transport
                self.onLeave(types.CloseDetails(msg.reason, msg.message))

                # don't close the transport, as WAMP allows to reattach a session
                # to the same or a different realm without closing the transport
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
            except Exception:
                self.log.failure("Exception raised in onLeave callback")

            try:
                self._router.detach(self)
            except Exception as e:
                self.log.error(
                    "Failed to detach session '{}': {}".format(self._session_id, e)
                )
                self.log.debug("{tb}".format(tb=Failure().getTraceback()))

            self._session_id = None

        self._pending_session_id = None

        self._authid = None
        self._authrole = None
        self._authmethod = None
        self._authprovider = None

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

    def _swallow_error_and_abort(self, fail):
        """
        Internal method that logs an error that would otherwise be
        unhandled and also *cancels it*. This will also completely
        abort the session, sending Abort to the other side.

        DO NOT attach to Deferreds that are returned to calling code.
        """
        self.log.failure("Internal error (2): {log_failure.value}", failure=fail)

        # tell other side we're done
        reply = message.Abort(u"wamp.error.authorization_failed", u"Internal server error")
        self._transport.send(reply)

        # cleanup
        if self._router:
            try:
                self._router.detach(self)
            except Exception:
                pass
        self._session_id = None
        self._pending_session_id = None
        return None  # we've handled the error; don't propagate

    def onHello(self, realm, details):

        try:
            # allow "Personality" classes to add authmethods
            extra_auth_methods = dict()
            if self._router_factory._worker:
                personality = self._router_factory._worker.personality
                extra_auth_methods = personality.EXTRA_AUTH_METHODS

            # default authentication method is "WAMP-Anonymous" if client doesn't specify otherwise
            authmethods = details.authmethods or [u'anonymous']
            authextra = details.authextra

            self.log.debug('onHello: {methods} {authextra}', authextra=authextra, methods=authmethods)

            # if the client had a reassigned realm during authentication, restore it from the cookie
            if hasattr(self._transport, '_authrealm') and self._transport._authrealm:
                if u'cookie' in authmethods:
                    realm = self._transport._authrealm
                    authextra = self._transport._authextra
                elif self._transport._authprovider == u'cookie':
                    # revoke authentication and invalidate cookie (will be revalidated if following auth is successful)
                    self._transport._authmethod = None
                    self._transport._authrealm = None
                    self._transport._authid = None
                    if hasattr(self._transport, '_cbtid'):
                        self._transport.factory._cookiestore.setAuth(self._transport._cbtid, None, None, None, None, None)
                else:
                    pass  # TLS authentication is not revoked here

            # perform authentication
            if self._transport._authid is not None and (self._transport._authmethod == u'trusted' or self._transport._authprovider in authmethods):

                # already authenticated .. e.g. via HTTP Cookie or TLS client-certificate

                # check if role still exists on realm
                allow = self._router_factory[realm].has_role(self._transport._authrole)

                if allow:
                    return types.Accept(realm=realm,
                                        authid=self._transport._authid,
                                        authrole=self._transport._authrole,
                                        authmethod=self._transport._authmethod,
                                        authprovider=self._transport._authprovider,
                                        authextra=authextra)
                else:
                    return types.Deny(ApplicationError.NO_SUCH_ROLE, message="session was previously authenticated (via transport), but role '{}' no longer exists on realm '{}'".format(self._transport._authrole, realm))

            else:
                auth_config = self._transport_config.get(u'auth', None)

                if not auth_config:
                    # if authentication is _not_ configured, allow anyone to join as "anonymous"!

                    # .. but don't if the client isn't ready/willing to go on "anonymous"
                    if u'anonymous' not in authmethods:
                        return types.Deny(ApplicationError.NO_AUTH_METHOD, message=u'cannot authenticate using any of the offered authmethods {}'.format(authmethods))

                    authmethod = u'anonymous'

                    if not realm:
                        return types.Deny(ApplicationError.NO_SUCH_REALM, message=u'no realm requested')

                    if realm not in self._router_factory:
                        return types.Deny(ApplicationError.NO_SUCH_REALM, message=u'no realm "{}" exists on this router'.format(realm))

                    # we ignore any details.authid the client might have announced, and use
                    # a cookie value or a random value
                    if hasattr(self._transport, "_cbtid") and self._transport._cbtid:
                        # if cookie tracking is enabled, set authid to cookie value
                        authid = self._transport._cbtid
                    else:
                        # if no cookie tracking, generate a random value for authid
                        authid = util.generate_serial_number()

                    try:
                        PendingAuthKlass = AUTHMETHOD_MAP[authmethod]
                    except KeyError:
                        PendingAuthKlass = extra_auth_methods[authmethod]
                    self._pending_auth = PendingAuthKlass(self, {u'type': u'static', u'authrole': u'anonymous', u'authid': authid})
                    return self._pending_auth.hello(realm, details)

                else:
                    # iterate over authentication methods announced by client ..
                    for authmethod in authmethods:

                        # invalid authmethod
                        if authmethod not in AUTHMETHODS and authmethod not in extra_auth_methods:
                            self.log.debug("Unknown authmethod: {}".format(authmethod))
                            return types.Deny(message=u'invalid authmethod "{}"'.format(authmethod))

                        # authmethod not configured
                        if authmethod not in auth_config:
                            self.log.debug("client requested valid, but unconfigured authentication method {authmethod}", authmethod=authmethod)
                            continue

                        # authmethod not available
                        if authmethod not in AUTHMETHOD_MAP and authmethod not in extra_auth_methods:
                            self.log.debug("client requested valid, but unavailable authentication method {authmethod}", authmethod=authmethod)
                            continue

                        # WAMP-Anonymous, WAMP-Ticket, WAMP-CRA, WAMP-TLS, WAMP-Cryptosign
                        # WAMP-SCRAM
                        pending_auth_methods = [
                            u'anonymous', u'ticket', u'wampcra', u'tls',
                            u'cryptosign', u'scram',
                        ] + list(extra_auth_methods.keys())
                        if authmethod in pending_auth_methods:
                            try:
                                PendingAuthKlass = AUTHMETHOD_MAP[authmethod]
                            except KeyError:
                                PendingAuthKlass = extra_auth_methods[authmethod]
                            self._pending_auth = PendingAuthKlass(self, auth_config[authmethod])
                            return self._pending_auth.hello(realm, details)

                        # WAMP-Cookie authentication
                        elif authmethod == u'cookie':
                            # the client requested cookie authentication, but there is 1) no cookie set,
                            # or 2) a cookie set, but that cookie wasn't authenticated before using
                            # a different auth method (if it had been, we would never have entered here, since then
                            # auth info would already have been extracted from the transport)
                            # consequently, we skip this auth method and move on to next auth method.
                            continue

                        else:
                            # should not arrive here
                            raise Exception("logic error")

                    # no suitable authmethod found!
                    return types.Deny(ApplicationError.NO_AUTH_METHOD, message=u'cannot authenticate using any of the offered authmethods {}'.format(authmethods))

        except Exception as e:
            self.log.failure('internal error: {log_failure.value}')
            self.log.critical("internal error: {msg}", msg=str(e))
            return types.Deny(message=u'internal error: {}'.format(e))

    def onAuthenticate(self, signature, extra):
        """
        Callback fired when a client responds to an authentication CHALLENGE.
        """
        self.log.debug("onAuthenticate: {signature} {extra}", signature=signature, extra=extra)

        # if there is a pending auth, check the challenge response. The specifics
        # of how to check depend on the authentication method
        if self._pending_auth:

            # WAMP-Ticket, WAMP-CRA, WAMP-Cryptosign
            if isinstance(self._pending_auth, PendingAuthTicket) or \
               isinstance(self._pending_auth, PendingAuthWampCra) or \
               isinstance(self._pending_auth, PendingAuthCryptosign) or \
               isinstance(self._pending_auth, PendingAuthScram):
                return self._pending_auth.authenticate(signature)

            # should not arrive here: logic error
            else:
                self.log.warn('unexpected pending authentication {pending_auth}', pending_auth=self._pending_auth)
                return types.Deny(message=u'internal error: unexpected pending authentication')

        # should not arrive here: client misbehaving!
        else:
            return types.Deny(message=u'no pending authentication')

    def onJoin(self, details):

        if hasattr(self._transport, '_cbtid') and self._transport._cbtid:
            if details.authmethod != 'cookie':
                self._transport.factory._cookiestore.setAuth(self._transport._cbtid, details.authid, details.authrole, details.authmethod, details.authextra, self._realm)

        # Router/Realm service session
        #
        self._service_session = self._router._realm.session
        # self._router:                  crossbar.router.session.CrossbarRouter
        # self._router_factory:          crossbar.router.session.CrossbarRouterFactory
        # self._router._realm:           crossbar.worker.router.RouterRealm
        # self._router._realm.session:   crossbar.router.session.CrossbarRouterServiceSession

        self._session_details = details
        self._router._session_joined(self, details)

        # dispatch session metaevent from WAMP AP
        #
        if self._service_session:
            evt = {
                u'session': details.session,
                u'authid': details.authid,
                u'authrole': details.authrole,
                u'authmethod': details.authmethod,
                u'authextra': details.authextra,
                u'authprovider': details.authprovider,
                u'transport': self._transport._transport_info
            }
            self._service_session.publish(u'wamp.session.on_join', evt)

    def onWelcome(self, msg):
        # this is a hook for authentication methods to deny the
        # session after the Welcome message -- do we need to do
        # anything in this impl?
        pass

    def onLeave(self, details):

        # _router can be None when, e.g., authentication fails hard
        # (e.g. the client aborts the connection during auth challenge
        # because they hit a syntax error)
        if self._router is not None:
            # todo: move me into detatch when session resumption happens
            for msg in self._testaments[u"detached"]:
                self._router.process(self, msg)

            for msg in self._testaments[u"destroyed"]:
                self._router.process(self, msg)

            self._router._session_left(self, self._session_details, details)

        # dispatch session metaevent from WAMP AP
        #
        if self._service_session and self._session_id:
            # if we got a proper Goodbye, we already sent out the
            # on_leave and our self._session_id is already None; if
            # the transport vanished our _session_id will still be
            # valid.
            self._service_session.publish(u'wamp.session.on_leave', self._session_id)

        self._session_details = None

        # if asked to explicitly close the session ..
        if details.reason == u"wamp.close.logout":

            # if cookie was set on transport ..
            if self._transport._cbtid and self._transport.factory._cookiestore:
                cs = self._transport.factory._cookiestore

                # set cookie to "not authenticated"
                cs.setAuth(self._transport._cbtid, None, None, None, None, None)

                # kick all session for the same auth cookie
                for proto in cs.getProtos(self._transport._cbtid):
                    proto.sendClose()


ITransportHandler.register(RouterSession)


class RouterSessionFactory(object):
    """
    Factory creating the router side of (non-embedded) Crossbar.io WAMP sessions.
    This is the session factory that will be given to router transports.
    """

    log = make_logger()

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
