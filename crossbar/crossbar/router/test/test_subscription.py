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
import pickle
from StringIO import StringIO

from autobahn.wamp.message import Subscribe

from crossbar.router.subscription import ExactUriObservation, \
    PrefixUriObservation, WildcardUriObservation, UriObservationMap


class FakeObserver:
    pass


class TestSubscription(unittest.TestCase):

    def test_create_exact(self):
        """
        Create an exact-matching observation.
        """
        sub1 = ExactUriObservation(u"com.example.uri1")
        self.assertEqual(type(sub1.id), int)
        self.assertEqual(sub1.uri, u"com.example.uri1")
        self.assertEqual(sub1.match, u"exact")
        self.assertEqual(sub1.observers, set())

    def test_create_prefix(self):
        """
        Create a prefix-matching observation.
        """
        sub1 = PrefixUriObservation(u"com.example.uri1")
        self.assertEqual(type(sub1.id), int)
        self.assertEqual(sub1.uri, u"com.example.uri1")
        self.assertEqual(sub1.match, u"prefix")
        self.assertEqual(sub1.observers, set())

    def test_create_wildcard(self):
        """
        Create a wildcard-matching observation.
        """
        sub1 = WildcardUriObservation(u"com.example..create")
        self.assertEqual(type(sub1.id), int)
        self.assertEqual(sub1.uri, u"com.example..create")
        self.assertEqual(sub1.match, u"wildcard")
        self.assertEqual(sub1.observers, set())
        self.assertEqual(sub1.pattern, (False, False, True, False))
        self.assertEqual(sub1.pattern_len, 4)

    def test_pickle(self):
        """
        Test pickling of observations (__getstate__, __setstate__).
        """
        subs = [
            ExactUriObservation(u"com.example.uri1"),
            PrefixUriObservation(u"com.example.uri1"),
            WildcardUriObservation(u"com.example..create"),
        ]

        for sub in subs:
            data = StringIO()
            pickle.dump(sub, data)

            read_fd = StringIO(data.getvalue())
            sub2 = pickle.load(read_fd)

            self.assertEqual(sub.id, sub2.id)
            self.assertEqual(sub.uri, sub2.uri)
            self.assertEqual(sub.match, sub2.match)
            self.assertEqual(sub2.observers, set())


