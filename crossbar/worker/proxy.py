#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
from pprint import pformat
from typing import Dict, Any, Optional, Tuple, Set

from twisted.internet.base import ReactorBase
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.internet.error import DNSLookupError

from txaio import make_logger, as_future, time_ns

from autobahn.wamp import cryptosign

from autobahn import wamp
from autobahn import util
from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp.auth import create_authenticator
from autobahn.wamp.exception import ApplicationError, TransportLost, ProtocolError
from autobahn.wamp.role import RoleDealerFeatures, RoleBrokerFeatures
from autobahn.wamp.component import _create_transport
from autobahn.wamp.interfaces import ITransportHandler, IMessage
from autobahn.twisted.wamp import Session, ApplicationSession
from autobahn.twisted.component import _create_transport_factory, _create_transport_endpoint
from autobahn.twisted.component import Component

from crossbar.interfaces import IRealmContainer
from crossbar._util import hltype, hlid, hlval
from crossbar.node import worker
from crossbar.worker.controller import WorkerController
from crossbar.worker.transport import TransportController
from crossbar.common.key import _read_node_key
from crossbar.router.auth import PendingAuthWampCra, PendingAuthTicket, PendingAuthScram
from crossbar.router.auth import AUTHMETHOD_MAP
from crossbar.router.session import RouterSessionFactory
from crossbar.router.session import RouterFactory

try:
    from crossbar.router.auth import PendingAuthCryptosign, PendingAuthCryptosignProxy
except ImportError:
    PendingAuthCryptosign = None  # type: ignore
    PendingAuthCryptosignProxy = None  # type: ignore

__all__ = (
    'ProxyWorkerProcess',
    'ProxyController',
    'ProxyConnection',
    'ProxyRoute',
)

log = make_logger()


class ProxyWorkerProcess(worker.NativeWorkerProcess):

    TYPE = 'proxy'
    LOGNAME = 'Proxy'


