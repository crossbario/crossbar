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

from __future__ import absolute_import

from pytrie import StringTrie
from crossbar.router.wildcard import WildcardMatcher, WildcardTrieMatcher

from autobahn import util

__all__ = (
    'UriObservationMap',
    'is_protected_uri'
)


def is_protected_uri(uri, details=None):
    """
    Test if the given URI is from a "protected namespace" (starting with `wamp.`
    or `crossbar.`). Note that "trusted" clients can access all namespaces.
    """
    trusted = details and details.caller_authrole == u'trusted'
    if trusted:
        return False
    else:
        return uri.startswith(u'wamp.') or uri.startswith(u'crossbar.')


class OrderedSet(set):

    __slots__ = ('_list',)

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

    __slots__ = (
        'uri',
        'ordered',
        'extra',
        'id',
        'created',
        'observers'
    )

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

        # arbitrary, opaque extra data attached to the observers of this observation
        self.observers_extra = {}

    def __repr__(self):
        return "{}(id={}, uri={}, match={}, ordered={}, extra={}, created={}, observers={})".format(
            self.__class__.__name__, self.id, self.uri, self.match, self.ordered, self.extra, self.created,
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


class UriObservationMap(object):

    """
    Represents the current set of observations maintained by a broker/dealer.

    To test: trial crossbar.router.test.test_subscription
    """

    __slots__ = (
        '_ordered',
        '_observations_exact',
        '_observations_prefix',
        '_observations_wildcard',
        '_observation_id_to_observation'
    )

    def __init__(self, ordered=False):
        # flag indicating whether observers should be maintained in a SortedSet
        # or a regular set (unordered)
        self._ordered = ordered

        # map: URI => ExactUriObservation
        self._observations_exact = {}

        # map: URI => PrefixUriObservation
        self._observations_prefix = StringTrie()

        # map: URI => WildcardUriObservation
        if True:
            # use a Trie-based implementation (supposed to be faster, but
            # otherwise compatible to the naive implementation below)
            self._observations_wildcard = WildcardTrieMatcher()
        else:
            self._observations_wildcard = WildcardMatcher()

        # map: observation ID => UriObservation
        self._observation_id_to_observation = {}

    def __repr__(self):
        return "{}(_ordered={}, _observations_exact={}, _observations_wildcard={})".format(
            self.__class__.__name__,
            self._ordered,
            self._observations_exact,
            self._observations_prefix,
            self._observations_wildcard,
            self._observation_id_to_observation)

    def add_observer(self, observer, uri, match=u"exact", extra=None, observer_extra=None):
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
        if not isinstance(uri, str):
            raise Exception("'uri' should be unicode, not {}".format(type(uri).__name__))

        is_first_observer = False

        if match == u"exact":

            # if the exact-matching URI isn't in our map, create a new observation
            #
            if uri not in self._observations_exact:
                self.create_observation(uri, match, extra)
                is_first_observer = True

            # get the observation
            #
            observation = self._observations_exact[uri]

        elif match == u"prefix":

            # if the prefix-matching URI isn't in our map, create a new observation
            #
            if uri not in self._observations_prefix:
                self.create_observation(uri, match, extra)
                is_first_observer = True

            # get the observation
            #
            observation = self._observations_prefix[uri]

        elif match == u"wildcard":

            # if the wildcard-matching URI isn't in our map, create a new observation
            #
            if uri not in self._observations_wildcard:
                self.create_observation(uri, match, extra)
                is_first_observer = True

            # get the observation
            #
            observation = self._observations_wildcard[uri]

        else:
            raise Exception("invalid match strategy '{}'".format(match))

        # add observer if not already in observation
        #
        if observer not in observation.observers:
            was_already_observed = False

            # add the observer to the set of observers sitting on the observation
            observation.observers.add(observer)

            # if there is observer-specific extra data, store it
            if observer_extra:
                observation.observers_extra[observer] = observer_extra
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

        if not isinstance(uri, str):
            raise Exception("'uri' should be unicode, not {}".format(type(uri).__name__))

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

        if not isinstance(uri, str):
            raise Exception("'uri' should be unicode, not {}".format(type(uri).__name__))

        if uri in self._observations_exact:
            observations.append(self._observations_exact[uri])

        for observation in self._observations_prefix.iter_prefix_values(uri):
            observations.append(observation)

        for observation in self._observations_wildcard.iter_matches(uri):
            observations.append(observation)

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
        if not isinstance(uri, str):
            raise Exception("'uri' should be unicode, not {}".format(type(uri).__name__))

        # a exact matching observation is always "best", if any
        if uri in self._observations_exact:
            return self._observations_exact[uri]

        # "second best" is the longest prefix-matching observation, if any
        # FIXME: do we want this to take precedence over _any_ wildcard (see below)?
        try:
            return self._observations_prefix.longest_prefix_value(uri)
        except KeyError:
            # workaround because of https://bitbucket.org/gsakkis/pytrie/issues/4/string-keys-of-zero-length-are-not
            if u'' in self._observations_prefix:
                return self._observations_prefix[u'']

        # FIXME: for wildcard observations, when there are multiple matching, we'd
        # like to deterministically select the "most selective one"
        # We first need a definition of "most selective", and then we need to implement
        # this here.
        for observation in self._observations_wildcard.iter_matches(uri):
            return observation

    def get_observation_by_id(self, id):
        """
        Get a observation by ID.

        :param id: The ID of the observation to retrieve.
        :type id: int

        :returns: The observation for the given ID or ``None``.
        :rtype: obj or None
        """
        return self._observation_id_to_observation.get(id, None)

    def create_observation(self, uri, match=u"exact", extra=None):
        """
        Create an observation with no observers.

        :param uri: The URI (or URI pattern) to get the observation for.
        :type uri: unicode
        :param match: The matching policy for observation to retrieve, one of ``u"exact"``, ``u"prefix"`` or ``u"wildcard"``.
        :type match: unicode

        :returns: The observation (instance of one of ``ExactUriObservation``, ``PrefixUriObservation`` or ``WildcardUriObservation``).
        :rtype: obj
        """
        if match == u"exact":
            observation = ExactUriObservation(uri, ordered=self._ordered, extra=extra)
            self._observations_exact[uri] = observation
        elif match == u"prefix":
            observation = PrefixUriObservation(uri, ordered=self._ordered, extra=extra)
            self._observations_prefix[uri] = observation
        elif match == u"wildcard":
            observation = WildcardUriObservation(uri, ordered=self._ordered, extra=extra)
            self._observations_wildcard[uri] = observation

        # note observation in observation ID map
        #
        self._observation_id_to_observation[observation.id] = observation

        return observation

    def drop_observer(self, observer, observation):
        """
        Drop a observer from a observation.

        :param observer: The observer to drop from the given observation.
        :type observer: obj
        :param observation: The observation from which to drop the observer. An instance
            of ``ExactUriObservation``, ``PrefixUriObservation`` or ``WildcardUriObservation`` previously
            created and handed out by this observation map.
        :type observation: obj
        :param delete: Whether or not to delete the observation if they are the last observer.
        :type delete: bool

        :returns: A tuple ``(was_observed, was_last_observer)``.
        :rtype: tuple
        """
        was_last_observer = False

        if observer in observation.observers:
            was_observed = True

            # remove observer from observation
            #
            observation.observers.discard(observer)

            # discard observer-level extra data (if any)
            #
            if observer in observation.observers_extra:
                del observation.observers_extra[observer]

            # no more observers on this observation!
            #
            if not observation.observers:
                was_last_observer = True

        else:
            # observer wasn't on this observation
            was_observed = False

        return was_observed, was_last_observer

    def delete_observation(self, observation):
        """
        Delete the observation from the map.

        :param observation: The observation which to remove from the map. An instance
            of ``ExactUriObservation``, ``PrefixUriObservation`` or ``WildcardUriObservation`` previously
            created and handed out by this observation map.
        :type observation: obj

        :rtype: None
        """

        if observation.observers:
            raise ValueError("Can't delete an observation with current observers.")

        if observation.match == u"exact":
            del self._observations_exact[observation.uri]

        elif observation.match == u"prefix":
            del self._observations_prefix[observation.uri]

        elif observation.match == u"wildcard":
            del self._observations_wildcard[observation.uri]

        else:
            # should not arrive here
            raise Exception("logic error")

        del self._observation_id_to_observation[observation.id]
