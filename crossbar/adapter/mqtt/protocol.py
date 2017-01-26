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

from __future__ import absolute_import, division, print_function

from ._events import (
    Failure, ParseFailure,
    Connect, ConnACK,
    Subscribe, SubACK,
    Unsubscribe, UnsubACK,
    Publish, PubACK,
    PubREC, PubREL, PubCOMP,
    PingREQ, PingRESP,
    Disconnect,
)

import bitstring

__all__ = [
    "MQTTParser",
]


class _NeedMoreData(Exception):
    """
    We need more data before we can get the bytes length.
    """


# State machine events
WAITING_FOR_NEW_PACKET = 0
COLLECTING_REST_OF_PACKET = 1
PROTOCOL_VIOLATION = 2

P_CONNECT = 1
P_CONNACK = 2
P_PUBLISH = 3
P_PUBACK = 4
P_PUBREC = 5
P_PUBREL = 6
P_PUBCOMP = 7
P_SUBSCRIBE = 8
P_SUBACK = 9
P_UNSUBSCRIBE = 10
P_UNSUBACK = 11
P_PINGREQ = 12
P_PINGRESP = 13
P_DISCONNECT = 14

server_packet_handlers = {
    P_CONNECT: Connect,
    P_PUBLISH: Publish,
    P_PUBACK: PubACK,
    P_SUBSCRIBE: Subscribe,
    P_UNSUBSCRIBE: Unsubscribe,
    P_PINGREQ: PingREQ,
    P_PUBREL: PubREL,
    P_PUBREC: PubREC,
    P_PUBCOMP: PubCOMP,
    P_DISCONNECT: Disconnect,
}

client_packet_handlers = {
    P_CONNACK: ConnACK,
    P_PUBLISH: Publish,
    P_PUBACK: PubACK,
    P_SUBACK: SubACK,
    P_UNSUBACK: UnsubACK,
    P_PINGRESP: PingRESP,
    P_PUBREC: PubREC,
    P_PUBREL: PubREL,
    P_PUBCOMP: PubCOMP,
}


def _parse_header(data):
    # New packet
    packet_type = data.read('uint:4')
    flags = (data.read("bool"),
             data.read("bool"),
             data.read("bool"),
             data.read("bool"))

    multiplier = 1
    value = 0
    encodedByte = -1

    while (encodedByte & 128) != 0:
        try:
            encodedByte = data.read('uint:8')
        except bitstring.ReadError:
            # Not enough data yet, raise that up...
            raise _NeedMoreData()
        value += (encodedByte & 127) * multiplier
        multiplier = multiplier * 128

        if multiplier > (128 * 128 * 128):
            raise ParseFailure("Too big packet size")

    return (packet_type, flags, value)


class MQTTParser(object):

    _packet_handlers = server_packet_handlers
    _first_pkt = P_CONNECT

    def __init__(self):

        self._data = bitstring.BitStream()
        self._bytes_expected = 0
        self._state = WAITING_FOR_NEW_PACKET
        self._packet_header = None
        self._packet_count = 0

    def data_received(self, data):

        if self._state is PROTOCOL_VIOLATION:
            # Conformance statement MQTT-4.8.0-1: Must close the connection on
            # a protocol violation. For us, if we keep getting data somehow
            # (e.g. flushed input buffers), just drop the data.
            return []

        events = []

        self._data.append(bitstring.BitArray(bytes=data))
        self._data = self._data[self._data.bitpos:]

        while True:

            if self._state == WAITING_FOR_NEW_PACKET and len(self._data) > 8:

                try:
                    self._packet_header = _parse_header(self._data)
                except _NeedMoreData:
                    # Reset the data stream
                    self._data.bitpos = 0
                    # Return the events we have
                    return events
                except ParseFailure as e:
                    events.append(Failure(e.args[0]))
                    self._state = PROTOCOL_VIOLATION
                    return events

                self._bytes_expected = self._packet_header[2]
                self._data = self._data[self._data.bitpos:]
                self._state = COLLECTING_REST_OF_PACKET

            elif self._state == COLLECTING_REST_OF_PACKET:

                self._data = self._data[self._data.bitpos:]

                if len(self._data) < self._bytes_expected * 8:
                    return events

            else:
                self._data = self._data[self._data.bitpos:]
                return events

            if self._bytes_expected * 8 <= len(self._data):

                self._state = WAITING_FOR_NEW_PACKET

                packet_type, flags, value = self._packet_header

                if self._packet_count == 0 and packet_type != self._first_pkt:
                    self._state = PROTOCOL_VIOLATION
                    return [Failure("Connect packet was not first")]

                if self._packet_count > 0 and packet_type == self._first_pkt:
                    events.append(Failure("Multiple Connect packets"))
                    self._state = PROTOCOL_VIOLATION
                    return events

                try:
                    dataToGive = self._data.read(value * 8)

                    if packet_type not in self._packet_handlers:
                        self._state = PROTOCOL_VIOLATION
                        events.append(Failure("Unimplemented packet type %d" % (
                            packet_type,)))
                        return events

                    packet_handler = self._packet_handlers[packet_type]
                    deser = packet_handler.deserialise(flags, dataToGive)
                    events.append(deser)
                except ParseFailure as e:
                    if len(e.args) == 1:
                        events.append(Failure(e.args[0]))
                    else:
                        events.append(Failure(
                            e.args[1] + " in " + e.args[0].__name__))
                    self._state = PROTOCOL_VIOLATION
                    return events
                except bitstring.ReadError as e:
                    # whoops the parsing fell off the amount of data
                    events.append(Failure("Corrupt data, fell off the end: " +
                                          str(e)))
                    self._state = PROTOCOL_VIOLATION
                    return events

                self._packet_header = None
                self._data = self._data[self._data.bitpos:]
                self._packet_count += 1
            else:
                return events


class MQTTClientParser(MQTTParser):
    _first_pkt = P_CONNACK
    _packet_handlers = client_packet_handlers