class ProxyFrontendSession(object):
    """
    A router-side proxy session that handles incoming client
    connections.
    """
    # Note: "roles" come from self._router.attach() in non-proxy code
    ROLES = {
        'broker':
        RoleBrokerFeatures(
            publisher_identification=True,
            pattern_based_subscription=True,
            session_meta_api=True,
            subscription_meta_api=True,
            subscriber_blackwhite_listing=True,
            publisher_exclusion=True,
            subscription_revocation=True,
            event_retention=True,
            payload_transparency=True,
            payload_encryption_cryptobox=True,
        ),
        'dealer':
        RoleDealerFeatures(
            caller_identification=True,
            pattern_based_registration=True,
            session_meta_api=True,
            registration_meta_api=True,
            shared_registration=True,
            progressive_call_results=True,
            registration_revocation=True,
            payload_transparency=True,
            testament_meta_api=True,
            payload_encryption_cryptobox=True,
            call_canceling=True,
        )
    }

    log = make_logger()

    def __init__(self, router_factory):
        self._router_factory = router_factory
        self._controller = router_factory.worker
        self._reset()

    def _reset(self):
        # after the frontend connection is open, this will be the frontend transport
        self.transport = None

        # if we have a backend connection, it'll be here (and be a
        # Session instance)
        self._backend_session = None

        # pending session id (before the session is fully joined)
        self._pending_session_id = None

        # authenticated+joined session information
        self._session_id = None
        self._authid = None
        self._realm = None
        self._authid = None
        self._authrole = None
        self._authmethod = None
        self._authprovider = None
        self._authextra = None

        self._custom_authextra = {}

    @property
    def realm(self):
        return self._realm

    @property
    def authid(self):
        return self._authid

    @property
    def authrole(self):
        return self._authrole

    @property
    def authmethod(self):
        return self._authmethod

    @property
    def authprovider(self):
        return self._authprovider

    @property
    def authextra(self):
        return self._authextra

    def onOpen(self, transport):
        """
        Callback fired when transport is open. May run asynchronously. The transport
        is considered running and is_open() would return true, as soon as this callback
        has completed successfully.

        :param transport: The WAMP transport.
        :type transport: object implementing :class:`autobahn.wamp.interfaces.ITransport`
        """
        self.log.debug('{func}(transport={transport})', func=hltype(self.onOpen), transport=transport)
        self.transport = transport

        # transport configuration
        if hasattr(self.transport, 'factory') and hasattr(self.transport.factory, '_config'):
            self._transport_config = self.transport.factory._config
        else:
            self._transport_config = {}

        self._custom_authextra = {
            'x_cb_proxy_node': self._router_factory._node_id,
            'x_cb_proxy_worker': self._router_factory._worker_id,
            'x_cb_proxy_peer': str(self.transport.peer),
            'x_cb_proxy_pid': os.getpid(),
        }

        self.log.info('{func} proxy frontend session connected from peer {peer}',
                      func=hltype(self.onOpen),
                      peer=hlval(self.transport.transport_details.peer) if self.transport.transport_details else None)

    def onClose(self, wasClean):
        """
        Callback fired when the transport has been closed.

        :param wasClean: Indicates if the transport has been closed regularly.
        :type wasClean: bool
        """
        self.log.info('{func} proxy frontend session closed (wasClean={wasClean})',
                      func=hltype(self.onClose),
                      wasClean=wasClean)

        # actually, at this point, the backend session should already be gone, but better check!
        if self._backend_session:
            self._controller.unmap_backend(self, self._backend_session)
            self._backend_session = None

        # reset everything (even though this frontend protocol instance should not be reused anyways)
        self._reset()

    @inlineCallbacks
    def onMessage(self, msg):
        """
        Callback fired when a WAMP message was received. May run asynchronously. The callback
        should return or fire the returned deferred/future when it's done processing the message.
        In particular, an implementation of this callback must not access the message afterwards.

        :param msg: The WAMP message received.
        :type msg: object implementing :class:`autobahn.wamp.interfaces.IMessage`
        """
        self.log.debug('{func} proxy frontend session onMessage(msg={msg})', func=hltype(self.onMessage), msg=msg)
        if self._session_id is None:
            # no frontend session established yet, so we expect one of HELLO, ABORT, AUTHENTICATE

            # https://wamp-proto.org/_static/gen/wamp_latest.html#session-establishment
            if isinstance(msg, message.Hello):
                yield self._process_Hello(msg)

            # https://wamp-proto.org/_static/gen/wamp_latest.html#session-closing
            elif isinstance(msg, message.Abort):
                self.transport.send(
                    message.Abort(ApplicationError.AUTHENTICATION_FAILED, message='Proxy authentication failed'))

            # https://wamp-proto.org/_static/gen/wamp_latest.html#wamp-level-authentication
            elif isinstance(msg, message.Authenticate):
                self._process_Authenticate(msg)

            else:
                raise ProtocolError("Received {} message while proxy frontend session is not joined".format(
                    msg.__class__.__name__))

        else:
            # frontend session is established: process WAMP message

            if isinstance(msg, message.Hello) or isinstance(msg, message.Abort) or isinstance(
                    msg, message.Authenticate):
                raise ProtocolError("Received {} message while proxy frontend session is already joined".format(
                    msg.__class__.__name__))

            # https://wamp-proto.org/_static/gen/wamp_latest.html#session-closing
            elif isinstance(msg, message.Goodbye):

                # compare this code here for proxies to :meth:`RouterSession.onLeave` for routers

                # 1) if asked to explicitly close the session
                if msg.reason == "wamp.close.logout":
                    cookie_deleted = None
                    cnt_kicked = 0

                    # if cookie was set on transport
                    if self.transport and hasattr(
                            self.transport,
                            '_cbtid') and self.transport._cbtid and self.transport.factory._cookiestore:
                        cbtid = self.transport._cbtid
                        cs = self.transport.factory._cookiestore

                        # set cookie to "not authenticated"
                        # cs.setAuth(cbtid, None, None, None, None, None)
                        cs.delAuth(cbtid)
                        cookie_deleted = cbtid

                        # kick all transport protos (e.g. WampWebSocketServerProtocol) for the same auth cookie
                        for proto in cs.getProtos(cbtid):
                            # but don't kick ourselves
                            if proto != self.transport:
                                proto.sendClose()
                                cnt_kicked += 1

                    self.log.info(
                        '{func} {action} completed for session {session_id} (cookie authentication deleted: '
                        '"{cookie_deleted}", pro-actively kicked (other) sessions: {cnt_kicked})',
                        action=hlval('wamp.close.logout', color='red'),
                        session_id=hlid(self._session_id),
                        cookie_deleted=hlval(cookie_deleted, color='red') if cookie_deleted else 'none',
                        cnt_kicked=hlval(cnt_kicked, color='red') if cnt_kicked else 'none',
                        func=hltype(self.onMessage))

                # 2) if we currently have a session from proxy to backend router (as normally the case),
                # disconnect and unmap that session as well
                if self._backend_session:
                    self._controller.unmap_backend(self,
                                                   self._backend_session,
                                                   leave_reason=msg.reason,
                                                   leave_message=msg.message)
                    self._backend_session = None
                else:
                    self.log.warn('{func} frontend session left, but no active backend session to close!',
                                  func=hltype(self.onMessage))

                # 3) complete the closing handshake (initiated by the client in this case) by replying with GOODBYE
                self.transport.send(message.Goodbye(message="Proxy session closing"))
            else:
                if self._backend_session is None or self._backend_session._transport is None:
                    raise TransportLost(
                        "Expected to relay {} message, but proxy backend session or transport is gone".format(
                            msg.__class__.__name__, ))
                else:
                    # if we have an active backend connection, forward the WAMP message
                    self._backend_session._transport.send(msg)

    def frontend_accepted(self, accept):
        # we have done authentication with the client; now we can connect to
        # the backend (and we wait to tell the client they're
        # welcome until we have actually connected to the
        # backend).
        self.log.info('{func} proxy frontend session accepted ({accept})',
                      func=hltype(self.frontend_accepted),
                      accept=accept)

        if (hasattr(self.transport, '_cbtid') and hasattr(self.transport.factory, '_cookiestore')
                and self.transport.factory._cookiestore):
            self.transport.factory._cookiestore.setAuth(self.transport._cbtid, accept.authid, accept.authrole,
                                                        accept.authmethod, accept.authextra, accept.realm)

        result = Deferred()

        @inlineCallbacks
        def backend_connected(backend: ProxyBackendSession):
            # bytestream-level transport to backend router worker connected.
            try:
                # first, wait for the WAMP-level transport to connect before starting to join
                yield backend._on_connect

                # node private key
                key = _read_node_key(self._controller._cbdir, private=False)

                # authid of the connecting backend (proxy service) session is this proxy node's ID
                backend_authid = self._controller.node_id

                # authmethods we announce to the backend router we connect to
                authmethods = list(backend._authenticators.keys())

                # authentication extra we transmit from the proxy to backend router worker
                authextra = {
                    # for WAMP-cryptosign authentication of the proxy frontend
                    # to the backend router
                    "pubkey": key['hex'],

                    # forward authentication credentials of the connecting client
                    #
                    # the following are the effective (realm, authid, authrole) under
                    # which the client (proxy frontend connection) was successfully
                    # authenticated (using the authmethod+authprovider)
                    "proxy_realm": accept.realm,
                    "proxy_authid": accept.authid,
                    "proxy_authrole": accept.authrole,
                    "proxy_authmethod": accept.authmethod,
                    "proxy_authprovider": accept.authprovider,

                    # this is the authextra returned from the proxy frontend authenticator
                    "proxy_authextra": accept.authextra or {},
                }

                # get marshalled transport details for this proxy frontend session
                if self.transport.transport_details:
                    # IMPORTANT: this attribute "transport" is in addition to _other_ attributes that
                    # might be already present from "accept.authextra".
                    assert 'transport' not in authextra["proxy_authextra"]

                    # these are the transport details from the proxy frontend session. this is picked
                    # up in PendingAuthAnonymousProxy.hello() and PendingAuthCryptosignProxy.hello()
                    authextra["proxy_authextra"]["transport"] = self.transport.transport_details.marshal()

                self.log.info(
                    '{func} proxy backend session authenticating with authmethods={authmethods}, pubkey={pubkey}: '
                    'proxy_authid="{proxy_authid}", proxy_authrole="{proxy_authrole}", proxy_realm="{proxy_realm}"',
                    func=hltype(backend_connected),
                    authmethods=hlval(authmethods),
                    pubkey=hlval(authextra['pubkey']),
                    proxy_authid=hlid(authextra['proxy_authid']),
                    proxy_authrole=hlid(authextra['proxy_authrole']),
                    proxy_realm=hlid(authextra['proxy_realm']))

                # now join WAMP session, which might first start WAMP authentication (for authmethod "cryptosign-proxy")
                backend.join(accept.realm, authmethods=authmethods, authid=backend_authid, authextra=authextra)

                def backend_joined(session, details):
                    self.log.debug('{func} proxy backend session joined (backend_session_id={backend_session_id})',
                                   backend_session_id=hlid(details.session),
                                   backend_session=session,
                                   pending_session_id=self._pending_session_id,
                                   func=hltype(backend_joined))
                    # we're ready now! store and return the backend session
                    self._backend_session = session

                    # we set the frontend session ID to that of the backend session mapped for our frontend session ..
                    self._session_id = details.session
                    # .. NOT our (fake) pending session ID (generated in the proxy worker)
                    # self._session_id = self._pending_session_id

                    # credentials of the backend session mapped for our frontend session
                    self._realm = details.realm
                    self._authid = details.authid
                    self._authrole = details.authrole

                    # this is the authextra returned for the backend session mapped for our frontend session
                    self._authextra = details.authextra

                    # authentication method & provider are the requested (and succeeding) ones
                    self._authmethod = accept.authmethod
                    self._authprovider = accept.authprovider

                    result.callback(session)

                backend.on('join', backend_joined)
                yield backend._on_ready
                return backend
            except Exception as e:
                self.log.failure()
                result.errback(e)

        def backend_failed(fail):
            result.errback(fail)

        # map and connect bytestream-level transport to backend router worker
        backend_d = self._controller.map_backend(
            self,
            accept.realm,
            accept.authid,
            accept.authrole,
            accept.authextra,
        )
        backend_d.addCallback(backend_connected)
        backend_d.addErrback(backend_failed)

        return result

    def _forward(self, msg):
        # we received a message on the backend connection: forward to client over frontend connection
        if self.transport:
            self.transport.send(msg)
        else:
            # FIXME: can we improve this?
            # eg when the frontend client connection has closed before we had a chance to stop the backend and we still
            # receive eg a Result(request=23033, args=[] ..) from the backend.
            self.log.debug('Trying to forward a message to the client, but no frontend transport! [{msg}]', msg=msg)

    @inlineCallbacks
    def _process_Hello(self, msg):
        """
        We have received a Hello from the frontend client.

        Now we do any authentication necessary with them and connect
        to our backend.
        """
        self.log.debug('{func} proxy frontend session processing HELLO (msg={msg})',
                       func=hltype(self._process_Hello),
                       msg=msg)
        self._pending_session_id = util.id()
        self._goodbye_sent = False

        realm = msg.realm

        # allow "Personality" classes to add authmethods
        extra_auth_methods = self._controller.personality.EXTRA_AUTH_METHODS
        authmethods = list(extra_auth_methods.keys()) + (msg.authmethods or ['anonymous'])

        # if the client had a reassigned realm during authentication, restore it from the cookie
        if hasattr(self.transport, '_authrealm') and self.transport._authrealm:
            if 'cookie' in authmethods:
                realm = self.transport._authrealm  # noqa
                authextra = self.transport._authextra  # noqa
            elif self.transport._authprovider == 'cookie':
                # revoke authentication and invalidate cookie (will be revalidated if following auth is successful)
                self.transport._authmethod = None
                self.transport._authrealm = None
                self.transport._authid = None
                if hasattr(self.transport, '_cbtid'):
                    self.transport.factory._cookiestore.setAuth(self.transport._cbtid, None, None, None, None, None)
            else:
                pass  # TLS authentication is not revoked here

        # already authenticated, e.g. via HTTP-cookie or TLS-client-certificate authentication
        if self.transport._authid is not None and (self.transport._authmethod == 'trusted'
                                                   or self.transport._authprovider in authmethods):
            msg.realm = realm
            msg.authid = self.transport._authid
            msg.authrole = self.transport._authrole
            msg.authextra = self.transport._authextra

        details = types.HelloDetails(realm=realm,
                                     authmethods=authmethods,
                                     authid=msg.authid,
                                     authrole=msg.authrole,
                                     authextra=msg.authextra,
                                     session_roles=msg.roles,
                                     pending_session=self._pending_session_id)

        # start authentication based on configuration, compare/sync with code here:
        # https://github.com/crossbario/crossbar/blob/6b6e25b1356b0641eff5dc5086d3971ecfb9a421/crossbar/router/session.py#L861
        auth_config = self._transport_config.get('auth', None)

        # if authentication is _not_ configured, allow anyone to join as "anonymous"!
        if not auth_config:
            # we ignore any details.authid the client might have announced, and use
            # a cookie value or a random value
            if hasattr(self.transport, "_cbtid") and self.transport._cbtid:
                # if cookie tracking is enabled, set authid to cookie value
                authid = self.transport._cbtid
            else:
                # if no cookie tracking, generate a random value for authid
                authid = util.generate_serial_number()

            # FIXME: really forward any requested authrole?
            authrole = msg.authrole

            auth_config = {
                'anonymous': {
                    'type': 'static',
                    'authrole': authrole,
                    'authid': authid,
                }
            }
            self.log.warn(
                '{func} no authentication configured for proxy frontend session (using builtin anonymous '
                'access policy)',
                func=hltype(self._process_Hello))

        # iterate over authentication methods announced by client ..
        for authmethod in authmethods:

            # invalid authmethod
            if authmethod not in AUTHMETHOD_MAP and authmethod not in extra_auth_methods:
                self.transport.send(
                    message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                  message='authmethod "{}" not allowed'.format(authmethod)))
                return

            # authmethod is valid, but not configured: continue trying other authmethods the client is announcing
            if authmethod not in auth_config:
                continue

            # authmethod not available
            if authmethod not in AUTHMETHOD_MAP and authmethod not in extra_auth_methods:
                self.log.debug("{func} client requested valid, but unavailable authentication method {authmethod}",
                               func=hltype(self._process_Hello),
                               authmethod=authmethod)
                continue

            # WAMP-Cookie authentication
            if authmethod == 'cookie':
                cbtid = self.transport._cbtid
                if cbtid:
                    if self.transport.factory._cookiestore.exists(cbtid):
                        _cookie_authid, _cookie_authrole, _cookie_authmethod, _cookie_authrealm, _cookie_authextra = self.transport.factory._cookiestore.getAuth(
                            cbtid)
                        if _cookie_authid is None:
                            self.log.info('{func}: received cookie for cbtid={cbtid} not authenticated before [2]',
                                          func=hltype(self._process_Hello),
                                          cbtid=hlid(cbtid))
                            continue
                        else:
                            self.log.debug(
                                '{func}: authentication for received cookie {cbtid} found: authid={authid}, authrole={authrole}, authmethod={authmethod}, authrealm={authrealm}, authextra={authextra}',
                                func=hltype(self._process_Hello),
                                cbtid=hlid(cbtid),
                                authid=hlid(_cookie_authid),
                                authrole=hlid(_cookie_authrole),
                                authmethod=hlid(_cookie_authmethod),
                                authrealm=hlid(_cookie_authrealm),
                                authextra=_cookie_authextra)
                            hello_result = types.Accept(realm=_cookie_authrealm,
                                                        authid=_cookie_authid,
                                                        authrole=_cookie_authrole,
                                                        authmethod=_cookie_authmethod,
                                                        authprovider='cookie',
                                                        authextra=_cookie_authextra)
                    else:
                        self.log.debug('{func}: received cookie for cbtid={cbtid} not authenticated before [1]',
                                       func=hltype(self._process_Hello),
                                       cbtid=hlid(cbtid))
                        continue
                else:
                    # the client requested cookie authentication, but there is 1) no cookie set,
                    # or 2) a cookie set, but that cookie wasn't authenticated before using
                    # a different auth method (if it had been, we would never have entered here, since then
                    # auth info would already have been extracted from the transport)
                    # consequently, we skip this auth method and move on to next auth method.
                    self.log.debug('{func}: no cookie set for cbtid', func=hltype(self._process_Hello))
                    continue

            else:
                # create instance of authenticator using authenticator class for the respective authmethod
                authklass = extra_auth_methods[authmethod] if authmethod in extra_auth_methods else AUTHMETHOD_MAP[
                    authmethod]

                if authklass is None:
                    self.log.warn('{func}: skipping authenticator for authmethod "{authmethod}"',
                                  func=hltype(self._process_Hello),
                                  authmethod=hlval(authmethod))
                    self.log.warn()
                    continue

                self.log.info('{func}: instantiating authenticator class {authklass} for authmethod "{authmethod}"',
                              func=hltype(self._process_Hello),
                              authklass=hltype(authklass),
                              authmethod=hlval(authmethod))
                self._pending_auth = authklass(
                    self._pending_session_id,
                    self.transport.transport_details,
                    self._controller,
                    auth_config[authmethod],
                )
                try:
                    # call into authenticator for processing the HELLO message
                    hello_result = yield as_future(self._pending_auth.hello, realm, details)
                except Exception as e:
                    self.log.failure()
                    self.transport.send(
                        message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                      message='Frontend connection accept failed ({})'.format(e)))
                    return
                self.log.debug('{func} authmethod "{authmethod}" completed with result={hello_result}',
                               func=hltype(self._process_Hello),
                               authmethod=hlval(authmethod),
                               hello_result=hello_result)

            # if the frontend session is accepted right away (eg when doing "anonymous" authentication), process the
            # frontend accept ..
            if isinstance(hello_result, types.Accept):
                try:
                    # get a backend session mapped to the incoming frontend session
                    session = yield self.frontend_accepted(hello_result)
                except Exception as e:
                    self.log.failure()
                    self.transport.send(
                        message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                      message='Frontend connection accept failed ({})'.format(e)))
                    return

                def _on_backend_joined(session, details):
                    # we now got everything! the frontend is authenticated, and a backend session is associated.
                    msg = message.Welcome(self._session_id,
                                          ProxyFrontendSession.ROLES,
                                          realm=details.realm,
                                          authid=details.authid,
                                          authrole=details.authrole,
                                          authmethod=hello_result.authmethod,
                                          authprovider=hello_result.authprovider,
                                          authextra=dict(details.authextra or {}, **self._custom_authextra))
                    self._backend_session = session
                    self.transport.send(msg)
                    self.log.debug(
                        '{func} proxy frontend session WELCOME: session_id={session}, session={session}, '
                        'details="{details}"',
                        func=hltype(self._process_Hello),
                        session_id=hlid(self._session_id),
                        session=self,
                        details=details)

                session.on('join', _on_backend_joined)

            # if the client is required to do an authentication message exchange, answer sending a CHALLENGE message
            elif isinstance(hello_result, types.Challenge):
                self.transport.send(message.Challenge(hello_result.method, extra=hello_result.extra))

            # if the client is denied right away, answer by sending an ABORT message
            elif isinstance(hello_result, types.Deny):
                self.transport.send(message.Abort(hello_result.reason, message=hello_result.message))

            else:
                # should not arrive here: internal (logic) error
                self.log.warn('{func} internal error: unexpected authenticator return type {rtype}',
                              rtype=hltype(hello_result),
                              func=hltype(self._process_Hello))
                self.transport.send(
                    message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                  message='internal error: unexpected authenticator return type {}'.format(
                                      type(hello_result))))
            return

        self.transport.send(message.Abort(ApplicationError.NO_AUTH_METHOD, message='no suitable authmethod found'))

    @inlineCallbacks
    def _process_Authenticate(self, msg):
        self.log.debug('{func} proxy frontend session process AUTHENTICATE (msg={msg})',
                       func=hltype(self._process_Authenticate),
                       msg=msg)
        if self._pending_auth:
            if isinstance(self._pending_auth, PendingAuthTicket) or \
               isinstance(self._pending_auth, PendingAuthWampCra) or \
               isinstance(self._pending_auth, PendingAuthCryptosign) or \
               isinstance(self._pending_auth, PendingAuthScram):
                auth_result = yield as_future(self._pending_auth.authenticate, msg.signature)
                self.log.debug('{func} processed pending authentication {pending_auth}: {authresult}',
                               func=hltype(self._process_Authenticate),
                               pending_auth=self._pending_auth,
                               authresult=auth_result)
                if isinstance(auth_result, types.Accept):
                    try:
                        session = yield self.frontend_accepted(auth_result)
                    except Exception as e:
                        self.log.failure()
                        self.transport.send(
                            message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                          message='Frontend connection accept failed ({})'.format(e)))
                    else:

                        def _on_backend_joined(session, details):
                            msg = message.Welcome(self._session_id,
                                                  ProxyFrontendSession.ROLES,
                                                  realm=details.realm,
                                                  authid=details.authid,
                                                  authrole=details.authrole,
                                                  authmethod=auth_result.authmethod,
                                                  authprovider=auth_result.authprovider,
                                                  authextra=dict(details.authextra or {}, **self._custom_authextra))
                            self._backend_session = session
                            self.transport.send(msg)
                            self.log.debug(
                                '{func} proxy frontend session WELCOME: session_id={session_id}, '
                                'session={session}, msg={msg}',
                                func=hltype(self._process_Authenticate),
                                session_id=hlid(self._session_id),
                                session=self,
                                msg=msg)

                        session.on('join', _on_backend_joined)
                elif isinstance(auth_result, types.Deny):
                    self.transport.send(message.Abort(auth_result.reason, message=auth_result.message))
                else:
                    # should not arrive here: logic error
                    self.log.warn('{func} internal error: unexpected authenticator return type {rtype}',
                                  rtype=hltype(auth_result),
                                  func=hltype(self._process_Authenticate))
                    self.transport.send(
                        message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                      message='internal error: unexpected authenticator return type {}'.format(
                                          type(auth_result))))
            else:
                # should not arrive here: logic error
                self.transport.send(
                    message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                  message='internal error: unexpected pending authentication'))
        else:
            # should not arrive here: client misbehaving!
            self.transport.send(
                message.Abort(ApplicationError.AUTHENTICATION_FAILED, message='no pending authentication'))


