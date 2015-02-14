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

from crossbar.router.subscription import Subscription, SubscriptionMap


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

    def test_get_subscriptions_empty(self):
        """
        An empty subscriber map returns an empty subscriber set for any topic.
        """
        sub_map = SubscriptionMap()

        for topic in [u"com.example.topic1", u"com.example.topic2", u""]:
            subs = sub_map.get_subscriptions(topic)
            self.assertEqual(subs, [])

    def test_add_subscriber(self):
        """
        When a subscriber is added, a subscription is returned.
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()
        subscription, was_already_subscribed, is_first_subscriber = sub_map.add_subscriber(sub1, topic1)

        self.assertIsInstance(subscription, Subscription)
        self.assertFalse(was_already_subscribed)
        self.assertTrue(is_first_subscriber)

    def test_add_subscriber_was_already_subscribed(self):
        """
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()

        subscription1, was_already_subscribed, _ = sub_map.add_subscriber(sub1, topic1)
        self.assertFalse(was_already_subscribed)

        subscription2, was_already_subscribed, _ = sub_map.add_subscriber(sub1, topic1)
        self.assertTrue(was_already_subscribed)

        self.assertEqual(subscription1, subscription2)

    def test_add_subscriber_is_first_subscriber(self):
        """
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()
        sub2 = FakeSubscriber()

        _, _, is_first_subscriber = sub_map.add_subscriber(sub1, topic1)
        self.assertTrue(is_first_subscriber)

        _, _, is_first_subscriber = sub_map.add_subscriber(sub2, topic1)
        self.assertFalse(is_first_subscriber)

    def test_get_subscriptions_match_exact(self):
        """
        When a subscriber subscribes to a topic (match exact),
        the subscriber is returned for the topic upon lookup.
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()

        subscription1, _, _ = sub_map.add_subscriber(sub1, topic1)

        subscriptions = sub_map.get_subscriptions(topic1)

        self.assertEqual(subscriptions, [subscription1])

    def test_get_subscriptions_match_exact_same(self):
        """
        When multiple different subscribers subscribe to the same topic (match exact),
        all get the same subscription nevertheless.
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()
        sub2 = FakeSubscriber()
        sub3 = FakeSubscriber()

        subscription1, _, _ = sub_map.add_subscriber(sub1, topic1)
        subscription2, _, _ = sub_map.add_subscriber(sub2, topic1)
        subscription3, _, _ = sub_map.add_subscriber(sub3, topic1)

        subscriptions = sub_map.get_subscriptions(topic1)

        self.assertEqual(subscriptions, [subscription1])
        self.assertEqual(subscriptions[0].subscribers, set([sub1, sub2, sub3]))

    def test_get_subscriptions_match_exact_multi(self):
        """
        When the same subscriber is added multiple times to the same topic (match exact),
        the subscribed is only returned once, and every time the same subscription ID is returned.
        """
        sub_map = SubscriptionMap()

        topic1 = u"com.example.topic1"
        sub1 = FakeSubscriber()

        subscription1, _, _  = sub_map.add_subscriber(sub1, topic1)
        subscription2, _, _  = sub_map.add_subscriber(sub1, topic1)
        subscription3, _, _  = sub_map.add_subscriber(sub1, topic1)

        self.assertEqual(subscription1, subscription2)
        self.assertEqual(subscription1, subscription3)

        subscriptions = sub_map.get_subscriptions(topic1)

        self.assertEqual(subscriptions, [subscription1])
        self.assertEqual(subscriptions[0].subscribers, set([sub1]))

    def test_get_subscriptions_match_prefix(self):
        """
        When a subscriber subscribes to a topic (match prefix),
        the subscriber is returned for all topics upon lookup
        where the subscribed topic is a prefix.
        """
        sub_map = SubscriptionMap()

        sub1 = FakeSubscriber()

        subscription1, _, _  = sub_map.add_subscriber(sub1, u"com.example", match=Subscribe.MATCH_PREFIX)

        # test matches
        for topic in [u"com.example.topic1.foobar.barbaz",
                      u"com.example.topic1.foobar",
                      u"com.example.topic1",
                      u"com.example.topi",
                      u"com.example.",
                      u"com.example2",
                      u"com.example"]:
            subscriptions = sub_map.get_subscriptions(topic)
            self.assertEqual(subscriptions, [subscription1])
            self.assertEqual(subscriptions[0].subscribers, set([sub1]))

        # test non-matches
        for topic in [u"com.foobar.topic1",
                      u"com.exampl.topic1",
                      u"com.exampl",
                      u"com",
                      u""]:
            subscriptions = sub_map.get_subscriptions(topic)
            self.assertEqual(subscriptions, [])
