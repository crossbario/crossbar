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

import warnings
import attr

from attr.validators import instance_of, optional
from bitstring import pack

from ._utils import (read_prefixed_data, read_string, build_string,
                     build_header, ParseFailure, SerialisationFailure)

unicode = type(u"")


@attr.s
class Failure(object):
    reason = attr.ib(default=None)


@attr.s
class Disconnect(object):
    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        return build_header(14, (False, False, False, False), 0)

    @classmethod
    def deserialise(cls, flags, data):
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        return cls()


@attr.s
class PingRESP(object):
    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        return build_header(13, (False, False, False, False), 0)

    @classmethod
    def deserialise(cls, flags, data):
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        return cls()


@attr.s
class PingREQ(object):
    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        return build_header(12, (False, False, False, False), 0)

    @classmethod
    def deserialise(cls, flags, data):
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        return cls()


@attr.s
class UnsubACK(object):
    packet_identifier = attr.ib(validator=instance_of(int))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(11, (False, False, False, False), len(payload))

        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []

        # Session identifier
        b.append(pack('uint:16', self.packet_identifier).bytes)

        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        packet_identifier = data.read('uint:16')
        return cls(packet_identifier=packet_identifier)


@attr.s
class Unsubscribe(object):
    packet_identifier = attr.ib(validator=instance_of(int))
    topics = attr.ib(validator=instance_of(list))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(10, (False, False, True, False), len(payload))

        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []

        # Session identifier
        b.append(pack('uint:16', self.packet_identifier).bytes)

        for topic in self.topics:
            if not isinstance(topic, unicode):
                raise SerialisationFailure(self, "Topics must be Unicode")

            b.append(build_string(topic))

        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        if flags != (False, False, True, False):
            raise ParseFailure(cls, "Bad flags")

        topics = []
        packet_identifier = data.read('uint:16')

        while not data.bitpos == len(data):
            topics.append(read_string(data))

        if len(topics) == 0:
            raise ParseFailure(cls, "Must contain a payload.")

        return cls(packet_identifier=packet_identifier, topics=topics)


@attr.s
class PubCOMP(object):
    packet_identifier = attr.ib(validator=instance_of(int))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(7, (False, False, False, False), len(payload))
        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []
        b.append(pack('uint:16', self.packet_identifier).bytes)
        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        """
        Disassemble from an on-wire message.
        """
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        packet_identifier = data.read('uint:16')

        return cls(packet_identifier)


@attr.s
class PubREL(object):
    packet_identifier = attr.ib(validator=instance_of(int))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(6, (False, False, True, False), len(payload))
        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []
        b.append(pack('uint:16', self.packet_identifier).bytes)
        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        """
        Disassemble from an on-wire message.
        """
        if flags != (False, False, True, False):
            raise ParseFailure(cls, "Bad flags")

        packet_identifier = data.read('uint:16')

        return cls(packet_identifier)


@attr.s
class PubREC(object):
    packet_identifier = attr.ib(validator=instance_of(int))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(5, (False, False, False, False), len(payload))
        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []
        b.append(pack('uint:16', self.packet_identifier).bytes)
        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        """
        Disassemble from an on-wire message.
        """
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        packet_identifier = data.read('uint:16')

        return cls(packet_identifier)


@attr.s
class PubACK(object):
    packet_identifier = attr.ib(validator=instance_of(int))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(4, (False, False, False, False), len(payload))
        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []
        b.append(pack('uint:16', self.packet_identifier).bytes)
        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        """
        Disassemble from an on-wire message.
        """
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        packet_identifier = data.read('uint:16')

        return cls(packet_identifier)


@attr.s
class Publish(object):
    duplicate = attr.ib(validator=instance_of(bool))
    qos_level = attr.ib(validator=instance_of(int))
    retain = attr.ib(validator=instance_of(bool))
    topic_name = attr.ib(validator=instance_of(unicode))
    payload = attr.ib(validator=instance_of(bytes))
    packet_identifier = attr.ib(validator=optional(instance_of(int)),
                                default=None)

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        flags = [self.duplicate]
        if self.qos_level == 0:
            flags.extend([False, False])
        elif self.qos_level == 1:
            flags.extend([False, True])
        elif self.qos_level == 2:
            flags.extend([True, False])
        else:
            raise SerialisationFailure(self, "QoS must be 0, 1, or 2")
        flags.append(self.retain)

        payload = self._make_payload()
        header = build_header(3, flags, len(payload))

        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []

        # Topic Name
        b.append(build_string(self.topic_name))

        if self.packet_identifier:
            if self.qos_level > 0:
                # Session identifier
                b.append(pack('uint:16', self.packet_identifier).bytes)
            else:
                raise SerialisationFailure(self, "Packet Identifier on non-QoS 1/2 packet")
        else:
            if self.qos_level > 0:
                raise SerialisationFailure(self, "QoS level > 0 but no Packet Identifier")

        # Payload (bytes)
        b.append(self.payload)

        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):

        total_length = len(data)

        duplicate = flags[0]

        if flags[1:3] == (False, False):
            qos_level = 0
        elif flags[1:3] == (False, True):
            qos_level = 1
        elif flags[1:3] == (True, False):
            qos_level = 2
        elif flags[1:3] == (True, True):
            raise ParseFailure(cls, "Invalid QoS value")

        retain = flags[3]

        topic_name = read_string(data)

        if qos_level in [1, 2]:
            packet_identifier = data.read('uint:16')
        else:
            packet_identifier = None

        payload = data.read(total_length - data.bitpos).bytes

        return cls(duplicate=duplicate, qos_level=qos_level, retain=retain,
                   topic_name=topic_name, packet_identifier=packet_identifier,
                   payload=payload)


