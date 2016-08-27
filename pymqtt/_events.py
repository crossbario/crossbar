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

import attr
import warnings

from attr.validators import instance_of, optional


from bitstring import pack

from pymqtt._utils import read_prefixed_data, read_string

unicode = type(u"")


class ParseFailure(Exception):
    pass


def build_string(string):

    string = string.encode('utf8')
    return pack('uint:16', len(string)).bytes + string


def build_header(packet_id, flags, payload_length):

    header = pack('uint:4, bool, bool, bool, bool', packet_id, *flags)

    byte_count = 0

    byted = []

    while payload_length > 0:

        encodedByte = payload_length % 128
        payload_length = payload_length // 128
        if payload_length > 0:
            encodedByte = encodedByte | 128
        byted.append(encodedByte)

    return header.bytes + pack(','.join(['uint:8'] * len(byted)), *byted).bytes


@attr.s
class Failure(object):
    reason = attr.ib(default=None)


@attr.s
class ConnACK(object):
    session_present = attr.ib(validator=instance_of(bool))
    return_code = attr.ib(validator=instance_of(int))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(2, (False, False, False, False), len(payload))

        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []

        # Flags -- 7 bit reserved + Session Present flag
        b.append(pack('uint:7, bool', 0, self.session_present).bytes)

        # Return code
        b.append(pack('uint:8', self.return_code).bytes)

        return b"".join(b)


    @classmethod
    def deserialise(cls, flags, data):

        reserved = data.read(7).uint

        if reserved:
            raise ParseFailure("Reserved flag used.")

        built = cls(session_present=data.read(1).bool,
                    return_code=data.read(8).uint)

        # XXX: Do some more verification, re conn flags

        if not data.bitpos == len(data):
            # There's some wacky stuff going on here -- data they included, but
            # didn't put flags for, maybe?
            warnings.warn(("Quirky server CONNACK -- packet length was "
                           "%d bytes but only had %d bytes of useful data") % (
                               data.bitpos, len(data)))

        return built


@attr.s
class ConnectFlags(object):
    username = attr.ib(validator=instance_of(bool))
    password = attr.ib(validator=instance_of(bool))
    will = attr.ib(validator=instance_of(bool))
    will_retain = attr.ib(validator=instance_of(bool))
    will_qos = attr.ib(validator=instance_of(int))
    clean_session = attr.ib(validator=instance_of(bool))
    reserved = attr.ib(validator=instance_of(bool))

    def serialise(self):
        """
        Assemble this into an on-wire message portion.
        """
        return pack(
            'bool, bool, bool, uint:2, bool, bool, bool',
            self.username, self.password, self.will_retain, self.will_qos,
            self.will, self.clean_session, self.reserved).bytes

    @classmethod
    def deserialise(cls, data):
        built = cls(
            username=data.read(1).bool,
            password=data.read(1).bool,
            will_retain=data.read(1).bool,
            will_qos=data.read(2).uint,
            will=data.read(1).bool,
            clean_session=data.read(1).bool,
            reserved=data.read(1).bool
        )

        # XXX: Do some more conformance checking here
        # Need to worry about invalid flag combinations

        if built.reserved:
            # MQTT-3.1.2-3, reserved flag must not be used
            raise ParseFailure("Reserved flag in CONNECT used")

        return built


@attr.s
class Connect(object):

    flags = attr.ib(validator=instance_of(ConnectFlags))
    keep_alive = attr.ib(validator=instance_of(int))
    client_id = attr.ib(validator=instance_of(unicode))
    will_topic = attr.ib(validator=optional(instance_of(unicode)))
    will_message = attr.ib(validator=optional(instance_of(unicode)))
    username = attr.ib(validator=optional(instance_of(unicode)))
    password = attr.ib(validator=optional(instance_of(unicode)))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(1, (False, False, False, False), len(payload))

        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []

        # Protocol name (MQTT)
        b.append(build_string(u"MQTT"))

        # Protocol Level (4 == 3.1.1)
        b.append(pack('uint:8', 4).bytes)

        # CONNECT flags
        b.append(self.flags.serialise())

        # Keep Alive time
        b.append(pack('uint:16', self.keep_alive).bytes)

        # Client ID
        b.append(build_string(self.client_id))

        # XXX: Implement other fields

        return b"".join(b)


    @classmethod
    def deserialise(cls, flags, data):
        """
        Disassemble from an on-wire message.
        """
        if flags != (False, False, False, False):
            return Failure("Bad flags")

        protocol = read_string(data)

        if protocol != u"MQTT":
            return Failure("Bad protocol name")

        protocol_level = data.read('uint:8')

        if protocol_level != 4:
            return Failure("Bad protocol level")

        flags = ConnectFlags.deserialise(data.read(8))

        # Keep alive, in seconds
        keep_alive = data.read('uint:16')

        # The client ID
        client_id = read_string(data)

        if flags.will:
            # MQTT-3.1.3-10, topic must be UTF-8
            will_topic = read_string(data)
            will_message = read_prefixed_data(data)
        else:
            will_topic = None
            will_message = None

        # Username
        if flags.username:
            username = read_string(data)
        else:
            username = None

        # Password
        if flags.password:
            password = read_string(data)
        else:
            password = None

        if not data.bitpos == len(data):
            # There's some wacky stuff going on here -- data they included, but
            # didn't put flags for, maybe?
            warnings.warn(("Quirky client CONNECT -- packet length was "
                           "%d bytes but only had %d bytes of useful data") % (
                               data.bitpos, len(data)))

        # The event
        return cls(flags=flags, keep_alive=keep_alive, client_id=client_id,
                   will_topic=will_topic, will_message=will_message,
                   username=username, password=password)
