#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import unittest

from autobahn.wamp.message import Subscribe

from crossbar.router.observation import ExactUriObservation, \
    PrefixUriObservation, WildcardUriObservation, UriObservationMap


class FakeObserver:
    pass


class TestObservation(unittest.TestCase):
    def test_create_exact(self):
        """
        Create an exact-matching observation.
        """
        obs1 = ExactUriObservation("com.example.uri1")
        self.assertTrue(isinstance(obs1.id, (int, )))
        self.assertEqual(obs1.uri, "com.example.uri1")
        self.assertEqual(obs1.match, "exact")
        self.assertEqual(obs1.observers, set())

    def test_create_prefix(self):
        """
        Create a prefix-matching observation.
        """
        obs1 = PrefixUriObservation("com.example.uri1")
        self.assertTrue(isinstance(obs1.id, (int, )))
        self.assertEqual(obs1.uri, "com.example.uri1")
        self.assertEqual(obs1.match, "prefix")
        self.assertEqual(obs1.observers, set())

    def test_create_wildcard(self):
        """
        Create a wildcard-matching observation.
        """
        obs1 = WildcardUriObservation("com.example..create")
        self.assertTrue(isinstance(obs1.id, (int, )))
        self.assertEqual(obs1.uri, "com.example..create")
        self.assertEqual(obs1.match, "wildcard")
        self.assertEqual(obs1.observers, set())


