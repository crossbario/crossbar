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
            raise Exception("not implemented")

        else:
            raise Exception("invalid match strategy '{}'".format(match))

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

        return subscriptions
