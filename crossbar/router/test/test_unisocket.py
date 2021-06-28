#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from collections import OrderedDict

from twisted.trial.unittest import TestCase
from twisted.internet.protocol import Protocol, Factory
from twisted.test.proto_helpers import StringTransportWithDisconnection as StringTransport
from twisted.web.server import Site
from twisted.web.resource import Resource

from crossbar.router.unisocket import UniSocketServerFactory


class UniSocketTests(TestCase):
    """
    Tests for Crossbar's RawSocket.
    """
    def test_rawsocket_with_no_factory(self):
        """
        Trying to speak RawSocket with no RawSocket factory configured will
        drop the connection.
        """
        t = StringTransport()

        f = UniSocketServerFactory()
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'\x7F0000000')

        self.assertFalse(t.connected)

    def test_rawsocket_with_factory(self):
        """
        Speaking RawSocket when the connection is made will make UniSocket
        create a new RawSocket protocol and send the data to it.
        """
        t = StringTransport()

        class MyFakeRawSocket(Protocol):
            """
            A fake RawSocket factory which just echos data back.
            """
            def dataReceived(self, data):
                self.transport.write(data)

        fake_rawsocket = Factory.forProtocol(MyFakeRawSocket)
        f = UniSocketServerFactory(rawsocket_factory=fake_rawsocket)
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'\x7F0000000')
        p.dataReceived(b'moredata')

        self.assertTrue(t.connected)
        self.assertEqual(t.value(), b'\x7F0000000moredata')

    def test_web_with_no_factory(self):
        """
        Trying to speak HTTP without a factory will drop the connection.
        """
        t = StringTransport()

        f = UniSocketServerFactory()
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'GET /foo HTTP/1.1\r\n\r\n')
        self.assertFalse(t.connected)

    def test_invalid_status_line(self):
        """
        Not speaking RawSocket or MQTT but also not speaking a type of HTTP
        will cause the connection to be dropped.
        """
        t = StringTransport()

        f = UniSocketServerFactory()
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'this is not HTTP\r\n\r\n')
        self.assertFalse(t.connected)

    def test_web_with_factory(self):
        """
        Speaking HTTP will pass it down to the HTTP factory.
        """
        t = StringTransport()

        class MyResource(Resource):
            isLeaf = True

            def render_GET(self, request):
                return b"hi!"

        r = MyResource()
        s = Site(r)

        f = UniSocketServerFactory(web_factory=s)
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'GET / HTTP/1.1\r\nConnection: close\r\n\r\n')
        self.assertFalse(t.connected)

        self.assertIn(b"hi!", t.value())

    def test_websocket_with_map(self):
        """
        Speaking WebSocket when the connection is made will make UniSocket
        create a new WebSocket protocol and send the data to it.
        """
        t = StringTransport()

        class MyFakeWebSocket(Protocol):
            """
            A fake WebSocket factory which just echos data back.
            """
            def dataReceived(self, data):
                self.transport.write(data)

        fake_websocket = Factory.forProtocol(MyFakeWebSocket)
        websocket_map = OrderedDict({"baz": None})
        websocket_map["ws"] = fake_websocket

        f = UniSocketServerFactory(websocket_factory_map=websocket_map)
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'GET /ws HTTP/1.1\r\nConnection: close\r\n\r\n')

        self.assertTrue(t.connected)
        self.assertEqual(t.value(), b'GET /ws HTTP/1.1\r\nConnection: close\r\n\r\n')

    def test_websocket_with_no_map(self):
        """
        A web request that matches no WebSocket path will go to HTTP/1.1.
        """
        t = StringTransport()

        websocket_map = {"x": None, "y": None}

        f = UniSocketServerFactory(websocket_factory_map=websocket_map)
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'GET /ws HTTP/1.1\r\nConnection: close\r\n\r\n')

        self.assertFalse(t.connected)
        self.assertEqual(t.value(), b"")

    def test_mqtt_with_no_factory(self):
        """
        Trying to speak MQTT with no MQTT factory configured will
        drop the connection.
        """
        t = StringTransport()

        f = UniSocketServerFactory()
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'\x100000000')

        self.assertFalse(t.connected)

    def test_mqtt_with_factory(self):
        """
        Speaking MQTT when the connection is made will make UniSocket
        create a new MQTT protocol and send the data to it.
        """
        t = StringTransport()

        class MyFakeMQTT(Protocol):
            """
            A fake MQTT factory which just echos data back.
            """
            def connectionMade(self, *a):
                pass

            def dataReceived(self, data):
                self.transport.write(data)

        fake_mqtt = Factory.forProtocol(MyFakeMQTT)
        f = UniSocketServerFactory(mqtt_factory=fake_mqtt)
        p = f.buildProtocol(None)

        p.makeConnection(t)
        t.protocol = p

        self.assertTrue(t.connected)
        p.dataReceived(b'\x100000000')
        p.dataReceived(b'moredata')

        self.assertTrue(t.connected)
        self.assertEqual(t.value(), b'\x100000000moredata')
