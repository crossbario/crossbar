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

from bitstring import BitStream
import attr

from pymqtt._events import Connect, ConnACK, Subscribe

from twisted.trial.unittest import TestCase

def iterbytes(b):
    for i in range(len(b)):
        yield b[i:i+1]


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