class TestUriObservationMap(unittest.TestCase):
    def test_match_observations_empty(self):
        """
        An empty observer map returns an empty observer set for any URI.
        """
        obs_map = UriObservationMap()

        for uri in ["com.example.uri1", "com.example.uri2", ""]:
            obsvs = obs_map.match_observations(uri)
            self.assertEqual(obsvs, [])

    def test_add_observer(self):
        """
        When a observer is added, a observation is returned.
        """
        obs_map = UriObservationMap()

        uri1 = "com.example.uri1"
        obs1 = FakeObserver()
        observation, was_already_observed, is_first_observer = obs_map.add_observer(obs1, uri1)

        self.assertIsInstance(observation, ExactUriObservation)
        self.assertFalse(was_already_observed)
        self.assertTrue(is_first_observer)

    def test_add_observer_was_already_observed(self):
        """
        When a observer is added, the ``was_already_observed`` flag in
        the return is correct.
        """
        obs_map = UriObservationMap()

        uri1 = "com.example.uri1"
        obs1 = FakeObserver()

        observation1, was_already_observed, _ = obs_map.add_observer(obs1, uri1)
        self.assertFalse(was_already_observed)

        observation2, was_already_observed, _ = obs_map.add_observer(obs1, uri1)
        self.assertTrue(was_already_observed)

        self.assertEqual(observation1, observation2)

    def test_add_observer_is_first_observer(self):
        """
        When a observer is added, the ``is_first_observer`` flag in the
        return is correct.
        """
        obs_map = UriObservationMap()

        uri1 = "com.example.uri1"
        obs1 = FakeObserver()
        obs2 = FakeObserver()

        _, _, is_first_observer = obs_map.add_observer(obs1, uri1)
        self.assertTrue(is_first_observer)

        _, _, is_first_observer = obs_map.add_observer(obs2, uri1)
        self.assertFalse(is_first_observer)

    def test_delete_observer(self):
        obs_map = UriObservationMap()

        uri = "com.example.uri1"
        obs1 = FakeObserver()
        obs2 = FakeObserver()

        ob1, uri1, _ = obs_map.add_observer(obs1, uri)
        ob2, uri2, _ = obs_map.add_observer(obs2, uri)

        self.assertTrue(ob1 is ob2)
        obs_map.drop_observer(obs1, ob1)

        # error if we delete because there's still one observer
        with self.assertRaises(ValueError):
            obs_map.delete_observation(ob2)

        # drop last observer and delete
        obs_map.drop_observer(obs2, ob1)
        obs_map.delete_observation(ob2)

    def test_match_observations_match_exact(self):
        """
        When a observer observes an URI (match exact), the observer
        is returned for the URI upon lookup.
        """
        obs_map = UriObservationMap()

        uri1 = "com.example.uri1"
        obs1 = FakeObserver()

        observation1, _, _ = obs_map.add_observer(obs1, uri1)

        observations = obs_map.match_observations(uri1)

        self.assertEqual(observations, [observation1])

    def test_match_observations_match_exact_same(self):
        """
        When multiple different observers observe the same URI (match exact),
        all get the same observation.
        """
        obs_map = UriObservationMap()

        uri1 = "com.example.uri1"
        obs1 = FakeObserver()
        obs2 = FakeObserver()
        obs3 = FakeObserver()

        observation1, _, _ = obs_map.add_observer(obs1, uri1)
        observation2, _, _ = obs_map.add_observer(obs2, uri1)
        observation3, _, _ = obs_map.add_observer(obs3, uri1)

        observations = obs_map.match_observations(uri1)

        self.assertEqual(observations, [observation1])
        self.assertEqual(observations[0].observers, set([obs1, obs2, obs3]))

    def test_match_observations_match_exact_multi(self):
        """
        When the same observer is added multiple times to the same URI (match exact),
        the observation is only returned once, and every time the same observation ID is returned.
        """
        obs_map = UriObservationMap()

        uri1 = "com.example.uri1"
        obs1 = FakeObserver()

        observation1, _, _ = obs_map.add_observer(obs1, uri1)
        observation2, _, _ = obs_map.add_observer(obs1, uri1)
        observation3, _, _ = obs_map.add_observer(obs1, uri1)

        self.assertEqual(observation1, observation2)
        self.assertEqual(observation1, observation3)

        observations = obs_map.match_observations(uri1)

        self.assertEqual(observations, [observation1])
        self.assertEqual(observations[0].observers, set([obs1]))

    def test_match_observations_match_prefix(self):
        """
        When a observer observes an URI (match prefix), the observer is
        returned for all uris upon lookup where the observed URI is a prefix.
        """
        obs_map = UriObservationMap()

        obs1 = FakeObserver()

        observation1, _, _ = obs_map.add_observer(obs1, "com.example", match=Subscribe.MATCH_PREFIX)

        # test matches
        for uri in [
                "com.example.uri1.foobar.barbaz", "com.example.uri1.foobar", "com.example.uri1", "com.example.topi",
                "com.example.", "com.example2", "com.example"
        ]:
            observations = obs_map.match_observations(uri)
            self.assertEqual(observations, [observation1])
            self.assertEqual(observations[0].observers, set([obs1]))

        # test non-matches
        for uri in ["com.foobar.uri1", "com.exampl.uri1", "com.exampl", "com", ""]:
            observations = obs_map.match_observations(uri)
            self.assertEqual(observations, [])

    def test_match_observations_match_wildcard_single(self):
        """
        When a observer observes to a uri (wildcard prefix), the observer is
        returned for all uris upon lookup where the observed uri matches
        the wildcard pattern.
        """
        obs_map = UriObservationMap()

        obs1 = FakeObserver()

        observation1, _, _ = obs_map.add_observer(obs1, "com.example..create", match=Subscribe.MATCH_WILDCARD)

        # test matches
        for uri in ["com.example.foobar.create", "com.example.1.create"]:
            observations = obs_map.match_observations(uri)
            self.assertEqual(observations, [observation1])
            self.assertEqual(observations[0].observers, set([obs1]))

        # test non-matches
        for uri in [
                "com.example.foobar.delete", "com.example.foobar.create2", "com.example.foobar.create.barbaz"
                "com.example.foobar", "com.example.create", "com.example"
        ]:
            observations = obs_map.match_observations(uri)
            self.assertEqual(observations, [])

    def test_match_observations_match_wildcard_multi(self):
        """
        Test with multiple wildcards in wildcard-matching observation.
        """
        obs_map = UriObservationMap()

        obs1 = FakeObserver()

        observation1, _, _ = obs_map.add_observer(obs1, "com...create", match=Subscribe.MATCH_WILDCARD)

        # test matches
        for uri in [
                "com.example.foobar.create",
                "com.example.1.create",
                "com.myapp.foobar.create",
                "com.myapp.1.create",
        ]:
            observations = obs_map.match_observations(uri)
            self.assertEqual(observations, [observation1])
            self.assertEqual(observations[0].observers, set([obs1]))

        # test non-matches
        for uri in [
                "com.example.foobar.delete",
                "com.example.foobar.create2",
                "com.example.foobar.create.barbaz"
                "com.example.foobar",
                "org.example.foobar.create",
                "org.example.1.create",
                "org.myapp.foobar.create",
                "org.myapp.1.create",
        ]:
            observations = obs_map.match_observations(uri)
            self.assertEqual(observations, [])

    def test_match_observations_match_multimode(self):
        """
        When a observer is observed to multiple observations each matching
        a given uri looked up, the observer is returned in each observation.
        """
        obs_map = UriObservationMap()

        obs1 = FakeObserver()

        observation1, _, _ = obs_map.add_observer(obs1, "com.example.product.create", match=Subscribe.MATCH_EXACT)
        observation2, _, _ = obs_map.add_observer(obs1, "com.example.product", match=Subscribe.MATCH_PREFIX)
        observation3, _, _ = obs_map.add_observer(obs1, "com.example..create", match=Subscribe.MATCH_WILDCARD)

        observations = obs_map.match_observations("com.example.product.create")
        self.assertEqual(observations, [observation1, observation2, observation3])
        self.assertEqual(observations[0].observers, set([obs1]))
        self.assertEqual(observations[1].observers, set([obs1]))
        self.assertEqual(observations[2].observers, set([obs1]))

        observations = obs_map.match_observations("com.example.foobar.create")
        self.assertEqual(observations, [observation3])
        self.assertEqual(observations[0].observers, set([obs1]))

        observations = obs_map.match_observations("com.example.product.delete")
        self.assertEqual(observations, [observation2])
        self.assertEqual(observations[0].observers, set([obs1]))
