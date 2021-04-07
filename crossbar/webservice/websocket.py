#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.twisted.resource import WebSocketResource

from crossbar.router.protocol import WampWebSocketServerFactory, WebSocketReverseProxyServerFactory
from crossbar.webservice.base import RouterWebService


class RouterWebServiceWebSocket(RouterWebService):
    """
    WAMP-WebSocket service.
    """
    @staticmethod
    def create(transport, path, config):
        websocket_factory = WampWebSocketServerFactory(transport._worker._router_session_factory, transport.cbdir,
                                                       config, transport.templates)

        # FIXME: Site.start/stopFactory should start/stop factories wrapped as Resources
        websocket_factory.startFactory()

        resource = WebSocketResource(websocket_factory)

        return RouterWebServiceWebSocket(transport, path, config, resource)


class RouterWebServiceWebSocketReverseProxy(RouterWebService):
    """
    Reverse WebSocket service.
    """
    @staticmethod
    def create(transport, path, config):
        ws_rproxy_factory = WebSocketReverseProxyServerFactory(transport._worker._reactor, config)
        ws_rproxy_factory.startFactory()
        resource = WebSocketResource(ws_rproxy_factory)
        return RouterWebServiceWebSocketReverseProxy(transport, path, config, resource)
