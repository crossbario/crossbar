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

from __future__ import absolute_import, division

import attr

from functools import partial
from binascii import unhexlify

from crossbar.adapter.mqtt.tx import (
    MQTTServerTwistedProtocol, AwaitingACK, Session, Message)
from crossbar.adapter.mqtt.protocol import (
    MQTTParser, MQTTClientParser, client_packet_handlers, P_CONNACK)
from crossbar.adapter.mqtt._events import (
    Connect, ConnectFlags, ConnACK,
    SubACK, Subscribe,
    Publish, PubACK, PubREC, PubREL, PubCOMP,
    Unsubscribe, UnsubACK,
    SubscriptionTopicRequest
)
from crossbar.adapter.mqtt._utils import iterbytes
from crossbar._logging import LogCapturer, LogLevel

from twisted.test.proto_helpers import Clock, StringTransport
from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, succeed, inlineCallbacks


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


def make_test_items(handler, sessions=None):

    sessions = sessions or {}

    r = Clock()
    t = StringTransport()
    p = MQTTServerTwistedProtocol(handler, r, sessions)
    cp = MQTTClientParser()

    p.makeConnection(t)

    return sessions, r, t, p, cp


class TwistedProtocolLoggingTests(TestCase):
    """
    Tests for the logging functionality of the Twisted MQTT protocol.
    """

    def test_send_packet(self):
        """
        On sending a packet, a trace log message is emitted with details of the
        sent packet.
        """
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        sessions, r2, t2, p2, cp2 = make_test_items(h, sessions=sessions)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        sessions, r2, t2, p2, cp2 = make_test_items(h, sessions=sessions)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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

        sessions, r2, t2, p2, cp2 = make_test_items(h, sessions=sessions)

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
        d = Deferred()
        h = BasicHandler()
        h.process_connect = lambda x: d
        sessions, r, t, p, cp = make_test_items(h)

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
        d = Deferred()
        h = BasicHandler(6)
        sessions, r, t, p, cp = make_test_items(h)

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
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        # This shouldn't normally happen, but just in case.
        from crossbar.adapter.mqtt import protocol
        protocol.server_packet_handlers[protocol.P_SUBACK] = SubACK
        self.addCleanup(
            lambda: protocol.server_packet_handlers.pop(protocol.P_SUBACK))

        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

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

    def test_lose_conn_on_reserved_qos3(self):
        """
        If we get, somehow, a QoS "3" Publish (one with both QoS bits set to
        3), we will drop the connection.

        Compliance statement: MQTT-3.3.1-4
        """
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        conn = Connect(client_id=u"test123",
                       flags=ConnectFlags(clean_session=False))
        pub = Publish(duplicate=False, qos_level=3, retain=False,
                      topic_name=u"foo", packet_identifier=2345,
                      payload=b"bar")

        with LogCapturer("trace") as logs:
            p._handle_events([conn, pub])

        sent_logs = logs.get_category("MQ403")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.error)

        self.assertTrue(t.disconnecting)

    def test_packet_id_is_sixteen_bit(self):
        """
        The packet ID generator makes IDs that fit within a 16bit uint.
        """
        session = Session(client_id=u"test123", wamp_session=None)
        session_id = session.get_packet_id()
        self.assertTrue(session_id > -1)
        self.assertTrue(session_id < 65536)

        # And it is a valid session ID...
        SubACK(session_id, [1]).serialise()


class NonZeroConnACKTests(object):

    connect_code = None

    def test_non_zero_connect_code_must_have_no_present_session(self):
        """
        A non-zero connect code in a CONNACK must be paired with no session
        present.

        Compliance statement MQTT-3.2.2-4
        """
        d = Deferred()
        h = BasicHandler(self.connect_code)
        sessions, r, t, p, cp = make_test_items(h)

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
        class SubHandler(BasicHandler):
            def process_subscribe(self, event):
                return succeed([128])

        h = SubHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        class SubHandler(BasicHandler):
            def process_subscribe(self, event):
                return succeed([0])

        h = SubHandler()
        sessions, r, t, p, cp = make_test_items(h)

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
        class SubHandler(BasicHandler):
            @inlineCallbacks
            def process_subscribe(self, event):
                raise Exception("boom!")

        h = SubHandler()
        sessions, r, t, p, cp = make_test_items(h)

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

        sent_logs = logs.get_category("MQ501")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.critical)
        self.assertEqual(sent_logs[0]["log_failure"].value.args[0], "boom!")

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertTrue(t.disconnecting)

        # We got the error, we need to flush it so it doesn't make the test
        # error
        self.flushLoggedErrors()


