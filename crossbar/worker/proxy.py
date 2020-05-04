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

import os
import binascii
from pprint import pformat

from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

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
from autobahn.wamp.interfaces import ITransportHandler
from autobahn.twisted.wamp import Session, ApplicationSession
from autobahn.twisted.component import _create_transport_factory, _create_transport_endpoint
from autobahn.twisted.component import Component

from crossbar._util import hltype, hlid, hlval
from crossbar.node import worker
from crossbar.worker.controller import WorkerController
from crossbar.worker.router import _TransportController
from crossbar.common.key import _read_node_key
from crossbar.common.twisted.endpoint import extract_peer_certificate
from crossbar.router.auth import PendingAuthWampCra, PendingAuthTicket, PendingAuthScram
from crossbar.router.auth import AUTHMETHOD_MAP
from crossbar.router.session import RouterSessionFactory
from crossbar.router.session import RouterFactory

try:
    from crossbar.router.auth import PendingAuthCryptosign, PendingAuthCryptosignProxy
except ImportError:
    PendingAuthCryptosign = None
    PendingAuthCryptosignProxy = None


__all__ = (
    'ProxyWorkerProcess',
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
        'broker': RoleBrokerFeatures(
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
        'dealer': RoleDealerFeatures(
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

    def onOpen(self, transport):
        """
        Callback fired when transport is open. May run asynchronously. The transport
        is considered running and is_open() would return true, as soon as this callback
        has completed successfully.

        :param transport: The WAMP transport.
        :type transport: object implementing :class:`autobahn.wamp.interfaces.ITransport`
        """
        self.log.info('{klass}.onOpen(transport={transport})', klass=self.__class__.__name__, transport=transport)
        self.transport = transport

        # transport configuration
        if hasattr(self.transport, 'factory') and hasattr(self.transport.factory, '_config'):
            self._transport_config = self.transport.factory._config
        else:
            self._transport_config = {}

        # a dict with x509 TLS client certificate information (if the client provided a cert)
        # constructed from information from the Twisted stream transport underlying the WAMP transport
        client_cert = None
        # eg LongPoll transports lack underlying Twisted stream transport, since LongPoll is
        # implemented at the Twisted Web layer. But we should nevertheless be able to
        # extract the HTTP client cert! <= FIXME
        if hasattr(self.transport, 'transport'):
            client_cert = extract_peer_certificate(self.transport.transport)
        if client_cert:
            self.transport._transport_info['client_cert'] = client_cert
            self.log.info("Proxy frontend session connecting with TLS client certificate {client_cert}",
                          client_cert=client_cert)

        # forward the transport channel ID (if any) on transport details
        channel_id = None
        if hasattr(self.transport, 'get_channel_id'):
            # channel ID isn't implemented for LongPolL!
            channel_id = self.transport.get_channel_id()
        if channel_id:
            self.transport._transport_info['channel_id'] = binascii.b2a_hex(channel_id).decode('ascii')

        self._custom_authextra = {
            'x_cb_proxy_node': self._router_factory._node_id,
            'x_cb_proxy_worker': self._router_factory._worker_id,
            'x_cb_proxy_peer': str(self.transport.peer),
            'x_cb_proxy_pid': os.getpid(),
        }

        self.log.info("Proxy frontend session connected - transport: {transport_info}",
                      transport_info=self.transport._transport_info)

    def onClose(self, wasClean):
        """
        Callback fired when the transport has been closed.

        :param wasClean: Indicates if the transport has been closed regularly.
        :type wasClean: bool
        """
        self.log.info('{klass}.onClose(wasClean={wasClean})', klass=self.__class__.__name__, wasClean=wasClean)

        # actually, at this point, the backend session should already be gone .. but better check!
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
        self.log.debug('{klass}.onMessage(msg={msg})', klass=self.__class__.__name__, msg=msg)
        if self._session_id is None:
            # no frontend session established yet, so we expect one of HELLO, ABORT, AUTHENTICATE

            # https://wamp-proto.org/_static/gen/wamp_latest.html#session-establishment
            if isinstance(msg, message.Hello):
                yield self._process_Hello(msg)

            # https://wamp-proto.org/_static/gen/wamp_latest.html#session-closing
            elif isinstance(msg, message.Abort):
                self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                                  message='Proxy authentication failed'))

            # https://wamp-proto.org/_static/gen/wamp_latest.html#wamp-level-authentication
            elif isinstance(msg, message.Authenticate):
                self._process_Authenticate(msg)

            else:
                raise ProtocolError("Received {} message while proxy frontend session is not joined".format(msg.__class__.__name__))

        else:
            # frontend session is established: process WAMP message

            if isinstance(msg, message.Hello) or isinstance(msg, message.Abort) or isinstance(msg, message.Authenticate):
                raise ProtocolError("Received {} message while proxy frontend session is already joined".format(msg.__class__.__name__))

            # https://wamp-proto.org/_static/gen/wamp_latest.html#session-closing
            elif isinstance(msg, message.Goodbye):
                if self._backend_session:
                    self._controller.unmap_backend(self, self._backend_session)
                    self._backend_session = None
                else:
                    self.log.warn('Frontend session left, but no active backend session to close!')

                # complete the closing handshake (initiated by the client in this case) by replying with GOODBYE
                self.transport.send(message.Goodbye(message="Proxy session closing"))
            else:
                if self._backend_session is None or self._backend_session._transport is None:
                    raise TransportLost(
                        "Expected to relay {} message, but proxy backend session or transport is gone".format(
                            msg.__class__.__name__,
                        )
                    )
                else:
                    # if we have an active backend connection, forward the WAMP message ..
                    self._backend_session._transport.send(msg)

    def _accept(self, accept):
        # we have done authentication with the client; now we can connect to
        # the backend (and we wait to tell the client they're
        # welcome until we have actually connected to the
        # backend).
        self.log.info('Frontend session accepted ({accept}) - opening proxy backend session ...', accept=accept)

        result = Deferred()

        @inlineCallbacks
        def _backend_connected(backend_session):
            try:
                # wait for the WAMP-level transport to connect
                yield backend_session._on_connect

                # node private key
                key = _read_node_key(self._controller._cbdir, private=False)

                # FIXME
                authmethods = [
                    '{}-proxy'.format(x)
                    for x in backend_session._authenticators.keys()
                ]
                # authmethods = ['cryptosign-proxy']
                self.log.info('Proxy backend session authenticating using authmethods={authmethods} ..',
                              authmethods=authmethods)

                backend_session.join(
                    accept.realm,
                    authmethods=authmethods,
                    authid=None,
                    authrole=None,
                    authextra={
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

                        # this is the authextra returned from the frontend authenticator, which
                        # would normally be returned to the client
                        "proxy_authextra": accept.authextra,
                    }
                )

                def _on_backend_joined(session, details):
                    self.log.info('Proxy backend session JOINED: session_id={backend_session_id} session={backend_session}, details={details}',
                                  backend_session_id=hlid(details.session), backend_session=session,
                                  pending_session_id=self._pending_session_id, details=details)
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

                backend_session.on('join', _on_backend_joined)
                yield backend_session._on_ready
                return backend_session
            except Exception as e:
                self.log.failure()
                result.errback(e)

        def _backend_failed(fail):
            result.errback(fail)

        backend_d = self._controller.map_backend(
            self,
            accept.realm,
            accept.authid,
            accept.authrole,
            accept.authextra,
        )
        backend_d.addCallback(_backend_connected)
        backend_d.addErrback(_backend_failed)

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
        self.log.info('{klass}._process_Hello(msg={msg})', klass=self.__class__.__name__, msg=msg)
        self._pending_session_id = util.id()
        self._goodbye_sent = False

        extra_auth_methods = self._controller.personality.EXTRA_AUTH_METHODS

        # allow "Personality" classes to add authmethods
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

        # already authenticated, eg via HTTP-cookie or TLS-client-certificate authentication
        if self.transport._authid is not None and (self.transport._authmethod == 'trusted' or self.transport._authprovider in authmethods):
            msg.realm = self.transport._realm
            msg.authid = self.transport._authid
            msg.authrole = self.transport._authrole

        details = types.HelloDetails(
            realm=msg.realm,
            authmethods=authmethods,
            authid=msg.authid,
            authrole=msg.authrole,
            authextra=msg.authextra,
            session_roles=msg.roles,
            pending_session=self._pending_session_id
        )
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
            auth_config = {
                'anonymous': {
                    'type': 'static',
                    'authrole': 'anonymous',
                    'authid': authid,
                }
            }
            self.log.warn('No authentication configured for proxy frontend: using default anonymous access policy for incoming proxy frontend session')

        for authmethod in authmethods:
            # invalid authmethod
            if authmethod not in AUTHMETHOD_MAP and authmethod not in extra_auth_methods:
                self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                                  message='authmethod "{}" not allowed'.format(authmethod)))
                return

            # authmethod is valid, but not configured: continue trying other authmethods the client is announcing
            if authmethod not in auth_config:
                continue

            # authmethod not available
            if authmethod not in AUTHMETHOD_MAP and authmethod not in extra_auth_methods:
                self.log.debug("client requested valid, but unavailable authentication method {authmethod}",
                               authmethod=authmethod)
                continue

            # create instance of authenticator using authenticator class for the respective authmethod
            authklass = extra_auth_methods[authmethod] if authmethod in extra_auth_methods else AUTHMETHOD_MAP[authmethod]
            self._pending_auth = authklass(
                self._pending_session_id,
                self.transport._transport_info,
                self._controller,
                auth_config[authmethod],
            )
            try:
                # call into authenticator for processing the HELLO message
                hello_result = yield as_future(self._pending_auth.hello, msg.realm, details)
            except Exception as e:
                self.log.failure()
                self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                                  message='Frontend connection accept failed ({})'.format(e)))
                return
            self.log.info('{klass}._process_Hello() processed authmethod "{authmethod}" using {authklass}: {hello_result}',
                          klass=self.__class__.__name__, authmethod=authmethod, authklass=authklass,
                          hello_result=hello_result)

            # if the frontend session is accepted right away (eg when doing "anonymous" authentication), process the
            # frontend accept ..
            if isinstance(hello_result, types.Accept):
                try:
                    # get a backend session mapped to the incoming frontend session
                    session = yield self._accept(hello_result)
                except Exception as e:
                    self.log.failure()
                    self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
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
                    self.log.info('Proxy frontend session WELCOME: session_id={session}, session={session}, session_details={details}',
                                  session_id=hlid(self._session_id), session=self, details=details)

                session.on('join', _on_backend_joined)

            # if the client is required to do an authentication message exchange, answer sending a CHALLENGE message
            elif isinstance(hello_result, types.Challenge):
                self.transport.send(message.Challenge(hello_result.method, extra=hello_result.extra))

            # if the client is denied right away, answer by sending an ABORT message
            elif isinstance(hello_result, types.Deny):
                self.transport.send(message.Abort(hello_result.reason, message=hello_result.message))

            # should not arrive here: internal (logic) error
            else:
                self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                                  message='internal error: unexpected authenticator return type {}'.format(type(hello_result))))
            return

        self.transport.send(message.Abort(ApplicationError.NO_AUTH_METHOD, message='no suitable authmethod found'))

    @inlineCallbacks
    def _process_Authenticate(self, msg):
        self.log.info('{klass}._process_Authenticate(msg={msg})', klass=self.__class__.__name__, msg=msg)
        if self._pending_auth:
            if isinstance(self._pending_auth, PendingAuthTicket) or \
               isinstance(self._pending_auth, PendingAuthWampCra) or \
               isinstance(self._pending_auth, PendingAuthCryptosign) or \
               isinstance(self._pending_auth, PendingAuthScram):
                auth_result = self._pending_auth.authenticate(msg.signature)
                self.log.info(
                    '{klass}._process_Authenticate() processed pending authentication {pending_auth}: {authresult}',
                    klass=self.__class__.__name__, pending_auth=self._pending_auth, authresult=auth_result)
                if isinstance(auth_result, types.Accept):
                    try:
                        session = yield self._accept(auth_result)
                    except Exception as e:
                        self.log.failure()
                        self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
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
                            self.log.info('Proxy frontend session WELCOME: session_id={session_id}, session={session}, msg={msg}',
                                          session_id=hlid(self._session_id), session=self, msg=msg)

                        session.on('join', _on_backend_joined)
                elif isinstance(auth_result, types.Deny):
                    self.transport.send(message.Abort(auth_result.reason, message=auth_result.message))
                else:
                    # should not arrive here: logic error
                    self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                                      message='internal error: unexpected authenticator return type {}'.format(type(auth_result))))
            else:
                # should not arrive here: logic error
                self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                                  message='internal error: unexpected pending authentication'))
        else:
            # should not arrive here: client misbehaving!
            self.transport.send(message.Abort(ApplicationError.AUTHENTICATION_FAILED,
                                              message='no pending authentication'))