class TestUriObservationMap(unittest.TestCase):

    def test_match_observations_empty(self):
        """
        An empty subscriber map returns an empty subscriber set for any topic.
        """
        sub_map = UriObservationMap()

        for topic in [u"com.example.uri1", u"com.example.uri2", u""]:
            subs = sub_map.match_observations(topic)
            self.assertEqual(subs, [])

    def test_add_subscriber(self):
        """
        When a subscriber is added, a observation is returned.
        """
        sub_map = UriObservationMap()

        topic1 = u"com.example.uri1"
        sub1 = FakeObserver()
        observation, was_already_observed, is_first_observer = sub_map.add_observer(sub1, topic1)

        self.assertIsInstance(observation, ExactUriObservation)
        self.assertFalse(was_already_observed)
        self.assertTrue(is_first_observer)

    def test_add_subscriber_was_already_observed(self):
        """
        When a subscriber is added, the ``was_already_observed`` flag in
        the return is correct.
        """
        sub_map = UriObservationMap()

        topic1 = u"com.example.uri1"
        sub1 = FakeObserver()

        observation1, was_already_observed, _ = sub_map.add_observer(sub1, topic1)
        self.assertFalse(was_already_observed)

        observation2, was_already_observed, _ = sub_map.add_observer(sub1, topic1)
        self.assertTrue(was_already_observed)

        self.assertEqual(observation1, observation2)

    def test_add_subscriber_is_first_observer(self):
        """
        When a subscriber is added, the ``is_first_observer`` flag in the
        return is correct.
        """
        sub_map = UriObservationMap()

        topic1 = u"com.example.uri1"
        sub1 = FakeObserver()
        sub2 = FakeObserver()

        _, _, is_first_observer = sub_map.add_observer(sub1, topic1)
        self.assertTrue(is_first_observer)

        _, _, is_first_observer = sub_map.add_observer(sub2, topic1)
        self.assertFalse(is_first_observer)

    def test_match_observations_match_exact(self):
        """
        When a subscriber subscribes to a topic (match exact), the subscriber
        is returned for the topic upon lookup.
        """
        sub_map = UriObservationMap()

        topic1 = u"com.example.uri1"
        sub1 = FakeObserver()

        observation1, _, _ = sub_map.add_observer(sub1, topic1)

        observations = sub_map.match_observations(topic1)

        self.assertEqual(observations, [observation1])

    def test_match_observations_match_exact_same(self):
        """
        When multiple different subscribers subscribe to the same topic (match exact),
        all get the same observation nevertheless.
        """
        sub_map = UriObservationMap()

        topic1 = u"com.example.uri1"
        sub1 = FakeObserver()
        sub2 = FakeObserver()
        sub3 = FakeObserver()

        observation1, _, _ = sub_map.add_observer(sub1, topic1)
        observation2, _, _ = sub_map.add_observer(sub2, topic1)
        observation3, _, _ = sub_map.add_observer(sub3, topic1)

        observations = sub_map.match_observations(topic1)

        self.assertEqual(observations, [observation1])
        self.assertEqual(observations[0].observers, set([sub1, sub2, sub3]))

    def test_match_observations_match_exact_multi(self):
        """
        When the same subscriber is added multiple times to the same topic (match exact),
        the subscribed is only returned once, and every time the same observation ID is returned.
        """
        sub_map = UriObservationMap()

        topic1 = u"com.example.uri1"
        sub1 = FakeObserver()

        observation1, _, _ = sub_map.add_observer(sub1, topic1)
        observation2, _, _ = sub_map.add_observer(sub1, topic1)
        observation3, _, _ = sub_map.add_observer(sub1, topic1)

        self.assertEqual(observation1, observation2)
        self.assertEqual(observation1, observation3)

        observations = sub_map.match_observations(topic1)

        self.assertEqual(observations, [observation1])
        self.assertEqual(observations[0].observers, set([sub1]))

    def test_match_observations_match_prefix(self):
        """
        When a subscriber subscribes to a topic (match prefix), the subscriber is
        returned for all topics upon lookup where the subscribed topic is a prefix.
        """
        sub_map = UriObservationMap()

        sub1 = FakeObserver()

        observation1, _, _ = sub_map.add_observer(sub1, u"com.example", match=Subscribe.MATCH_PREFIX)

        # test matches
        for topic in [u"com.example.uri1.foobar.barbaz",
                      u"com.example.uri1.foobar",
                      u"com.example.uri1",
                      u"com.example.topi",
                      u"com.example.",
                      u"com.example2",
                      u"com.example"]:
            observations = sub_map.match_observations(topic)
            self.assertEqual(observations, [observation1])
            self.assertEqual(observations[0].observers, set([sub1]))

        # test non-matches
        for topic in [u"com.foobar.uri1",
                      u"com.exampl.uri1",
                      u"com.exampl",
                      u"com",
                      u""]:
            observations = sub_map.match_observations(topic)
            self.assertEqual(observations, [])

    def test_match_observations_match_wildcard_single(self):
        """
        When a subscriber subscribes to a topic (wildcard prefix), the subscriber is
        returned for all topics upon lookup where the subscribed topic matches
        the wildcard pattern.
        """
        sub_map = UriObservationMap()

        sub1 = FakeObserver()

        observation1, _, _ = sub_map.add_observer(sub1, u"com.example..create", match=Subscribe.MATCH_WILDCARD)

        # test matches
        for topic in [u"com.example.foobar.create",
                      u"com.example.1.create"
                      ]:
            observations = sub_map.match_observations(topic)
            self.assertEqual(observations, [observation1])
            self.assertEqual(observations[0].observers, set([sub1]))

        # test non-matches
        for topic in [u"com.example.foobar.delete",
                      u"com.example.foobar.create2",
                      u"com.example.foobar.create.barbaz"
                      u"com.example.foobar",
                      u"com.example.create",
                      u"com.example"
                      ]:
            observations = sub_map.match_observations(topic)
            self.assertEqual(observations, [])

    def test_match_observations_match_wildcard_multi(self):
        """
        Test with multiple wildcards in wildcard-matching observation.
        """
        sub_map = UriObservationMap()

        sub1 = FakeObserver()

        observation1, _, _ = sub_map.add_observer(sub1, u"com...create", match=Subscribe.MATCH_WILDCARD)

        # test matches
        for topic in [u"com.example.foobar.create",
                      u"com.example.1.create",
                      u"com.myapp.foobar.create",
                      u"com.myapp.1.create",
                      ]:
            observations = sub_map.match_observations(topic)
            self.assertEqual(observations, [observation1])
            self.assertEqual(observations[0].observers, set([sub1]))

        # test non-matches
        for topic in [u"com.example.foobar.delete",
                      u"com.example.foobar.create2",
                      u"com.example.foobar.create.barbaz"
                      u"com.example.foobar",
                      u"org.example.foobar.create",
                      u"org.example.1.create",
                      u"org.myapp.foobar.create",
                      u"org.myapp.1.create",
                      ]:
            observations = sub_map.match_observations(topic)
            self.assertEqual(observations, [])

    def test_match_observations_match_multimode(self):
        """
        When a subscriber is subscribed to multiple observations each matching
        a given topic looked up, the subscriber is returned in each observation.
        """
        sub_map = UriObservationMap()

        sub1 = FakeObserver()

        observation1, _, _ = sub_map.add_observer(sub1, u"com.example.product.create", match=Subscribe.MATCH_EXACT)
        observation2, _, _ = sub_map.add_observer(sub1, u"com.example.product", match=Subscribe.MATCH_PREFIX)
        observation3, _, _ = sub_map.add_observer(sub1, u"com.example..create", match=Subscribe.MATCH_WILDCARD)

        observations = sub_map.match_observations(u"com.example.product.create")
        self.assertEqual(observations, [observation1, observation2, observation3])
        self.assertEqual(observations[0].observers, set([sub1]))
        self.assertEqual(observations[1].observers, set([sub1]))
        self.assertEqual(observations[2].observers, set([sub1]))

        observations = sub_map.match_observations(u"com.example.foobar.create")
        self.assertEqual(observations, [observation3])
        self.assertEqual(observations[0].observers, set([sub1]))

        observations = sub_map.match_observations(u"com.example.product.delete")
        self.assertEqual(observations, [observation2])
        self.assertEqual(observations[0].observers, set([sub1]))
