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


from twisted.trial.unittest import TestCase

from crossbar.bridge.mqtt.wamp import _mqtt_topicfilter_to_wamp, _mqtt_topicname_to_wamp


class MQTTTopicTests(TestCase):
    """
    Tests our processing of MQTT topic names and topic filters.
    """

    def test_topic_filters_valid(self):
        """
        Test checking and conversion of valid MQTT topic filters.
        """
        for topic, mapped_topic, match_policy in [
            # exact matching
            ('foobar', 'foobar', 'exact'),
            ('com/example/topic1', 'com.example.topic1', 'exact'),
            ('tennis/player1', 'tennis.player1', 'exact'),
            ('tennis', 'tennis', 'exact'),

            # prefix matching
            ('sport/tennis/player1/#', 'sport.tennis.player1.', 'prefix'),
            ('#', '', 'prefix'),

            # wildcard matching
            ('+', '', 'wildcard'),
            ('+/tennis/player1', '.tennis.player1', 'wildcard'),
            ('sport/+/player1', 'sport..player1', 'wildcard'),
            ('sport/tennis/+', 'sport.tennis.', 'wildcard'),
            ('+/+/+', '..', 'wildcard')
        ]:
            _mapped_topic, _match_policy = _mqtt_topicfilter_to_wamp(topic)
            self.assertEqual(_mapped_topic, mapped_topic)
            self.assertEqual(_match_policy, match_policy)

    def test_topic_filters_invalid(self):
        """
        Test invalid MQTT topic filters.
        """
        for topic in [
            # invalid types
            None,
            23,
            b'bla',

            # invalid according to MQTT v3.3.1
            '',
            'sport/tennis#',
            'sport/tennis/#/ranking',
            '##',
            '++',
            'sport+',
            'sport/+ab/player1',

            # The following are valid topic names/filters in MQTT v3.3.1,
            # but are invalid in Crossbar.io (WAMP):

            # cannot combine wildcard and prefix matching
            '+/tennis/#',
            '+/#',

            # components cannot contain whitespace
            'spo oh rt',
            'foo/b r/baz',
            'sport/ /#',
            'sport/ten nis/#',

            # no trailing/leading level separator
            '/tennis/player1',
            'tennis/player1/',
            '/tennis/player1/',

            # no double, triple, .. level separator
            'tennis//player1',
            '//',
            'tennis///player1',
            '///',
        ]:
            with self.assertRaises(TypeError):
                _mqtt_topicfilter_to_wamp(topic)

    def test_topic_names_valid(self):
        """
        Test checking and conversion of valid MQTT topic names.
        """
        for topic, mapped_topic in [
            ('com/example/topic1', 'com.example.topic1'),
            ('a', 'a'),
            ('foobar', 'foobar'),
            ('com/example/topic1', 'com.example.topic1'),
            ('tennis/player1', 'tennis.player1'),
            ('tennis', 'tennis'),
        ]:
            _mapped_topic = _mqtt_topicname_to_wamp(topic)
            self.assertEqual(_mapped_topic, mapped_topic)

    def test_topic_names_invalid(self):
        """
        Test invalid MQTT topic names.
        """
        for topic in [
            # invalid types
            None,
            23,
            b'bla',

            # must not contain wildcard characters
            '#',
            '+',
            'sport/tennis/player1/#',
            'sport/+/player1',

            # topic cannot be empty
            '',

            # The following are valid topic names/filters in MQTT v3.3.1,
            # but are invalid in Crossbar.io (WAMP):

            # components cannot contain whitespace
            'spo oh rt',
            'foo/b r/baz',

            # no trailing/leading level separator
            '/tennis/player1',
            'tennis/player1/',
            '/tennis/player1/',

            # no double, triple, .. level separator
            'tennis//player1',
            '//',
            'tennis///player1',
            '///',
        ]:
            with self.assertRaises(TypeError):
                _mqtt_topicname_to_wamp(topic)