ITransportHandler.register(ProxyFrontendSession)


class ProxyBackendSession(Session):
    """
    This is a single WAMP session to the real backend service

    There is one of these for every client connection. (In the future,
    we could multiplex over a single backend connection -- for now,
    there's a backend connection per frontend client).
    """
    def onOpen(self, transport):
        self.log.debug('{func}(transport={transport})', func=hltype(self.onOpen), transport=transport)
        # instance of Frontend (frontend_session)
        self._frontend = transport._proxy_other_side
        self._on_connect = Deferred()
        self._on_ready = Deferred()
        return Session.onOpen(self, transport)

    def onConnect(self):
        """
        The base class will call .join() which we do NOT want to do;
        instead we await the frontend sending its hello and forward
        that along.
        """
        self.log.debug('{func}(): on_connect={on_connect}', func=hltype(self.onConnect), on_connect=self._on_connect)
        self._on_connect.callback(None)

    def onChallenge(self, challenge):
        self.log.debug('{func}(challenge={})', func=hltype(self.onChallenge), challenge=challenge)
        if challenge.method == "cryptosign-proxy":
            return super(ProxyBackendSession, self).onChallenge(types.Challenge("cryptosign", extra=challenge.extra))

        return super(ProxyBackendSession, self).onChallenge(challenge)

    def onWelcome(self, _msg):
        self.log.debug('{func}(message={msg})', func=hltype(self.onWelcome), msg=_msg)
        # This is WRONG:
        # if msg.authmethod == "cryptosign-proxy":
        #     msg.authmethod = "cryptosign"
        # elif msg.authmethod == "anonymous-proxy":
        #     msg.authmethod = "anonymous"
        return super(ProxyBackendSession, self).onWelcome(_msg)

    def onJoin(self, details):
        self.log.info(
            '{func} proxy backend session joined (authmethod={authmethod}, authprovider={authprovider}): '
            'realm="{realm}", authid="{authid}", authrole="{authrole}"',
            func=hltype(self.onJoin),
            realm=hlid(details.realm),
            authid=hlid(details.authid),
            authrole=hlid(details.authrole),
            authmethod=hlval(details.authmethod),
            authprovider=hlval(details.authprovider))

        if not self._on_ready.called:
            self._on_ready.callback(self)

    def onClose(self, wasClean):
        self.log.info('{func} proxy backend session closed (wasClean={wasClean})',
                      func=hltype(self.onClose),
                      wasClean=wasClean)
        if self._frontend is not None and self._frontend.transport is not None:
            try:
                if self._session_id:
                    self._frontend.transport.send(message.Goodbye())
                else:
                    self._frontend.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED))
            except Exception as e:
                self.log.info(
                    "Backend closed, Abort/Goodbye to frontend failed: {fail}",
                    fail=e,
                )
        self._frontend = None
        super(ProxyBackendSession, self).onClose(wasClean)

    def onMessage(self, msg: IMessage):
        if isinstance(msg, (message.Welcome, message.Challenge, message.Abort, message.Goodbye)):
            super(ProxyBackendSession, self).onMessage(msg)
        else:
            # msg is a real WAMP message that our backend WAMP protocol has deserialized. so now we re-serialize it
            # for whatever the frontend is speaking and forward
            self._frontend._forward(msg)


