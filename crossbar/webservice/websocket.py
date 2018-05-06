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


from autobahn.twisted.resource import WebSocketResource

from crossbar.router.protocol import WampWebSocketServerFactory, WebSocketReverseProxyServerFactory
from crossbar.webservice.base import RouterWebService


class RouterWebServiceWebSocket(RouterWebService):
    """
    WAMP-WebSocket service.
    """

    @staticmethod
    def create(transport, path, config):
        websocket_factory = WampWebSocketServerFactory(transport._worker._router_session_factory,
                                                       transport.cbdir,
                                                       config,
                                                       transport.templates)

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
