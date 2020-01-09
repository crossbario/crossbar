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

from twisted.internet.defer import inlineCallbacks, maybeDeferred

from autobahn import wamp
from autobahn.wamp.exception import ApplicationError, TransportLost
from autobahn.wamp.message import Goodbye
from autobahn.wamp.component import _create_transport
from autobahn.wamp.websocket import parseSubprotocolIdentifier
from autobahn.wamp.websocket import WampWebSocketFactory  # just for protocol negotiation..
from autobahn.twisted.wamp import Session
from autobahn.twisted.resource import WebSocketResource
from autobahn.twisted.websocket import WebSocketServerProtocol
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.component import _create_transport_factory, _create_transport_endpoint

from crossbar.node import worker
from crossbar.worker.controller import WorkerController
from crossbar.worker.router import RouterController
from crossbar.webservice.base import RouterWebService


__all__ = (
    'ProxyWorkerProcess',
)


class ProxyWorkerProcess(worker.NativeWorkerProcess):

    TYPE = 'proxy'
    LOGNAME = 'Proxy'


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
        # print("BackendProxySession.onOpen", transport, self)
        # instance of Frontend
        self._frontend = transport._proxy_other_side
        Session.onOpen(self, transport)

    def onConnect(self):
        """
        The base class will call .join() which we do NOT want to do;
        instead we await the frontend sending its hello and forward
        that along.
        """
        pass

    def onClose(self, wasClean):
        if self._frontend.transport:
            self._frontend.transport.loseConnection()
        self._frontend = None
        super(BackendProxySession, self).onClose(wasClean)

    def onMessage(self, msg):
        # 'msg' is a real WAMP message that our backend WAMP protocol
        # has deserialized -- so now we re-serialize it for whatever
        # the frontend is speaking
        self._frontend.forward_message(msg)

        # ... should we do this explicitly, or just count on the
        # "disconnect" propogating properly
        if False and isinstance(msg, Goodbye) and self._frontend:
            self._frontend.transport.loseConnection()
            self._frontend = None


