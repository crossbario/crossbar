#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
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
        for topic, mapped_topic, match_policy in [('foobar', 'foobar', 'exact'),
                                                  ('com/example/topic1', 'com.example.topic1', 'exact'),
                                                  ('tennis/player1', 'tennis.player1', 'exact'),
                                                  ('tennis', 'tennis', 'exact'),
                                                  ('sport/tennis/player1/#', 'sport.tennis.player1.', 'prefix'),
                                                  ('#', '', 'prefix'), ('+', '', 'wildcard'),
                                                  ('+/tennis/player1', '.tennis.player1', 'wildcard'),
                                                  ('sport/+/player1', 'sport..player1', 'wildcard'),
                                                  ('sport/tennis/+', 'sport.tennis.', 'wildcard'),
                                                  ('+/+/+', '..', 'wildcard')]:
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