class ConnectHandlingTests(TestCase):

    def test_got_sent_packet(self):
        """
        `process_connect` on the handler will get the correct Connect packet.
        """
        got_packets = []

        class SubHandler(BasicHandler):
            def process_connect(self_, event):
                got_packets.append(event)
                return succeed(0)

        h = SubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        self.assertEqual(len(got_packets), 1)
        self.assertEqual(got_packets[0].client_id, u"test123")
        self.assertEqual(got_packets[0].serialise(), data)

    def test_exception_in_connect_drops_connection(self):
        """
        Transient failures (like an exception from handler.process_connect)
        will cause the connection it happened on to be dropped.

        Compliance statement MQTT-4.8.0-2
        """
        class SubHandler(BasicHandler):
            @inlineCallbacks
            def process_connect(self, event):
                raise Exception("boom!")

        h = SubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ500")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.critical)
        self.assertEqual(sent_logs[0]["log_failure"].value.args[0], "boom!")

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 0)
        self.assertTrue(t.disconnecting)

        # We got the error, we need to flush it so it doesn't make the test
        # error
        self.flushLoggedErrors()


class UnsubscribeHandlingTests(TestCase):

    def test_exception_in_connect_drops_connection(self):
        """
        Transient failures (like an exception from handler.process_connect)
        will cause the connection it happened on to be dropped.

        Compliance statement MQTT-4.8.0-2
        """
        class SubHandler(BasicHandler):
            def process_unsubscribe(self, event):
                raise Exception("boom!")

        h = SubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() +
            Unsubscribe(packet_identifier=1234, topics=[u"foo"]).serialise()
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ502")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.critical)
        self.assertEqual(sent_logs[0]["log_failure"].value.args[0], "boom!")

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertTrue(t.disconnecting)

        # We got the error, we need to flush it so it doesn't make the test
        # error
        self.flushLoggedErrors()

    def test_unsubscription_gets_unsuback_with_same_id(self):
        """
        When an unsubscription is processed, the UnsubACK has the same ID.
        Unsubscriptions are always processed.

        Compliance statements MQTT-3.10.4-4, MQTT-3.10.4-5, MQTT-3.12.4-1
        """
        got_packets = []

        class SubHandler(BasicHandler):
            def process_unsubscribe(self, event):
                got_packets.append(event)
                return succeed(None)

        h = SubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        unsub = Unsubscribe(packet_identifier=1234,
                            topics=[u"foo"]).serialise()

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() + unsub
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 2)
        self.assertFalse(t.disconnecting)

        # UnsubACK that has the same ID
        self.assertIsInstance(events[1], UnsubACK)
        self.assertEqual(events[1].packet_identifier, 1234)

        # The unsubscribe handler should have been called
        self.assertEqual(len(got_packets), 1)
        self.assertEqual(got_packets[0].serialise(), unsub)