class FrontendProxyProtocol(WebSocketServerProtocol):
    """
    When a client connects, ProxyWebSocketService creates an instance
    of this to handle the connection so there is one instance of this
    class every client connection.

    Note that this is just a WebSocket connection, not a WAMP one
    .. although we do *some* WAMP handling because we wait for the
    `Hello` before connecting to the backend in order to have the
    realm. Mostly, WAMP messages are shuffled to the backend (see
    `onMessage`) and WAMP messages from the backend (see
    `forward_message`) are written to the front.

    Care must be taken with 'connected-ness': if the frontend
    disconnects (either 'nicely' via a Goodbye or 'not nicely' via
    disconnecting the transport or just dropping) we must inform the
    backend connection (and vice-versa).

    Future enhancements:

     - multiplex over a single backend connection -- for now, there's
       a backend connection per frontend client.

     - might be able to optimize out some de/serialization (although
       the need to 'spy' on some messages might make this
       hard). Another option is to prefer a 'zero work' serialization
       format like CapnProto or flatbuffers (at least for the backend
       connection -- producing less load on that end).
    """

    _backend_transport = None

    def onClose(self, wasClean, code, reason):
        # print("FrontendProxySession.onClose: {} {} {}".format(wasClean, code, reason))
        if self._backend_transport:
            try:
                self._backend_transport.send(
                    Goodbye(
                        reason=u"wamp.close.error",
                        message=reason,
                    )
                )
                self._backend_transport.close()
            except TransportLost:
                self.transport = None

    def onConnect(self, request):
        """
        We have a connection! However, we want to wait until the client
        sends a `Hello` so we know the realm -- thus we cache the
        request. We do protocol-negotiation here though, so that we
        can continue the handshake and thus get the `Hello`.
        """
        # print("FrontendProxyProtocol.onConnect({})".format(request))
        # XXX can we leverage WampWebSocketServerProtocol to do this
        # .. withOUT "being" one of those?

        self._request = request
        # we are using this factory *just* for its knowledge of valid serializers
        fac = WampWebSocketFactory(None, serializers=self.factory._service._serializers)
        # note: we don't have to copy the serializer instance out of
        # "fac" becaue we throw the factory away at the end of this
        # method -- but we DO want a unique serializer instance for
        # every protocol instance (because it keeps statistics)

        self._awaiting_hello = True
        for subprotocol in request.protocols:
            version, serializer_id = parseSubprotocolIdentifier(subprotocol)
            if version == 2:
                s = fac._serializers.get(serializer_id, None)
                if s is not None:
                    self._serializer = s
                    return subprotocol

        # error? or do we want the same the assumptions in onConnect
        # from wampwebsocketserver? (should ideally factor that part
        # out of there and use it directly)
        self._serializer = fac._serializers["json"]
        return "wamp.2.json"

    def onMessage(self, payload, isBinary):
        """
        We've received messages from the frontend client; if we're still
        awaiting the first (`Hello`) message, we treat it specially
        (we wait for the `Hello` so we can find out the realm, thus
        basing our decision as to which backend to connect to on
        that). Otherwise, we just forward everything onwards.
        """
        # XXX THINK: is it possible for more messages to arrive BEFORE
        # _hello_received() finishes processing (and thus we've sent
        # the Hello onwards to the real backend)? I don't believe so:
        # the client won't (is that a MUST NOT, though?) send more
        # until it gets the Welcome, which will only arrive via the
        # real backend...

        # print("onMessage({} bytes, isBinary={})".format(len(payload), isBinary))

        messages = self._serializer.unserialize(payload, isBinary)

        if self._awaiting_hello:
            if len(messages) != 1:
                raise RuntimeError(
                    "While waiting for Hello message, got {} WAMP "
                    "messages (expected exactly one)".format(len(messages))
                )
            hello = messages[0]
            # print("hello: realm='{}' path='{}'".format(hello.realm, self._request.path))
            self._hello_received(self._request, hello)
            self._request = None

        else:
            # XXX it MIGHT be possible to skip the deserialization and
            # re-serialization here if we know the backend is using
            # the same serializer .. right? (or, are there
            # edge-cases?)
            for msg in messages:
                self._backend_transport.send(msg)

    def forward_message(self, msg):
        """
        the backend uses this to tell us to send a message onwards to the
        client
        """
        data, is_binary = self._serializer.serialize(msg)
        self.sendMessage(data, is_binary)

    def _hello_received(self, request, hello_msg):
        """
        Whenever a client connects, we create a (new) client-type
        connection to our configured backend. We actually don't do
        this until the first client message arrives -- a Hello message
        -- so that we can choose a different backend based on the
        realm (and/or any request headers as a future enhancement).

        (In the future, this could be a lazily-created multiplex
        connection -- that exists only while we have >= 1 client
        active)
        """
        self._awaiting_hello = None

        # this import should remain in here so we don't interfere with
        # any reactor selection code
        from twisted.internet import reactor

        # locate and create the backend endpoint for this path + realm
        service = self.factory._service
        backend_config = service._find_backend_for(request, hello_msg.realm)
        backend = _create_transport(0, backend_config)

        # client-factory
        factory = _create_transport_factory(reactor, backend, BackendProxySession)
        factory._frontend = self
        endpoint = _create_transport_endpoint(reactor, backend_config["endpoint"])
        self._transport_d = endpoint.connect(factory)

        def good(proto):
            self._transport_d = None
            # we give the backend a way to get back to us .. perhaps
            # there's another / better way?
            proto._proxy_other_side = self
            self._backend_transport = proto

            # So, we need to wait for the connection to "be open"
            # before we can forward the Hello .. but there's no
            # listener interface on RawSocket :/ so we have to wrap
            # things ... at least we know "it's all Twisted" here (but
            # also: perhaps there SHOULD be a more-general interface
            # for this)

            if not proto.isOpen():
                # XXX rawsocket-specific
                if hasattr(proto, "_on_handshake_complete"):
                    orig = proto._on_handshake_complete

                    def _connected(*args, **kw):
                        x = orig(*args, **kw)
                        self._backend_transport.send(hello_msg)
                        return x
                    proto._on_handshake_complete = _connected

                # XXX websocket-specific
                else:

                    def _connected(arg):
                        self._backend_transport.send(hello_msg)
                        return arg
                    proto.is_open.addCallback(_connected)

                    def _closed(*arg, **kw):
                        self.close()
                    proto.is_closed.addCallback(_closed)
            else:
                self._backend_transport.send(hello_msg)

        def bad(f):
            self._transport_d = None
            print("fail: {}".format(f))
            self._teardown()
        self._transport_d.addCallbacks(good, bad)
        return self._transport_d