def make_backend_connection(reactor: ReactorBase, controller: 'ProxyController', backend_config: Dict[str, Any],
                            frontend_session: ApplicationSession) -> Deferred:
    """
    Create a connection to a router backend, wiring up the given proxy frontend session
    to forward WAMP in both directions between the frontend and backend sessions.

    Backend configuration example:

        .. code-block:: json
            {
                'auth': {
                    'cryptosign-proxy': {
                        'type': 'static'
                    }
                },
                'transport': {
                    'type': 'rawsocket',
                    'endpoint': {
                        'type': 'tcp',
                        'host': '127.0.0.1',
                        'port': 8442
                    },
                    'serializer': 'cbor',
                    'url': 'rs://localhost'
                }
            }

    :param reactor: Twisted reactor to use.
    :param controller: The proxy controller the backend connection originates from.
    :param cbdir: This node's directory.
    :param backend_config: Proxy backend connection.
    :param frontend_session: The proxy frontend session for which to create a mapped
        backend connection.
    :return: A deferred that resolves with a proxy backend session that is joined on the realm,
        under the authrole, as the proxy frontend session.
    """
    log.info('{func} proxy connecting to backend with backend_config=\n{backend_config}',
             func=hltype(make_backend_connection),
             backend_config=pformat(backend_config))

    cbdir = controller.cbdir

    # fired when the component has connected, authenticated and joined a realm on the backend node
    ready = Deferred()

    # connected node transport
    backend = _create_transport(0, backend_config['transport'])

    # connecting node (this node) private key
    key = _read_node_key(cbdir, private=True)

    # factory for proxy->router backend connections, uses authentication (to router backend worker)
    def create_session():

        # this is our WAMP session to the backend
        session = ProxyBackendSession()

        authextra = {}
        log.debug('{func}::create_session() connecting to backend with authextra=\n{authextra}',
                  func=hltype(make_backend_connection),
                  authextra=pformat(authextra))

        # if auth is configured and includes "cryptosign-proxy", always prefer
        # that and connect to the backend node authenticating with WAMP-cryptosign
        # using the connecting proxy node's key
        #
        # authentication via WAMP-cryptosign SHOULD always be possible with the backend node
        #
        if 'auth' in backend_config and 'cryptosign-proxy' in backend_config['auth']:
            session.add_authenticator(create_authenticator('cryptosign-proxy', privkey=key['hex'],
                                                           authextra=authextra))
            log.debug('{func} using cryptosign-proxy authenticator for backend connection, authextra=\n{authextra}',
                      func=hltype(make_backend_connection),
                      authextra=pformat(authextra))

        # if auth is not configured, or is configured and includes "anonymous-proxy",
        # try to connect to the backend node authenticating with WAMP-anonymous
        #
        # authentication via WAMP-anonymous MAY be possible with the backend node if enabled
        #
        elif 'auth' not in backend_config or 'anonymous-proxy' in backend_config['auth']:
            # IMPORTANT: this is security sensitive! we only allow anonymous proxy
            # locally on a host, that is, when the transport type is Unix domain socket
            if backend_config['transport']['endpoint']['type'] == 'unix':
                session.add_authenticator(create_authenticator('anonymous-proxy', authextra=authextra))
                log.debug(
                    '{func} using anonymous-proxy over UDS authenticator for backend connection, '
                    'authextra=\n{authextra}',
                    func=hltype(make_backend_connection),
                    authextra=pformat(authextra))
            else:
                raise RuntimeError(
                    'anonymous-proxy authenticator only allowed on Unix domain socket based transports, not type "{}"'.
                    format(backend_config['transport']['endpoint']['type']))

        # no valid authentication method found
        else:
            raise RuntimeError('could not determine valid authentication method to connect to the backend node')

        def connected(new_session, transport):
            ready.callback(new_session)

        session.on('connect', connected)
        return session

    # client transport factory to carry our session
    factory = _create_transport_factory(reactor, backend, create_session)
    # reduce noise from logs, otherwise for each connect/disconnect to the backend
    factory.noisy = False
    endpoint = _create_transport_endpoint(reactor, backend_config['transport']['endpoint'])
    transport_d = endpoint.connect(factory)

    def _connected(proto):
        proto._proxy_other_side = frontend_session
        return proto

    def _error(f):
        # backend session disconnected without ever having joined before
        if not ready.called:
            ready.errback(f)

    transport_d.addErrback(_error)
    transport_d.addCallback(_connected)

    return ready


class AuthenticatorSession(ApplicationSession):

    # when running over TLS, require TLS channel binding
    # CHANNEL_BINDING = 'tls-unique'
    CHANNEL_BINDING = None

    def __init__(self, config=None):
        ApplicationSession.__init__(self, config)

        # load the client private key (raw format)
        try:
            self._key = cryptosign.CryptosignKey.from_bytes(config.extra['key'])
        except:
            self.log.failure()
            if self.is_attached():
                self.leave()
        else:
            self.log.info('{func} client public key loaded: {pubkey}',
                          pubkey=hlval(self._key.public_key()),
                          func=hltype(self.__init__))

    def onConnect(self):
        extra = {
            'pubkey': self._key.public_key(),
        }
        self.join(self.config.realm,
                  authmethods=['cryptosign'],
                  authid=self.config.extra.get('authid', None),
                  authextra=extra)

    async def onChallenge(self, challenge):
        try:
            channel_id_type = self.CHANNEL_BINDING
            channel_id = self.transport.transport_details.channel_id.get(self.CHANNEL_BINDING, None)
            signed_challenge = await self._key.sign_challenge(challenge,
                                                              channel_id=channel_id,
                                                              channel_id_type=channel_id_type)
            return signed_challenge
        except:
            self.log.failure()
            raise

    def onJoin(self, details):
        if self.config.extra['ready']:
            self.config.extra['ready'].callback(self)
            self.config.extra['ready'] = None

    def onLeave(self, details):
        self.log.info('{func} session closed (details={details})', details=details, func=hltype(self.onDisconnect))

    def onDisconnect(self):
        self.log.info('{func} connection closed', func=hltype(self.onDisconnect))


