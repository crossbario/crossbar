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

import os
import traceback
import crossbar

from autobahn.twisted import websocket
from autobahn.twisted import rawsocket
from autobahn.websocket.compress import PerMessageDeflateOffer, PerMessageDeflateOfferAccept

from txaio import make_logger

from crossbar.router.cookiestore import CookieStoreMemoryBacked, CookieStoreFileBacked

log = make_logger()

__all__ = (
    'WampWebSocketServerFactory',
    'WampRawSocketServerFactory',
    'WampWebSocketServerProtocol',
    'WampRawSocketServerProtocol',
    'WampWebSocketClientFactory',
    'WampRawSocketClientFactory',
    'WampWebSocketClientProtocol',
    'WampRawSocketClientProtocol',
)


def set_websocket_options(factory, options):
    """
    Set WebSocket options on a WebSocket or WAMP-WebSocket factory.

    :param factory: The WebSocket or WAMP-WebSocket factory to set options on.
    :type factory:  Instance of :class:`autobahn.twisted.websocket.WampWebSocketServerFactory`
                    or :class:`autobahn.twisted.websocket.WebSocketServerFactory`.
    :param options: Options from Crossbar.io transport configuration.
    :type options: dict
    """
    c = options

    # we need to pop() this, since it is not a WebSocket option to be consumed
    # by setProtocolOption(), but will get used in onConnect() ("STRICT_PROTOCOL_NEGOTIATION")
    #
    factory._requireWebSocketSubprotocol = c.pop("require_websocket_subprotocol", True)

    versions = []
    if c.get("enable_hybi10", True):
        versions.append(8)
    if c.get("enable_rfc6455", True):
        versions.append(13)

    # FIXME: enforce!!
    #
    # self.connectionCap = c.get("max_connections")

    # convert to seconds
    #
    openHandshakeTimeout = float(c.get("open_handshake_timeout", 0))
    if openHandshakeTimeout:
        openHandshakeTimeout = openHandshakeTimeout / 1000.

    closeHandshakeTimeout = float(c.get("close_handshake_timeout", 0))
    if closeHandshakeTimeout:
        closeHandshakeTimeout = closeHandshakeTimeout / 1000.

    autoPingInterval = None
    if "auto_ping_interval" in c:
        autoPingInterval = float(c["auto_ping_interval"]) / 1000.

    autoPingTimeout = None
    if "auto_ping_timeout" in c:
        autoPingTimeout = float(c["auto_ping_timeout"]) / 1000.

    # WebSocket compression
    #
    per_msg_compression = lambda _: None  # noqa
    if 'compression' in c:

        # permessage-deflate
        #
        if 'deflate' in c['compression']:

            log.debug("enabling WebSocket compression (permessage-deflate)")

            params = c['compression']['deflate']

            request_no_context_takeover = params.get('request_no_context_takeover', False)
            request_max_window_bits = params.get('request_max_window_bits', 0)
            no_context_takeover = params.get('no_context_takeover', None)
            window_bits = params.get('max_window_bits', None)
            mem_level = params.get('memory_level', None)

            def accept(offers):
                for offer in offers:
                    if isinstance(offer, PerMessageDeflateOffer):
                        if (request_max_window_bits == 0 or offer.accept_max_window_bits) and \
                           (not request_no_context_takeover or offer.accept_no_context_takeover):
                            return PerMessageDeflateOfferAccept(offer,
                                                                request_max_window_bits=request_max_window_bits,
                                                                request_no_context_takeover=request_no_context_takeover,
                                                                no_context_takeover=no_context_takeover,
                                                                window_bits=window_bits,
                                                                mem_level=mem_level)
            per_msg_compression = accept

    factory.setProtocolOptions(
        versions=versions,
        webStatus=c.get("enable_webstatus", True),
        utf8validateIncoming=c.get("validate_utf8", True),
        maskServerFrames=c.get("mask_server_frames", False),
        requireMaskedClientFrames=c.get("require_masked_client_frames", True),
        applyMask=c.get("apply_mask", True),
        maxFramePayloadSize=c.get("max_frame_size", 0),
        maxMessagePayloadSize=c.get("max_message_size", 0),
        autoFragmentSize=c.get("auto_fragment_size", 0),
        failByDrop=c.get("fail_by_drop", False),
        echoCloseCodeReason=c.get("echo_close_codereason", False),
        openHandshakeTimeout=openHandshakeTimeout,
        closeHandshakeTimeout=closeHandshakeTimeout,
        tcpNoDelay=c.get("tcp_nodelay", True),
        autoPingInterval=autoPingInterval,
        autoPingTimeout=autoPingTimeout,
        autoPingSize=c.get("auto_ping_size", None),
        serveFlashSocketPolicy=c.get("enable_flash_policy", None),
        flashSocketPolicy=c.get("flash_policy", None),
        allowedOrigins=c.get("allowed_origins", ["*"]),
        allowNullOrigin=bool(c.get("allow_null_origin", True)),
        perMessageCompressionAccept=per_msg_compression,
    )


