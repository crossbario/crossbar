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
from autobahn.wamp.message import Subscribe

__all__ = ('SubscriptionMap',)


class Subscription(object):
    """
    Represents a subscription maintained by the broker.
    """
    match = None

    def __init__(self, topic):
        """

        :param topic: The topic (or topic pattern) for this subscription.
        :type topic: unicode
        """
        # topic (or topic pattern) this subscription is created for
        self.topic = topic

        # generate a new ID for the subscription
        self.id = util.id()

        # set of subscribers
        self.subscribers = set()

    def __getstate__(self):
        return {
            'id': self.id,
            'topic': self.topic,
            'match': self.match,
        }

    def __setstate__(self, state):
        self.topic = state['topic']
        self.match = state['match']
        self.id = state['id']
        self.subscribers = set()


class ExactSubscription(Subscription):
    """
    Represents an exact-matching subscription.
    """

    match = u"exact"


class PrefixSubscription(Subscription):
    """
    Represents a prefix-matching subscription.
    """

    match = u"prefix"


class WildcardSubscription(Subscription):
    """
    Represents a wildcard-matching subscription.
    """
    match = u"wildcard"

    def __init__(self, topic):
        Subscription.__init__(self, topic)

        # a topic pattern like "com.example..create" will have a pattern (False, False, True, False)
        self.pattern = tuple([part == "" for part in self.topic.split('.')])

        # length of the pattern (above would have length 4, as it consists of 4 URI components)
        self.pattern_len = len(self.pattern)


