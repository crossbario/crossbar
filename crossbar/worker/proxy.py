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

from twisted.internet.defer import inlineCallbacks, Deferred, returnValue
from twisted.internet.endpoints import UNIXClientEndpoint

from autobahn import wamp
from autobahn import util
from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp.auth import create_authenticator
from autobahn.wamp.exception import ApplicationError, ProtocolError, Error
from autobahn.wamp.role import RoleDealerFeatures, RoleBrokerFeatures
from autobahn.wamp.component import _create_transport
from autobahn.wamp.interfaces import ITransportHandler
from autobahn.twisted.wamp import Session
from autobahn.twisted.component import _create_transport_factory, _create_transport_endpoint

from crossbar.node import worker
from crossbar.worker.controller import WorkerController
from crossbar.worker.router import RouterController
from crossbar.common.key import _read_node_key


__all__ = (
    'ProxyWorkerProcess',
)


class ProxyWorkerProcess(worker.NativeWorkerProcess):

    TYPE = 'proxy'
    LOGNAME = 'Proxy'


class ProxySession(object):
    """
    A router-side proxy session that handles incoming client
    connections.
    """

    def __init__(self, router_factory):
        self.transport = None
        self._router_factory = router_factory

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
        self._controller = router_factory._proxy_controller

        # if we have a backend connection, it'll be here (and be a
        # Session instance)
        self._backend_session = None
        self._established = False

        # in _transport_info are (possibly) the following keys (gleaned from router/session.py):
        # client_cert
        # channel_id
        # type (websocket, etc)
        # protocol (websocket subprotocol?) None for rawsocket
        # peer
        # http_headers_received
        # http_headers_sent
        # http_response_lines
        # websocket_extensions_in_use
        # cbtid

        # for rawsocket, it's type, protocol=None and peer

    def onOpen(self, transport):
        """
        Callback fired when transport is open. May run asynchronously. The transport
        is considered running and is_open() would return true, as soon as this callback
        has completed successfully.

        :param transport: The WAMP transport.
        :type transport: object implementing :class:`autobahn.wamp.interfaces.ITransport`
        """
        # print("ProxySession.onOpen: {}".format(transport))
        self.transport = transport

    def onMessage(self, msg):
        """
        Callback fired when a WAMP message was received. May run asynchronously. The callback
        should return or fire the returned deferred/future when it's done processing the message.
        In particular, an implementation of this callback must not access the message afterwards.

        :param msg: The WAMP message received.
        :type msg: object implementing :class:`autobahn.wamp.interfaces.IMessage`
        """
        # print("ProxySession.onMessage: {}".format(msg))

        if isinstance(msg, message.Hello):
            self._hello_received(msg)

        elif isinstance(msg, message.Welcome):
            self._established = True

        else:
            if self._backend_session is None:
                raise RuntimeError(
                    "Expected to relay message of type {} but backend is gone".format(
                        msg.__class__.__name__,
                    )
                )
            else:
                if self._backend_session._transport is not None:
                    self._backend_session._transport.send(msg)

    def _hello_received(self, msg):
        """
        We have received a Hello from the frontend client.

        Now we do any authentication necessary with them and connect
        to our backend.
        """
        if self._session_id is not None:
            raise ProtocolError("Hello received but session established already")

        self._realm = msg.realm
        self._session_id = util.id()
        self._goodbye_sent = False

        authid = msg.authid
        authrole = msg.authrole or 'anonymous'
        # XXX x_cb_node_id, x_cb_peer, x_cb_pid

        details = types.HelloDetails(
            realm=self._realm,
            authmethods=msg.authmethods,
            authid=authid,
            authrole=authrole or 'anonymous',
            authextra=msg.authextra,
            session_roles=msg.roles,
            pending_session=self._pending_session_id
        )

        res = self._do_authentication(self._realm, details)

        # Note: "roles" come from self._router.attach() in non-proxy
        # code
        roles = {
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

        msg = None
        if isinstance(res, types.Accept):
            msg = message.Welcome(
                self._session_id,
                roles,
                realm=self._realm,
                authid=self._authid,
                authrole=self._authrole,
                authmethod=self._authmethod,
                authprovider=self._authprovider,
                authextra=self._authextra,
                #  custom=custom,
            )

        elif isinstance(res, types.Challenge):
            msg = message.Challenge(
                res.method,
                res.extra,
            )

        elif isinstance(res, types.Deny):
            msg = message.Abort(
                res.reason,
                res.message,
            )

        else:
            msg = message.Abort("wamp.error.runtime_error", "Internal logic error")

        if isinstance(msg, message.Welcome):

            @inlineCallbacks
            def _backend_connected(backend_session):
                """
                we have done authentication with the client; now we can connect to
                the backend (and we wait to tell the client they're
                welcome until we have actually connected to the
                backend).
                """

                yield backend_session._on_connect
                self._backend_session = backend_session

                def welcome(session, details):
                    """
                    finally pass our Welcome to the frontend once we've Joined on the
                    backend
                    """
                    self.transport.send(msg)
                self._backend_session.on('join', welcome)

                key = _read_node_key(self._controller._cbdir, private=False)
                authmethods = [
                    '{}-proxy'.format(x)
                    for x in self._backend_session._authenticators.keys()
                ]

                self._backend_session.join(
                    self._realm,
                    authmethods=authmethods,
                    authid=None,
                    authrole=self._authrole,  # same role as front-end?
                    authextra={
                        "cb_proxy_authid": self._authid,
                        "cb_proxy_authrealm": self._realm,
                        "cb_proxy_authrole": self._authrole,
                        "cb_proxy_authextra": msg.authextra,
                        "pubkey": key['hex'],
                    }
                )
                return backend_session

            def _backend_failed(fail):
                # print("_backend_failed", fail)
                self.transport.send(
                    message.Abort(
                        "wamp.error.runtime_error",
                        "Failed to connect to backend: {}".format(fail),
                    )
                )

            backend_d = self._controller.map_backend(
                self,
                self._realm,
                self._authid,
                self._authrole,
            )
            backend_d.addCallback(_backend_connected)
            backend_d.addErrback(_backend_failed)
        else:
            # 'msg' is a Deny or a Challenge, so communicate that to
            # the client before we try connecting to the backend
            self.transport.send(msg)

    def _do_authentication(self, realm, details):
        if not realm:
            return types.Deny(
                ApplicationError.NO_SUCH_REALM,
                message='no realm requested',
            )
        if not self._controller.has_realm(realm):
            return types.Deny(
                ApplicationError.NO_SUCH_REALM,
                message='no realm "{}" exists on this proxy'.format(realm),
            )
        if not self._controller.can_map_backend(details.pending_session, realm, details.authid, details.authrole):
            # XXX maybe want better errors here? maybe can_map should return a Deny?
            return types.Deny(
                "wamp.error.runtime_error",
                message='Proxy cannot map session to a backend (realm="{}" role="{}")'.format(
                    realm,
                    details.authrole,
                )
            )

        if details.authmethods and 'anonymous' not in details.authmethods:
            return types.Deny(
                ApplicationError.NO_AUTH_METHOD,
                message='cannot authenticate using any of the offered authmethods {}'.format(details.authmethods),
            )

        from crossbar.router.auth import AUTHMETHOD_MAP
        PendingAuthKlass = AUTHMETHOD_MAP['anonymous']
        self._pending_auth = PendingAuthKlass(
            details.pending_session,
            {"type": "proxy"},  # what else goes in _transport_info
            self._controller,
            {
                'type': 'static',
                'role': details.authrole,
                'authid': util.generate_serial_number(),
            }
        )
        self._authrole = details.authrole
        self._authprovider = 'anonymous'
        self._authextra = details.authextra

        return self._pending_auth.hello(realm, details)

    def forward_message(self, msg):
        self.transport.send(msg)

    def onClose(self, wasClean):
        """
        Callback fired when the transport has been closed.

        :param wasClean: Indicates if the transport has been closed regularly.
        :type wasClean: bool
        """
        # print("ProxySession.onClose: {}".format(wasClean))
        if self._backend_session is not None:
            try:
                self._backend_session.leave()
            except Error:
                pass
            self._backend_session = None
            self.transport = None


ITransportHandler.register(ProxySession)


class BackendProxySession(Session):
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
            return super(BackendProxySession, self).onChallenge(
                types.Challenge("cryptosign", extra=challenge.extra)
            )

        return super(BackendProxySession, self).onChallenge(challenge)

    def onWelcome(self, msg):
        if msg.authmethod == "cryptosign-proxy":
            msg.authmethod = "cryptosign"
        elif msg.authmethod == "anonymous-proxy":
            msg.authmethod = "anonymous"
        return super(BackendProxySession, self).onWelcome(msg)

    def onClose(self, wasClean):
        if self._frontend:
            try:
                self._frontend.transport.send(message.Goodbye())
            except Exception as e:
                self.log.info(
                    "Backend closed, Goodbye to frontend failed: {fail}",
                    fail=e,
                )
        self._frontend = None
        super(BackendProxySession, self).onClose(wasClean)

    def onMessage(self, msg):
        # 'msg' is a real WAMP message that our backend WAMP protocol
        # has deserialized -- so now we re-serialize it for whatever
        # the frontend is speaking
        # print("BackendProxySession.onMessage: {}".format(msg))
        if isinstance(msg, (message.Welcome, message.Challenge, message.Abort, message.Goodbye)):
            super(BackendProxySession, self).onMessage(msg)
        else:
            self._frontend.forward_message(msg)


def make_backend_connection(backend_config, frontend_session, cbdir):
    """
    Connects to a 'backend' session with the given config; returns a
    transport that is definitely connected (e.g. you can send a Hello
    right away).
    """

    from twisted.internet import reactor

    connected_d = Deferred()
    backend = _create_transport(0, backend_config['transport'])
    key = _read_node_key(cbdir, private=True)

    def create_session():
        session = BackendProxySession()
        # we allow anonymous authentication to just unix-sockets
        # currently. I don't think it's a good idea to allow any
        # anonymous auth to "real" backends over TCP due to
        # cross-protocol hijinks (and if a Web browser is running on
        # that machine, any website can try to access the "real"
        # backend)
        if isinstance(endpoint, UNIXClientEndpoint):
            # print("local unix endpoint; anonymous auth permitted")
            session.add_authenticator(create_authenticator("anonymous"))

        # we will do cryptosign authentication to any backend
        session.add_authenticator(
            create_authenticator(
                "cryptosign",
                privkey=key['hex'],
            )
        )

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


# implements IRealmContainer
class ProxyController(RouterController):
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

        # superclass sets up:
        # self._router_factory
        # self._router_session_factory

        # will be set up via Node by start_proxy_connection et al.
        self._backend_configs = dict()
        # this lets ProxySession get back to the controller
        self._router_factory._proxy_controller = self
        # override RouterSession
        self._router_session_factory.session = ProxySession

    def has_realm(self, realm):
        """
        IRealmContainer
        """
        return realm in self._routes

    def has_role(self, realm, role):
        """
        IRealmContainer
        """
        return role in self._routes.get(realm, {})

    def get_service_session(self, realm):
        """
        IRealmContainer (this is used by dynamic authenticators)
        """
        return self

    def can_map_backend(self, session_id, realm, authid, authrole):
        """
        :returns: True only-if map_backend() can succeed later for the
        same args (essentially, if the realm + role exist).
        """
        return self.has_realm(realm) and self.has_role(realm, authrole)

    @inlineCallbacks
    def map_backend(self, frontend_session, realm, authid, authrole):
        """
        :returns: a protocol instance connected to the backend
        """
        backend_config = self.get_backend_config(realm, authrole)

        # if auth uses cryptosign but has no privkey, we'd ideally
        # insert the node's private key

        if authrole is None:
            if len(self._routes.get(realm, {})) != 1:
                raise RuntimeError(
                    "Cannot select default role unless realm has exactly 1"
                )
            self._routes.get(realm, {}).values()[0]

        backend_proto = yield make_backend_connection(backend_config, frontend_session, self._cbdir)

        returnValue(backend_proto)

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

    @wamp.register(None)
    @inlineCallbacks
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

        yield self.start_router_transport(transport_id, config, create_paths=False)

    @wamp.register(None)
    @inlineCallbacks
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
        self._routes[realm_name] = route_role

        for role_name in config:
            route_role[role_name] = {
                "backend_name": config[role_name],
            }

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