class WampWebSocketServerProtocol(websocket.WampWebSocketServerProtocol):

    """
    Crossbar.io WAMP-over-WebSocket server protocol.
    """
    log = make_logger()

    def __init__(self):
        super(WampWebSocketServerProtocol, self).__init__()
        self._cbtid = None

    def onConnect(self, request):

        if self.factory.debug_traffic:
            from twisted.internet import reactor

            def print_traffic():
                self.log.info(
                    "Traffic {peer}: {wire_in} / {wire_out} in / out bytes - {ws_in} / {ws_out} in / out msgs",
                    peer=self.peer,
                    wire_in=self.trafficStats.incomingOctetsWireLevel,
                    wire_out=self.trafficStats.outgoingOctetsWireLevel,
                    ws_in=self.trafficStats.incomingWebSocketMessages,
                    ws_out=self.trafficStats.outgoingWebSocketMessages,
                )
                reactor.callLater(1, print_traffic)

            print_traffic()

        # if WebSocket client did not set WS subprotocol, assume "wamp.2.json"
        #
        self.STRICT_PROTOCOL_NEGOTIATION = self.factory._requireWebSocketSubprotocol

        # handle WebSocket opening handshake
        #
        protocol, headers = websocket.WampWebSocketServerProtocol.onConnect(self, request)

        try:

            self._origin = request.origin

            # transport-level WMAP authentication info
            #
            self._authid = None
            self._authrole = None
            self._authrealm = None
            self._authmethod = None
            self._authextra = None
            self._authprovider = None

            # cookie tracking and cookie-based authentication
            #
            self._cbtid = None

            if self.factory._cookiestore:

                # try to parse an already set cookie from HTTP request headers
                self._cbtid = self.factory._cookiestore.parse(request.headers)

                # if no cookie is set, create a new one ..
                if self._cbtid is None:

                    self._cbtid, headers['Set-Cookie'] = self.factory._cookiestore.create()

                    self.log.debug("Setting new cookie: {cookie}",
                                   cookie=headers['Set-Cookie'])
                else:
                    self.log.debug("Cookie already set")

                # add this WebSocket connection to the set of connections
                # associated with the same cookie
                self.factory._cookiestore.addProto(self._cbtid, self)

                self.log.debug("Cookie tracking enabled on WebSocket connection {ws}", ws=self)

                # if cookie-based authentication is enabled, set auth info from cookie store
                #
                if 'auth' in self.factory._config and 'cookie' in self.factory._config['auth']:

                    self._authid, self._authrole, self._authmethod, self._authrealm, self._authextra = self.factory._cookiestore.getAuth(self._cbtid)

                    if self._authid:
                        # there is a cookie set, and the cookie was previously successfully authenticated,
                        # so immediately authenticate the client using that information
                        self._authprovider = u'cookie'
                        self.log.debug("Authenticated client via cookie {cookiename}={cbtid} as authid={authid}, authrole={authrole}, authmethod={authmethod}, authrealm={authrealm}",
                                       cookiename=self.factory._cookiestore._cookie_id_field, cbtid=self._cbtid, authid=self._authid, authrole=self._authrole, authmethod=self._authmethod, authrealm=self._authrealm)
                    else:
                        # there is a cookie set, but the cookie wasn't authenticated yet using a different auth method
                        self.log.debug("Cookie-based authentication enabled, but cookie isn't authenticated yet")
                else:
                    self.log.debug("Cookie-based authentication disabled")
            else:
                self.log.debug("Cookie tracking disabled on WebSocket connection {ws}", ws=self)

            # remember transport level info for later forwarding in
            # WAMP meta event "wamp.session.on_join"
            #
            self._transport_info = {
                u'type': 'websocket',
                u'protocol': protocol,
                u'peer': self.peer,

                # all HTTP headers as received by the WebSocket client
                u'http_headers_received': request.headers,

                # only customer user headers (such as cookie)
                u'http_headers_sent': headers,

                # all HTTP response lines sent (verbatim, in order as sent)
                # this will get filled in onOpen() from the HTTP response
                # data that will be stored by AutobahnPython at the WebSocket
                # protocol level (WebSocketServerProtocol)
                # u'http_response_lines': None,

                # WebSocket extensions in use .. will be filled in onOpen() - see below
                u'websocket_extensions_in_use': None,

                # Crossbar.io tracking ID (for cookie tracking)
                u'cbtid': self._cbtid
            }

            # accept the WebSocket connection, speaking subprotocol `protocol`
            # and setting HTTP headers `headers`
            #
            return (protocol, headers)

        except Exception:
            traceback.print_exc()

    def onOpen(self):
        if False:
            # this is little bit silly, we parse the complete response data into lines again
            http_response_lines = []
            for line in self.http_response_data.split('\r\n'):
                line = line.strip()
                if line:
                    http_response_lines.append(line)
            self._transport_info[u'http_response_lines'] = http_response_lines

        # note the WebSocket extensions negotiated
        self._transport_info[u'websocket_extensions_in_use'] = [e.__json__() for e in self.websocket_extensions_in_use]

        return super(WampWebSocketServerProtocol, self).onOpen()

    def sendServerStatus(self, redirectUrl=None, redirectAfter=0):
        """
        Used to send out server status/version upon receiving a HTTP/GET without
        upgrade to WebSocket header (and option serverStatus is True).
        """
        try:
            page = self.factory._templates.get_template('cb_ws_status.html')
            self.sendHtml(page.render(redirectUrl=redirectUrl,
                                      redirectAfter=redirectAfter,
                                      cbVersion=crossbar.__version__,
                                      wsUri=self.factory.url,
                                      peer=self.peer,
                                      workerPid=os.getpid()))
        except Exception:
            self.log.failure("Error rendering WebSocket status page template: {log_failure.value}")

    def onClose(self, wasClean, code, reason):
        super(WampWebSocketServerProtocol, self).onClose(wasClean, code, reason)

        # remove this WebSocket connection from the set of connections
        # associated with the same cookie
        if self._cbtid:
            self.factory._cookiestore.dropProto(self._cbtid, self)


