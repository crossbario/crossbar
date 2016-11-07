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

from __future__ import absolute_import, division

import attr

from functools import partial
from binascii import unhexlify

from crossbar.adapter.mqtt.tx import MQTTServerTwistedProtocol
from crossbar.adapter.mqtt.protocol import (
    MQTTParser, client_packet_handlers, P_CONNACK)
from crossbar.adapter.mqtt._events import (
    Connect, ConnectFlags, ConnACK, SubACK, Subscribe,
    SubscriptionTopicRequest
)
from crossbar.adapter.mqtt._utils import iterbytes
from crossbar._logging import LogCapturer, LogLevel

from twisted.test.proto_helpers import Clock, StringTransport
from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, succeed, inlineCallbacks


class MQTTClientParser(MQTTParser):
    _first_pkt = P_CONNACK
    _packet_handlers = client_packet_handlers


@attr.s
class BasicHandler(object):
    _connect_code = attr.ib(default=0)

    def process_connect(self, event):
        d = Deferred()
        d.callback(self._connect_code)
        return d

    def new_wamp_session(self, event):
        return None

    def existing_wamp_session(self, event):
        return None


class TwistedProtocolLoggingTests(TestCase):
    """
    Tests for the logging functionality of the Twisted MQTT protocol.b
    """

    def test_send_packet(self):
        """
        On sending a packet, a trace log message is emitted with details of the
        sent packet.
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)
        cp = MQTTClientParser()

        p.makeConnection(t)

        data = (
            # CONNECT
            b"101300044d51545404020002000774657374313233"
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(unhexlify(data)):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ101")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.debug)
        self.assertEqual(sent_logs[0]["txaio_trace"], True)
        self.assertIn("ConnACK", logs.log_text.getvalue())

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ConnACK)

    def test_recv_packet(self):
        """
        On receiving a packet, a trace log message is emitted with details of
        the received packet.
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        p.makeConnection(t)

        data = (
            # CONNECT
            b"101300044d51545404020002000774657374313233"
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(unhexlify(data)):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ100")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.debug)
        self.assertEqual(sent_logs[0]["txaio_trace"], True)
        self.assertIn("Connect", logs.log_text.getvalue())


class TwistedProtocolTests(TestCase):

    def test_keepalive(self):
        """
        If a client connects with a timeout, and sends no data in keep_alive *
        1.5, they will be disconnected.

        Compliance statement MQTT-3.1.2-24
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        p.makeConnection(t)

        data = (
            # CONNECT, with keepalive of 2
            b"101300044d51545404020002000774657374313233"
        )

        for x in iterbytes(unhexlify(data)):
            p.dataReceived(x)

        self.assertEqual(len(r.calls), 1)
        self.assertEqual(r.calls[0].func, p._lose_connection)
        self.assertEqual(r.calls[0].getTime(), 3.0)

        self.assertFalse(t.disconnecting)

        r.advance(2.9)
        self.assertFalse(t.disconnecting)

        r.advance(0.1)
        self.assertTrue(t.disconnecting)


    def test_keepalive_canceled_on_lost_connection(self):
        """
        If a client connects with a timeout, and disconnects themselves, we
        will remove the timeout.
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        p.makeConnection(t)

        data = (
            # CONNECT, with keepalive of 2
            b"101300044d51545404020002000774657374313233"
        )

        for x in iterbytes(unhexlify(data)):
            p.dataReceived(x)

        self.assertEqual(len(r.calls), 1)
        self.assertEqual(r.calls[0].getTime(), 3.0)
        timeout = r.calls[0]

        # Clean connection lost
        p.connectionLost(None)

        self.assertEqual(len(r.calls), 0)
        self.assertTrue(timeout.cancelled)
        self.assertFalse(timeout.called)


    def test_keepalive_requires_full_packet(self):
        """
        If a client connects with a keepalive, and sends no FULL packets in
        keep_alive * 1.5, they will be disconnected.

        Compliance statement MQTT-3.1.2-24
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        p.makeConnection(t)

        data = (
            # CONNECT, with keepalive of 2
            b"101300044d51545404020002000774657374313233"
        )

        for x in iterbytes(unhexlify(data)):
            p.dataReceived(x)

        self.assertEqual(len(r.calls), 1)
        self.assertEqual(r.calls[0].func, p._lose_connection)
        self.assertEqual(r.calls[0].getTime(), 3.0)

        self.assertFalse(t.disconnecting)

        r.advance(2.9)
        self.assertFalse(t.disconnecting)

        data = (
            # PINGREQ header, no body (incomplete packet)
            b"c0"
        )

        for x in iterbytes(unhexlify(data)):
            p.dataReceived(x)

        # Timeout has not changed. If it reset the timeout on data recieved,
        # the delayed call's trigger time would instead be 2.9 + 3.
        self.assertEqual(len(r.calls), 1)
        self.assertEqual(r.calls[0].func, p._lose_connection)
        self.assertEqual(r.calls[0].getTime(), 3.0)

        r.advance(0.1)
        self.assertTrue(t.disconnecting)

    def test_keepalive_full_packet_resets_timeout(self):
        """
        If a client connects with a keepalive, and sends packets in under
        keep_alive * 1.5, the connection will remain, and the timeout will be
        reset.
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        p.makeConnection(t)

        data = (
            # CONNECT, with keepalive of 2
            b"101300044d51545404020002000774657374313233"
        )

        for x in iterbytes(unhexlify(data)):
            p.dataReceived(x)

        self.assertEqual(len(r.calls), 1)
        self.assertEqual(r.calls[0].func, p._lose_connection)
        self.assertEqual(r.calls[0].getTime(), 3.0)

        self.assertFalse(t.disconnecting)

        r.advance(2.9)
        self.assertFalse(t.disconnecting)

        data = (
            # Full PINGREQ packet
            b"c000"
        )

        for x in iterbytes(unhexlify(data)):
            p.dataReceived(x)

        # Timeout has changed, to be 2.9 (the time the packet was recieved) + 3
        self.assertEqual(len(r.calls), 1)
        self.assertEqual(r.calls[0].func, p._lose_connection)
        self.assertEqual(r.calls[0].getTime(), 2.9 + 3.0)

        r.advance(0.1)
        self.assertFalse(t.disconnecting)

    def test_only_unique(self):
        """
        Connected clients must have unique client IDs.

        Compliance statement MQTT-3.1.3-2
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)
        cp = MQTTClientParser()

        p.makeConnection(t)

        data = (
            # CONNECT, client ID of test123
            b"\x10\x13\x00\x04MQTT\x04\x02\x00x\x00\x07test123"
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        self.assertFalse(t.disconnecting)
        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'return_code': 0,
                'session_present': False,
            })

        # New session
        r2 = Clock()
        t2 = StringTransport()
        p2 = MQTTServerTwistedProtocol(h, r2, sessions)
        cp2 = MQTTClientParser()

        p2.makeConnection(t2)

        # Send the same connect, with the same client ID
        for x in iterbytes(data):
            p2.dataReceived(x)

        events = cp2.data_received(t2.value())
        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'return_code': 2,
                'session_present': True,
            })

    def test_allow_connects_with_same_id_if_disconnected(self):
        """
        If a client connects and there is an existing session which is
        disconnected, it may connect.
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)
        cp = MQTTClientParser()

        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        self.assertFalse(t.disconnecting)
        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'return_code': 0,
                'session_present': False,
            })

        p.connectionLost(None)

        # New session
        r2 = Clock()
        t2 = StringTransport()
        p2 = MQTTServerTwistedProtocol(h, r2, sessions)
        cp2 = MQTTClientParser()

        p2.makeConnection(t2)

        # Send the same connect, with the same client ID
        for x in iterbytes(data):
            p2.dataReceived(x)

        # Connection allowed
        events = cp2.data_received(t2.value())
        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'return_code': 0,
                'session_present': True,
            })

        # Same session
        self.assertEqual(p.session, p2.session)

    def test_clean_session_destroys_session(self):
        """
        Setting the clean_session flag to True when connecting means that any
        existing session for that user ID will be destroyed.

        Compliance statement MQTT-3.2.2-1
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        self.assertFalse(t.disconnecting)
        self.assertEqual(list(sessions.keys()), [u"test123"])
        old_session = sessions[u"test123"]

        # Close the connection
        p.connectionLost(None)

        # New session, clean_session=True
        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        r2 = Clock()
        t2 = StringTransport()
        p2 = MQTTServerTwistedProtocol(h, r2, sessions)
        cp2 = MQTTClientParser()

        p2.makeConnection(t2)

        # Send the same connect, with the same client ID
        for x in iterbytes(data):
            p2.dataReceived(x)

        # Connection allowed
        events = cp2.data_received(t2.value())
        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'return_code': 0,
                'session_present': False,
            })

        self.assertEqual(list(sessions.keys()), [u"test123"])
        new_session = sessions[u"test123"]

        # Brand new session, that won't survive
        self.assertIsNot(old_session, new_session)
        self.assertFalse(new_session.survives)

        # We close the connection, the session is destroyed
        p2.connectionLost(None)
        self.assertEqual(list(sessions.keys()), [])

    def test_transport_paused_while_processing(self):
        """
        The transport is paused whilst the MQTT protocol is parsing/handling
        existing items.
        """
        sessions = {}

        d = Deferred()
        h = BasicHandler()
        h.process_connect = lambda x: d
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        t.connected = True
        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        self.assertEqual(t.producerState, 'producing')

        for x in iterbytes(data):
            p.dataReceived(x)

        self.assertEqual(t.producerState, 'paused')
        d.callback(0)
        self.assertEqual(t.producerState, 'producing')

    def test_unknown_connect_code_must_lose_connection(self):
        """
        A non-zero, and non-1-to-5 connect code from the handler must result in
        a lost connection, and no CONNACK.

        Compliance statements MQTT-3.2.2-4, MQTT-3.2.2-5
        """
        sessions = {}

        d = Deferred()
        h = BasicHandler(6)
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)
        cp = MQTTClientParser()

        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        self.assertTrue(t.disconnecting)
        self.assertEqual(t.value(), b'')

    def test_lose_conn_on_protocol_violation(self):
        """
        When a protocol violation occurs, the connection to the client will be
        terminated, and an error will be logged.

        Compliance statement MQTT-4.8.0-1
        """
        sessions = {}

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        p.makeConnection(t)

        data = (
            # Invalid CONNECT
            b"111300044d51545404020002000774657374313233"
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(unhexlify(data)):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ401")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.error)
        self.assertIn("Connect", logs.log_text.getvalue())

        self.assertEqual(t.value(), b'')
        self.assertTrue(t.disconnecting)

    def test_lose_conn_on_unimplemented_packet(self):
        """
        If we get a valid, but unimplemented for that role packet (e.g. SubACK,
        which we will only ever send, and getting it is a protocol violation),
        we will drop the connection.

        Compliance statement: MQTT-4.8.0-1
        """
        sessions = {}

        # This shouldn't normally happen, but just in case.
        from crossbar.adapter.mqtt import protocol
        protocol.server_packet_handlers[protocol.P_SUBACK] = SubACK
        self.addCleanup(
            lambda: protocol.server_packet_handlers.pop(protocol.P_SUBACK))

        h = BasicHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)

        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise() +
            SubACK(1, [1]).serialise()
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ402")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.error)
        self.assertEqual(sent_logs[0]["packet_id"], "SubACK")

        self.assertTrue(t.disconnecting)


class NonZeroConnACKTests(object):

    connect_code = None

    def test_non_zero_connect_code_must_have_no_present_session(self):
        """
        A non-zero connect code in a CONNACK must be paired with no session
        present.

        Compliance statement MQTT-3.2.2-4
        """
        sessions = {}

        d = Deferred()
        h = BasicHandler(self.connect_code)
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)
        cp = MQTTClientParser()

        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'return_code': self.connect_code,
                'session_present': False,
            })


for x in [1, 2, 3, 4, 5]:
    # Generate test cases for each of the return codes.
    class cls(NonZeroConnACKTests, TestCase):
        connect_code = x

    name = "NonZeroConnACKWithCode" + str(x) + "Tests"

    cls.__name__ = name
    if hasattr(cls, "__qualname__"):
        cls.__qualname__ = cls.__qualname__.replace("cls", name)

    globals().update({name: cls})
    del name
    del cls


class SubscribeHandlingTests(TestCase):

    def test_subscribe_always_gets_packet(self):
        """
        Subscriptions always get a ConnACK, even if none of the subscriptions
        were successful.

        Compliance statements MQTT-3.8.4-1
        """
        sessions = {}

        class SubHandler(BasicHandler):
            def process_subscribe(self, event):
                return succeed([128])

        h = SubHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)
        cp = MQTTClientParser()

        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() +
            Subscribe(packet_identifier=1234,
                      topic_requests=[SubscriptionTopicRequest(u"a", 0)]
            ).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].return_codes, [128])


    def test_subscribe_same_id(self):
        """
        SubACKs have the same packet IDs as the Subscription that it is
        replying to.

        Compliance statements MQTT-3.8.4-2
        """
        sessions = {}

        class SubHandler(BasicHandler):
            def process_subscribe(self, event):
                return succeed([0])

        h = SubHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)
        cp = MQTTClientParser()

        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() +
            Subscribe(packet_identifier=1234,
                      topic_requests=[SubscriptionTopicRequest(u"a", 0)]
            ).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].return_codes, [0])
        self.assertEqual(events[1].packet_identifier, 1234)


    def test_exception_in_subscribe_drops_connection(self):
        """
        Transient failures (like an exception from handler.process_subscribe)
        will cause the connection it happened on to be dropped.

        Compliance statement MQTT-4.8.0-2
        """
        sessions = {}

        class SubHandler(BasicHandler):
            @inlineCallbacks
            def process_subscribe(self, event):
                raise Exception("boom!")

        h = SubHandler()
        r = Clock()
        t = StringTransport()
        p = MQTTServerTwistedProtocol(h, r, sessions)
        cp = MQTTClientParser()

        p.makeConnection(t)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() +
            Subscribe(packet_identifier=1234,
                      topic_requests=[SubscriptionTopicRequest(u"a", 0)]
            ).serialise()
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ500")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.critical)
        self.assertEqual(sent_logs[0]["log_failure"].value.args[0], "boom!")

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertTrue(t.disconnecting)

        # We got the error, we need to flush it so it doesn't make the test
        # error
        self.flushLoggedErrors()
