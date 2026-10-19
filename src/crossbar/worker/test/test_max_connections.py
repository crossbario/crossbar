#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
from unittest import mock

from autobahn.twisted.util import transport_channel_id
from cryptography.hazmat.primitives.asymmetric import ec
from twisted.internet import reactor
from twisted.internet.defer import Deferred, gatherResults, inlineCallbacks
from twisted.internet.endpoints import SSL4ClientEndpoint, TCP4ClientEndpoint, connectProtocol
from twisted.internet.protocol import Protocol
from twisted.internet.ssl import CertificateOptions
from twisted.internet.task import deferLater
from twisted.protocols.policies import ProtocolWrapper
from twisted.protocols.tls import TLSMemoryBIOProtocol
from twisted.trial import unittest

from crossbar._util import get_free_tcp_port
from crossbar.common.checkconfig import InvalidConfigException, check_router_transport
from crossbar.common.twisted.test.test_tls import _write_self_signed
from crossbar.personality import Personality
from crossbar.worker.transport import RouterTransport, create_router_transport

# WAMP-RawSocket handshake: magic octet, max. message length 2**24 and JSON serializer, reserved
_HANDSHAKE = b"\x7f\xf1\x00\x00"


class _RawSocketClient(Protocol):
    """
    Sends a WAMP-RawSocket handshake. ``handshaked`` fires with True when the router answered the
    handshake, or with False when the connection was closed without an answer.
    """

    def __init__(self):
        self.handshaked = Deferred()
        self.lost = Deferred()
        self._data = b""

    def connectionMade(self):
        self.transport.write(_HANDSHAKE)

    def dataReceived(self, data):
        self._data += data
        if len(self._data) >= 4 and not self.handshaked.called:
            self.handshaked.callback(self._data[:1] == b"\x7f")

    def connectionLost(self, reason):
        if not self.handshaked.called:
            self.handshaked.callback(False)
        self.lost.callback(None)


class _WebSocketClient(_RawSocketClient):
    """
    Sends a WAMP-WebSocket opening handshake. ``handshaked`` fires with True when the router
    answered with "101 Switching Protocols".
    """

    def connectionMade(self):
        self.transport.write(
            b"GET / HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            b"Sec-WebSocket-Version: 13\r\n"
            b"Sec-WebSocket-Protocol: wamp.2.json\r\n"
            b"\r\n"
        )

    def dataReceived(self, data):
        self._data += data
        if b"\r\n\r\n" in self._data and not self.handshaked.called:
            self.handshaked.callback(self._data.startswith(b"HTTP/1.1 101"))


def _rawsocket_transport_config(**extra):
    config = {
        "type": "rawsocket",
        "endpoint": {"type": "tcp", "interface": "127.0.0.1", "port": get_free_tcp_port("127.0.0.1")},
    }
    config.update(extra)
    return config


class _TransportTestCase(unittest.TestCase):
    """
    Starts router transports on a mocked worker and connects real TCP clients.
    """

    def setUp(self):
        self.worker = mock.Mock()
        self.worker.personality = Personality
        self.worker.config.extra.cbdir = self.mktemp()
        self.worker.templates.return_value = None
        self.worker._reactor = reactor
        self.clients = []

    @inlineCallbacks
    def _start(self, config):
        transport = RouterTransport(self.worker, "transport001", config)
        yield transport.start()
        self.addCleanup(transport.stop)
        return transport

    @inlineCallbacks
    def _connect(self, transport):
        endpoint = TCP4ClientEndpoint(reactor, "127.0.0.1", transport._config["endpoint"]["port"])
        client = yield connectProtocol(endpoint, _RawSocketClient())
        self.clients.append(client)
        handshaked = yield client.handshaked
        return client, handshaked

    def tearDown(self):
        for client in self.clients:
            if not client.lost.called:
                client.transport.loseConnection()
        return gatherResults([client.lost for client in self.clients])


