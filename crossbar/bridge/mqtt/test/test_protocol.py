#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import attr

from binascii import unhexlify

from crossbar.bridge.mqtt.protocol import (
    MQTTParser,
    Failure,
    PROTOCOL_VIOLATION,
    Connect,
    Subscribe,
    Unsubscribe,
    PingREQ,
)
from crossbar.bridge.mqtt._utils import iterbytes

from twisted.trial.unittest import TestCase


class MQTTEventTestBase(object):
    def _assert_event(self, event, eventType, contents):
        self.assertIsInstance(event, eventType)
        self.assertEqual(attr.asdict(event), contents)


class ProtocolTests(TestCase, MQTTEventTestBase):

    maxDiff = None

    def test_correct_connect(self):
        """
        The most basic possible connect -- MQTT 3.1.1, no QoS/username/password
        and compliant with the spec.
        """
        events = []
        p = MQTTParser()

        good = b"\x10\x13\x00\x04MQTT\x04\x02\x00x\x00\x07test123"

        for x in iterbytes(good):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]), {
                'username': None,
                'password': None,
                'will_message': None,
                'will_topic': None,
                'client_id': "test123",
                'keep_alive': 120,
                'flags': {
                    'username': False,
                    'password': False,
                    'will': False,
                    'will_qos': 0,
                    'will_retain': False,
                    'clean_session': True,
                    'reserved': False
                }
            })

    def test_malformed_packet(self):
        """
        A parsing failure (e.g. an incorrect flag leads us to read off the end)
        is safely handled.
        """
        events = []
        p = MQTTParser()

        bad = b"\x10\x13\x00\x04MQTT\x04\x02\x00x\x00\x09test123"

        for x in iterbytes(bad):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(attr.asdict(events[0]),
                         {'reason': ("Corrupt data, fell off the end: Cannot read 72 "
                                     "bits, only 56 available.")})
        self.assertEqual(p._state, PROTOCOL_VIOLATION)

    def test_quirks_mode_connect(self):
        """
        Nyamuk sends two extra bytes at the end of the CONNECT packet (that
        cannot mean anything), we should just cope with it.
        """
        events = []
        p = MQTTParser()

        #             vv correct length                           vv why???
        good = b"\x10\x15\x00\x04MQTT\x04\x02\x00x\x00\x07test123\x00\x00"

        for x in iterbytes(good):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]), {
                'username': None,
                'password': None,
                'will_message': None,
                'will_topic': None,
                'client_id': "test123",
                'keep_alive': 120,
                'flags': {
                    'username': False,
                    'password': False,
                    'will': False,
                    'will_qos': 0,
                    'will_retain': False,
                    'clean_session': True,
                    'reserved': False
                }
            })
        warnings = self.flushWarnings()
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["message"], ("Quirky client CONNECT -- packet length was 152 "
                                                  "bytes but only had 168 bytes of useful data"))

    def test_connect_ping(self):
        """
        A connect, then a ping.
        """
        events = []
        p = MQTTParser()

        data = (
            # CONNECT
            b"101300044d51545404020002000774657374313233"
            # PINGREQ
            b"c000")

        for x in iterbytes(unhexlify(data)):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 2)

        self._assert_event(
            events.pop(0), Connect, {
                'username': None,
                'password': None,
                'will_message': None,
                'will_topic': None,
                'client_id': "test123",
                'keep_alive': 2,
                'flags': {
                    'username': False,
                    'password': False,
                    'will': False,
                    'will_qos': 0,
                    'will_retain': False,
                    'clean_session': True,
                    'reserved': False
                }
            })

        self._assert_event(events.pop(0), PingREQ, {})

        # We want to have consumed all the events
        self.assertEqual(len(events), 0)

    def test_connect_subscribe_unsubscribe(self):
        """
        A connect, then a subscribe and an immediate unsubscribe.
        """
        events = []
        p = MQTTParser()

        data = (
            # CONNECT
            b"101300044d51545404020002000774657374313233"
            # SUBSCRIBE
            b"820d00010008746573742f31323300"
            # UNSUBSCRIBE
            b"a20c00030008746573742f313233")

        for x in iterbytes(unhexlify(data)):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 3)

        self._assert_event(
            events.pop(0), Connect, {
                'username': None,
                'password': None,
                'will_message': None,
                'will_topic': None,
                'client_id': "test123",
                'keep_alive': 2,
                'flags': {
                    'username': False,
                    'password': False,
                    'will': False,
                    'will_qos': 0,
                    'will_retain': False,
                    'clean_session': True,
                    'reserved': False
                }
            })

        self._assert_event(events.pop(0), Subscribe, {
            'packet_identifier': 1,
            'topic_requests': [{
                'topic_filter': 'test/123',
                'max_qos': 0,
            }]
        })

        self._assert_event(events.pop(0), Unsubscribe, {
            'packet_identifier': 3,
            'topics': ['test/123'],
        })

        # We want to have consumed all the events
        self.assertEqual(len(events), 0)


