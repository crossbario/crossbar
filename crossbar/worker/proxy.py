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
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import Session
from autobahn.twisted.resource import WebSocketResource
from autobahn.twisted.websocket import WampWebSocketServerProtocol

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
        # instance of Frontend
        self._frontend = transport._proxy_other_side

    def onMessage(self, msg):
        # 'msg' is a real WAMP message that our backend WAMP protocol
        # has deserialized -- so now we re-serialize it for whatever
        # the frontend is speaking
        self._frontend.send(msg)

        # XXX if they're both speaking the same serializer, can we
        # avoid deserializing here and just pass along the bytes
        # .. somehow? (We could monkey-patch the transports so they
        # bypass the deserialize .. but, yuck)


class FrontendProxySession(Session):
    """
    This is a single WAMP session from a client.

    There is one of these for every client connection. This will take
    incoming messages and pass them to the backend, and take backend
    messages and forward them to the client.  (In the future, we could
    multiplex over a single backend connection -- for now, there's a
    backend connection per frontend client).

    XXX serializer translation?

    XXX before ^ just negotiate with the frontend to have the same
    serializer as the backend.
    """

    def onOpen(self, transport):
        # instance of RawSocketProtocol or WebSocketProtocol
        self._backend = transport._session

    def onMessage(self, msg):
        # print("FrontendProxySession.onMessage(): {}".format(msg))
        # 'msg' is a real WAMP message that our frontend WAMP protocol
        # has deserialized -- so now we re-serialize it for whatever
        # the backend is speaking
        self._backend.send(msg)

        # XXX if they're both speaking the same serializer, can we
        # avoid deserializing here and just pass along the bytes
        # .. somehow?


class Frontend(WampWebSocketServerProtocol):
    """
    The WebSocket protocol instance that talks to the real client that
    has contacted the proxy.
    """

    def onConnect(self, request):
        # print("frontend: onConnect: {}".format(request))

        # whenever a client connects, we create a (new) client-type
        # connection to our configured backend. (In the future, this
        # could be a lazily-created multiplex connection -- that
        # exists only while we have >= 1 client active)

        from twisted.internet import reactor
        from autobahn.wamp.component import _create_transport
        from autobahn.twisted.component import _create_transport_factory, _create_transport_endpoint

        backend_config = {
            "type": "rawsocket",
            "endpoint": {
                "type": "unix",
                "path": "router.sock"
            },
            "url": "rs://localhost",
            "serializer": "cbor"
        }
        backend = _create_transport(0, backend_config)
        # client-factory
        factory = _create_transport_factory(reactor, backend, BackendProxySession)
        endpoint = _create_transport_endpoint(reactor, backend_config["endpoint"])
        d = endpoint.connect(factory)

        def good(proto):
            # we give the backend a way to get back to us .. perhaps
            # there's another / better way?
            proto._proxy_other_side = self
            self._backend_transport = proto
            # print("Frontend.onConnect(): request protocols: {}".format(request.protocols))
            x = super(Frontend, self).onConnect(request)
            # print("returning: {}".format(x))
            return x

        def bad(f):
            print("fail: {}".format(f))
            self._teardown()
        d.addCallbacks(good, bad)
        return d

    def onMessage(self, payload, isBinary):
        # print("Frontend.onMessage: {} bytes isBinary={}".format(len(payload), isBinary))
        # self._serializer is set by parent in onConnect()
        # (i.e. during sub-protocol negotiation)
        messages = self._serializer.unserialize(payload, isBinary)
        for msg in messages:
            self._backend_transport.send(msg)

        # if we knew, for example, that we were using the same
        # serializer as the backend .. then we could do something like
        # this (e.g. AND we know the backend is raw-socket):
        if False:
            assert isBinary
            import struct
            self._backend_transport.transport.write(struct.pack("!I", len(payload)))
            self._backend_transport.transport.write(payload)

    def _teardown(self):
        print("_teardown")
        # we need to disconnect from the backend .. but practically
        # speaking right now this is only called when we fail to
        # connect to the backend...


class ProxyWebSocketService(RouterWebService):
    """
    For every 'type=websocket' node configured in a proxy there is one
    of these; it will start FrontendProxySession instances upon every client
    connection
    """

    @staticmethod
    def create(transport, path, config, controller):
        # this is the crossbar-specific wamp-websocket-server
        #from crossbar.router.protocol import WampWebSocketServerFactory
        from autobahn.twisted.websocket import WampWebSocketServerFactory
        websocket_factory = WampWebSocketServerFactory(FrontendProxySession)
        websocket_factory.protocol = Frontend

        resource = WebSocketResource(websocket_factory)

        return ProxyWebSocketService(transport, path, config, resource)


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

        # XXX remove "websocket" things from this config??
        x = self.start_router_transport(transport_id, config, create_paths=False)
        print("started: {}".format(x))

        for path, path_config in config['paths'].items():
            if path_config['type'] == "websocket":
                # XXX okay this is where we "actually" want to start a
                # proxy worker .. which just shovels bytes to the
                # "backend". Are we assured exactly one backend? (At
                # this point, we have to assume yes I think)
                transport = self.transports[transport_id]  # should always exist now .. right?
                webservice = yield maybeDeferred(ProxyWebSocketService.create, transport, path, config, self)
                transport.root[path] = webservice
            else:
                x = yield self.start_web_transport_service(
                    transport_id,
                    path,
                    path_config
                )
                print("started: {}".format(x))

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
    def start_proxy_backend(self, name, options, details=None):
        self.log.info(
            u"start_proxy_backend {name}: {options}",
            name=name,
            options=options,
        )
        if len(self._backend_configs) > 0:
            raise ApplicationError(
                u"crossbarfabric.error",
                u"Can only have a single backend currently",
            )

        # XXX FIXME checkconfig

        self._backend_configs[name] = options
