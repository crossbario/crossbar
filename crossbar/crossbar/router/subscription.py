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


class Subscription(object):
    """
    Represents a subscription maintained by the broker.
    """

    def __init__(self, topic, match):
        # topic this subscription is created for
        self.topic = topic

        # matching method this subscription is created for
        self.match = match

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


class SubscriptionMap(object):
    """
    Represents the current set of subscriptions maintained by the broker.

    trial crossbar.router.test.test_subscription
    """

    def __init__(self):
        self._subscriptions_exact = {}
        self._subscriptions_prefix = StringTrie()
        self._subscriptions_wildcard = {}
        self._subscriptions_wildcard_patterns = {}
        self._subscription_id_to_subscription = {}

    def add_subscriber(self, subscriber, topic, match=Subscribe.MATCH_EXACT):
        """
        Adds a subscriber to the subscription set and returns the respective subscription.

        Returns a tuple:

        subscription, was_already_subscribed, was_first_subscriber
        """
        if match == Subscribe.MATCH_EXACT:

            # if the exact-matching topic isn't in our map, create a new subscription
            #
            if topic not in self._subscriptions_exact:
                self._subscriptions_exact[topic] = Subscription(topic, match)
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
                self._subscriptions_prefix[topic] = Subscription(topic, match)
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

                self._subscriptions_wildcard[topic] = Subscription(topic, match)
                is_first_subscriber = True

                pattern = tuple([part == "" for part in topic.split('.')])
                pattern_len = len(pattern)

                if pattern_len not in self._subscriptions_wildcard_patterns:
                    self._subscriptions_wildcard_patterns[pattern_len] = {}

                if pattern not in self._subscriptions_wildcard_patterns[pattern_len]:
                    self._subscriptions_wildcard_patterns[pattern_len][pattern] = 1
                else:
                    self._subscriptions_wildcard_patterns[pattern_len][pattern] += 1

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

    def get_subscriptions(self, topic):
        """
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
        return self._subscription_id_to_subscription.get(id, None)

    def drop_subscriber(self, subscriber, subscription):
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
                    raise Exception("not implemented")

                else:
                    raise Exception("logic error")

                was_last_subscriber = True

            else:
                was_last_subscriber = False

        else:
            # subscriber wasn't on this subscription
            was_subscribed = False

        return was_subscribed, was_last_subscriber