class MaxConnectionsTests(_TransportTestCase):
    """
    A listening transport refuses connections beyond ``max_connections`` (#2324).
    """

    @inlineCallbacks
    def test_third_connection_refused(self):
        transport = yield self._start(_rawsocket_transport_config(max_connections=2))
        _, ok1 = yield self._connect(transport)
        _, ok2 = yield self._connect(transport)
        client3, ok3 = yield self._connect(transport)
        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertFalse(ok3)
        yield client3.lost

        # the first two connections keep working
        self.assertTrue(self.clients[0].transport.connected)
        self.assertTrue(self.clients[1].transport.connected)

    @inlineCallbacks
    def test_closed_connection_frees_slot(self):
        transport = yield self._start(_rawsocket_transport_config(max_connections=2))
        client1, _ = yield self._connect(transport)
        yield self._connect(transport)

        client1.transport.loseConnection()
        yield client1.lost

        # the router notices the close asynchronously: retry until the slot is free
        for _ in range(50):
            _, ok = yield self._connect(transport)
            if ok:
                break
            yield deferLater(reactor, 0.1, lambda: None)
        self.assertTrue(ok)

    @inlineCallbacks
    def test_no_max_connections_configured(self):
        """
        A transport without "max_connections" accepts connections as before (default cap 50000).
        """
        transport = yield self._start(_rawsocket_transport_config())
        for _ in range(3):
            _, ok = yield self._connect(transport)
            self.assertTrue(ok)

    def test_default_max_connections(self):
        from crossbar.worker.transport import DEFAULT_MAX_CONNECTIONS

        self.assertEqual(DEFAULT_MAX_CONNECTIONS, 50000)


class MaxConnectionsConfigTests(unittest.TestCase):
    """
    ``max_connections`` is checked by ``crossbar check`` (#2324).
    """

    def _check(self, transport):
        check_router_transport(Personality, transport)

    def _endpoint(self):
        return {"type": "tcp", "port": 8080}

    def test_valid(self):
        for ttype in ["websocket", "rawsocket", "web", "universal", "mqtt"]:
            transport = {"type": ttype, "endpoint": self._endpoint(), "max_connections": 2}
            if ttype == "web":
                transport["paths"] = {"/": {"type": "static", "directory": ".."}}
            if ttype == "mqtt":
                transport["options"] = {"realm": "realm1"}
            self._check(transport)

    def test_invalid_values(self):
        for value in [0, -1, "10", 1.5, True, None]:
            transport = {"type": "rawsocket", "endpoint": self._endpoint(), "max_connections": value}
            with self.assertRaises(InvalidConfigException, msg=repr(value)) as e:
                self._check(transport)
            self.assertIn("max_connections", str(e.exception))

    def test_not_on_universal_subtransport(self):
        """
        In a Universal transport, the cap is set on the Universal transport, which owns the listening port.
        """
        transport = {"type": "universal", "endpoint": self._endpoint(), "rawsocket": {"max_connections": 2}}
        with self.assertRaises(InvalidConfigException) as e:
            self._check(transport)
        self.assertIn("max_connections", str(e.exception))


