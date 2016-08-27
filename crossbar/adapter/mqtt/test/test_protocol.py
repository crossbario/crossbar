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

from crossbar.adapter.mqtt.protocol import MQTTServerProtocol
from crossbar.adapter.mqtt._utils import iterbytes

from twisted.trial.unittest import TestCase


class ProtocolTests(TestCase):

    maxDiff = None

    def test_correct_connect(self):
        """
        The most basic possible connect -- MQTT 3.1.1, no QoS/username/password
        and compliant with the spec.
        """
        events = []
        p = MQTTServerProtocol()

        good = b"\x10\x13\x00\x04MQTT\x04\x02\x00x\x00\x07test123"

        for x in iterbytes(good):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'username': None,
                'password': None,
                'will_message': None,
                'will_topic': None,
                'client_id': u"test123",
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
            }
        )

    def test_malformed_packet(self):
        """
        A parsing failure (e.g. an incorrect flag leads us to read off the end)
        is safely handled.
        """
        events = []
        p = MQTTServerProtocol()

        bad = b"\x10\x13\x00\x04MQTT\x04\x02\x00x\x00\x09test123"

        for x in iterbytes(bad):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'reason': ("Corrupt data, fell off the end: Cannot read 72 "
                           "bits, only 56 available.")
            }
        )

    def test_quirks_mode_connect(self):
        """
        Nyamuk sends two extra bytes at the end of the CONNECT packet (that
        cannot mean anything), we should just cope with it.
        """
        events = []
        p = MQTTServerProtocol()

        #             vv correct length                           vv why???
        good = b"\x10\x15\x00\x04MQTT\x04\x02\x00x\x00\x07test123\x00\x00"

        for x in iterbytes(good):
            events.extend(p.data_received(x))

        self.assertEqual(len(events), 1)
        self.assertEqual(
            attr.asdict(events[0]),
            {
                'username': None,
                'password': None,
                'will_message': None,
                'will_topic': None,
                'client_id': u"test123",
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
            }
        )
        warnings = self.flushWarnings()
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["message"],
                         ("Quirky client CONNECT -- packet length was 152 "
                          "bytes but only had 168 bytes of useful data"))