ITransportHandler.register(ProxyFrontendSession)


class ProxyBackendSession(Session):
    """
    This is a single WAMP session to the real backend service

    There is one of these for every client connection. (In the future,
    we could multiplex over a single backend connection -- for now,
    there's a backend connection per frontend client).

    XXX serializer translation?

    XXX before ^ just negotiate with the frontend to have the same
    serializer as the backend.
    """

    def onOpen(self, transport):
        # instance of Frontend
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
        self._on_connect.callback(None)

    def onChallenge(self, challenge):
        if challenge.method == "cryptosign-proxy":
            return super(ProxyBackendSession, self).onChallenge(
                types.Challenge("cryptosign", extra=challenge.extra)
            )

        return super(ProxyBackendSession, self).onChallenge(challenge)

    def onWelcome(self, msg):
        if msg.authmethod == "cryptosign-proxy":
            msg.authmethod = "cryptosign"
        elif msg.authmethod == "anonymous-proxy":
            msg.authmethod = "anonymous"
        return super(ProxyBackendSession, self).onWelcome(msg)

    def onJoin(self, details):
        if not self._on_ready.called:
            self._on_ready.callback(self)

    def onClose(self, wasClean):
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

    def onMessage(self, msg):
        # 'msg' is a real WAMP message that our backend WAMP protocol
        # has deserialized -- so now we re-serialize it for whatever
        # the frontend is speaking
        if isinstance(msg, (message.Welcome, message.Challenge, message.Abort, message.Goodbye)):
            super(ProxyBackendSession, self).onMessage(msg)
        else:
            self._frontend._forward(msg)


