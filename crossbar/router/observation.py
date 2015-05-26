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

from pytrie import StringTrie

from autobahn import util

__all__ = ('UriObservationMap', 'is_protected_uri')


def is_protected_uri(uri):
    return uri.startswith(u'wamp.') or uri.startswith(u'crossbar.')


class OrderedSet(set):

    def __init__(self):
        super(set, self).__init__()
        self._list = []

    def add(self, item):
        super(OrderedSet, self).add(item)
        self._list.append(item)

    def discard(self, item):
        self._list.remove(item)
        return super(OrderedSet, self).discard(item)

    def __getitem__(self, index):
        return self._list[index]

    def __iter__(self):
        return iter(self._list)

    def __reversed__(self):
        return reversed(self._list)


class UriObservation(object):
    """
    Represents an URI observation maintained by a broker/dealer.
    """
    match = None

    def __init__(self, uri, ordered=False, extra=None):
        """

        :param uri: The URI (or URI pattern) for this observation.
        :type uri: unicode
        """
        # URI (or URI pattern) this observation is created for
        self.uri = uri

        # flag indicating whether observers should be maintained
        # in an ordered set or a regular, unordered set
        self.ordered = ordered

        # arbitrary, opaque extra data attached to the observation
        self.extra = extra

        # generate a new ID for the observation
        self.id = util.id()

        # UTC timestamp this observation was created
        self.created = util.utcnow()

        # set of observers
        if self.ordered:
            self.observers = OrderedSet()
        else:
            self.observers = set()

    def __repr__(self):
        return "<{} id={} uri={} ordered={} extra={} created={} observers={}>".format(
            self.__class__.__name__, self.id, self.uri, self.ordered, self.extra, self.created,
            self.observers)


class ExactUriObservation(UriObservation):

    """
    Represents an exact-matching observation.
    """

    match = u"exact"


class PrefixUriObservation(UriObservation):

    """
    Represents a prefix-matching observation.
    """

    match = u"prefix"


class WildcardUriObservation(UriObservation):

    """
    Represents a wildcard-matching observation.
    """
    match = u"wildcard"

    def __init__(self, uri, ordered=False, extra=None):
        UriObservation.__init__(self, uri, ordered, extra)

        # an URI pattern like "com.example..create" will have a pattern (False, False, True, False)
        self.pattern = tuple([part == "" for part in self.uri.split('.')])

        # length of the pattern (above would have length 4, as it consists of 4 URI components)
        self.pattern_len = len(self.pattern)


