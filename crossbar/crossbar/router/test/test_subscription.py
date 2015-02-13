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

from __future__ import absolute_import

import unittest

from autobahn.wamp.message import Subscribe

from crossbar.router.subscription import SubscriptionMap


class FakeSubscriber:
    pass


class TestSubscriptionMap(unittest.TestCase):

    """
    """

    def setUp(self):
        """
        """

    def tearDown(self):
        """
        """

    def test_empty_submap(self):
        """
        An empty subscriber map returns an empty subscriber set for any topic.
        """
        sub_map = SubscriptionMap()

        for topic in [u"com.example.topic1", u"com.example.topic2", u""]:
            subs = sub_map.get_subscribers(topic)
            self.assertEqual(subs, set())

    def test_sub_id(self):
        """
        When a subscriber is added, a subscription ID is returned.
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()
        sub_id = sub_map.add_subscriber(sub1, topic1)

        self.assertEqual(type(sub_id), int)

    def test_match_exact(self):
        """
        When a subscriber subscribes to a topic (match exact),
        the subscriber is returned for the topic upon lookup.
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()

        sub_map.add_subscriber(sub1, topic1)

        subs = sub_map.get_subscribers(topic1)

        self.assertEqual(subs, set([sub1]))

    def test_match_exact_same(self):
        """
        When multiple subscribers subscriber to the same topic (match exact),
        all are returned for the topic, and all get the same subscription ID.
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()
        sub2 = FakeSubscriber()
        sub3 = FakeSubscriber()

        sub_id1 = sub_map.add_subscriber(sub1, topic1)
        sub_id2 = sub_map.add_subscriber(sub2, topic1)
        sub_id3 = sub_map.add_subscriber(sub3, topic1)

        subs = sub_map.get_subscribers(topic1)

        self.assertEqual(subs, set([sub1, sub2, sub3]))

        self.assertEqual(sub_id1, sub_id2)
        self.assertEqual(sub_id1, sub_id3)

    def test_match_exact_multi(self):
        """
        When the same subscriber is added multiple times to the same topic (match exact),
        the subscribed is only returned once, and every time the same subscription ID is returned.
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()

        sub_id1 = sub_map.add_subscriber(sub1, topic1)
        sub_id2 = sub_map.add_subscriber(sub1, topic1)
        sub_id3 = sub_map.add_subscriber(sub1, topic1)

        subs = sub_map.get_subscribers(topic1)

        self.assertEqual(subs, set([sub1]))

        self.assertEqual(sub_id1, sub_id2)
        self.assertEqual(sub_id1, sub_id3)

    def test_match_prefix(self):
        """
        When a subscriber subscribes to a topic (match prefix),
        the subscriber is returned for all topics upon lookup
        where the subscribed topic is a prefix.
        """
        sub_map = SubscriptionMap()

        topic_pat1 = u"com.example"
        sub1 = FakeSubscriber()

        sub_map.add_subscriber(sub1, topic_pat1, match=Subscribe.MATCH_PREFIX)

        for topic in [u"com.example.topic1", topic_pat1]:
            subs = sub_map.get_subscribers(topic)

            # self.assertEqual(subs, set([sub1]))

        for topic in [u"com.foobar.topic1"]:
            subs = sub_map.get_subscribers(topic)
