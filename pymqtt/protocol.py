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

from __future__ import absolute_import, division, print_function

from struct import unpack
import bitstring
import attr

# These are event IDs that pyMQTT may return.
events = ["STOP_AND_CATCH_FIRE", "CONNECT"]


# State machine events
WAITING_FOR_NEW_PACKET = 0
COLLECTING_REST_OF_PACKET = 1


@attr.s
class Failure(object):
    reason = attr.ib(default=None)


@attr.s
class Connect(object):

    flags = attr.ib()
    keep_alive = attr.ib()
    client_id = attr.ib()
    will_topic = attr.ib()
    will_message = attr.ib()
    username = attr.ib()
    password = attr.ib()

    def write(self):
        """
        Assemble this into an on-wire message.
        """


def read_prefixed_data(data):
    """
    Reads the next 16-bit-uint prefixed data block from `data`.
    """
    data_length = data.read('uint:16')
    return data.read(data_length * 8).bytes

def read_string(data):
    """
    Reads the next MQTT pascal-style string from `data`.
    """
    return read_prefixed_data(data).decode('utf8')


def packet_CONNECT(flags, data):

    if flags.int != 0:
        return Failure("Bad flags")

    protocol = read_string(data)

    if protocol != u"MQTT":
        return Failure("Bad protocol name")

    protocol_level = data.read(8).uint

    if protocol_level != 4:
        return Failure("Bad protocol level")

    flags = {
        "User Name": data.read(1).bool,
        "Password": data.read(1).bool,
        "Will Retain": data.read(1).bool,
        "Will QoS": data.read(2).uint,
        "Will": data.read(1).bool,
        "Clean Session": data.read(1).bool,
        "Reserved": data.read(1).bool,
    }

    # Conformance checking
    if flags["Reserved"] == 1:
        # MQTT-3.1.2-3, reserved flag must not be used
        return Failure("Reserved flag in CONNECT used")

    # Keep alive, in seconds
    keep_alive = data.read('uint:16')

    # The client ID
    client_id = read_string(data)

    if flags["Will"] == 1:
        # MQTT-3.1.3-10, topic must be UTF-8
        will_topic = read_string(data)
        will_message = read_prefixed_data(data)
    else:
        will_topic = None
        will_message = None

    # Username
    if flags["User Name"] == 1:
        username = read_string(data)
    else:
        username = None

    # Password
    if flags["Password"] == 1:
        password = read_string(data)
    else:
        password = None

    # The event
    return Connect(flags=flags, keep_alive=keep_alive, client_id=client_id,
                   will_topic=will_topic, will_message=will_message,
                   username=username, password=password)


P_CONNECT = 1



packet_handlers = {
    P_CONNECT: packet_CONNECT
}

class MQTTServerProtocol(object):

    def __init__(self):

        self._data = bitstring.BitStream()
        self._bytes_expected = 0
        self._state = WAITING_FOR_NEW_PACKET
        self._packet_header = None
        self._packet_count = 0

    def data_received(self, data):

        events = []

        self._data.append(bitstring.BitArray(bytes=data))

        while True:

            if self._state == WAITING_FOR_NEW_PACKET and len(self._data) > 8:

                # New packet
                packet_type = self._data.read('uint:4')
                flags = self._data.read(4)

                final_length = 0

                multiplier = 1
                value = 0
                encodedByte = -1

                while (encodedByte & 128) != 0:
                    encodedByte = self._data.read('uint:8')
                    value += (encodedByte & 127) * multiplier
                    multiplier = multiplier * 128

                    if multiplier > (128*128*128):
                        events.append(Failure("Too big packet size"))
                        return events

                self._bytes_expected = value * 8

                self._packet_header = (packet_type, flags, value)

                self._data = self._data[self._data.bitpos:]
                self._state = COLLECTING_REST_OF_PACKET

            elif self._state == COLLECTING_REST_OF_PACKET:

                self._data = self._data[self._data.bitpos:]

                if len(self._data) < self._bytes_expected:
                    return events

            else:
                self._data = self._data[self._data.bitpos:]
                return events

            if self._bytes_expected <= len(self._data):

                self._state = WAITING_FOR_NEW_PACKET

                packet_type, flags, value = self._packet_header

                if self._packet_count > 0 and packet_type != P_CONNECT:
                    return [Failure("Connect packet was not first")]

                dataToGive = self._data.read(value*8)

                events.append(packet_handlers[packet_type](flags, dataToGive))

                self._packet_header = None
                self._data = self._data[self._data.bitpos:]
                self._packet_count += 1
            else:
                return events