def make_service_session(reactor: ReactorBase, controller: 'ProxyController', backend_config: Dict[str, Any],
                         realm: str, authrole: str) -> Deferred:
    """
    Create a connection to a router backend, creating a new service session.

    :param reactor: Twisted reactor to use.
    :param controller: The proxy controller this service session is for.
    :param backend_config: Proxy backend connection.
    :param realm: The WAMP realm the service session is joined on.
    :param authrole: The WAMP authrole the service session is joined as.
    :return: A service session joined on the given realm, under the given authrole.
    """
    cbdir = controller.cbdir

    # authid of the proxy session forwarded to the backend: for service session that are
    # not forwarding incoming session (like make_backend_session), but represent an
    # independent session (exposed on the proxy), we synthesize an authid
    proxy_authid = 'proxy-{}'.format(util.generate_serial_number())

    # authid of the connecting backend (proxy service) session is this proxy node's ID
    backend_authid = controller.node_id

    # if auth is configured and includes "cryptosign-proxy", always prefer
    # that and connect to the backend node authenticating with WAMP-cryptosign
    # using the connecting proxy node's key
    #
    # authentication via WAMP-cryptosign SHOULD always be possible with the backend node
    #
    if 'auth' in backend_config and 'cryptosign-proxy' in backend_config['auth']:
        # we will do cryptosign authentication to any backend node

        # FIXME: get node private key from this proxy node
        node_privkey = _read_node_key(cbdir, private=True)['hex']

        authentication = {
            'cryptosign-proxy': {
                'privkey': node_privkey,
                'authid': backend_authid,
                'authextra': {
                    'proxy_realm': realm,
                    'proxy_authid': proxy_authid,
                    'proxy_authrole': authrole,
                    'proxy_authextra': None,
                }
            }
        }

    # if auth is not configured, or is configured and includes "anonymous-proxy",
    # try to connect to the backend node authenticating with WAMP-anonymous
    #
    # authentication via WAMP-anonymous MAY be possible with the backend node if enabled
    #
    elif 'auth' not in backend_config or 'anonymous-proxy' in backend_config['auth']:
        # IMPORTANT: this is security sensitive! we only allow anonymous proxy
        # locally on a host, that is, when the transport type is Unix domain socket
        if backend_config['transport']['endpoint']['type'] == 'unix':
            authentication = {
                'anonymous-proxy': {
                    'authid': backend_authid,
                    'authextra': {
                        'proxy_realm': realm,
                        'proxy_authid': proxy_authid,
                        'proxy_authrole': authrole,
                        'proxy_authextra': None,
                    }
                }
            }
        else:
            raise RuntimeError(
                'anonymous-proxy authenticator only allowed on Unix domain socket based transports, not type "{}"'.
                format(backend_config['transport']['endpoint']['type']))

    # no valid authentication method found
    else:
        raise RuntimeError('could not determine valid authentication method to connect to the backend node')

    # use Component API and create a component for the service session
    comp = Component(transports=[backend_config['transport']], realm=realm, authentication=authentication)

    # fired when the component has connected, authenticated and joined a realm on the backend node
    ready = Deferred()

    @comp.on_join
    def joined(session, details):
        ready.callback(session)

    @comp.on_disconnect
    def disconnect(session, was_clean=False):
        if not ready.called:
            ready.errback(RuntimeError('backend session disconnected without ever having joined before'))

    # start the component and return the component's ready deferred
    comp.start(reactor)
    return ready


STATE_CREATED = 1
STATE_STARTING = 2
STATE_STARTED = 3
STATE_FAILED = 4
STATE_STOPPING = 5
STATE_STOPPED = 6

STATES = {
    STATE_CREATED: "created",
    STATE_STARTING: "starting",
    STATE_STARTED: "started",
    STATE_FAILED: "failed",
    STATE_STOPPING: "stopping",
    STATE_STOPPED: "stopped",
}


class ProxyRoute(object):
    """
    Proxy route run-time representation.
    """
    log = make_logger()

    def __init__(self, controller: 'ProxyController', realm_name: str, route_id: str, config: Dict[str, Any]):
        """

        :param controller: The (proxy) worker controller session the proxy connection is created from.

        :param realm_name: The realm this route applies to.

        :param route_id: The run-time route ID within the proxy worker.

        :param config: The proxy route's configuration, which is a dictionary of role names
            and connection IDs as values.
        """
        self._controller = controller
        self._realm_name = realm_name
        self._route_id = route_id
        self._config = config
        self._started = None
        self._stopped = None
        self._state = STATE_CREATED

    def marshal(self) -> Dict[str, Any]:
        return {
            'realm': self._realm_name,
            'id': self._route_id,
            'config': self._config,
            'started': self._started,
            'stopped': self._stopped,
            'state': self._state,
        }

    def __str__(self):
        return pformat(self.marshal())

    @property
    def realm(self) -> str:
        """

        :return: The realm this route applies to.
        """
        return self._realm_name

    def has_role(self, role_name) -> bool:
        """
        Checks if the given role is mapped in this proxy route.

        :param role_name: Role to lookup.
        :return: ``True`` if the role is configured in this proxy route.
        """
        return role_name in self._config

    def map_connection_id(self, role_name) -> Optional[str]:
        """
        Map the given role to a connection ID according to the configuration of this route.

        :param role_name: Role to map.
        :return: Connection ID configured for the role in this proxy route.
        """
        if role_name in self._config:
            return self._config[role_name]
        else:
            return None

    @property
    def id(self) -> str:
        """

        :return: The ID of this proxy route.
        """
        return self._route_id

    @property
    def config(self) -> Dict[str, Any]:
        """

        :return: The original configuration as supplied to this proxy route.
        """
        return self._config

    @property
    def started(self) -> Optional[int]:
        """

        :return: When this route was started in it's hosting worker.
        """
        return self._started

    @property
    def stopped(self) -> Optional[int]:
        """

        :return: When this route was stopped in it's hosting worker.
        """
        return self._stopped

    @property
    def state(self) -> int:
        """

        :return: Current state of route in it's hosting worker.
        """
        return self._state

    @inlineCallbacks
    def start(self):
        """
        Start proxy route.
        """
        assert self._state == STATE_CREATED
        self._state = STATE_STARTING

        topic = '{}.on_proxy_route_starting'.format(self._controller._uri_prefix)
        yield self._controller.publish(topic, self.marshal(), options=types.PublishOptions(acknowledge=True))

        self._state = STATE_STARTED
        self._started = time_ns()
        self._stopped = None

        topic = '{}.on_proxy_route_started'.format(self._controller._uri_prefix)
        yield self._controller.publish(topic, self.marshal(), options=types.PublishOptions(acknowledge=True))

        self.log.info('{func} proxy route {route_id} started for realm "{realm}" with config=\n{config}',
                      func=hltype(self.start),
                      route_id=hlid(self._route_id),
                      realm=hlval(self._realm_name),
                      config=pformat(self._config))

    @inlineCallbacks
    def stop(self):
        """
        Stop proxy route.
        """
        assert self._state == STATE_STARTED
        self._state = STATE_STOPPING

        topic = '{}.on_proxy_route_stopping'.format(self._controller._uri_prefix)
        yield self._controller.publish(topic, self.marshal(), options=types.PublishOptions(acknowledge=True))

        self._state = STATE_STOPPED
        self._started = None
        self._stopped = time_ns()

        topic = '{}.on_proxy_route_stopped'.format(self._controller._uri_prefix)
        yield self._controller.publish(topic, self.marshal(), options=types.PublishOptions(acknowledge=True))

        self.log.info('{func} proxy route {route_id} stopped for realm "{realm}"',
                      func=hltype(self.stop),
                      route_id=hlid(self._route_id),
                      realm=hlval(self._realm_name))