class WampWebSocketServerFactory(websocket.WampWebSocketServerFactory):

    """
    Crossbar.io WAMP-over-WebSocket server factory.
    """

    showServerVersion = False
    protocol = WampWebSocketServerProtocol
    log = make_logger()

    def __init__(self, factory, cbdir, config, templates):
        """
        Ctor.

        :param factory: WAMP session factory.
        :type factory: An instance of ..
        :param cbdir: The Crossbar.io node directory.
        :type cbdir: str
        :param config: Crossbar transport configuration.
        :type config: dict
        """
        self.debug_traffic = config.get('debug_traffic', False)

        options = config.get('options', {})

        self.showServerVersion = options.get('show_server_version', self.showServerVersion)
        if self.showServerVersion:
            server = "Crossbar/{}".format(crossbar.__version__)
        else:
            server = "Crossbar"
        externalPort = options.get('external_port', None)

        # explicit list of WAMP serializers
        #
        if 'serializers' in config:
            serializers = []
            sers = set(config['serializers'])

            if u'cbor' in sers:
                # try CBOR WAMP serializer
                try:
                    from autobahn.wamp.serializer import CBORSerializer
                    serializers.append(CBORSerializer(batched=True))
                    serializers.append(CBORSerializer())
                except ImportError:
                    self.log.warn("Warning: could not load WAMP-CBOR serializer")
                else:
                    sers.discard(u'cbor')

            if u'msgpack' in sers:
                # try MsgPack WAMP serializer
                try:
                    from autobahn.wamp.serializer import MsgPackSerializer
                    serializers.append(MsgPackSerializer(batched=True))
                    serializers.append(MsgPackSerializer())
                except ImportError:
                    self.log.warn("Warning: could not load WAMP-MsgPack serializer")
                else:
                    sers.discard('msgpack')

            if u'ubjson' in sers:
                # try UBJSON WAMP serializer
                try:
                    from autobahn.wamp.serializer import UBJSONSerializer
                    serializers.append(UBJSONSerializer(batched=True))
                    serializers.append(UBJSONSerializer())
                except ImportError:
                    self.log.warn("Warning: could not load WAMP-UBJSON serializer")
                else:
                    sers.discard(u'ubjson')

            if u'json' in sers:
                # try JSON WAMP serializer
                try:
                    from autobahn.wamp.serializer import JsonSerializer
                    serializers.append(JsonSerializer(batched=True))
                    serializers.append(JsonSerializer())
                except ImportError:
                    self.log.warn("Warning: could not load WAMP-JSON serializer")
                else:
                    sers.discard(u'json')

            if not serializers:
                raise Exception("no valid WAMP serializers specified")

            if len(sers) > 0:
                raise Exception("invalid WAMP serializers specified (the following were unprocessed) {}".format(sers))

        else:
            serializers = None

        websocket.WampWebSocketServerFactory.__init__(self,
                                                      factory,
                                                      serializers=serializers,
                                                      url=config.get('url', None),
                                                      server=server,
                                                      externalPort=externalPort)

        # Crossbar.io node directory
        self._cbdir = cbdir

        # transport configuration
        self._config = config

        # Jinja2 templates for 404 etc
        self._templates = templates

        # cookie tracking
        if 'cookie' in config:
            cookie_store_type = config['cookie']['store']['type']

            # ephemeral, memory-backed cookie store
            if cookie_store_type == 'memory':
                self._cookiestore = CookieStoreMemoryBacked(config['cookie'])
                self.log.info("Memory-backed cookie store active.")

            # persistent, file-backed cookie store
            elif cookie_store_type == 'file':
                cookie_store_file = os.path.abspath(os.path.join(self._cbdir, config['cookie']['store']['filename']))
                self._cookiestore = CookieStoreFileBacked(cookie_store_file, config['cookie'])
                self.log.info("File-backed cookie store active {cookie_store_file}", cookie_store_file=cookie_store_file)

            else:
                # should not arrive here as the config should have been checked before
                raise Exception("logic error")
        else:
            self._cookiestore = None

        # set WebSocket options
        set_websocket_options(self, options)


