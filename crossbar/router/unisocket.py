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

from __future__ import absolute_import

import six
from six.moves.urllib import parse as urlparse

import txaio
txaio.use_twisted()  # noqa

from twisted.internet.protocol import Factory, Protocol
from twisted.internet.interfaces import IProtocolNegotiationFactory
from zope.interface import implementer


__all__ = (
    'UniSocketServerProtocol',
    'UniSocketServerFactory',
)


class UniSocketServerProtocol(Protocol):
    """
    """

    log = txaio.make_logger()

    def __init__(self, factory, addr):
        self._factory = factory
        self._addr = addr
        self._proto = None
        self._data = b''

    def dataReceived(self, data):

        if self._proto:
            # we already determined the actual protocol to speak. just forward received data
            self._proto.dataReceived(data)
        else:
            if data[0:1] == b'\x7F':
                # switch to RawSocket ..
                if not self._factory._rawsocket_factory:
                    self.log.warn('client wants to talk RawSocket, but we have no factory configured for that')
                    self.transport.loseConnection()
                else:
                    self.log.debug('switching to RawSocket')
                    self._proto = self._factory._rawsocket_factory.buildProtocol(self._addr)
                    self._proto.transport = self.transport
                    self._proto.connectionMade()
                    self._proto.dataReceived(data)
            elif data[0:1] == b'\x10':
                # switch to MQTT
                if not self._factory._mqtt_factory:
                    self.log.warn('client wants to talk MQTT, but we have no factory configured for that')
                    self.transport.loseConnection()
                else:
                    self.log.debug('switching to MQTT')
                    self._proto = self._factory._mqtt_factory.buildProtocol(self._addr)
                    self._proto.transport = self.transport
                    self._proto.connectionMade(True)
                    self._proto.dataReceived(data)
            else:
                # switch to HTTP, further subswitching to WebSocket (from Autobahn, like a WebSocketServerFactory)
                # or Web (from Twisted Web, like a Site). the subswitching is based on HTTP Request-URI.
                self._data += data

                request_line_end = self._data.find(b'\x0d\x0a')
                request_line = self._data[:request_line_end]

                # HTTP request line, eg 'GET /ws HTTP/1.1'
                rl = request_line.split()

                # we only check for number of parts in HTTP request line, not for HTTP method
                # nor HTTP version - checking these things is the job of the protocol instance
                # we switch to (as only the specific protocol knows what is allowed for the other
                # parts). iow, we solely switch based on the HTTP Request-URI.
                if len(rl) != 3:
                    self.log.warn('received invalid HTTP request line for HTTP protocol subswitch: "{request_line}"', request_line=request_line)
                    self.transport.loseConnection()
                    return

                request_uri = rl[1].strip()

                # support IRIs: "All non-ASCII code points in the IRI should next be encoded as UTF-8,
                # and the resulting bytes percent-encoded, to produce a valid URI."
                if six.PY3:
                    request_uri = urlparse.unquote(request_uri.decode('ascii'))
                else:
                    request_uri = urlparse.unquote(request_uri).decode('utf8')

                # the first component for the URI requested, eg for "/ws/foo/bar", it'll be "ws", and "/"
                # will map to ""
                request_uri_first_component = [x.strip() for x in request_uri.split(u'/') if x.strip() != u'']
                if len(request_uri_first_component) > 0:
                    request_uri_first_component = request_uri_first_component[0]
                else:
                    request_uri_first_component = u''

                self.log.debug('switching to HTTP on Request-URI {request_uri}, mapping part {request_uri_first_component}', request_uri=request_uri, request_uri_first_component=request_uri_first_component)

                # _first_ try to find a matching URL prefix in the WebSocket factory map ..
                if self._factory._websocket_factory_map:
                    for uri_component, websocket_factory in self._factory._websocket_factory_map.items():
                        if request_uri_first_component == uri_component:
                            self._proto = websocket_factory.buildProtocol(self._addr)
                            self.log.debug('found and build websocket protocol for request URI {request_uri}, mapping part {request_uri_first_component}', request_uri=request_uri, request_uri_first_component=request_uri_first_component)
                            break
                    self.log.debug('no mapping found for request URI {request_uri}, trying to map part {request_uri_first_component}', request_uri=request_uri, request_uri_first_component=request_uri_first_component)

                if not self._proto:
                    # mmh, still no protocol, so there has to be a Twisted Web (a "Site") factory
                    # hooked on this URL
                    if self._factory._web_factory:

                        self.log.debug('switching to HTTP/Web on Request-URI {request_uri}', request_uri=request_uri)
                        self._proto = self._factory._web_factory.buildProtocol(self._addr)

                        # watch out: this is definitely a hack!
                        self._proto._channel.transport = self.transport
                    else:
                        self.log.warn('client wants to talk HTTP/Web, but we have no factory configured for that')
                        self.transport.loseConnection()
                        return
                else:
                    # we've got a protocol instance already created from a WebSocket factory. cool.

                    self.log.debug('switching to HTTP/WebSocket on Request-URI {request_uri}', request_uri=request_uri)

                    # is this a hack? or am I allowed to do this?
                    self._proto.transport = self.transport

                # fake connection, forward data received beginning from the very first octet. this allows
                # to use the protocol being switched to in a standard, unswitched context without modification
                self._proto.connectionMade()
                self._proto.dataReceived(self._data)
                self._data = None

    def connectionLost(self, reason):
        if self._proto:
            self._proto.connectionLost(reason)


@implementer(IProtocolNegotiationFactory)
class UniSocketServerFactory(Factory):
    """
    """

    noisy = False

    def __init__(self, web_factory=None, websocket_factory_map=None, rawsocket_factory=None, mqtt_factory=None):
        """
        """
        self._web_factory = web_factory
        self._websocket_factory_map = websocket_factory_map
        self._rawsocket_factory = rawsocket_factory
        self._mqtt_factory = mqtt_factory

    def buildProtocol(self, addr):
        proto = UniSocketServerProtocol(self, addr)
        return proto

    # IProtocolNegotiationFactory
    def acceptableProtocols(self):
        """
        Protocols this server can speak.
        """
        if self._web_factory:
            return self._web_factory.acceptableProtocols()
        return None
