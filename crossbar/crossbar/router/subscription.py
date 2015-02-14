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

    def __init__(self):
        self.id = util.id()
        self.subs = set()


class SubscriptionMap(object):
    """
    trial crossbar.router.test.test_subscription
    """

    def __init__(self):
        self._subs_exact = {}
        self._subs_prefix = StringTrie()

    def add_subscriber(self, subscriber, topic, match=Subscribe.MATCH_EXACT):
        """
        """
        if match == Subscribe.MATCH_EXACT:
            if topic not in self._subs_exact:
                self._subs_exact[topic] = Subscription()
            sub = self._subs_exact[topic]
            if subscriber not in sub.subs:
                sub.subs.add(subscriber)
            return sub.id

        elif match == Subscribe.MATCH_PREFIX:
            if topic not in self._subs_prefix:
                self._subs_prefix[topic] = Subscription()
            sub = self._subs_prefix[topic]
            if subscriber not in sub.subs:
                sub.subs.add(subscriber)
            return sub.id

        elif match == Subscribe.MATCH_WILDCARD:
            raise Exception("not implemented")

        else:
            raise Exception("invalid match strategy '{}'".format(match))

    def get_subscribers(self, topic):
        """
        """
        subs = set()

        if topic in self._subs_exact:
            subs.update(self._subs_exact[topic].subs)

        for subscription in self._subs_prefix.iter_prefix_values(topic):
            subs.update(subscription.subs)

        return subs