class MQTTConformanceTests(TestCase, MQTTEventTestBase):
    """
    Tests for MQTT conformance.
    """
    def test_connect_not_first(self):
        """
        Sending a packet that is not a CONNECT as the first packet is a
        protocol violation.

        Conformance Statement MQTT-3.1.0-1
        """
        events = []
        p = MQTTParser()

        data = (
            # SUBSCRIBE
            b"820d00010008746573742f31323300")

        for x in iterbytes(unhexlify(data)):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)

        # Reserved packet
        self._assert_event(events.pop(0), Failure, {'reason': "Connect packet was not first"})

        # We want to have consumed all the events
        self.assertEqual(len(events), 0)
        self.assertEqual(p._state, PROTOCOL_VIOLATION)

    def test_multiple_connects(self):
        """
        Sending multiple CONNECT packets is a protocol violation.

        Conformance Statement MQTT-3.1.0-2
        """
        events = []
        p = MQTTParser()

        data = (
            # CONNECT
            b"101300044d51545404020002000774657374313233"
            # CONNECT
            b"101300044d51545404020002000774657374313233")

        for x in iterbytes(unhexlify(data)):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 2)

        # First, successful connect
        self.assertIsInstance(events.pop(0), Connect)

        # Reserved packet
        self._assert_event(events.pop(0), Failure, {'reason': "Multiple Connect packets"})

        # We want to have consumed all the events
        self.assertEqual(len(events), 0)
        self.assertEqual(p._state, PROTOCOL_VIOLATION)

    def test_connect_reserved_area(self):
        """
        The reserved section in the CONNECT packet must not be used.

        Conformance Statement MQTT-3.1.2-3
        """
        events = []
        p = MQTTParser()

        data = (
            # CONNECT using the second nibble
            b"111300044d51545404020002000774657374313233")

        for x in iterbytes(unhexlify(data)):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)

        # Reserved packet
        self._assert_event(events.pop(0), Failure, {'reason': "Bad flags in Connect"})

        # We want to have consumed all the events
        self.assertEqual(len(events), 0)
        self.assertEqual(p._state, PROTOCOL_VIOLATION)

    def test_too_large_header(self):
        """
        The reserved section in the CONNECT packet must not be used.

        Conformance Statement MQTT-3.1.2-3
        """
        events = []
        p = MQTTParser()

        data = (
            # CONNECT using the second nibble, plus junk we should never read
            b"10ffffffff000000000000000000")

        for x in iterbytes(unhexlify(data)):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)

        # Reserved packet
        self._assert_event(events.pop(0), Failure, {'reason': "Too big packet size"})

        # We want to have consumed all the events
        self.assertEqual(len(events), 0)
        self.assertEqual(p._state, PROTOCOL_VIOLATION)

    def test_invalid_utf8_continuation(self):
        """
        Invalid UTF-8 sequences (i.e. those containing UTF-16 surrogate pairs
        encoded in UTF-8) are a protocol violation.

        Conformance statement MQTT-1.5.3-1
        """
        events = []
        p = MQTTParser()

        bad = b"\x10\x13\x00\x04\xed\xbf\xbfT\x04\x02\x00x\x00\x07test123"

        for x in iterbytes(bad):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(attr.asdict(events[0]), {'reason': ("Invalid UTF-8 string (contains surrogates)")})
        self.assertEqual(p._state, PROTOCOL_VIOLATION)

    def test_invalid_utf8_null(self):
        """
        UTF-8 strings may not contain null bytes.

        Conformance statement MQTT-1.5.3-2
        """
        events = []
        p = MQTTParser()

        bad = b"\x10\x13\x00\x04\x00QTT\x04\x02\x00x\x00\x07test123"

        for x in iterbytes(bad):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(attr.asdict(events[0]), {'reason': ("Invalid UTF-8 string (contains nulls)")})
        self.assertEqual(p._state, PROTOCOL_VIOLATION)

    def test_utf8_zwnbsp(self):
        """
        UTF-8 strings containing the sequence 0xEF 0xBB 0xBF must decode to
        U+FEFF.

        Conformance statement MQTT-1.5.3-3
        """
        events = []
        p = MQTTParser()

        bad = b"\x10\x13\x00\x04MQTT\x04\x02\x00x\x00\x07test\xef\xbb\xbf"

        for x in iterbytes(bad):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]), {
                'username': None,
                'password': None,
                'will_message': None,
                'will_topic': None,
                'client_id': "test\uFEFF",
                'keep_alive': 120,
                'flags': {
                    'username': False,
                    'password': False,
                    'will': False,
                    'will_qos': 0,
                    'will_retain': False,
                    'clean_session': True,
                    'reserved': False
                }
            })

    def test_reserved_packet_15(self):
        """
        Using the reserved packet 15 is a protocol violation

        No conformance statement, but see "Table 2.1 - Control packet types".
        """
        events = []
        p = MQTTParser()

        data = (
            # CONNECT
            b"101300044d51545404020002000774657374313233"
            # Reserved packet #15
            b"f01300044d51545404020002000774657374313233")

        for x in iterbytes(unhexlify(data)):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 2)

        # Regular connect, we don't care about it
        self.assertIsInstance(events.pop(0), Connect)

        # Reserved packet type
        self._assert_event(events.pop(0), Failure, {'reason': "Unimplemented packet type 15"})

        # We want to have consumed all the events
        self.assertEqual(len(events), 0)
        self.assertEqual(p._state, PROTOCOL_VIOLATION)

    def test_reserved_packet_0(self):
        """
        Using the reserved packet 0 is a protocol violation.

        No conformance statement, but see "Table 2.1 - Control packet types".
        """
        events = []
        p = MQTTParser()

        data = (
            # CONNECT
            b"101300044d51545404020002000774657374313233"
            # Reserved packet #15
            b"001300044d51545404020002000774657374313233")

        for x in iterbytes(unhexlify(data)):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 2)

        # Regular connect, we don't care about it
        self.assertIsInstance(events.pop(0), Connect)

        # Reserved packet
        self._assert_event(events.pop(0), Failure, {'reason': "Unimplemented packet type 0"})

        # We want to have consumed all the events
        self.assertEqual(len(events), 0)
        self.assertEqual(p._state, PROTOCOL_VIOLATION)