class PublishHandlingTests(TestCase):

    def test_qos_0_sends_no_ack(self):
        """
        When a QoS 0 Publish packet is recieved, we don't send back a PubACK.
        """
        got_packets = []

        class PubHandler(BasicHandler):
            def process_publish_qos_0(self, event):
                got_packets.append(event)
                return succeed(None)

        h = PubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        pub = Publish(duplicate=False, qos_level=0, retain=False,
                      topic_name=u"foo", packet_identifier=None,
                      payload=b"bar").serialise()

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() + pub
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertFalse(t.disconnecting)

        # Just the connack, no puback.
        self.assertEqual(len(events), 1)

        # The publish handler should have been called
        self.assertEqual(len(got_packets), 1)
        self.assertEqual(got_packets[0].serialise(), pub)

        # We should get a debug message saying we got the publish
        messages = logs.get_category("MQ201")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["publish"].serialise(), pub)

    def test_qos_0_failure_drops_connection(self):
        """
        Transient failures (like an exception from
        handler.process_publish_qos_0) will cause the connection it happened on
        to be dropped.

        Compliance statement MQTT-4.8.0-2
        """
        class PubHandler(BasicHandler):
            def process_publish_qos_0(self, event):
                raise Exception("boom!")

        h = PubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() +
            Publish(duplicate=False, qos_level=0, retain=False,
                    topic_name=u"foo", packet_identifier=None,
                    payload=b"bar").serialise()
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ503")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.critical)
        self.assertEqual(sent_logs[0]["log_failure"].value.args[0], "boom!")

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertTrue(t.disconnecting)

        # We got the error, we need to flush it so it doesn't make the test
        # error
        self.flushLoggedErrors()

    def test_qos_1_sends_ack(self):
        """
        When a QoS 1 Publish packet is recieved, we send a PubACK with the same
        packet identifier as the original Publish.

        Compliance statement MQTT-3.3.4-1
        Spec part 3.4
        """
        got_packets = []

        class PubHandler(BasicHandler):
            def process_publish_qos_1(self, event):
                got_packets.append(event)
                return succeed(None)

        h = PubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        pub = Publish(duplicate=False, qos_level=1, retain=False,
                      topic_name=u"foo", packet_identifier=2345,
                      payload=b"bar").serialise()

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() + pub
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertFalse(t.disconnecting)

        # ConnACK + PubACK with the same packet ID
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1], PubACK(packet_identifier=2345))

        # The publish handler should have been called
        self.assertEqual(len(got_packets), 1)
        self.assertEqual(got_packets[0].serialise(), pub)

        # We should get a debug message saying we got the publish
        messages = logs.get_category("MQ202")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["publish"].serialise(), pub)

    def test_qos_1_failure_drops_connection(self):
        """
        Transient failures (like an exception from
        handler.process_publish_qos_1) will cause the connection it happened on
        to be dropped.

        Compliance statement MQTT-4.8.0-2
        """
        class PubHandler(BasicHandler):
            def process_publish_qos_1(self, event):
                raise Exception("boom!")

        h = PubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() +
            Publish(duplicate=False, qos_level=1, retain=False,
                    topic_name=u"foo", packet_identifier=2345,
                    payload=b"bar").serialise()
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ504")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.critical)
        self.assertEqual(sent_logs[0]["log_failure"].value.args[0], "boom!")

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertTrue(t.disconnecting)

        # We got the error, we need to flush it so it doesn't make the test
        # error
        self.flushLoggedErrors()

    def test_qos_2_sends_ack(self):
        """
        When a QoS 2 Publish packet is recieved, we send a PubREC with the same
        packet identifier as the original Publish, wait for a PubREL, and then
        send a PubCOMP.

        Compliance statement MQTT-4.3.3-2
        Spec part 3.4, 4.3.3
        """
        got_packets = []

        class PubHandler(BasicHandler):
            def process_publish_qos_2(self, event):
                got_packets.append(event)
                return succeed(None)

        h = PubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        pub = Publish(duplicate=False, qos_level=2, retain=False,
                      topic_name=u"foo", packet_identifier=2345,
                      payload=b"bar").serialise()

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() + pub
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertFalse(t.disconnecting)

        # ConnACK + PubREC with the same packet ID
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1], PubREC(packet_identifier=2345))

        # The publish handler should have been called
        self.assertEqual(len(got_packets), 1)
        self.assertEqual(got_packets[0].serialise(), pub)

        # We should get a debug message saying we got the publish
        messages = logs.get_category("MQ203")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["publish"].serialise(), pub)

        # Clear the client transport
        t.clear()

        # Now we send the PubREL
        pubrel = PubREL(packet_identifier=2345)
        for x in iterbytes(pubrel.serialise()):
            p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertFalse(t.disconnecting)

        # We should get a PubCOMP in response
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], PubCOMP(packet_identifier=2345))

    def test_qos_2_failure_drops_connection(self):
        """
        Transient failures (like an exception from
        handler.process_publish_qos_2) will cause the connection it happened on
        to be dropped.

        Compliance statement MQTT-4.8.0-2
        """
        class PubHandler(BasicHandler):
            def process_publish_qos_2(self, event):
                raise Exception("boom!")

        h = PubHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise() +
            Publish(duplicate=False, qos_level=2, retain=False,
                    topic_name=u"foo", packet_identifier=2345,
                    payload=b"bar").serialise()
        )

        with LogCapturer("trace") as logs:
            for x in iterbytes(data):
                p.dataReceived(x)

        sent_logs = logs.get_category("MQ505")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.critical)
        self.assertEqual(sent_logs[0]["log_failure"].value.args[0], "boom!")

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertTrue(t.disconnecting)

        # We got the error, we need to flush it so it doesn't make the test
        # error
        self.flushLoggedErrors()