class ProxyConnection(object):
    """
    Proxy connection run-time representation.
    """
    log = make_logger()

    def __init__(self, controller: 'ProxyController', connection_id: str, config: Dict[str, Any]):
        """
        Example connection configuration for a Unix domain socket based connection using
        WAMP-anonymous proxy authentication:

        .. code-block:: json

            {
                "transport": {
                    "type": "rawsocket",
                    "endpoint": {
                        "type": "unix",
                        "path": "router.sock"
                    },
                    "url": "ws://localhost",
                    "serializer": "cbor"
                },
                "auth": {
                    "anonymous-proxy": {
                        "type": "static"
                    }
                }
            }

        Example connection configuration for a TCP based connection using
        WAMP-cryptosign proxy authentication:

        .. code-block:: json

            {
                "transport": {
                    "type": "rawsocket",
                    "endpoint": {
                        "type": "tcp",
                        "host": "core1",
                        "port": 10023
                    },
                    "url": "ws://core1",
                    "serializer": "cbor"
                },
                "auth": {
                    "cryptosign-proxy": {
                        "type": "static"
                    }
                }
            }

        :param controller: The (proxy) worker controller session the proxy connection is created from.
        :param connection_id: The run-time connection ID within the proxy worker.
        :param config: The proxy connection's configuration.
        """
        self._controller = controller
        self._connection_id = connection_id
        self._config = config
        self._started = None
        self._stopped = None
        self._state = STATE_CREATED

    def marshal(self):
        return {
            'id': self._connection_id,
            'config': self._config,
            'started': self._started,
            'stopped': self._stopped,
            'state': self._state,
        }

    def __str__(self):
        return pformat(self.marshal())

    @property
    def id(self) -> str:
        """

        :return: The ID of this proxy backend connection.
        """
        return self._connection_id

    @property
    def config(self) -> Dict[str, Any]:
        """

        :return: The original configuration as supplied to this proxy backend connection.
        """
        return self._config

    @property
    def started(self) -> Optional[int]:
        """

        :return: When this proxy backend connection was started (Posix time in ns).
        """
        return self._started

    @property
    def stopped(self) -> Optional[int]:
        """

        :return: When this proxy backend connection was stopped (Posix time in ns).
        """
        return self._stopped

    @property
    def state(self) -> int:
        """

        :return: Current state of this proxy backend connection.
        """
        return self._state

    @inlineCallbacks
    def start(self):
        """
        Start this proxy backend connection.
        """
        assert self._state == STATE_CREATED
        self._state = STATE_STARTING

        topic = '{}.on_proxy_connection_starting'.format(self._controller._uri_prefix)
        yield self._controller.publish(topic, self.marshal(), options=types.PublishOptions(acknowledge=True))

        self._state = STATE_STARTED
        self._started = time_ns()
        self._stopped = None

        topic = '{}.on_proxy_connection_started'.format(self._controller._uri_prefix)
        yield self._controller.publish(topic, self.marshal(), options=types.PublishOptions(acknowledge=True))

    @inlineCallbacks
    def stop(self):
        """
        Stop this proxy backend connection.
        """
        assert self._state == STATE_STARTED
        self._state = STATE_STOPPING

        topic = '{}.on_proxy_connection_stopping'.format(self._controller._uri_prefix)
        yield self._controller.publish(topic, self.marshal(), options=types.PublishOptions(acknowledge=True))

        self._state = STATE_STOPPED
        self._started = None
        self._stopped = time_ns()

        topic = '{}.on_proxy_connection_stopped'.format(self._controller._uri_prefix)
        yield self._controller.publish(topic, self.marshal(), options=types.PublishOptions(acknowledge=True))


