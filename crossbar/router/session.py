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

from __future__ import absolute_import, division, print_function

import traceback
import six

from twisted.internet.interfaces import ISSLTransport

import txaio

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

from crossbar._logging import make_logger
from crossbar.router.auth import PendingAuthWampCra, PendingAuthTicket
from crossbar.router.auth import AUTHMETHODS, AUTHMETHOD_MAP, PendingAuthCryptosign


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

    def _swallow_error(self, fail, msg):
        try:
            if self._session:
                self._session.onUserError(fail, msg)
        except:
            pass
        return None

    def isOpen(self):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransport.isOpen`
        """

    def is_closed(self):
        return False

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

            # fire onOpen callback and handle any exception escaping from there
            d = txaio.as_future(self._session.onJoin, details)
            txaio.add_callbacks(d, None, lambda fail: self._swallow_error(fail, "While firing onJoin"))

        # app-to-router
        #
        elif isinstance(msg, (message.Publish,
                              message.Subscribe,
                              message.Unsubscribe,
                              message.Call,
                              message.Yield,
                              message.Register,
                              message.Unregister,
                              message.Cancel)) or \
            (isinstance(msg, message.Error) and
             msg.request_type == message.Invocation.MESSAGE_TYPE):

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
            # fire onClose callback and handle any exception escaping from there
            d = txaio.as_future(self._session.onClose, None)
            txaio.add_callbacks(d, None, lambda fail: self._swallow_error(fail, "While firing onClose"))

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
        BaseSession.__init__(self)
        self._transport = None

        self._router_factory = router_factory
        self._router = None
        self._realm = None

        self._goodbye_sent = False
        self._transport_is_closing = False

    def onOpen(self, transport):
        """
        Implements :func:`autobahn.wamp.interfaces.ITransportHandler.onOpen`
        """
        # this is a WAMP transport instance
        self._transport = transport

        # this is a Twisted stream transport instance
        stream_transport = self._transport.transport

        # a dict with x509 TLS client certificate information (if the client provided a cert)
        self._client_cert = None

        # check if stream_transport is a TLSMemoryBIOProtocol
        if hasattr(stream_transport, 'getPeerCertificate') and ISSLTransport.providedBy(stream_transport):
            cert = self._transport.transport.getPeerCertificate()
            if cert:
                def extract_x509(cert):
                    """
                    Extract x509 name components from an OpenSSL X509Name object.
                    """
                    # pkey = cert.get_pubkey()

                    result = {
                        u'md5': u'{}'.format(cert.digest('md5')).upper(),
                        u'sha1': u'{}'.format(cert.digest('sha1')).upper(),
                        u'sha256': u'{}'.format(cert.digest('sha256')).upper(),
                        u'expired': cert.has_expired(),
                        u'hash': cert.subject_name_hash(),
                        u'serial': cert.get_serial_number(),
                        u'signature_algorithm': cert.get_signature_algorithm(),
                        u'version': cert.get_version(),
                        u'not_before': cert.get_notBefore(),
                        u'not_after': cert.get_notAfter(),
                        u'extensions': []
                    }
                    for i in range(cert.get_extension_count()):
                        ext = cert.get_extension(i)
                        ext_info = {
                            u'name': u'{}'.format(ext.get_short_name()),
                            u'value': u'{}'.format(ext),
                            u'criticial': ext.get_critical() != 0
                        }
                        result[u'extensions'].append(ext_info)
                    for entity, name in [(u'subject', cert.get_subject()), (u'issuer', cert.get_issuer())]:
                        result[entity] = {}
                        for key, value in name.get_components():
                            result[entity][u'{}'.format(key).lower()] = u'{}'.format(value)
                    return result

                self._client_cert = extract_x509(self._transport.transport.getPeerCertificate())
                self.log.debug("Client connecting with TLS certificate cn='{cert_cn}', sha1={cert_sha1}.., expired={cert_expired}",
                               cert_cn=self._client_cert['subject']['cn'],
                               cert_sha1=self._client_cert['sha1'][:12],
                               cert_expired=self._client_cert['expired'])

        if self._transport._transport_info:
            self._transport._transport_info[u'client_cert'] = self._client_cert

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
        self._authextra = None

        if hasattr(self._transport, 'factory') and hasattr(self._transport.factory, '_config'):
            self._transport_config = self._transport.factory._config
        else:
            self._transport_config = {}

        self._pending_auth = None
        self._session_details = None
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

                roles = self._router.attach(self)

                msg = message.Welcome(self._session_id,
                                      roles,
                                      realm=realm,
                                      authid=authid,
                                      authrole=authrole,
                                      authmethod=authmethod,
                                      authprovider=authprovider,
                                      authextra=authextra,
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
                raise ProtocolError("Received {0} message, and session is not yet established".format(msg.__class__))

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
                self._router.detach(self)

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
        self.log.failure("Internal error (2): {log_failure.value}", log_failure=fail)

        # tell other side we're done
        reply = message.Abort(u"wamp.error.authorization_failed", u"Internal server error")
        self._transport.send(reply)

        # cleanup
        if self._router:
            self._router.detach(self)
        self._session_id = None
        self._pending_session_id = None
        return None  # we've handled the error; don't propagate

    def onHello(self, realm, details):

        try:
            # default authentication method is "WAMP-Anonymous" if client doesn't specify otherwise
            authmethods = details.authmethods or [u'anonymous']

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
                                        authextra=None)
                else:
                    return types.Deny(ApplicationError.NO_SUCH_ROLE, message="session was previously authenticated (via transport), but role '{}' no longer exists on realm '{}'".format(self._transport._authrole, realm))

            else:
                auth_config = self._transport_config.get(u'auth', None)

                if not auth_config:
                    # if authentication is _not_ configured, allow anyone to join as "anonymous"!

                    # .. but don't if the client isn't ready/willing to go on "anonymous"
                    if u'anonymous' not in authmethods:
                        return types.Deny(ApplicationError.NO_AUTH_METHOD, message=u'cannot authenticate using any of the offered authmethods {}'.format(authmethods))

                    if not realm:
                        return types.Deny(ApplicationError.NO_SUCH_REALM, message=u'no realm requested')

                    if realm not in self._router_factory:
                        return types.Deny(ApplicationError.NO_SUCH_REALM, message=u'no realm "{}" exists on this router'.format(realm))

                    # we ignore any details.authid the client might have announced, and use
                    # a cookie value or a random value
                    if self._transport._cbtid:
                        # if cookie tracking is enabled, set authid to cookie value
                        authid = self._transport._cbtid
                    else:
                        # if no cookie tracking, generate a random value for authid
                        authid = util.newid(24)

                    return types.Accept(realm=realm,
                                        authid=authid,
                                        authrole=u'anonymous',
                                        authmethod=u'anonymous',
                                        authprovider=u'static',
                                        authextra=None)

                else:
                    # iterate over authentication methods announced by client ..
                    for authmethod in authmethods:

                        # invalid authmethod
                        if authmethod not in AUTHMETHODS:
                            return types.Deny(message=u'invalid authmethod "{}"'.format(authmethod))

                        # authmethod not configured
                        if authmethod not in auth_config:
                            self.log.debug("client requested valid, but unconfigured authentication method {authmethod}", authmethod=authmethod)
                            continue

                        # authmethod not available
                        if authmethod not in AUTHMETHOD_MAP:
                            self.log.debug("client requested valid, but unavailable authentication method {authmethod}", authmethod=authmethod)
                            continue

                        # WAMP-Ticket, WAMP-CRA, WAMP-TLS, WAMP-Cryptosign
                        if authmethod in [u'ticket', u'wampcra', u'tls', u'cryptosign']:
                            PendingAuthKlass = AUTHMETHOD_MAP[authmethod]
                            self._pending_auth = PendingAuthKlass(self, auth_config[authmethod])
                            return self._pending_auth.hello(realm, details)

                        # WAMP-Anonymous authentication
                        elif authmethod == u'anonymous':
                            cfg = self._transport_config['auth']['anonymous']

                            # authrole mapping
                            authrole = cfg.get('role', 'anonymous')

                            # check if role exists on realm anyway
                            if not self._router_factory[realm].has_role(authrole):
                                return types.Deny(ApplicationError.NO_SUCH_ROLE, message="authentication failed - realm '{}' has no role '{}'".format(realm, authrole))

                            # authid generation
                            if self._transport._cbtid:
                                # if cookie tracking is enabled, set authid to cookie value
                                authid = self._transport._cbtid
                            else:
                                # if no cookie tracking, generate a random value for authid
                                authid = util.newid(24)

                            authprovider = u'static'
                            authextra = None

                            # FIXME: not sure about this .. "anonymous" is a transport-level auth mechanism .. so forward
                            self._transport._authid = authid
                            self._transport._authrole = authrole
                            self._transport._authmethod = authmethod
                            self._transport._authprovider = authmethod
                            self._transport._authextra = authmethod

                            return types.Accept(realm=realm,
                                                authid=authid,
                                                authrole=authrole,
                                                authmethod=authmethod,
                                                authprovider=authprovider,
                                                authextra=authextra)

                        # WAMP-Cookie authentication
                        elif authmethod == u'cookie':
                            # the client requested cookie authentication, but there is 1) no cookie set,
                            # or 2) a cookie set, but that cookie wasn't authenticated before using
                            # a different auth method (if it had been, we would never have entered here, since then
                            # auth info would already have been extracted from the transport)
                            # consequently, we skip this auth method and move on to next auth method.
                            pass

                        else:
                            # should not arrive here
                            raise Exception("logic error")

                    # no suitable authmethod found!
                    return types.Deny(ApplicationError.NO_AUTH_METHOD, message=u'cannot authenticate using any of the offered authmethods {}'.format(authmethods))

        except Exception as e:
            traceback.print_exc()
            return types.Deny(message="internal error: {}".format(e))

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
               isinstance(self._pending_auth, PendingAuthCryptosign):
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
                self._transport.factory._cookiestore.setAuth(self._transport._cbtid, details.authid, details.authrole, details.authmethod)

        # Router/Realm service session
        #
        self._service_session = self._router._realm.session
        # self._router:                  crossbar.router.session.CrossbarRouter
        # self._router_factory:          crossbar.router.session.CrossbarRouterFactory
        # self._router._realm:           crossbar.worker.router.RouterRealm
        # self._router._realm.session:   crossbar.router.session.CrossbarRouterServiceSession

        self._session_details = {
            'session': details.session,
            'authid': details.authid,
            'authrole': details.authrole,
            'authmethod': details.authmethod,
            'authprovider': details.authprovider,
            'transport': self._transport._transport_info
        }

        # dispatch session metaevent from WAMP AP
        #
        if self._service_session:
            self._service_session.publish(u'wamp.session.on_join', self._session_details)

    def onLeave(self, details):

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
                cs.setAuth(self._transport._cbtid, None, None, None)

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
