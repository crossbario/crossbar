#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from bitstring import BitStream

from crossbar.bridge.mqtt.protocol import (
    Connect,
    ConnACK,
    Subscribe,
    SubACK,
    Unsubscribe,
    UnsubACK,
    Publish,
    PubACK,
)

from twisted.trial.unittest import TestCase


class ConnectTests(TestCase):
    """
    Tests for Connect.
    """
    def test_round_trip(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        # Header for CONNECT
        header = b"\x10\x13"
        # CONNECT without header, valid, client ID is "test123", clean session
        good = b"\x00\x04MQTT\x04\x02\x00\x00\x00\x07test123"

        event = Connect.deserialise((False, False, False, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)


class ConnectAckTests(TestCase):
    """
    Tests for ConnectAck.
    """
    def test_round_trip(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        header = b"\x20\x02"
        good = b"\x00\x00"
        event = ConnACK.deserialise((False, False, False, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)


class SubscribeTests(TestCase):
    """
    Tests for Subscribe.
    """
    def test_round_trip(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        header = b"\x82\x10"
        good = (b"\x00\x01\x00\x0b\x66\x6f\x6f\x2f\x62\x61\x72\x2f\x62\x61" b"\x7a\x00")
        event = Subscribe.deserialise((False, False, True, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)


class SubACKTests(TestCase):
    """
    Tests for SubACK.
    """
    def test_round_trip(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        header = b"\x90\x03"
        good = b"\x00\x01\x00"
        event = SubACK.deserialise((False, False, False, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)


class PublishTests(TestCase):
    """
    Tests for Publish.
    """
    def test_round_trip(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        # DUP0, QoS 0, Retain 0
        header = b"\x30\x1a"
        good = (b"\x00\x0b\x66\x6f\x6f\x2f\x62\x61\x72\x2f\x62\x61\x7a\x68\x65"
                b"\x6c\x6c\x6f\x20\x66\x72\x69\x65\x6e\x64\x73")

        event = Publish.deserialise((False, False, False, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)

    def test_round_trip_qos1(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        # DUP0, QoS 1, Retain 0
        header = b"\x32\x1c"
        good = (b"\x00\x0b\x66\x6f\x6f\x2f\x62\x61\x72\x2f\x62\x61\x7a\x00\x02"
                b"\x68\x65\x6c\x6c\x6f\x20\x66\x72\x69\x65\x6e\x64\x73")

        event = Publish.deserialise((False, False, True, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)


class PubACKTests(TestCase):
    """
    Tests for PubACK.
    """
    def test_round_trip(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        header = b"\x40\x02"
        good = b"\x00\x02"

        event = PubACK.deserialise((False, False, False, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)


class UnsubscribeTests(TestCase):
    """
    Tests for Unsubscribe.
    """
    def test_round_trip(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        header = b"\xa2\x19"
        good = (b"\x00\x03\x00\x15\x63\x6f\x6d\x2e\x65\x78\x61\x6d\x70\x6c\x65"
                b"\x2e\x6f\x6e\x63\x6f\x75\x6e\x74\x65\x72")

        event = Unsubscribe.deserialise((False, False, True, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)


class UnsubACKTests(TestCase):
    """
    Tests for UnsubACK.
    """
    def test_round_trip(self):
        """
        Deserialising a message and serialising it again results in the same
        binary message.
        """
        header = b"\xb0\x02"
        good = b"\x00\x03"

        event = UnsubACK.deserialise((False, False, False, False), BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)