class ProxyWebSocketService(RouterWebService):
    """
    For every 'type=websocket-proxy' node configured in a proxy there is one
    of these; it will start FrontendProxySession instances upon every client
    connection.
    """
    _backend_configs = None

    @staticmethod
    def create(transport, path, config, controller):
        websocket_factory = WebSocketServerFactory()
        websocket_factory.protocol = FrontendProxyProtocol

        resource = WebSocketResource(websocket_factory)

        service = ProxyWebSocketService(transport, path, config, resource)
        websocket_factory._service = service

        service._serializers = config.get('serializers', None)

        # a proxy-transport must have at least one backend (fixme: checkconfig)

        for path, path_config in config.get("paths", dict()).items():
            if path_config['type'] != 'websocket-proxy':
                continue
            backends = path_config['backends']
            for backend in backends:
                service.start_backend_for_path(u"/{}".format(path), backend)

        return service

    def start_backend_for_path(self, path, config, details=None):
        if self._backend_configs is None:
            self._backend_configs = dict()

        if path not in self._backend_configs:
            path_backend = list()
            self._backend_configs[path] = path_backend
        else:
            path_backend = self._backend_configs[path]

        # all backends must have unique realms configured. there may
        # be a single default realm (i.e. no "realm" tag at all)
        for existing in path_backend:
            if existing.get('realm', None) == config.get('realm', None):
                # if the realm is None, there isn't one .. which means
                # "default", but there can be only one default (per path)
                if existing.get('realm', None) is None:
                    raise ApplicationError(
                        u"crossbar.error",
                        u"There can be only one default backend for path {}".format(path),
                    )

        # XXX FIXME checkconfig
        path_backend.append(config)

    def _find_backend_for(self, request, realm):
        """
        Returns the backend configuration for the given request + realm. A
        backend with no 'realm' key is a default one.
        """
        # print("_find_backend_for({}, {})".format(request, realm))
        if self._backend_configs is None:
            self._backend_configs = dict()
        default_config = None

        if request.path not in self._backend_configs:
            raise ApplicationError(
                u"crossbar.error",
                "No backends at path '{}'".format(
                    request.path,
                )
            )

        backends = self._backend_configs[request.path]
        for config in backends:
            if realm == config.get("realm", None):
                return config
            if config.get("realm", None) is None:
                default_config = config

        # we didn't find a config for the given realm .. but perhaps
        # there is a default config?
        if default_config is None:
            raise ApplicationError(
                u"crossbar.error",
                "No backend for realm '{}' (and no default backend)".format(
                    realm,
                )
            )
        return default_config


class ProxyController(RouterController):
    WORKER_TYPE = u'proxy'
    WORKER_TITLE = u'WAMP proxy'

    def __init__(self, config=None, reactor=None, personality=None):
        super(ProxyController, self).__init__(
            config=config,
            reactor=reactor,
            personality=personality,
        )

        self._cbdir = config.extra.cbdir
        self._reactor = reactor
        self._transports = dict()
        self._backend_configs = dict()

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
        self.log.info(
            u"start_proxy_transport: transport_id={transport_id}, config={config}",
            transport_id=transport_id,
            config=config,
        )

        if config['type'] != "web":
            raise RuntimeError("Only know about 'web' type services")

        # we remove "websocket-proxy" items from this config; only
        # this class knows about those, but we want the base-class to
        # start all other services

        def filter_paths(paths):
            """
            remove any 'websocket-proxy' type configs
            """
            return {
                k: v
                for k, v in paths.items()
                if v['type'] != "websocket-proxy"
            }

        config_prime = dict()
        for k, v in config.items():
            if k == 'paths':
                config_prime[k] = filter_paths(v)
            else:
                config_prime[k] = v

        yield self.start_router_transport(transport_id, config_prime, create_paths=False)

        for path, path_config in config['paths'].items():
            if path_config['type'] == "websocket-proxy":
                # XXX okay this is where we "actually" want to start a
                # proxy worker .. which just shovels bytes to the
                # "backend". Are we assured exactly one backend? (At
                # this point, we have to assume yes I think)
                transport = self.transports[transport_id]  # should always exist now .. right?
                webservice = yield maybeDeferred(
                    ProxyWebSocketService.create, transport, path, config, self
                )
                transport.root[path] = webservice
            else:
                yield self.start_web_transport_service(
                    transport_id,
                    path,
                    path_config
                )

    @wamp.register(None)
    @inlineCallbacks
    def stop_proxy_transport(self, name, details=None):
        if name not in self._transports:
            raise ApplicationError(
                u"crossbar.error.worker_not_running",
                u"No such worker '{}'".format(name),
            )
        yield self._transports[name].port.stopListening()
        del self._transports[name]

    @wamp.register(None)
    def start_proxy_backend(self, transport_id, name, options, details=None):
        self.log.info(
            u"start_proxy_backend '{transport_id}': {name}: {options}",
            transport_id=transport_id,
            name=name,
            options=options,
        )

        if transport_id not in self._transports:
            raise ApplicationError(
                u"crossbar.error",
                u"start_proxy_backend: no transport '{}'".format(transport_id),
            )

        return self._transport[transport_id].start_backend(name, options)