def make_backend_connection(backend_config, frontend_session, cbdir):
    """
    Connects to a 'backend' session with the given config; returns a
    transport that is definitely connected (e.g. you can send a Hello
    right away).

    :param backend_config: Backend connection configuration, for example:

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

    :param frontend_session: The frontend proxy session for which to create a mapped backend connection.

    :param cbdir: The node directory.
    """

    from twisted.internet import reactor

    connected_d = Deferred()
    backend = _create_transport(0, backend_config['transport'])
    key = _read_node_key(cbdir, private=True)

    def create_session():
        session = ProxyBackendSession()

        # we will do cryptosign authentication to any backend
        if 'auth' in backend_config and 'cryptosign-proxy' in backend_config['auth']:
            session.add_authenticator(create_authenticator("cryptosign", privkey=key['hex']))

        # we allow anonymous authentication to just unix-sockets
        # currently. I don't think it's a good idea to allow any
        # anonymous auth to "real" backends over TCP due to
        # cross-protocol hijinks (and if a Web browser is running on
        # that machine, any website can try to access the "real"
        # backend)
        if 'auth' not in backend_config or 'anonymous-proxy' in backend_config['auth']:
            if backend_config['transport']['endpoint']['type'] == 'unix':
                session.add_authenticator(create_authenticator("anonymous"))
            else:
                raise RuntimeError('anonymous-proxy authenticator only allowed on Unix domain socket based transports, not type "{}"'.format(backend_config['transport']['endpoint']['type']))

        def connected(session, transport):
            connected_d.callback(session)
        session.on('connect', connected)
        return session

    # client-factory
    factory = _create_transport_factory(reactor, backend, create_session)
    endpoint = _create_transport_endpoint(reactor, backend_config['transport']['endpoint'])
    transport_d = endpoint.connect(factory)

    def _connected(proto):
        proto._proxy_other_side = frontend_session
        return proto

    def _error(f):
        if not connected_d.called:
            connected_d.errback(f)
    transport_d.addErrback(_error)
    transport_d.addCallback(_connected)

    return connected_d