class UriObservationMap(object):

    """
    Represents the current set of observations maintained by a broker/dealer.

    To test: trial crossbar.router.test.test_subscription
    """

    def __init__(self, ordered=False):
        # flag indicating whether observers should be maintained in a SortedSet
        # or a regular set (unordered)
        self._ordered = ordered

        # map: URI => ExactUriObservation
        self._observations_exact = {}

        # map: URI => PrefixUriObservation
        self._observations_prefix = StringTrie()

        # map: URI => WildcardUriObservation
        self._observations_wildcard = {}

        # map: pattern length => (map: pattern => pattern count)
        self._observations_wildcard_patterns = {}

        # map: observation ID => UriObservation
        self._observation_id_to_observation = {}

    def add_observer(self, observer, uri, match=u"exact", extra=None):
        """
        Adds a observer to the observation set and returns the respective observation.

        :param observer: The observer to add (this can be any opaque object).
        :type observer: obj
        :param uri: The URI (or URI pattern) to add the observer to add to.
        :type uri: unicode
        :param match: The matching policy for observing, one of ``u"exact"``, ``u"prefix"`` or ``u"wildcard"``.
        :type match: unicode

        :returns: A tuple ``(observation, was_already_observed, was_first_observer)``. Here,
            ``observation`` is an instance of one of ``ExactUriObservation``, ``PrefixUriObservation`` or ``WildcardUriObservation``.
        :rtype: tuple
        """
        if match == u"exact":

            # if the exact-matching URI isn't in our map, create a new observation
            #
            if uri not in self._observations_exact:
                self._observations_exact[uri] = ExactUriObservation(uri, ordered=self._ordered, extra=extra)
                is_first_observer = True
            else:
                is_first_observer = False

            # get the observation
            #
            observation = self._observations_exact[uri]

        elif match == u"prefix":

            # if the prefix-matching URI isn't in our map, create a new observation
            #
            if uri not in self._observations_prefix:
                self._observations_prefix[uri] = PrefixUriObservation(uri, ordered=self._ordered, extra=extra)
                is_first_observer = True
            else:
                is_first_observer = False

            # get the observation
            #
            observation = self._observations_prefix[uri]

        elif match == u"wildcard":

            # if the wildcard-matching URI isn't in our map, create a new observation
            #
            if uri not in self._observations_wildcard:

                observation = WildcardUriObservation(uri, ordered=self._ordered, extra=extra)

                self._observations_wildcard[uri] = observation
                is_first_observer = True

                # setup map: pattern length -> patterns
                if observation.pattern_len not in self._observations_wildcard_patterns:
                    self._observations_wildcard_patterns[observation.pattern_len] = {}

                # setup map: (pattern length, pattern) -> pattern count
                if observation.pattern not in self._observations_wildcard_patterns[observation.pattern_len]:
                    self._observations_wildcard_patterns[observation.pattern_len][observation.pattern] = 1
                else:
                    self._observations_wildcard_patterns[observation.pattern_len][observation.pattern] += 1

            else:
                is_first_observer = False

            # get the observation
            #
            observation = self._observations_wildcard[uri]

        else:
            raise Exception("invalid match strategy '{}'".format(match))

        # note observation in observation ID map
        #
        if is_first_observer:
            self._observation_id_to_observation[observation.id] = observation

        # add observer if not already in observation
        #
        if observer not in observation.observers:
            observation.observers.add(observer)
            was_already_observed = False
        else:
            was_already_observed = True

        return observation, was_already_observed, is_first_observer

    def get_observation(self, uri, match=u"exact"):
        """
        Get a observation (if any) for given URI and match policy.

        :param uri: The URI (or URI pattern) to get the observation for.
        :type uri: unicode
        :param match: The matching policy for observation to retrieve, one of ``u"exact"``, ``u"prefix"`` or ``u"wildcard"``.
        :type match: unicode

        :returns: The observation (instance of one of ``ExactUriObservation``, ``PrefixUriObservation`` or ``WildcardUriObservation``)
            or ``None``.
        :rtype: obj or None
        """
        if match == u"exact":

            return self._observations_exact.get(uri, None)

        elif match == u"prefix":

            return self._observations_prefix.get(uri, None)

        elif match == u"wildcard":

            return self._observations_wildcard.get(uri, None)

        else:
            raise Exception("invalid match strategy '{}'".format(match))

    def match_observations(self, uri):
        """
        Returns the observations matching the given URI. This is the core method called
        by a broker to actually dispatch events.

        :param uri: The URI to match.
        :type uri: unicode

        :returns: A list of observations matching the URI. This is a list of instance of
            one of ``ExactUriObservation``, ``PrefixUriObservation`` or ``WildcardUriObservation``.
        :rtype: list
        """
        observations = []

        if uri in self._observations_exact:
            observations.append(self._observations_exact[uri])

        for observation in self._observations_prefix.iter_prefix_values(uri):
            observations.append(observation)

        uri_parts = tuple(uri.split('.'))
        uri_parts_len = len(uri_parts)
        if uri_parts_len in self._observations_wildcard_patterns:
            for pattern in self._observations_wildcard_patterns[uri_parts_len]:
                patterned_uri = '.'.join(['' if pattern[i] else uri_parts[i] for i in range(uri_parts_len)])
                if patterned_uri in self._observations_wildcard:
                    observations.append(self._observations_wildcard[patterned_uri])

        return observations

    def best_matching_observation(self, uri):
        """
        Returns the observation that best matches the given URI. This is the core method called
        by a dealer to actually forward calls.

        :param uri: The URI to match.
        :type uri: unicode

        :returns: The observation best matching the URI. This is an instance of
            ``ExactUriObservation``, ``PrefixUriObservation`` or ``WildcardUriObservation`` or ``None``.
        :rtype: obj or None
        """
        # a exact matching observation is always "best", if any
        #
        if uri in self._observations_exact:
            return self._observations_exact[uri]

        # "second best" is the longest prefix-matching observation, if any
        # FIXME: do we want this to take precedence over _any_ wildcard (see below)?
        #
        try:
            return self._observations_prefix.longest_prefix_value(uri)
        except KeyError:
            pass

        # FIXME: for wildcard observations, when there are multiple matching, we'd
        # like to deterministically select the "most selective one"
        # We first need a definition of "most selective", and then we need to implement
        # this here.
        #
        uri_parts = tuple(uri.split('.'))
        uri_parts_len = len(uri_parts)
        if uri_parts_len in self._observations_wildcard_patterns:
            for pattern in self._observations_wildcard_patterns[uri_parts_len]:
                patterned_uri = '.'.join(['' if pattern[i] else uri_parts[i] for i in range(uri_parts_len)])
                if patterned_uri in self._observations_wildcard:
                    return self._observations_wildcard[patterned_uri]

    def get_observation_by_id(self, id):
        """
        Get a observation by ID.

        :param id: The ID of the observation to retrieve.
        :type id: int

        :returns: The observation for the given ID or ``None``.
        :rtype: obj or None
        """
        return self._observation_id_to_observation.get(id, None)

    def drop_observer(self, observer, observation):
        """
        Drop a observer from a observation.

        :param observer: The observer to drop from the given observation.
        :type observer: obj
        :param observation: The observation from which to drop the observer. An instance
            of ``ExactUriObservation``, ``PrefixUriObservation`` or ``WildcardUriObservation`` previously
            created and handed out by this observation map.
        :type observation: obj

        :returns: A tuple ``(was_observed, was_last_observer)``.
        :rtype: tuple
        """
        if observer in observation.observers:

            was_observed = True

            # remove observer from observation
            #
            observation.observers.discard(observer)

            # no more observers on this observation!
            #
            if not observation.observers:

                if observation.match == u"exact":
                    del self._observations_exact[observation.uri]

                elif observation.match == u"prefix":
                    del self._observations_prefix[observation.uri]

                elif observation.match == u"wildcard":

                    # cleanup if this was the last observation with given pattern
                    self._observations_wildcard_patterns[observation.pattern_len][observation.pattern] -= 1
                    if not self._observations_wildcard_patterns[observation.pattern_len][observation.pattern]:
                        del self._observations_wildcard_patterns[observation.pattern_len][observation.pattern]

                    # cleanup if this was the last observation with given pattern length
                    if not self._observations_wildcard_patterns[observation.pattern_len]:
                        del self._observations_wildcard_patterns[observation.pattern_len]

                    # remove actual observation
                    del self._observations_wildcard[observation.uri]

                else:
                    # should not arrive here
                    raise Exception("logic error")

                was_last_observer = True

                del self._observation_id_to_observation[observation.id]

            else:
                was_last_observer = False

        else:
            # observer wasn't on this observation
            was_observed = False

        return was_observed, was_last_observer
