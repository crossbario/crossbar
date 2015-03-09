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

from __future__ import absolute_import

import os
import traceback

from twisted.python import log

from autobahn.twisted.websocket import WampWebSocketServerProtocol, \
    WampWebSocketServerFactory, \
    WampWebSocketClientProtocol, \
    WampWebSocketClientFactory

from autobahn.twisted.rawsocket import WampRawSocketServerProtocol, \
    WampRawSocketServerFactory, \
    WampRawSocketClientProtocol, \
    WampRawSocketClientFactory

from autobahn.websocket.compress import *  # noqa

import crossbar

from crossbar.router.cookiestore import CookieStore, PersistentCookieStore

__all__ = (
    'CrossbarWampWebSocketServerProtocol',
    'CrossbarWampWebSocketServerFactory',
    'CrossbarWampRawSocketServerProtocol',
    'CrossbarWampRawSocketServerFactory',
    'CrossbarWampRawSocketClientProtocol',
    'CrossbarWampRawSocketClientFactory',
    'CrossbarWampWebSocketClientProtocol',
    'CrossbarWampWebSocketClientFactory',
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
    if c.get("enable_hixie76", True):
        versions.append(0)
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

    factory.setProtocolOptions(versions=versions,
                               allowHixie76=c.get("enable_hixie76", True),
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
                               allowedOrigins=c.get("allowed_origins", ["*"]))

    # WebSocket compression
    #
    factory.setProtocolOptions(perMessageCompressionAccept=lambda _: None)
    if 'compression' in c:

        # permessage-deflate
        #
        if 'deflate' in c['compression']:

            log.msg("enabling WebSocket compression (permessage-deflate)")

            params = c['compression']['deflate']

            requestNoContextTakeover = params.get('request_no_context_takeover', False)
            requestMaxWindowBits = params.get('request_max_window_bits', 0)
            noContextTakeover = params.get('no_context_takeover', None)
            windowBits = params.get('max_window_bits', None)
            memLevel = params.get('memory_level', None)

            def accept(offers):
                for offer in offers:
                    if isinstance(offer, PerMessageDeflateOffer):
                        if (requestMaxWindowBits == 0 or offer.acceptMaxWindowBits) and \
                           (not requestNoContextTakeover or offer.acceptNoContextTakeover):
                            return PerMessageDeflateOfferAccept(offer,
                                                                requestMaxWindowBits=requestMaxWindowBits,
                                                                requestNoContextTakeover=requestNoContextTakeover,
                                                                noContextTakeover=noContextTakeover,
                                                                windowBits=windowBits,
                                                                memLevel=memLevel)

            factory.setProtocolOptions(perMessageCompressionAccept=accept)


class CrossbarWampWebSocketServerProtocol(WampWebSocketServerProtocol):

    """
    Crossbar.io WAMP-over-WebSocket server protocol.
    """

    def onConnect(self, request):

        if self.factory.debug_traffic:
            from twisted.internet import reactor

            def print_traffic():
                print("Traffic {}: {} / {} in / out bytes - {} / {} in / out msgs".format(self.peer,
                                                                                          self.trafficStats.incomingOctetsWireLevel,
                                                                                          self.trafficStats.outgoingOctetsWireLevel,
                                                                                          self.trafficStats.incomingWebSocketMessages,
                                                                                          self.trafficStats.outgoingWebSocketMessages))
                reactor.callLater(1, print_traffic)

            print_traffic()

        # if WebSocket client did not set WS subprotocol, assume "wamp.2.json"
        #
        self.STRICT_PROTOCOL_NEGOTIATION = self.factory._requireWebSocketSubprotocol

        # handle WebSocket opening handshake
        #
        protocol, headers = WampWebSocketServerProtocol.onConnect(self, request)

        try:

            self._origin = request.origin

            # transport authentication
            #
            self._authid = None
            self._authrole = None
            self._authmethod = None

            # cookie tracking
            #
            self._cbtid = None

            if self.factory._cookiestore:

                self._cbtid = self.factory._cookiestore.parse(request.headers)

                # if no cookie is set, create a new one ..
                if self._cbtid is None:

                    self._cbtid, headers['Set-Cookie'] = self.factory._cookiestore.create()

                    if self.debug:
                        log.msg("Setting new cookie: %s" % headers['Set-Cookie'])

                else:
                    if self.debug:
                        log.msg("Cookie already set")

                # add this WebSocket connection to the set of connections
                # associated with the same cookie
                self.factory._cookiestore.addProto(self._cbtid, self)

                if self.debug:
                    log.msg("Cookie tracking enabled on WebSocket connection {}".format(self))

                # if cookie-based authentication is enabled, set auth info from cookie store
                #
                if 'auth' in self.factory._config and 'cookie' in self.factory._config['auth']:

                    self._authid, self._authrole, self._authmethod = self.factory._cookiestore.getAuth(self._cbtid)

                    if self.debug:
                        log.msg("Authenticated client via cookie", self._authid, self._authrole, self._authmethod)
                else:
                    if self.debug:
                        log.msg("Cookie-based authentication disabled")

            else:

                if self.debug:
                    log.msg("Cookie tracking disabled on WebSocket connection {}".format(self))

            # remember transport level info for later forwarding in
            # WAMP meta event "wamp.session.on_join"
            #
            self._transport_info = {
                'type': 'websocket',
                'protocol': protocol,
                'peer': self.peer,
                'http_headers_received': request.headers,
                'http_headers_sent': headers
            }

            # accept the WebSocket connection, speaking subprotocol `protocol`
            # and setting HTTP headers `headers`
            #
            return (protocol, headers)

        except Exception:
            traceback.print_exc()

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
        except Exception as e:
            log.msg("Error rendering WebSocket status page template: %s" % e)

    def onDisconnect(self):
        # remove this WebSocket connection from the set of connections
        # associated with the same cookie
        if self._cbtid:
            self.factory._cookiestore.dropProto(self._cbtid, self)


class CrossbarWampWebSocketServerFactory(WampWebSocketServerFactory):

    """
    Crossbar.io WAMP-over-WebSocket server factory.
    """

    protocol = CrossbarWampWebSocketServerProtocol

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
        self.debug = config.get('debug', False)
        self.debug_traffic = config.get('debug_traffic', False)

        options = config.get('options', {})

        server = "Crossbar/{}".format(crossbar.__version__)
        externalPort = options.get('external_port', None)

        # explicit list of WAMP serializers
        #
        if 'serializers' in config:
            serializers = []
            sers = set(config['serializers'])

            if 'json' in sers:
                # try JSON WAMP serializer
                try:
                    from autobahn.wamp.serializer import JsonSerializer
                    serializers.append(JsonSerializer())
                except ImportError:
                    print("Warning: could not load WAMP-JSON serializer")
                else:
                    sers.discard('json')

            if 'msgpack' in sers:
                # try MsgPack WAMP serializer
                try:
                    from autobahn.wamp.serializer import MsgPackSerializer
                    serializers.append(MsgPackSerializer())
                except ImportError:
                    print("Warning: could not load WAMP-MsgPack serializer")
                else:
                    sers.discard('msgpack')

            if not serializers:
                raise Exception("no valid WAMP serializers specified")

            if len(sers) > 0:
                raise Exception("invalid WAMP serializers specified: {}".format(sers))

        else:
            serializers = None

        WampWebSocketServerFactory.__init__(self,
                                            factory,
                                            serializers=serializers,
                                            url=config.get('url', None),
                                            server=server,
                                            externalPort=externalPort,
                                            debug=self.debug,
                                            debug_wamp=self.debug)

        # Crossbar.io node directory
        self._cbdir = cbdir

        # transport configuration
        self._config = config

        # Jinja2 templates for 404 etc
        self._templates = templates

        # cookie tracking
        if 'cookie' in config:
            if 'database' in config['cookie']:
                dbfile = os.path.abspath(os.path.join(self._cbdir, config['cookie']['database']))
                self._cookiestore = PersistentCookieStore(dbfile, config['cookie'])
                log.msg("Persistent cookie store active: {}".format(dbfile))
            else:
                self._cookiestore = CookieStore(config['cookie'])
                log.msg("Transient cookie store active.")
        else:
            self._cookiestore = None

        # set WebSocket options
        set_websocket_options(self, options)


class CrossbarWampRawSocketServerProtocol(WampRawSocketServerProtocol):

    """
    Crossbar.io WAMP-over-RawSocket server protocol.
    """

    def connectionMade(self):
        WampRawSocketServerProtocol.connectionMade(self)

        # transport authentication
        #
        self._authid = None
        self._authrole = None
        self._authmethod = None

        # cookie tracking
        #
        self._cbtid = None

        # remember transport level info for later forwarding in
        # WAMP meta event "wamp.session.on_join"
        #
        self._transport_info = {
            'type': 'rawsocket',
            'protocol': None,  # FIXME
            'peer': self.peer
        }

    def lengthLimitExceeded(self, length):
        if self.factory.debug:
            log.msg("failing RawSocket connection - message length exceeded: message was {0} bytes, but current maximum is {1} bytes".format(length, self.MAX_LENGTH))
        self.transport.loseConnection()


class CrossbarWampRawSocketServerFactory(WampRawSocketServerFactory):

    """
    Crossbar.io WAMP-over-RawSocket server factory.
    """

    protocol = CrossbarWampRawSocketServerProtocol

    def __init__(self, factory, config):

        # remember transport configuration
        #
        self._config = config

        # WAMP serializer
        #
        serid = config.get('serializer', 'msgpack')

        if serid == 'json':
            # try JSON WAMP serializer
            try:
                from autobahn.wamp.serializer import JsonSerializer
                serializer = JsonSerializer()
            except ImportError:
                raise Exception("could not load WAMP-JSON serializer")

        elif serid == 'msgpack':
            # try MsgPack WAMP serializer
            try:
                from autobahn.wamp.serializer import MsgPackSerializer
                serializer = MsgPackSerializer()
                serializer._serializer.ENABLE_V5 = False  # FIXME
            except ImportError:
                raise Exception("could not load WAMP-MsgPack serializer")

        else:
            raise Exception("invalid WAMP serializer '{}'".format(serid))

        # Maximum message size
        #
        self._max_message_size = config.get('max_message_size', 128 * 1024)  # default is 128kB

        # transport debugging
        #
        debug = config.get('debug', False)

        WampRawSocketServerFactory.__init__(self, factory, serializer, debug=debug)

        if self.debug:
            log.msg("RawSocket transport factory created using {0} serializer, max. message size {1}".format(serid, self._max_message_size))

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        p.MAX_LENGTH = self._max_message_size
        return p


class CrossbarWampWebSocketClientProtocol(WampWebSocketClientProtocol):

    """
    Crossbar.io WAMP-over-WebSocket client protocol.
    """


class CrossbarWampWebSocketClientFactory(WampWebSocketClientFactory):

    """
    Crossbar.io WAMP-over-WebSocket client factory.
    """

    protocol = CrossbarWampWebSocketClientProtocol

    def buildProtocol(self, addr):
        self._proto = WampWebSocketClientFactory.buildProtocol(self, addr)
        return self._proto


class CrossbarWampRawSocketClientProtocol(WampRawSocketClientProtocol):

    """
    Crossbar.io WAMP-over-RawSocket client protocol.
    """


class CrossbarWampRawSocketClientFactory(WampRawSocketClientFactory):

    """
    Crossbar.io WAMP-over-RawSocket client factory.
    """

    protocol = CrossbarWampRawSocketClientProtocol

    def __init__(self, factory, config):

        # transport configuration
        self._config = config

        # WAMP serializer
        #
        serid = config.get('serializer', 'msgpack')

        if serid == 'json':
            # try JSON WAMP serializer
            try:
                from autobahn.wamp.serializer import JsonSerializer
                serializer = JsonSerializer()
            except ImportError:
                raise Exception("could not load WAMP-JSON serializer")

        elif serid == 'msgpack':
            # try MsgPack WAMP serializer
            try:
                from autobahn.wamp.serializer import MsgPackSerializer
                serializer = MsgPackSerializer()
                serializer._serializer.ENABLE_V5 = False  # FIXME
            except ImportError:
                raise Exception("could not load WAMP-MsgPack serializer")

        else:
            raise Exception("invalid WAMP serializer '{}'".format(serid))

        WampRawSocketClientFactory.__init__(self, factory, serializer)