class ProxyController(TransportController):
    """
    Controller for proxy workers. Manages:

    * **proxy transports**, for accepting incoming client connections
    * **proxy connections**, for backend router connections
    * **proxy routes**, for routes from ``(realm_name, role_name)`` to backend router connections

    and

    * web transport services (from base class `TransportController`), when running a proxy transport
    of type ``web``.

    Proxy controllers also inherit more procedures and events from the base classes

    * :class:`crossbar.worker.transport.TransportController`,
    * :class:`crossbar.worker.controller.WorkerController` and
    * :class:`crossbar.common.process.NativeProcess`.
    """
    WORKER_TYPE = 'proxy'
    WORKER_TITLE = 'WAMP proxy'

    def __init__(self, config=None, reactor=None, personality=None):
        super(ProxyController, self).__init__(
            config=config,
            reactor=reactor,
            personality=personality,
        )
        # the Twisted reactor under which to run
        self._reactor = reactor

        # the node's home directory of this worker
        self._cbdir = config.extra.cbdir

        # map: connection_id -> ProxyConnection
        self._connections: Dict[str, ProxyConnection] = {}

        # map: (realm, authrole) -> Set[ProxyConnection]
        self._connections_by_auth: Dict[Tuple[str, str], Set[ProxyConnection]] = {}

        # map: realm_name -> route_id -> ProxyRoute
        self._routes: Dict[str, Dict[str, ProxyRoute]] = {}

        # map: connection_id -> Set[ProxyRoute]
        self._routes_by_connection: Dict[str, Set[ProxyRoute]] = {}

        # for creating route IDs
        self._next_route_id = 0

        # next route to use in a realm while forwarding connections
        # map: (realm, authrole) -> int
        self._roundrobin_idx = {}

        # since we share some functionality with RouterController we
        # need to have a router_session_factory
        self._router_factory = RouterFactory(
            self.config.extra.node,
            self.config.extra.worker,
            self,  # ProxySession get to ProxyController via .worker here
        )
        self._router_session_factory = RouterSessionFactory(self._router_factory)
        self._router_session_factory.session = ProxyFrontendSession

        # currently mapped session: map of frontend_session => backend_session
        self._backends_by_frontend = {}

        # map: (realm_name, role_name) -> ProxyRoute
        self._service_sessions = {}

    def has_realm(self, realm: str) -> bool:
        """
        Check if a route to a realm with the given name is currently running.

        :param realm: Realm name (the WAMP name, _not_ the run-time object ID).

        :returns: True if a route to the realm (for any role) exists.
        """
        result = realm in self._routes
        self.log.debug('{func}(realm="{realm}") -> {result}',
                       func=hltype(ProxyController.has_realm),
                       realm=hlid(realm),
                       result=hlval(result))
        return result

    def has_role(self, realm: str, authrole: str) -> bool:
        """
        Check if a role with the given name is currently running in the given realm.

        :param realm: WAMP realm (the WAMP name, _not_ the run-time object ID).

        :param authrole: WAMP authentication role (the WAMP URI, _not_ the run-time object ID).

        :returns: True if a route to the realm for the role exists.
        """
        authrole = authrole or 'trusted'
        if realm in self._routes:
            realm_routes = self._routes[realm]

            # the route config is a map with role name as key
            result = any(authrole in route.config for route in realm_routes.values())
        else:
            realm_routes = None
            result = False
        self.log.debug(
            '{func}(realm="{realm}", authrole="{authrole}") -> {result} [routes={routes}, realm_routes={realm_routes}]',
            func=hltype(ProxyController.has_role),
            realm=hlid(realm),
            authrole=hlid(authrole),
            result=hlval(result),
            realm_routes=hlval([route.config for route in realm_routes.values()] if realm_routes else []),
            routes=sorted(self._routes.keys()))
        return result

    @inlineCallbacks
    def get_service_session(self, realm: str, authrole: str) -> ApplicationSession:
        """
        Returns a cached service session on the given realm using the given role.

        Service sessions are used for:

        * access dynamic authenticators (see
            :method:`crossbar.router.auth.pending.PendingAuth._init_dynamic_authenticator`)
        * access the WAMP meta API for the realm
        * forward to/from WAMP for the HTTP bridge

        Service sessions are NOT used to forward WAMP client connections incoming to the proxy worker.

        :param realm: WAMP realm (the WAMP name, _not_ the run-time object ID).

        :param authrole: WAMP authentication role (the WAMP URI, _not_ the run-time object ID).

        :returns: The service session for the realm.
        """
        try:
            self.log.info('{klass}.get_service_session(realm="{realm}", authrole="{authrole}")',
                          klass=self.__class__.__name__,
                          realm=realm,
                          authrole=authrole)

            # create new service session for (realm, authrole) if it doesn't exist yet ..

            # .. check for realm
            if realm not in self._service_sessions:
                if self.has_realm(realm):
                    self.log.info(
                        '{klass}.get_service_session(realm="{realm}", authrole="{authrole}") -> '
                        'not cached, creating new session ..',
                        klass=self.__class__.__name__,
                        realm=realm,
                        authrole=authrole)
                    self._service_sessions[realm] = {}
                else:
                    # mark as non-existing!
                    self._service_sessions[realm] = None

            # .. check for (realm, authrole)
            if self._service_sessions[realm] is not None and authrole not in self._service_sessions[realm]:
                if self.has_role(realm, authrole):
                    # get backend connection configuration selected (round-robin or randomly) from all routes
                    # for the desired (realm, authrole)
                    backend_config = self.get_backend_config(realm, authrole)

                    # create and store a new service session connected to the backend router worker
                    self._service_sessions[realm][authrole] = yield make_service_session(
                        self._reactor, self, backend_config, realm, authrole)
                else:
                    # mark as non-existing!
                    self._service_sessions[realm][authrole] = None

            # return cached service session
            if self._service_sessions[realm] and self._service_sessions[realm][authrole]:
                service_session = self._service_sessions[realm][authrole]
                self.log.info(
                    '{klass}.get_service_session(realm="{realm}", authrole="{authrole}") -> found cached service '
                    'session {session} with authid "{session_authid}" and authrole "{session_authrole}"',
                    klass=self.__class__.__name__,
                    realm=realm,
                    authrole=authrole,
                    session=service_session.session_id,
                    session_authid=service_session.authid,
                    session_authrole=service_session.authrole)
                return service_session
            else:
                self.log.warn(
                    '{klass}.get_service_session(realm="{realm}", authrole="{authrole}") -> no such realm/authrole!',
                    klass=self.__class__.__name__,
                    realm=realm,
                    authrole=authrole)
                return None
        except:
            self.log.failure()
            raise

    def can_map_backend(self, session_id, realm, authid, authrole, authextra):
        """
        Checks if the proxy can map the incoming frontend session to a backend.

        :returns: True only-if map_backend() can succeed later for the
            same args (essentially, if the realm + role exist).
        """
        return self.has_realm(realm) and self.has_role(realm, authrole)

    @inlineCallbacks
    def map_backend(self, frontend, realm: str, authid: str, authrole: str, authextra: Optional[Dict[str, Any]]):
        """
        Returns the cached backend forwarding session for the given frontend session.
        Map the given frontend session to a backend session under the given
        authentication credentials.

        :param frontend:
        :param realm:
        :param authid:
        :param authrole:
        :param authextra:
        :return: a protocol instance connected to the backend
        """
        self.log.debug(
            '{func}(frontend={frontend}, realm="{realm}", authid="{authid}", authrole="{authrole}", '
            'authextra={authextra})',
            func=hltype(self.map_backend),
            frontend=frontend,
            realm=hlid(realm),
            authid=hlid(authid),
            authrole=hlid(authrole),
            authextra=authextra)

        if frontend in self._backends_by_frontend:
            backend = self._backends_by_frontend[frontend]
            self.log.info('{func} CACHE HIT {backend}', func=hltype(self.map_backend), backend=backend)
            return backend

        backend_config = self.get_backend_config(realm, authrole)

        # if auth uses cryptosign but has no privkey, we'd ideally
        # insert the node's private key

        if authrole is None:
            if len(self._routes.get(realm, set())) != 1:
                raise RuntimeError("Cannot select default role unless realm has exactly 1")

        self.log.debug(
            '{func} CACHE MISS - opening new proxy backend connection for realm "{realm}", authrole "{authrole}" '
            'using backend_config=\n{backend_config}',
            func=hltype(self.map_backend),
            backend_config=pformat(backend_config),
            realm=hlid(realm),
            authrole=hlid(authrole))

        try:
            backend_proto = yield make_backend_connection(self._reactor, self, backend_config, frontend)
        except DNSLookupError as e:
            self.log.warn('{func} proxy worker could not connect to router backend: DNS resolution failed ({error})',
                          func=hltype(self.map_backend),
                          error=str(e))
            raise e

        if frontend:
            self._backends_by_frontend[frontend] = backend_proto

        self.log.debug(
            '{func} proxy backend connection opened mapping frontend session to realm "{realm}", authrole "{authrole}"',
            func=hltype(self.map_backend),
            backend_config=pformat(backend_config),
            realm=hlid(realm),
            authrole=hlid(authrole))

        returnValue(backend_proto)

    def unmap_backend(self, frontend, backend, leave_reason=None, leave_message=None):
        """
        Unmap the backend session from the given frontend session it is currently mapped to.
        """
        self.log.debug('{func}(frontend={frontend}, backend={backend})',
                       func=hltype(self.unmap_backend),
                       frontend=frontend,
                       backend=backend)
        if frontend in self._backends_by_frontend:
            if self._backends_by_frontend[frontend] == backend:
                # alright, the given frontend is indeed currently mapped to the given backend session: close the
                # session and delete it
                backend.leave(reason=leave_reason, message=leave_message)
                del self._backends_by_frontend[frontend]
                self.log.debug(
                    '{func} unmapped frontend session {frontend_session_id} from backend session {backend_session_id}',
                    func=hltype(self.unmap_backend),
                    frontend_session_id=hlid(frontend._session_id),
                    backend_session_id=hlid(backend._session_id))
            else:
                self.log.warn('{func} frontend session {frontend_session_id} currently mapped to backend session '
                              '{backend_session_id} - NOT to specified backend {specified_session_id}'.format(
                                  func=hltype(self.unmap_backend),
                                  frontend_session_id=hlid(frontend._session_id),
                                  backend_session_id=hlid(self._backends_by_frontend[frontend]._session_id),
                                  specified_session_id=hlid(backend._session_id)))
        else:
            if frontend:
                self.log.warn('{func} frontend session {session_id} not currently mapped to any backend',
                              func=hltype(self.unmap_backend),
                              session_id=hlid(frontend._session_id))

    def get_backend_config(self, realm_name, role_name):
        """
        Return backend connection information for the given backend realm and role.

        :returns: a dict containing the connection configuration for the backend
            identified by the realm_name and role_name
        """
        assert self.has_role(realm_name, role_name), \
            'missing (realm_name={}, role_name={}) in ProxyController routes'.format(realm_name, role_name)

        key = realm_name, role_name
        if key not in self._roundrobin_idx:
            self._roundrobin_idx[key] = 0
        else:
            self._roundrobin_idx[key] += 1

        idx = self._roundrobin_idx[key] % len(self._connections_by_auth[key])
        connection = list(self._connections_by_auth[key])[idx]

        return connection.config

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        self.log.info(
            '{func} proxy worker "{worker_id}" session {session_id} initializing',
            func=hltype(self.onJoin),
            worker_id=hlid(self._worker_id),
            session_id=hlid(details.session),
        )

        yield WorkerController.onJoin(self, details, publish_ready=False)

        yield self.publish_ready()

    @wamp.register(None)
    def get_proxy_transports(self, details=None):
        """
        Get proxy (listening) transports currently running in this proxy worker.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of transport IDs of transports currently running.
        :rtype: list
        """
        self.log.debug('{func}(caller_authid="{caller_authid}")',
                       func=hltype(self.get_proxy_transports),
                       caller_authid=hlval(details.caller_authid))
        return sorted(self.transports.keys())

    @wamp.register(None)
    def get_proxy_transport(self, transport_id, details=None):
        """
        Get transport currently running in this proxy worker.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of transports currently running.
        :rtype: dict
        """
        self.log.debug('{func}(transport_id={transport_id})',
                       func=hltype(self.get_proxy_transport),
                       transport_id=hlid(transport_id),
                       caller_authid=hlval(details.caller_authid))

        if transport_id in self.transports:
            transport = self.transports[transport_id]
            return transport.marshal()
        else:
            raise ApplicationError("crossbar.error.no_such_object", "No transport {}".format(transport_id))

    @inlineCallbacks
    @wamp.register(None)
    def start_proxy_transport(self, transport_id, config, details=None):
        """
        Start a new proxy front-end listening transport.

        :param transport_id: The run-time ID to start the transport under.
        :param config: The listening transport configuration.
        :param details: WAMP call details.

        :return: Proxy transport run-time metadata.
        """
        self.log.info('{func}(transport_id="{transport_id}", config={config})',
                      func=hltype(self.start_proxy_transport),
                      transport_id=hlid(transport_id),
                      config='...',
                      caller_authid=hlval(details.caller_authid))

        # prohibit starting a transport twice
        if transport_id in self.transports:
            _emsg = 'Could not start transport: a transport with ID "{}" is already running (or starting)'.format(
                transport_id)
            self.log.error(_emsg)
            raise ApplicationError('crossbar.error.already_running', _emsg)

        # create a transport and parse the transport configuration
        # (NOTE: yes, this is re-using create_router_transport so we
        # can proxy every service a 'real' router can)
        proxy_transport = self.personality.create_router_transport(self, transport_id, config)

        caller = details.caller if details else None
        transport_started = proxy_transport.marshal()
        self.publish('{}.on_proxy_transport_starting'.format(self._uri_prefix),
                     transport_started,
                     options=types.PublishOptions(exclude=caller))

        # start listening ..
        try:
            yield proxy_transport.start(False)
        except Exception as err:
            _emsg = "Cannot listen on transport endpoint: {log_failure}"
            self.log.error(_emsg, log_failure=err)

            self.publish('{}.on_proxy_transport_stopped'.format(self._uri_prefix),
                         transport_started,
                         options=types.PublishOptions(exclude=caller))

            raise ApplicationError("crossbar.error.cannot_listen", _emsg.format(log_failure=err))

        self.transports[transport_id] = proxy_transport

        self.publish('{}.on_proxy_transport_started'.format(self._uri_prefix),
                     transport_started,
                     options=types.PublishOptions(exclude=caller))

        self.log.info('{func} proxy transport "{transport_id}" started and listening!',
                      func=hltype(self.start_proxy_transport),
                      transport_id=hlid(transport_id))

        returnValue(proxy_transport.marshal())

    @inlineCallbacks
    @wamp.register(None)
    def stop_proxy_transport(self, transport_id, details=None):
        """
        Stop a currently running proxy front-end listening transport.

        :param transport_id: The run-time ID of the transport to stop.
        :param details: WAMP call details.
        :return: Proxy transport run-time information.
        """
        if transport_id not in self._transports:
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no proxy transport with ID "{}" currently running'.format(transport_id))

        caller = details.caller if details else None
        transport_stopped = self._transports[transport_id].marshal()

        self.publish('{}.on_proxy_transport_stopping'.format(self._uri_prefix),
                     transport_stopped,
                     options=types.PublishOptions(exclude=caller))

        yield self._transports[transport_id].port.stopListening()
        del self._transports[transport_id]

        self.publish('{}.on_proxy_transport_stopping'.format(self._uri_prefix),
                     transport_stopped,
                     options=types.PublishOptions(exclude=caller))

        return transport_stopped

    @wamp.register(None)
    def get_proxy_routes(self, details=None):
        """
        Get proxy routes currently running in this proxy worker.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of (target) realm names in proxy routes currently running.
        :rtype: list
        """
        self.log.debug('{func}(caller_authid="{caller_authid}")',
                       func=hltype(self.get_proxy_routes),
                       caller_authid=hlval(details.caller_authid))
        return sorted(self._routes.keys())

    @wamp.register(None)
    def list_proxy_realm_routes(self, realm_name, details=None):
        """
        Get list of all routes enabled for a particular realm
        """
        if realm_name in self._routes:
            return [self._routes[realm_name][route_id].marshal() for route_id in self._routes[realm_name].keys()]
        else:
            raise ApplicationError("crossbar.error.no_such_object",
                                   'No route for realm "{}" in proxy'.format(realm_name))

    @wamp.register(None)
    def get_proxy_realm_route(self, realm_name, route_id, details=None):
        """
        Get a particular realm-route

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: Proxy route object.
        :rtype: dict
        """
        self.log.debug('{func}(realm_name={realm_name})',
                       func=hltype(self.get_proxy_realm_route),
                       realm_name=hlid(realm_name),
                       caller_authid=hlval(details.caller_authid))

        try:
            return self._routes[realm_name][route_id]
        except KeyError:
            raise ApplicationError("crossbar.error.no_such_object",
                                   'No route "{}" for realm "{}" in proxy'.format(route_id, realm_name))

    @inlineCallbacks
    @wamp.register(None)
    def start_proxy_realm_route(self, realm_name, config, details=None):
        """
        Start a new proxy route for the given realm. A proxy route maps authroles
        on the given realm to proxy backend connection IDs.

        Example route configuration:

        .. code-block:: json

            {
                "anonymous": "conn1",
                "restbridge": "conn1",
                "user": "conn2"
            }

        In this example, the two specified connections ``"conn1"`` and ``"conn2"``
        must be running already.

        :param realm_name: The realm this route should apply for.
        :param config: The route configuration.
        :param details: WAMP call details.
        :return: Proxy route run-time information.
        """
        self.log.info(
            '{func}(realm_name="{realm_name}", config={config})',
            func=hltype(self.start_proxy_realm_route),
            realm_name=realm_name,
            config=config,
        )

        # check that we already know about all connections specified in the route
        connection_ids = set()
        for role_name in config.keys():
            connection_id = config[role_name]
            if connection_id not in self._connections:
                raise ApplicationError(
                    "crossbar.error.no_such_object",
                    'no connection "{}" found for realm "{}" and role "{}" in proxy route config'.format(
                        connection_id, realm_name, role_name))
            else:
                connection_ids.add(connection_id)

        # remember connections mapped from proxy routes by (realm, authrole)
        for role_name in config.keys():
            connection_id = config[role_name]
            connection = self._connections[connection_id]
            key = (realm_name, role_name)
            if key not in self._connections_by_auth:
                self._connections_by_auth[key] = set()
            self._connections_by_auth[key].add(connection)

        if realm_name not in self._routes:
            self._routes[realm_name] = dict()

        route_id = 'route{:03d}'.format(self._next_route_id)
        self._next_route_id += 1

        route = ProxyRoute(self, realm_name, route_id, config)
        yield route.start()

        # remember route by route ID
        self._routes[realm_name][route_id] = route

        # remember route by connections
        for connection_id in connection_ids:
            if connection_id not in self._routes_by_connection:
                self._routes_by_connection[connection_id] = set()
            self._routes_by_connection[connection_id].add(route)

        returnValue(route.marshal())

    @inlineCallbacks
    @wamp.register(None)
    def stop_proxy_realm_route(self, realm_name, route_id, details=None):
        """
        Stop a currently running proxy route.

        :param realm_name: The name of the realm to stop the route for.
        :param route_id: Which route to stop
        :param details: WAMP call details.
        :return: Run-time information about the stopped route.
        """
        self.log.info('{func}(realm_name={realm_name}, caller_authid="{caller_authid}")',
                      func=hltype(self.stop_proxy_realm_route),
                      realm_name=realm_name,
                      caller_authid=hlval(details.caller_authid))
        if realm_name not in self._routes:
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no proxy routes for realm "{}" currently running'.format(realm_name))
        if route_id not in self._routes[realm_name]:
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no route "{}" for realm "{}" currently running'.format(route_id, realm_name))

        route = self._routes[realm_name][route_id]
        yield route.stop()
        del self._routes[realm_name][route_id]

        # If all routes are stopped, clear the realm from routes map
        # Relevant discussion: https://github.com/crossbario/crossbar/pull/1968
        if len(self._routes[realm_name]) == 0:
            del self._routes[realm_name]

        returnValue(route.marshal())

    @wamp.register(None)
    def get_proxy_connections(self, details=None):
        """
        Get currently running proxy connections.

        :param details: WAMP call details.
        :return: List of run-time IDs of currently running connection.s
        """
        self.log.debug('{func}(caller_authid="{caller_authid}")',
                       func=hltype(self.get_proxy_connections),
                       caller_authid=hlval(details.caller_authid))

        return sorted(self._connections.keys())

    @wamp.register(None)
    def get_proxy_connection(self, connection_id, details=None):
        """
        Get run-time information for a currently running proxy connection.

        :param connection_id: The run-time ID of the proxy connection to return information for.
        :param details: WAMP call details.
        :return: Proxy connection configuration.
        """
        self.log.debug('{func}(connection_id={connection_id}, caller_authid="{caller_authid}")',
                       func=hltype(self.get_proxy_connection),
                       connection_id=hlid(connection_id),
                       caller_authid=hlval(details.caller_authid))

        if connection_id in self._connections:
            connection = self._connections[connection_id]
            return connection.marshal()
        else:
            raise ApplicationError("crossbar.error.no_such_object",
                                   'no proxy connection with ID "{}" currently running'.format(connection_id))

    @inlineCallbacks
    @wamp.register(None)
    def start_proxy_connection(self, connection_id, config, details=None):
        """
        Start a new backend connection for the proxy.

        Called from master node orchestration in
            :method:`crossbar.master.arealm.arealm.ApplicationRealmMonitor._apply_webcluster_connections`.

        :param connection_id:
        :param config:
        :param details:
        :return:
        """
        self.log.info('{func}(connection_id={connection_id}, config=.., caller_authid={caller_authid}):\n{config}',
                      func=hltype(self.start_proxy_connection),
                      connection_id=connection_id,
                      config=pformat(config),
                      caller_authid=hlval(details.caller_authid))
        if connection_id in self._connections:
            raise ApplicationError('crossbar.error.already_running',
                                   'proxy connection with ID "{}" already running'.format(connection_id))

        connection = ProxyConnection(self, connection_id, config)
        self._connections[connection_id] = connection
        yield connection.start()

        returnValue(connection.marshal())

    @inlineCallbacks
    @wamp.register(None)
    def stop_proxy_connection(self, connection_id, details=None):
        """

        :param connection_id:
        :param details:
        :return:
        """
        self.log.info('{func}(connection_id={connection_id}, caller_authid="{caller_authid}")',
                      func=hltype(self.stop_proxy_connection),
                      connection_id=connection_id,
                      caller_authid=hlval(details.caller_authid))
        if connection_id not in self._connections:
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no proxy connection with ID "{}" currently running'.format(connection_id))

        connection = self._connections[connection_id]
        yield connection.stop()
        del self._connections[connection_id]

        returnValue(connection.marshal())


IRealmContainer.register(ProxyController)