class AuthenticatorSession(ApplicationSession):

    # when running over TLS, require TLS channel binding
    # CHANNEL_BINDING = 'tls-unique'
    CHANNEL_BINDING = None

    def __init__(self, config=None):
        self.log.info("initializing component: {config}", config=config)
        ApplicationSession.__init__(self, config)

        # load the client private key (raw format)
        try:
            self._key = cryptosign.SigningKey.from_key_bytes(config.extra['key'])
        except:
            self.log.failure()
            if self.is_attached():
                self.leave()
        else:
            self.log.info("client public key loaded: {}".format(
                self._key.public_key()))

    def onConnect(self):
        self.log.info("connected to router")
        extra = {
            'pubkey': self._key.public_key(),
        }
        self.join(self.config.realm,
                  authmethods=['cryptosign'],
                  authid=self.config.extra.get('authid', None),
                  authextra=extra)

    async def onChallenge(self, challenge):
        self.log.info(
            "authentication challenge received: {challenge}", challenge=challenge)
        try:
            signed_challenge = await self._key.sign_challenge(self, challenge, channel_id_type=self.CHANNEL_BINDING)
            return signed_challenge
        except:
            self.log.failure()
            raise

    def onJoin(self, details):
        self.log.info('session joined: {details}', details=details)
        if self.config.extra['ready']:
            self.config.extra['ready'].callback(self)
            self.config.extra['ready'] = None

    def onLeave(self, details):
        self.log.info("session closed: {details}", details=details)

    def onDisconnect(self):
        self.log.info("connection to router closed")