@attr.s
class SubACK(object):
    packet_identifier = attr.ib(validator=instance_of(int))
    return_codes = attr.ib(validator=instance_of(list))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(9, (False, False, False, False), len(payload))

        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []

        # Session identifier
        b.append(pack('uint:16', self.packet_identifier).bytes)

        for code in self.return_codes:
            b.append(pack('uint:8', code).bytes)

        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        return_codes = []
        packet_identifier = data.read('uint:16')

        while not data.bitpos == len(data):
            return_code = data.read('uint:8')
            return_codes.append(return_code)

        return cls(packet_identifier=packet_identifier,
                   return_codes=return_codes)


@attr.s
class SubscriptionTopicRequest(object):
    topic_filter = attr.ib(validator=instance_of(unicode))
    max_qos = attr.ib(validator=instance_of(int))

    def serialise(self):
        """
        Assemble this into an on-wire message part.
        """
        b = []

        # Topic filter, as UTF-8
        b.append(build_string(self.topic_filter))

        # Reserved section + max QoS
        b.append(pack('uint:6, uint:2', 0, self.max_qos).bytes)

        return b"".join(b)


@attr.s
class Subscribe(object):
    packet_identifier = attr.ib(validator=instance_of(int))
    topic_requests = attr.ib(validator=instance_of(list))

    def serialise(self):
        """
        Assemble this into an on-wire message.
        """
        payload = self._make_payload()
        header = build_header(8, (False, False, True, False), len(payload))

        return header + payload

    def _make_payload(self):
        """
        Build the payload from its constituent parts.
        """
        b = []

        # Session identifier
        b.append(pack('uint:16', self.packet_identifier).bytes)

        for request in self.topic_requests:
            b.append(request.serialise())

        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        if flags != (False, False, True, False):
            raise ParseFailure(cls, "Bad flags")

        pairs = []
        packet_identifier = data.read('uint:16')

        def parse_pair():

            topic_filter = read_string(data)
            reserved = data.read("uint:6")
            max_qos = data.read("uint:2")

            if reserved:
                raise ParseFailure(cls, "Data in QoS Reserved area")

            if max_qos not in [0, 1, 2]:
                raise ParseFailure(cls, "Invalid QoS")

            pairs.append(SubscriptionTopicRequest(topic_filter=topic_filter,
                                                  max_qos=max_qos))

        parse_pair()

        while not data.bitpos == len(data):
            parse_pair()

        return cls(packet_identifier=packet_identifier, topic_requests=pairs)


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
        """
        Take an on-wire message and turn it into an instance of this class.
        """
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        reserved = data.read(7).uint

        if reserved:
            raise ParseFailure(cls, "Reserved flag used.")

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
    username = attr.ib(validator=instance_of(bool), default=False)
    password = attr.ib(validator=instance_of(bool), default=False)
    will = attr.ib(validator=instance_of(bool), default=False)
    will_retain = attr.ib(validator=instance_of(bool), default=False)
    will_qos = attr.ib(validator=instance_of(int), default=False)
    clean_session = attr.ib(validator=instance_of(bool), default=False)
    reserved = attr.ib(validator=instance_of(bool), default=False)

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
            raise ParseFailure(cls, "Reserved flag in CONNECT used")

        return built


@attr.s
class Connect(object):

    client_id = attr.ib(validator=instance_of(unicode))
    flags = attr.ib(validator=instance_of(ConnectFlags))
    keep_alive = attr.ib(validator=instance_of(int), default=0)
    will_topic = attr.ib(validator=optional(instance_of(unicode)),
                         default=None)
    will_message = attr.ib(validator=optional(instance_of(bytes)),
                           default=None)
    username = attr.ib(validator=optional(instance_of(unicode)),
                       default=None)
    password = attr.ib(validator=optional(instance_of(unicode)),
                       default=None)

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

        if self.flags.will:
            b.append(build_string(self.will_topic))

            # Will message is a uint16 prefixed bytestring
            b.append(pack('uint:16', len(self.will_message)).bytes)
            b.append(self.will_message)

        if self.flags.username:
            b.append(build_string(self.username))

        # Technically this should be binary data but we will only accept UTF-8
        if self.flags.password:
            b.append(build_string(self.password))

        return b"".join(b)

    @classmethod
    def deserialise(cls, flags, data):
        """
        Disassemble from an on-wire message.
        """
        if flags != (False, False, False, False):
            raise ParseFailure(cls, "Bad flags")

        protocol = read_string(data)

        if protocol != u"MQTT":
            print(protocol)
            raise ParseFailure(cls, "Bad protocol name")

        protocol_level = data.read('uint:8')

        if protocol_level != 4:
            raise ParseFailure(cls, "Bad protocol level")

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