class MaxConnectionsLayeringTests(_TransportTestCase):
    """
    The connection cap is the outermost layer of the listening port: the protocols see the same
    transports as without a cap, and a WebSocket upgrade on a Web transport stays counted (#2324).
    """

    def setUp(self):
        super().setUp()
        os.makedirs(self.worker.config.extra.cbdir)
        _write_self_signed(self.worker.config.extra.cbdir, ec.generate_private_key(ec.SECP256R1()))
        self.worker.templates.return_value = mock.Mock()

    def _tls(self, config):
        config["endpoint"]["tls"] = {"key": "server.key", "certificate": "server.crt"}
        return config

    @inlineCallbacks
    def _connect(self, transport, client=None):
        port = transport._config["endpoint"]["port"]
        if "tls" in transport._config["endpoint"]:
            endpoint = SSL4ClientEndpoint(reactor, "127.0.0.1", port, CertificateOptions())
        else:
            endpoint = TCP4ClientEndpoint(reactor, "127.0.0.1", port)
        client = yield connectProtocol(endpoint, client or _RawSocketClient())
        self.clients.append(client)
        handshaked = yield client.handshaked
        return client, handshaked

    def _server_protocols(self, transport):
        return [counted.wrappedProtocol for counted in transport._port.factory.protocols]

    @inlineCallbacks
    def test_tls_third_connection_refused(self):
        transport = yield self._start(self._tls(_rawsocket_transport_config(max_connections=2)))
        _, ok1 = yield self._connect(transport)
        _, ok2 = yield self._connect(transport)
        _, ok3 = yield self._connect(transport)
        self.assertEqual((ok1, ok2, ok3), (True, True, False))

    @inlineCallbacks
    def test_tls_transport_unchanged(self):
        """
        Under TLS, the WAMP protocol's transport is the TLS transport, so TLS channel binding works.
        """
        transport = yield self._start(self._tls(_rawsocket_transport_config(max_connections=2)))
        yield self._connect(transport)
        [tls] = self._server_protocols(transport)
        self.assertIsInstance(tls, TLSMemoryBIOProtocol)
        wamp_transport = tls.wrappedProtocol.transport
        self.assertIsInstance(wamp_transport, TLSMemoryBIOProtocol)
        channel_id = transport_channel_id(wamp_transport, True, "tls-unique")
        self.assertEqual(len(channel_id), 32)
        self.assertNotEqual(channel_id, b"\x00" * 32)

    @inlineCallbacks
    def test_plain_transport_unchanged(self):
        """
        Without TLS, the WAMP protocol's transport is the TCP connection, not the counting wrapper.
        """
        transport = yield self._start(_rawsocket_transport_config(max_connections=2))
        yield self._connect(transport)
        [wamp] = self._server_protocols(transport)
        self.assertNotIsInstance(wamp.transport, ProtocolWrapper)

    @inlineCallbacks
    def _check_web_websocket(self, config):
        transport = create_router_transport(self.worker, "transport001", config)
        yield transport.start()
        self.addCleanup(transport.stop)

        client1, ok1 = yield self._connect(transport, _WebSocketClient())
        _, ok2 = yield self._connect(transport, _WebSocketClient())
        self.assertEqual((ok1, ok2), (True, False))

        # after the WebSocket upgrade, closing the connection still frees the slot
        client1.transport.loseConnection()
        yield client1.lost
        for _ in range(50):
            _, ok = yield self._connect(transport, _WebSocketClient())
            if ok:
                break
            yield deferLater(reactor, 0.1, lambda: None)
        self.assertTrue(ok)

    def _web_config(self):
        config = _rawsocket_transport_config(max_connections=1)
        config["type"] = "web"
        config["paths"] = {"/": {"type": "websocket"}}
        return config

    def test_web_websocket_upgrade_counted(self):
        return self._check_web_websocket(self._web_config())

    def test_web_websocket_upgrade_counted_tls(self):
        return self._check_web_websocket(self._tls(self._web_config()))


class MaxConnectionsLogPrefixTests(unittest.TestCase):
    """
    The connection cap does not change the log lines of the listening port (#2324): e.g. the
    functional tests wait for "WampRawSocketServerFactory starting on <port>".
    """

    def test_factory_log_prefix(self):
        from twisted.internet.protocol import Factory

        from crossbar.common.twisted.endpoint import MaxConnectionsFactory

        class WampRawSocketServerFactory(Factory):
            pass

        factory = MaxConnectionsFactory(WampRawSocketServerFactory(), 2, "transport001", reactor, mock.Mock())
        self.assertEqual(factory.logPrefix(), "WampRawSocketServerFactory")

    @inlineCallbacks
    def _starting_message(self, tls):
        from twisted.python import log as legacy_log

        cbdir = self.mktemp()
        os.makedirs(cbdir)
        worker = mock.Mock()
        worker.personality = Personality
        worker.config.extra.cbdir = cbdir
        worker._reactor = reactor
        config = _rawsocket_transport_config(max_connections=2)
        if tls:
            _write_self_signed(cbdir, ec.generate_private_key(ec.SECP256R1()))
            config["endpoint"]["tls"] = {"key": "server.key", "certificate": "server.crt"}

        messages = []

        def observer(event):
            messages.extend(str(m) for m in event.get("message", ()))

        legacy_log.addObserver(observer)
        try:
            transport = RouterTransport(worker, "transport001", config)
            yield transport.start()
        finally:
            legacy_log.removeObserver(observer)
        self.addCleanup(transport.stop)
        port = config["endpoint"]["port"]
        return [m for m in messages if m.endswith("starting on {}".format(port))], port

    @inlineCallbacks
    def test_port_starting_message(self):
        messages, port = yield self._starting_message(tls=False)
        self.assertEqual(messages, ["WampRawSocketServerFactory starting on {}".format(port)])

    @inlineCallbacks
    def test_port_starting_message_tls(self):
        messages, port = yield self._starting_message(tls=True)
        self.assertEqual(messages, ["WampRawSocketServerFactory (TLS) starting on {}".format(port)])