def make_authenticator_session(backend_config, cbdir, realm, extra=None, reactor=None):
    # connect the remote session
    #
    # remote connection parameters to ApplicationRunner:
    #
    # url: The WebSocket URL of the WAMP router to connect to (e.g. ws://somehost.com:8090/somepath)
    # realm: The WAMP realm to join the application session to.
    # extra: Optional extra configuration to forward to the application component.
    # serializers: List of :class:`autobahn.wamp.interfaces.ISerializer` (or None for default serializers).
    # ssl: None or :class:`twisted.internet.ssl.CertificateOptions`
    # proxy: Explicit proxy server to use; a dict with ``host`` and ``port`` keys
    # headers: Additional headers to send (only applies to WAMP-over-WebSocket).
    # max_retries: Maximum number of reconnection attempts. Unlimited if set to -1.
    # initial_retry_delay: Initial delay for reconnection attempt in seconds (Default: 1.0s).
    # max_retry_delay: Maximum delay for reconnection attempts in seconds (Default: 60s).
    # retry_delay_growth: The growth factor applied to the retry delay between reconnection attempts (Default 1.5).
    # retry_delay_jitter: A 0-argument callable that introduces nose into the delay. (Default random.random)
    #
    log = make_logger()

    try:
        if not reactor:
            from twisted.internet import reactor

        extra = {
            'key': binascii.a2b_hex(_read_node_key(cbdir, private=True)['hex']),
        }
        comp = Component(
            transports=[backend_config['transport']],
            realm=realm,
            extra=extra,
            authentication={
                "cryptosign": {
                    "privkey": _read_node_key(cbdir, private=True)['hex'],
                }
            },
        )
        ready = Deferred()

        @comp.on_join
        def joined(session, details):
            ready.callback(session)

        @comp.on_disconnect
        def disconnect(session, was_clean=False):
            if not ready.called:
                ready.errback(Exception("Disconnected unexpectedly"))

        comp.start(reactor)
        return ready
    except Exception:
        log.failure()
        raise


