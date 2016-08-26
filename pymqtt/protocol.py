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

from pymqtt._events import (
    Failure, FailedParsing,
    Connect
)

from struct import unpack
import bitstring
import attr

# State machine events
WAITING_FOR_NEW_PACKET = 0
COLLECTING_REST_OF_PACKET = 1

P_CONNECT = 1

packet_handlers = {
    P_CONNECT: Connect
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
                flags = (self._data.read("bool"),
                         self._data.read("bool"),
                         self._data.read("bool"),
                         self._data.read("bool"))

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

                dataToGive = self._data.read(value * 8)
                packet_handler = packet_handlers[packet_type]
                try:
                    deser = packet_handler.deserialise(flags, dataToGive)
                    events.append(deser)
                except FailedParsing as e:
                    events.append(Failure(e.args[0]))
                    return events
                except bitstring.ReadError as e:
                    # whoops the parsing fell off the amount of data
                    events.append(Failure("Corrupt data, fell off the end: " +
                                          str(e)))
                    return events

                self._packet_header = None
                self._data = self._data[self._data.bitpos:]
                self._packet_count += 1
            else:
                return events