class WampRawSocketServerProtocol(rawsocket.WampRawSocketServerProtocol):

    """
    Crossbar.io WAMP-over-RawSocket server protocol.
    """
    log = make_logger()

    def connectionMade(self):
        rawsocket.WampRawSocketServerProtocol.connectionMade(self)

        # transport authentication
        #
        self._authid = None
        self._authrole = None
        self._authrealm = None
        self._authmethod = None
        self._authprovider = None
        self._authextra = None

        # cookie tracking ID
        #
        self._cbtid = None

        # remember transport level info for later forwarding in
        # WAMP meta event "wamp.session.on_join"
        #
        self._transport_info = {
            u'type': 'rawsocket',
            u'protocol': None,
            u'peer': self.peer
        }

    def _on_handshake_complete(self):
        self._transport_info[u'protocol'] = u'wamp.2.{}'.format(self._serializer.SERIALIZER_ID)
        return rawsocket.WampRawSocketServerProtocol._on_handshake_complete(self)

    def lengthLimitExceeded(self, length):
        self.log.error("failing RawSocket connection - message length exceeded: message was {len} bytes, but current maximum is {maxlen} bytes",
                       len=length, maxlen=self.MAX_LENGTH)
        self.transport.loseConnection()


class WampRawSocketServerFactory(rawsocket.WampRawSocketServerFactory):

    """
    Crossbar.io WAMP-over-RawSocket server factory.
    """

    protocol = WampRawSocketServerProtocol
    log = make_logger()

    def __init__(self, factory, config):

        # remember transport configuration
        #
        self._config = config

        # explicit list of WAMP serializers
        #
        if u'serializers' in config:
            serializers = []
            sers = set(config['serializers'])

            if u'cbor' in sers:
                # try CBOR WAMP serializer
                try:
                    from autobahn.wamp.serializer import CBORSerializer
                    serializers.append(CBORSerializer())
                except ImportError:
                    self.log.warn("Warning: could not load WAMP-CBOR serializer")
                else:
                    sers.discard(u'cbor')

            if u'msgpack' in sers:
                # try MsgPack WAMP serializer
                try:
                    from autobahn.wamp.serializer import MsgPackSerializer
                    serializer = MsgPackSerializer()
                    serializer._serializer.ENABLE_V5 = False  # FIXME
                    serializers.append(serializer)
                except ImportError:
                    self.log.warn("Warning: could not load WAMP-MsgPack serializer")
                else:
                    sers.discard(u'msgpack')

            if u'ubjson' in sers:
                # try UBJSON WAMP serializer
                try:
                    from autobahn.wamp.serializer import UBJSONSerializer
                    serializers.append(UBJSONSerializer(batched=True))
                    serializers.append(UBJSONSerializer())
                except ImportError:
                    self.log.warn("Warning: could not load WAMP-UBJSON serializer")
                else:
                    sers.discard(u'ubjson')

            if u'json' in sers:
                # try JSON WAMP serializer
                try:
                    from autobahn.wamp.serializer import JsonSerializer
                    serializers.append(JsonSerializer())
                except ImportError:
                    self.log.warn("Warning: could not load WAMP-JSON serializer")
                else:
                    sers.discard(u'json')

            if not serializers:
                raise Exception("no valid WAMP serializers specified")

            if len(sers) > 0:
                raise Exception("invalid WAMP serializers specified (the following were unprocessed) {}".format(sers))

        else:
            serializers = None

        # Maximum message size
        #
        self._max_message_size = config.get('max_message_size', 128 * 1024)  # default is 128kB

        rawsocket.WampRawSocketServerFactory.__init__(self, factory, serializers)

        self.log.debug("RawSocket transport factory created using {serializers} serializers, max. message size {maxsize}",
                       serializers=serializers, maxsize=self._max_message_size)

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        p.MAX_LENGTH = self._max_message_size
        return p