# implements IRealmContainer
class ProxyController(_TransportController):
    WORKER_TYPE = 'proxy'
    WORKER_TITLE = 'WAMP proxy'

    def __init__(self, config=None, reactor=None, personality=None):
        super(ProxyController, self).__init__(
            config=config,
            reactor=reactor,
            personality=personality,
        )

        self._cbdir = config.extra.cbdir
        self._reactor = reactor
        self._transports = dict()
        self._routes = dict()  # realm -> dict

        # map: transport ID -> RouterTransport
        self.transports = {}

        # will be set up via Node by start_proxy_connection et al.
        self._backend_configs = dict()

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

        self._service_sessions = {}

    def has_realm(self, realm: str) -> bool:
        """
        Check if a route to a realm with the given name is currently running.

        :param realm: Realm name (_not_ ID).
        :type realm: str

        :returns: True if a route to the realm exists.
        :rtype: bool
        """
        result = realm in self._routes
        self.log.info('{func}(realm="{realm}") -> {result}', func=hltype(ProxyController.has_realm),
                      realm=hlid(realm), result=hlval(result))
        return result

    def has_role(self, realm: str, authrole: str) -> bool:
        """
        Check if a role with the given name is currently running in the given realm.

        :param realm: WAMP realm (name, _not_ run-time ID).
        :type realm: str

        :param authrole: WAMP authentication role (URI, _not_ run-time ID).
        :type authrole: str

        :returns: True if realm is running.
        :rtype: bool
        """
        authrole = authrole or 'trusted'
        result = authrole in self._routes.get(realm, {})
        self.log.info('{func}(realm="{realm}", authrole="{authrole}") -> {result}',
                      func=hltype(ProxyController.has_role), realm=hlid(realm), authrole=hlid(authrole),
                      result=hlval(result))
        return result

    @inlineCallbacks
    def get_service_session(self, realm, authrole):
        """
        IRealmContainer (this is used by dynamic authenticators)
        """
        try:
            self.log.info('{klass}.get_service_session(realm="{realm}", authrole="{authrole}")',
                          klass=self.__class__.__name__, realm=realm, authrole=authrole)
            if realm not in self._service_sessions:
                if self.has_realm(realm):
                    self.log.info('{klass}.get_service_session(realm="{realm}") -> not cached, creating new session ..',
                                  klass=self.__class__.__name__, realm=realm)
                    # self._service_sessions[realm] = yield self.map_backend(None, realm, None, 'authenticator', None)
                    backend_config = self.get_backend_config(realm, authrole)
                    self._service_sessions[realm] = yield make_authenticator_session(backend_config, self._cbdir, realm)
                else:
                    # mark as non-existing!
                    self._service_sessions[realm] = None

            if self._service_sessions[realm]:
                self.log.info('{klass}.get_service_session(realm="{realm}") -> cached service session {session}',
                              klass=self.__class__.__name__, realm=realm, session=self._service_sessions[realm]._session_id)
                return self._service_sessions[realm]
            else:
                self.log.info('{klass}.get_service_session(realm="{realm}") -> no such realm!',
                              klass=self.__class__.__name__, realm=realm)
                return None
        except:
            self.log.failure()
            raise

    def can_map_backend(self, session_id, realm, authid, authrole, authextra):
        """
        :returns: True only-if map_backend() can succeed later for the
        same args (essentially, if the realm + role exist).
        """
        return self.has_realm(realm) and self.has_role(realm, authrole)

    @inlineCallbacks
    def map_backend(self, frontend, realm, authid, authrole, authextra):
        """
        Map the given frontend session to a backend session under the given
        authentication credentials.

        :returns: a protocol instance connected to the backend
        """
        self.log.info('{klass}.map_backend(frontend={frontend}, realm="{realm}", authid="{authid}", authrole="{authrole}", authextra={authextra})',
                      klass=self.__class__.__name__, frontend=frontend, realm=hlid(realm), authid=hlid(authid), authrole=hlid(authrole),
                      authextra=authextra)
        if frontend in self._backends_by_frontend:
            return self._backends_by_frontend[frontend]

        backend_config = self.get_backend_config(realm, authrole)

        # if auth uses cryptosign but has no privkey, we'd ideally
        # insert the node's private key

        if authrole is None:
            if len(self._routes.get(realm, {})) != 1:
                raise RuntimeError(
                    "Cannot select default role unless realm has exactly 1"
                )

        self.log.info('{klass}.map_backend(): opening backend connection for realm "{realm}", authrole "{authrole}" using backend_config\n{backend_config}',
                      klass=self.__class__.__name__, backend_config=pformat(backend_config), realm=hlid(realm), authrole=hlid(authrole))

        backend_proto = yield make_backend_connection(backend_config, frontend, self._cbdir)

        if frontend:
            self._backends_by_frontend[frontend] = backend_proto

        self.log.info('{klass}.map_backend(): ok, backend session {session_id} opened for realm "{realm}", authrole "{authrole}"',
                      klass=self.__class__.__name__, backend_config=pformat(backend_config), realm=hlid(realm),
                      authrole=hlid(authrole), session_id=backend_proto._session_id)

        returnValue(backend_proto)

    def unmap_backend(self, frontend, backend):
        """
        Unmap the backend session from the given frontend session it is currently mapped to.
        """
        self.log.info('{klass}.unmap_backend(frontend={frontend}, backend={backend})', klass=self.__class__.__name__,
                      frontend=frontend, backend=backend)
        if frontend in self._backends_by_frontend:
            if self._backends_by_frontend[frontend] == backend:
                # alright, the given frontend is indeed currently mapped to the given backend session: close the
                # session and delete it
                backend.leave()
                del self._backends_by_frontend[frontend]
                self.log.info('{klass}.unmap_backend: ok, unmapped frontend session {frontend_session_id} from backend session {backend_session_id}',
                              klass=self.__class__.__name__, frontend_session_id=frontend._session_id,
                              backend_session_id=backend._session_id)
            else:
                self.log.warn('{klass}.unmap_backend: frontend session {frontend_session_id} currently mapped to backend session {backend_session_id} - NOT to specified backend {specified_session_id}'.format(
                    klass=self.__class__.__name__, frontend_session_id=frontend._session_id,
                    backend_session_id=self._backends_by_frontend[frontend]._session_id,
                    specified_session_id=backend._session_id))
        else:
            if frontend:
                self.log.warn('{klass}.unmap_backend: frontend session {session_id} not currently mapped to any backend',
                              klass=self.__class__.__name__, session_id=frontend._session_id)

    def get_backend_config(self, realm_name, role_name):
        """
        :returns: a dict containing the configure for the backend
            identified by the realm_name and role_name
        """
        backend_name = self._routes[realm_name][role_name]['backend_name']
        return self._backend_configs[backend_name]

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        self.log.info(
            'Proxy worker "{worker_id}" session {session_id} initializing ..',
            worker_id=self._worker_id,
            session_id=details.session,
        )

        yield WorkerController.onJoin(self, details, publish_ready=False)

        yield self.publish_ready()

    @inlineCallbacks
    @wamp.register(None)
    def start_proxy_transport(self, transport_id, config, details=None):
        self.log.debug(
            "start_proxy_transport: transport_id={transport_id}, config={config}",
            transport_id=transport_id,
            config=config,
        )
        self.log.info(
            "start_proxy_transport: transport_id={transport_id}",
            transport_id=transport_id,
        )

        self.log.info(
            'Starting proxy transport "{transport_id}" {method}',
            transport_id=transport_id,
            method=self.start_proxy_transport,
        )

        # prohibit starting a transport twice
        if transport_id in self.transports:
            _emsg = 'Could not start transport: a transport with ID "{}" is already running (or starting)'.format(transport_id)
            self.log.error(_emsg)
            raise ApplicationError('crossbar.error.already_running', _emsg)

        # create a transport and parse the transport configuration
        # (NOTE: yes, this is re-using create_router_transport so we
        # can proxy every sevice a 'real' router can)
        proxy_transport = self.personality.create_router_transport(self, transport_id, config)

        caller = details.caller if details else None
        event = {
            'id': transport_id
        }
        topic = '{}.on_proxy_transport_starting'.format(self._uri_prefix)
        self.publish(topic, event, options=types.PublishOptions(exclude=caller))

        # start listening ..
        try:
            yield proxy_transport.start(False)
        except Exception as err:
            _emsg = "Cannot listen on transport endpoint: {log_failure}"
            self.log.error(_emsg, log_failure=err)

            topic = '{}.on_proxy_transport_stopped'.format(self._uri_prefix)
            self.publish(topic, event, options=types.PublishOptions(exclude=caller))

            raise ApplicationError("crossbar.error.cannot_listen", _emsg.format(log_failure=err))

        self.transports[transport_id] = proxy_transport
        self.log.debug('Router transport "{transport_id}" started and listening', transport_id=transport_id)

        topic = '{}.on_proxy_transport_started'.format(self._uri_prefix)
        self.publish(topic, event, options=types.PublishOptions(exclude=caller))

        returnValue(proxy_transport.marshal())

    @inlineCallbacks
    @wamp.register(None)
    def stop_proxy_transport(self, name, details=None):
        if name not in self._transports:
            raise ApplicationError(
                "crossbar.error.worker_not_running",
                "No such worker '{}'".format(name),
            )
        yield self._transports[name].port.stopListening()
        del self._transports[name]

    @wamp.register(None)
    def start_proxy_route(self, realm_name, config, details=None):
        self.log.info(
            "start_proxy_route: realm_name={realm_name}, config={config}",
            realm_name=realm_name,
            config=config,
        )
        if realm_name in self._routes:
            raise Exception("Already have realm '{}'".format(realm_name))

        route_role = dict()
        for role_name in config:
            route_role[role_name] = {
                "backend_name": config[role_name],
            }
        self._routes[realm_name] = route_role

        # FIXME: publish event; store in local metadata object

        route_started = {
            'started': time_ns(),
            'realm': realm_name,
            'route': route_role
        }
        return route_started

    @wamp.register(None)
    def start_proxy_connection(self, name, options, details=None):
        self.log.info(
            "start_proxy_connection '{name}': {options}",
            name=name,
            options=options,
        )
        if name in self._backend_configs:
            raise ValueError(
                "Already have a connection named '{}'".format(name)
            )
        self._backend_configs[name] = options
