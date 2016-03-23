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

from __future__ import absolute_import, division

import os
import platform

from collections import deque

from autobahn.util import utcnow

from txaio import make_logger

try:
    if platform.python_implementation() == 'PyPy':
        os.environ['LMDB_FORCE_CFFI'] = '1'
    import lmdb
    HAS_LMDB = True
except ImportError:
    HAS_LMDB = False

__all__ = ('HAS_LMDB', 'MemoryRealmStore', 'LmdbRealmStore')


class MemoryEventStore(object):
    """
    Event store in-memory implementation.
    """

    log = make_logger()

    GLOBAL_HISTORY_LIMIT = 100
    """
    The global history limit, in case not overridden.
    """

    def __init__(self, config=None):
        """

        config = {
            'type': 'memory',
            'limit': 1000,           <- global history limit (in case no topic specific limit has been set)
            'event-history': [
                {
                    'uri': 'com.example.foobar',   <- topic specific limit
                    'match': 'prefix',
                    'limit': 10000
                }
            ]
        }
        """
        # whole store configuration
        self._config = config or {}

        # limit to event history per subscription
        self._limit = self._config.get('limit', self.GLOBAL_HISTORY_LIMIT)

        # map of publication ID -> event dict
        self._event_store = {}

        # map of publication ID -> set of subscription IDs
        self._event_subscriptions = {}

        # map of subscription ID -> (limit, deque(of publication IDs))
        self._event_history = {}

    def attach_subscription_map(self, subscription_map):
        for sub in self._config.get('event-history', []):
            uri = sub['uri']
            match = sub.get('match', u'exact')
            observation, was_already_observed, was_first_observer = subscription_map.add_observer(self, uri=uri, match=match)
            subscription_id = observation.id

            # for in-memory history, we just use a double-ended queue
            self._event_history[subscription_id] = (sub.get('limit', self._limit), deque())

    def store_event(self, publisher_id, publication_id, topic, args=None, kwargs=None):
        """
        Persist the given event to history.

        :param publisher_id: The session ID of the publisher of the event being persisted.
        :type publisher_id: int
        :param publication_id: The publication ID of the event.
        :type publisher_id: int
        :param topic: The topic URI of the event.
        :type topic: unicode
        :param args: The args payload of the event.
        :type args: list or None
        :param kwargs: The kwargs payload of the event.
        :type kwargs: dict or None
        """
        assert(publication_id not in self._event_store)
        evt = {
            u'timestamp': utcnow(),
            u'publisher': publisher_id,
            u'publication': publication_id,
            u'topic': topic,
            u'args': args,
            u'kwargs': kwargs
        }
        self._event_store[publication_id] = evt
        self.log.debug("Event {publication_id} persisted", publication_id=publication_id)

    def store_event_history(self, publication_id, subscription_id):
        """
        Persist the given publication history to subscriptions.

        :param publication_id: The ID of the event publication to be persisted.
        :type publication_id: int
        :param subscription_id: The ID of the subscription the event (identified by the publication ID),
            was published to, because the event's topic matched the subscription.
        :type subscription_id: int
        """
        assert(publication_id in self._event_store)
        assert(subscription_id in self._event_history)

        limit, history = self._event_history[subscription_id]

        # append event to history
        history.append(publication_id)

        if publication_id not in self._event_subscriptions:
            self._event_subscriptions[publication_id] = set()

        self._event_subscriptions[publication_id].add(subscription_id)

        self.log.debug("Event {publication_id} history persisted for subscription {subscription_id}", publication_id=publication_id, subscription_id=subscription_id)

        # purge history if over limit
        if len(history) > limit:

            # remove leftmost event from history
            purged_publication_id = history.popleft()

            # remove the purged publication from event subscriptions
            self._event_subscriptions[purged_publication_id].remove(subscription_id)

            self.log.debug("Event {publication_id} purged fom history for subscription {subscription_id}", publication_id=purged_publication_id, subscription_id=subscription_id)

            # if no more event subscriptions exist for publication, remove that too
            if not self._event_subscriptions[purged_publication_id]:
                del self._event_subscriptions[purged_publication_id]
                del self._event_store[purged_publication_id]
                self.log.debug("Event {publication_id} purged completey", publication_id=purged_publication_id)

    def get_events(self, subscription_id, limit):
        """
        Retrieve given number of last events for a given subscription.

        If no history is maintained for the given subscription, None is returned.

        :param subscription_id: The ID of the subscription to retrieve events for.
        :type subscription_id: int
        :param limit: Limit number of events returned.
        :type limit: int

        :return: List of events.
        :rtype: list or None
        """
        if subscription_id not in self._event_history:
            return None
        else:
            _, history = self._event_history[subscription_id]

            # at most "limit" events in reverse chronological order
            res = []
            i = -1
            if limit > len(history):
                limit = len(history)
            for _ in range(limit):
                publication_id = history[i]
                res.append(self._event_store[publication_id])
                i -= 1
            return res

    def get_event_history(self, subscription_id, from_ts, until_ts):
        """
        Retrieve event history for time range for a given subscription.

        If no history is maintained for the given subscription, None is returned.

        :param subscription_id: The ID of the subscription to retrieve events for.
        :type subscription_id: int
        :param from_ts: Filter events from this date (string in ISO-8601 format).
        :type from_ts: unicode
        :param until_ts: Filter events until this date (string in ISO-8601 format).
        :type until_ts: unicode
        """
        raise Exception("not implemented")


class MemoryRealmStore(object):
    """
    """

    event_store = None
    """
    """

    def __init__(self, config):
        self.event_store = MemoryEventStore(config)


class LmdbEventStore(object):
    """
    """

    def __init__(self, env):
        self._env = env
        self._event_history = self._env.open_db('event-history')


class LmdbRealmStore(object):
    """
    """

    event_store = None
    """
    """

    def __init__(self, config):
        self._env = lmdb.open(config['dbfile'], max_dbs=16, writemap=True)
        self.event_store = LmdbEventStore(self._env)