class SubscriptionMap(object):
    """
    Represents the current set of subscriptions maintained by the broker.

    To test: trial crossbar.router.test.test_subscription
    """

    def __init__(self):
        # map: topic => ExactSubscription
        self._subscriptions_exact = {}

        # map: topic => PrefixSubscription
        self._subscriptions_prefix = StringTrie()

        # map: topic => WildcardSubscription
        self._subscriptions_wildcard = {}

        # map: pattern length => (map: pattern => pattern count)
        self._subscriptions_wildcard_patterns = {}

        # map: subscription ID => Subscription
        self._subscription_id_to_subscription = {}

    def add_subscriber(self, subscriber, topic, match=Subscribe.MATCH_EXACT):
        """
        Adds a subscriber to the subscription set and returns the respective subscription.

        :param subscriber: The subscriber to add (this can be any opaque object).
        :type subscriber: obj
        :param topic: The topic (or topic pattern) to add the subscriber to add to.
        :type topic: unicode
        :param match: The matching policy for subscribing, one of ``u"exact"``, ``u"prefix"`` or ``u"wildcard"``.
        :type match: unicode

        :returns: A tuple ``(subscription, was_already_subscribed, was_first_subscriber)``. Here,
            ``subscription`` is an instance of one of ``ExactSubscription``, ``PrefixSubscription`` or ``WildcardSubscription``.
        :rtype: tuple
        """
        if match == Subscribe.MATCH_EXACT:

            # if the exact-matching topic isn't in our map, create a new subscription
            #
            if topic not in self._subscriptions_exact:
                self._subscriptions_exact[topic] = ExactSubscription(topic)
                is_first_subscriber = True
            else:
                is_first_subscriber = False

            # get the subscription
            #
            subscription = self._subscriptions_exact[topic]

        elif match == Subscribe.MATCH_PREFIX:

            # if the prefix-matching topic isn't in our map, create a new subscription
            #
            if topic not in self._subscriptions_prefix:
                self._subscriptions_prefix[topic] = PrefixSubscription(topic)
                is_first_subscriber = True
            else:
                is_first_subscriber = False

            # get the subscription
            #
            subscription = self._subscriptions_prefix[topic]

        elif match == Subscribe.MATCH_WILDCARD:

            # if the prefix-matching topic isn't in our map, create a new subscription
            #
            if topic not in self._subscriptions_wildcard:

                subscription = WildcardSubscription(topic)

                self._subscriptions_wildcard[topic] = subscription
                is_first_subscriber = True

                # setup map: pattern length -> patterns
                if subscription.pattern_len not in self._subscriptions_wildcard_patterns:
                    self._subscriptions_wildcard_patterns[subscription.pattern_len] = {}

                # setup map: (pattern length, pattern) -> pattern count
                if subscription.pattern not in self._subscriptions_wildcard_patterns[subscription.pattern_len]:
                    self._subscriptions_wildcard_patterns[subscription.pattern_len][subscription.pattern] = 1
                else:
                    self._subscriptions_wildcard_patterns[subscription.pattern_len][subscription.pattern] += 1

            else:
                is_first_subscriber = False

            # get the subscription
            #
            subscription = self._subscriptions_wildcard[topic]

        else:
            raise Exception("invalid match strategy '{}'".format(match))

        # note subscription in subscription ID map
        #
        if is_first_subscriber:
            self._subscription_id_to_subscription[subscription.id] = subscription

        # add subscriber if not already in subscription
        #
        if subscriber not in subscription.subscribers:
            subscription.subscribers.add(subscriber)
            was_already_subscribed = False
        else:
            was_already_subscribed = True

        return subscription, was_already_subscribed, is_first_subscriber

    def get_subscription(self, topic, match=Subscribe.MATCH_EXACT):
        """
        Get a subscription (if any) for given topic and match policy.

        :param topic: The topic (or topic pattern) to get the subscription for.
        :type topic: unicode
        :param match: The matching policy for subscription to retrieve, one of ``u"exact"``, ``u"prefix"`` or ``u"wildcard"``.
        :type match: unicode

        :returns: The subscription (instance of one of ``ExactSubscription``, ``PrefixSubscription`` or ``WildcardSubscription``)
            or ``None``.
        :rtype: obj or None
        """
        if match == Subscribe.MATCH_EXACT:

            return self._subscriptions_exact.get(topic, None)

        elif match == Subscribe.MATCH_PREFIX:

            return self._subscriptions_prefix.get(topic, None)

        elif match == Subscribe.MATCH_WILDCARD:

            return self._subscriptions_wildcard.get(topic, None)

    def match_subscriptions(self, topic):
        """
        Returns the subscriptions matching the given topic. This is the core method called
        by the broker to actually dispatch events being published to receiving sessions.

        :param topic: The topic to match.
        :type topic: unicode

        :returns: A list of subscriptions matching the topic. This is a list of instance of
            one of ``ExactSubscription``, ``PrefixSubscription`` or ``WildcardSubscription``.
        :rtype: list
        """
        subscriptions = []

        if topic in self._subscriptions_exact:
            subscriptions.append(self._subscriptions_exact[topic])

        for subscription in self._subscriptions_prefix.iter_prefix_values(topic):
            subscriptions.append(subscription)

        topic_parts = tuple(topic.split('.'))
        topic_parts_len = len(topic_parts)
        if topic_parts_len in self._subscriptions_wildcard_patterns:
            for pattern in self._subscriptions_wildcard_patterns[topic_parts_len]:
                patterned_topic = '.'.join(['' if pattern[i] else topic_parts[i] for i in range(topic_parts_len)])
                if patterned_topic in self._subscriptions_wildcard:
                    subscriptions.append(self._subscriptions_wildcard[patterned_topic])

        return subscriptions

    def get_subscription_by_id(self, id):
        """
        Get a subscription by ID.

        :param id: The ID of the subscription to retrieve.
        :type id: int

        :returns: The subscription for the given ID or ``None``.
        :rtype: obj or None
        """
        return self._subscription_id_to_subscription.get(id, None)

    def drop_subscriber(self, subscriber, subscription):
        """
        Drop a subscriber from a subscription.

        :param subscriber: The subscriber to drop from the given subscription.
        :type subscriber: obj
        :param subscription: The subscription from which to drop the subscriber. An instance
            of ``ExactSubscription``, ``PrefixSubscription`` or ``WildcardSubscription`` previously
            created and handed out by this subscription map.
        :type subscription: obj

        :returns: A tuple ``(was_subscribed, was_last_subscriber)``.
        :rtype: tuple
        """
        if subscriber in subscription.subscribers:

            was_subscribed = True

            # remove subscriber from subscription
            #
            subscription.subscribers.discard(subscriber)

            # no more subscribers on this subscription!
            #
            if not subscription.subscribers:

                if subscription.match == Subscribe.MATCH_EXACT:
                    del self._subscriptions_exact[subscription.topic]

                elif subscription.match == Subscribe.MATCH_PREFIX:
                    del self._subscriptions_prefix[subscription.topic]

                elif subscription.match == Subscribe.MATCH_WILDCARD:

                    # cleanup if this was the last subscription with given pattern
                    self._subscriptions_wildcard_patterns[subscription.pattern_len][subscription.pattern] -= 1
                    if not self._subscriptions_wildcard_patterns[subscription.pattern_len][subscription.pattern]:
                        del self._subscriptions_wildcard_patterns[subscription.pattern_len][subscription.pattern]

                    # cleanup if this was the last subscription with given pattern length
                    if not self._subscriptions_wildcard_patterns[subscription.pattern_len]:
                        del self._subscriptions_wildcard_patterns[subscription.pattern_len]

                    # remove actual subscription
                    del self._subscriptions_wildcard[subscription.topic]

                else:
                    # should not arrive here
                    raise Exception("logic error")

                was_last_subscriber = True

            else:
                was_last_subscriber = False

        else:
            # subscriber wasn't on this subscription
            was_subscribed = False

        return was_subscribed, was_last_subscriber
