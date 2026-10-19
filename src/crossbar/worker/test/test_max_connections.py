#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from unittest import mock

from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.internet.protocol import Protocol
from twisted.internet.task import deferLater
from twisted.trial import unittest

from crossbar._util import get_free_tcp_port
from crossbar.common.checkconfig import InvalidConfigException, check_router_transport
from crossbar.personality import Personality
from crossbar.worker.transport import RouterTransport

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


def _rawsocket_transport_config(**extra):
    config = {
        "type": "rawsocket",
        "endpoint": {"type": "tcp", "interface": "127.0.0.1", "port": get_free_tcp_port("127.0.0.1")},
    }
    config.update(extra)
    return config


class MaxConnectionsTests(unittest.TestCase):
    """
    A listening transport refuses connections beyond ``max_connections`` (#2324).
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
            if client.transport is not None:
                client.transport.loseConnection()
        return deferLater(reactor, 0, lambda: None)

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