class WampWebSocketClientProtocol(websocket.WampWebSocketClientProtocol):

    """
    Crossbar.io WAMP-over-WebSocket client protocol.
    """


class WampWebSocketClientFactory(websocket.WampWebSocketClientFactory):

    """
    Crossbar.io WAMP-over-WebSocket client factory.
    """

    protocol = WampWebSocketClientProtocol

    def buildProtocol(self, addr):
        self._proto = websocket.WampWebSocketClientFactory.buildProtocol(self, addr)
        return self._proto


class WampRawSocketClientProtocol(rawsocket.WampRawSocketClientProtocol):

    """
    Crossbar.io WAMP-over-RawSocket client protocol.
    """


class WampRawSocketClientFactory(rawsocket.WampRawSocketClientFactory):

    """
    Crossbar.io WAMP-over-RawSocket client factory.
    """

    protocol = WampRawSocketClientProtocol

    def __init__(self, factory, config):

        # transport configuration
        self._config = config

        # WAMP serializer
        #
        serid = config.get(u'serializer', u'json')

        if serid == u'json':
            # try JSON WAMP serializer
            try:
                from autobahn.wamp.serializer import JsonSerializer
                serializer = JsonSerializer()
            except ImportError:
                raise Exception("could not load WAMP-JSON serializer")

        elif serid == u'msgpack':
            # try MessagePack WAMP serializer
            try:
                from autobahn.wamp.serializer import MsgPackSerializer
                serializer = MsgPackSerializer()
                serializer._serializer.ENABLE_V5 = False  # FIXME
            except ImportError:
                raise Exception("could not load WAMP-MessagePack serializer")

        elif serid == u'cbor':
            # try CBOR WAMP serializer
            try:
                from autobahn.wamp.serializer import CBORSerializer
                serializer = CBORSerializer()
            except ImportError:
                raise Exception("could not load WAMP-CBOR serializer")

        else:
            raise Exception("invalid WAMP serializer '{}'".format(serid))

        rawsocket.WampRawSocketClientFactory.__init__(self, factory, serializer)