class SendPublishTests(TestCase):
    """
    Tests for the WAMP layer sending messages to MQTT clients.
    """

    def test_qos_0_queues_message(self):
        """
        The WAMP layer calling send_publish will queue a message up for
        sending, and send it next time it has a chance.
        """
        got_packets = []

        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # No queued messages
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Connect has happened
        events = cp.data_received(t.value())
        t.clear()
        self.assertFalse(t.disconnecting)
        self.assertIsInstance(events[0], ConnACK)

        # WAMP layer calls send_publish
        p.send_publish(u"hello", 0, b'some bytes')

        # Nothing should have been sent yet, it is queued
        self.assertEqual(t.value(), b'')
        self.assertEqual(len(sessions[u"test123"].queued_messages), 1)

        # Advance the clock
        r.advance(0.1)

        # We should now get the sent Publish
        events = cp.data_received(t.value())
        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0],
            Publish(duplicate=False, qos_level=0, retain=False,
                    packet_identifier=None, topic_name=u"hello",
                    payload=b"some bytes"))

    def test_qos_1_queues_message(self):
        """
        The WAMP layer calling send_publish will queue a message up for
        sending, and send it next time it has a chance.
        """
        got_packets = []

        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # No queued messages
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Make the packet ID be deterministic
        sessions[u"test123"].get_packet_id = lambda: 4567

        # Connect has happened
        events = cp.data_received(t.value())
        t.clear()
        self.assertFalse(t.disconnecting)
        self.assertIsInstance(events[0], ConnACK)

        # WAMP layer calls send_publish, with QoS 1
        p.send_publish(u"hello", 1, b'some bytes')

        # Nothing should have been sent yet, it is queued
        self.assertEqual(t.value(), b'')
        self.assertEqual(len(sessions[u"test123"].queued_messages), 1)

        # Advance the clock
        r.advance(0.1)

        # We should now get the sent Publish
        expected_publish = Publish(
            duplicate=False, qos_level=1, retain=False, packet_identifier=4567,
            topic_name=u"hello", payload=b"some bytes")
        events = cp.data_received(t.value())
        t.clear()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], expected_publish)

        # Server is still awaiting the client's response
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=1, stage=0, message=expected_publish))

        # We send the PubACK, which we don't get a response to
        puback = PubACK(packet_identifier=4567)

        for x in iterbytes(puback.serialise()):
            p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 0)

        # It is no longer queued
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 0)
        self.assertNotIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertFalse(t.disconnecting)

    def test_qos_1_unassociated_puback_warns(self):
        """
        On receiving a PubACK which does not reference any known existing
        Publish the server has sent, it will drop it and raise a warning.

        XXX: Spec is unclear if this is the proper behaviour!
        """
        got_packets = []

        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # Connect has happened
        events = cp.data_received(t.value())
        t.clear()
        self.assertFalse(t.disconnecting)
        self.assertIsInstance(events[0], ConnACK)

        # We send the PubACK, which we don't get a response to (and also
        # doesn't refer to any Publish the client was sent)
        puback = PubACK(packet_identifier=4567)

        with LogCapturer("trace") as logs:
            for x in iterbytes(puback.serialise()):
                p.dataReceived(x)

        events = cp.data_received(t.value())
        self.assertEqual(len(events), 0)

        # A warning is raised
        sent_logs = logs.get_category("MQ300")
        self.assertEqual(len(sent_logs), 1)
        self.assertEqual(sent_logs[0]["log_level"], LogLevel.warn)
        self.assertEqual(sent_logs[0]["pub_id"], 4567)

    def test_qos_2_queues_message(self):
        """
        The WAMP layer calling send_publish will queue a message up for
        sending, and send it next time it has a chance.
        """
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # No queued messages
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Make the packet ID be deterministic
        sessions[u"test123"].get_packet_id = lambda: 4567

        # Connect has happened
        events = cp.data_received(t.value())
        t.clear()
        self.assertFalse(t.disconnecting)
        self.assertIsInstance(events[0], ConnACK)

        # WAMP layer calls send_publish, with QoS 2
        p.send_publish(u"hello", 2, b'some bytes')

        # Nothing should have been sent yet, it is queued
        self.assertEqual(t.value(), b'')
        self.assertEqual(len(sessions[u"test123"].queued_messages), 1)

        # Advance the clock
        r.advance(0.1)

        # We should now get the sent Publish
        expected_publish = Publish(duplicate=False, qos_level=2, retain=False,
                                   packet_identifier=4567, topic_name=u"hello",
                                   payload=b"some bytes")
        events = cp.data_received(t.value())
        t.clear()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], expected_publish)

        # Server is still awaiting the client's response
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=2, stage=0, message=expected_publish))

        # We send the PubREC, which we should get a PubREL back with
        pubrec = PubREC(packet_identifier=4567)

        for x in iterbytes(pubrec.serialise()):
            p.dataReceived(x)

        events = cp.data_received(t.value())
        t.clear()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], PubREL(packet_identifier=4567))

        # Server is still awaiting the client's response, it is not complete
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=2, stage=1, message=expected_publish))

        # We send the PubCOMP, which has no response
        pubcomp = PubCOMP(packet_identifier=4567)

        for x in iterbytes(pubcomp.serialise()):
            p.dataReceived(x)

        # It is no longer queued
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 0)
        self.assertNotIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertFalse(t.disconnecting)

    def test_qos_1_resent_on_disconnect(self):
        """
        If we send a QoS1 Publish and we did not get a PubACK from the client
        before it disconnected, we will resend the Publish packet if it
        connects with a non-clean session.

        Compliance statements: MQTT-4.4.0-1, MQTT-3.3.1-1
        """
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # No queued messages
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Make the packet ID be deterministic
        sessions[u"test123"].get_packet_id = lambda: 4567

        # WAMP layer calls send_publish, with QoS 1
        p.send_publish(u"hello", 1, b'some bytes')

        # Nothing should have been sent yet, it is queued
        self.assertEqual(len(sessions[u"test123"].queued_messages), 1)

        # Advance the clock
        r.advance(0.1)

        # We should now get the sent Publish
        expected_publish = Publish(duplicate=False, qos_level=1, retain=False,
                                   packet_identifier=4567, topic_name=u"hello",
                                   payload=b"some bytes")
        events = cp.data_received(t.value())
        t.clear()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1], expected_publish)

        # Server is still awaiting the client's response, message is not queued
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=1, stage=0, message=expected_publish))
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Disconnect the client
        t.connected = False
        t.loseConnection()
        p.connectionLost(None)

        sessions, r2, t2, p2, cp2 = make_test_items(h, sessions=sessions)

        # We must NOT have a clean session
        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p2.dataReceived(x)

        # The flushing is queued, so we'll have to spin the reactor
        self.assertEqual(p2._flush_publishes.args, (True,))

        r2.advance(0.1)

        # We should have two events; the ConnACK, and the Publish. The ConnACK
        # MUST come first.
        events = cp2.data_received(t2.value())
        t2.clear()
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], ConnACK)
        self.assertIsInstance(events[1], Publish)

        # The Publish packet must have DUP set to True.
        resent_publish = Publish(duplicate=True, qos_level=1, retain=False,
                                 packet_identifier=4567, topic_name=u"hello",
                                 payload=b"some bytes")
        self.assertEqual(events[1], resent_publish)

        # We send the PubACK to this Publish
        puback = PubACK(packet_identifier=4567)

        for x in iterbytes(puback.serialise()):
            p2.dataReceived(x)

        events = cp2.data_received(t2.value())
        self.assertEqual(len(events), 0)

        # It is no longer queued
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 0)
        self.assertNotIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)
        self.assertFalse(t2.disconnecting)

    def test_qos_2_resent_on_disconnect_pubrel(self):
        """
        If we send a QoS2 Publish and we did not get a PubREL from the client
        before it disconnected, we will resend the Publish packet if it
        connects with a non-clean session.

        Compliance statements: MQTT-4.4.0-1, MQTT-3.3.1-1
        """
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # No queued messages
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Make the packet ID be deterministic
        sessions[u"test123"].get_packet_id = lambda: 4567

        # WAMP layer calls send_publish, with QoS 2
        p.send_publish(u"hello", 2, b'some bytes')

        # Nothing should have been sent yet, it is queued
        self.assertEqual(len(sessions[u"test123"].queued_messages), 1)

        # Advance the clock
        r.advance(0.1)

        # We should now get the sent Publish
        expected_publish = Publish(duplicate=False, qos_level=2, retain=False,
                                   packet_identifier=4567, topic_name=u"hello",
                                   payload=b"some bytes")
        events = cp.data_received(t.value())
        t.clear()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1], expected_publish)

        # Server is still awaiting the client's response, message is not queued
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=2, stage=0, message=expected_publish))
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Disconnect the client
        t.connected = False
        t.loseConnection()
        p.connectionLost(None)

        sessions, r2, t2, p2, cp2 = make_test_items(h, sessions=sessions)

        # We must NOT have a clean session
        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p2.dataReceived(x)

        # The flushing is queued, so we'll have to spin the reactor
        self.assertEqual(p2._flush_publishes.args, (True,))

        r2.advance(0.1)

        # We should have two events; the ConnACK, and the Publish. The ConnACK
        # MUST come first.
        events = cp2.data_received(t2.value())
        t2.clear()
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], ConnACK)
        self.assertIsInstance(events[1], Publish)

        # The Publish packet must have DUP set to True.
        resent_publish = Publish(duplicate=True, qos_level=2, retain=False,
                                 packet_identifier=4567, topic_name=u"hello",
                                 payload=b"some bytes")
        self.assertEqual(events[1], resent_publish)

        # Server is still waiting for us to send the PubREC -- QoS2, Stage 0
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)
        self.assertFalse(t2.disconnecting)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=2, stage=0, message=resent_publish))

        # We send the PubREC to this Publish
        pubrec = PubREC(packet_identifier=4567)

        for x in iterbytes(pubrec.serialise()):
            p2.dataReceived(x)

        # Should get a PubREL back
        events = cp2.data_received(t2.value())
        t2.clear()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], PubREL(packet_identifier=4567))

        # Server is still waiting for us to send the PubCOMP -- QoS2, Stage 1
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)
        self.assertFalse(t2.disconnecting)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=2, stage=1, message=resent_publish))

        # We send the PubCOMP to this Publish
        pubcomp = PubCOMP(packet_identifier=4567)

        for x in iterbytes(pubcomp.serialise()):
            p2.dataReceived(x)

        # No more packets sent to us
        events = cp2.data_received(t2.value())
        self.assertEqual(len(events), 0)

        # Not queued, not awaiting ACK
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 0)
        self.assertNotIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)
        self.assertFalse(t2.disconnecting)

    def test_qos_2_resent_on_disconnect_pubcomp(self):
        """
        If we send a QoS2 Publish and we did not get a PubCOMP from the client
        before it disconnected, we will resend the PubREL packet if it
        connects with a non-clean session.

        Compliance statements: MQTT-4.4.0-1, MQTT-3.3.1-1
        """
        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # No queued messages
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Make the packet ID be deterministic
        sessions[u"test123"].get_packet_id = lambda: 4567

        # WAMP layer calls send_publish, with QoS 2
        p.send_publish(u"hello", 2, b'some bytes')

        # Nothing should have been sent yet, it is queued
        self.assertEqual(len(sessions[u"test123"].queued_messages), 1)

        # Advance the clock
        r.advance(0.1)

        # We should now get the sent Publish
        expected_publish = Publish(duplicate=False, qos_level=2, retain=False,
                                   packet_identifier=4567, topic_name=u"hello",
                                   payload=b"some bytes")
        events = cp.data_received(t.value())
        t.clear()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1], expected_publish)

        # Server is waiting for us to send the PubREC -- QoS2, Stage 0
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)
        self.assertFalse(t.disconnecting)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=2, stage=0, message=expected_publish))

        # We send the PubREC to this Publish
        pubrec = PubREC(packet_identifier=4567)

        for x in iterbytes(pubrec.serialise()):
            p.dataReceived(x)

        # Should get a PubREL back
        events = cp.data_received(t.value())
        t.clear()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], PubREL(packet_identifier=4567))

        # Server is waiting for a PubCOMP -- QoS2, Stage 1
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)
        self.assertFalse(t.disconnecting)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=2, stage=1, message=expected_publish))

        # Disconnect the client
        t.connected = False
        t.loseConnection()
        p.connectionLost(None)

        sessions, r2, t2, p2, cp2 = make_test_items(h, sessions=sessions)

        # We must NOT have a clean session
        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=False)).serialise()
        )

        for x in iterbytes(data):
            p2.dataReceived(x)

        # The flushing is queued, so we'll have to spin the reactor
        self.assertEqual(p2._flush_publishes.args, (True,))
        r2.advance(0.1)

        # Should get a resent PubREL back
        events = cp2.data_received(t2.value())
        t2.clear()
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], ConnACK)
        self.assertEqual(events[1], PubREL(packet_identifier=4567))

        # Server is still waiting for us to send the PubCOMP -- QoS2, Stage 1
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 1)
        self.assertIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)
        self.assertFalse(t2.disconnecting)
        self.assertEqual(sessions[u"test123"]._publishes_awaiting_ack[4567],
                         AwaitingACK(qos=2, stage=1, message=expected_publish))

        # We send the PubCOMP to this PubREL
        pubcomp = PubCOMP(packet_identifier=4567)

        for x in iterbytes(pubcomp.serialise()):
            p2.dataReceived(x)

        # No more packets sent to us
        events = cp2.data_received(t2.value())
        self.assertEqual(len(events), 0)

        # Not queued, not awaiting ACK
        self.assertEqual(len(sessions[u"test123"]._publishes_awaiting_ack), 0)
        self.assertNotIn(4567, sessions[u"test123"]._in_flight_packet_ids)
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)
        self.assertFalse(t2.disconnecting)

    def test_non_allowed_qos_not_queued(self):
        """
        A non-QoS 0, 1, or 2 message will be rejected by the publish layer.
        """
        got_packets = []

        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # No queued messages
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Connect has happened
        events = cp.data_received(t.value())
        t.clear()
        self.assertFalse(t.disconnecting)
        self.assertIsInstance(events[0], ConnACK)

        # WAMP layer calls send_publish w/ invalid QoS
        with self.assertRaises(ValueError):
            p.send_publish(u"hello", 5, b'some bytes')

        # Nothing will be sent or queued
        self.assertEqual(t.value(), b'')
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Advance the clock
        r.advance(0.1)

        # Still nothing
        self.assertEqual(t.value(), b'')

    def test_non_allowed_qos_in_queue_dropped(self):
        """
        If a non-QoS 0, 1, or 2 message gets into the queue, it will be
        dropped.
        """
        got_packets = []

        h = BasicHandler()
        sessions, r, t, p, cp = make_test_items(h)

        data = (
            Connect(client_id=u"test123",
                    flags=ConnectFlags(clean_session=True)).serialise()
        )

        for x in iterbytes(data):
            p.dataReceived(x)

        # Add a queued message
        sessions[u"test123"].queued_messages.append(Message(
            topic=u"foo", body=b"bar", qos=3))

        # Connect has happened
        events = cp.data_received(t.value())
        t.clear()
        self.assertFalse(t.disconnecting)
        self.assertIsInstance(events[0], ConnACK)

        # Nothing is sent, one is queued
        self.assertEqual(t.value(), b'')
        self.assertEqual(len(sessions[u"test123"].queued_messages), 1)

        with LogCapturer("trace") as logs:
            # Flush the saved messages
            p._flush_saved_messages()

        # We got the warning
        logs = logs.get_category("MQ303")
        self.assertEqual(len(logs), 1)

        # Nothing queued
        self.assertEqual(len(sessions[u"test123"].queued_messages), 0)

        # Nothing sent
        self.assertEqual(t.value(), b'')


class OutOfOrderAckTests(TestCase):
    pass
