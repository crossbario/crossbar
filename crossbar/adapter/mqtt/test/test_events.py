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

from bitstring import BitStream

from crossbar.adapter.mqtt.protocol import (
    Connect, ConnACK,
    Subscribe, SubACK,
    Unsubscribe, UnsubACK,
    Publish, PubACK,
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

        event = Connect.deserialise((False, False, False, False),
                                    BitStream(bytes=good))
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
        event = ConnACK.deserialise((False, False, False, False),
                                    BitStream(bytes=good))
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
        good = (b"\x00\x01\x00\x0b\x66\x6f\x6f\x2f\x62\x61\x72\x2f\x62\x61"
                b"\x7a\x00")
        event = Subscribe.deserialise((False, False, True, False),
                                      BitStream(bytes=good))
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
        event = SubACK.deserialise((False, False, False, False),
                                   BitStream(bytes=good))
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

        event = Publish.deserialise((False, False, False, False),
                                    BitStream(bytes=good))
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

        event = Publish.deserialise((False, False, True, False),
                                    BitStream(bytes=good))
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

        event = PubACK.deserialise((False, False, False, False),
                                   BitStream(bytes=good))
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

        event = Unsubscribe.deserialise((False, False, True, False),
                                        BitStream(bytes=good))
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

        event = UnsubACK.deserialise((False, False, False, False),
                                     BitStream(bytes=good))
        self.assertEqual(event.serialise(), header + good)
