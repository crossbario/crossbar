#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from collections import deque

from txaio import use_twisted  # noqa
from txaio import make_logger, time_ns

from autobahn.util import hltype

__all__ = ('RealmStoreMemory', )


class QueuedCall(object):

    __slots__ = ('session', 'call', 'registration', 'authorization')

    def __init__(self, session, call, registration, authorization):
        self.session = session
        self.call = call
        self.registration = registration
        self.authorization = authorization


class RealmStoreMemory(object):
    """
    Memory-backed realm store.
    """

    log = make_logger()

    STORE_TYPE = 'memory'

    GLOBAL_HISTORY_LIMIT = 100
    """
    The global history limit, in case not overridden.
    """
    def __init__(self, personality, factory, config):
        """

        See the example here:

        https://github.com/crossbario/crossbar-examples/tree/master/scaling-microservices/queued

        .. code-block:: json

            "store": {
                "type": "memory",
                "limit": 1000,      // global default for limit on call queues
                "call-queue": [
                    {
                        "uri": "com.example.compute",
                        "match": "exact",
                        "limit": 10000  // procedure specific call queue limit
                    }
                ]
            }
        """
        from twisted.internet import reactor

        self._reactor = reactor
        self._personality = personality
        self._factory = factory
        self._config = config or {}

        # limit to event history per subscription
        self._limit = self._config.get('limit', self.GLOBAL_HISTORY_LIMIT)

        # map of publication ID -> event dict
        self._event_store = {}

        # map of publication ID -> set of subscription IDs
        self._event_subscriptions = {}

        # map of subscription ID -> (limit, deque(of publication IDs))
        self._event_history = {}

        # map: registration.id -> deque( (session, call, registration, authorization) )
        self._queued_calls = {}

        self.log.info('{func} realm store initialized (type=memory)', func=hltype(self.__init__))

    def attach_subscription_map(self, subscription_map):
        for sub in self._config.get('event-history', []):
            uri = sub['uri']
            match = sub.get('match', 'exact')
            observation, was_already_observed, was_first_observer = subscription_map.add_observer(self,
                                                                                                  uri=uri,
                                                                                                  match=match)
            subscription_id = observation.id

            # for in-memory history, we just use a double-ended queue
            self._event_history[subscription_id] = (sub.get('limit', self._limit), deque())

    def store_session_joined(self, session, session_details):
        self.log.debug('{klass}.store_session_join(session={session}, session_details={session_details})',
                       klass=self.__class__.__name__,
                       session=session,
                       session_details=session_details)

    def store_session_left(self, session, session_details, close_details):
        self.log.debug(
            '{klass}.store_session_left(session={session}, session_details={session_details}, close_details={close_details})',
            klass=self.__class__.__name__,
            session=session,
            session_details=session_details,
            close_details=close_details)

    def store_event(self, session, publication_id, publish):
        """
        Store event to event history.

        :param session: The publishing session.
        :type session: :class:`autobahn.wamp.interfaces.ISession`

        :param publication_id: The WAMP publication ID under which the publish happens
        :type publication_id: int

        :param publish: The WAMP publish message.
        :type publish: :class:`autobahn.wamp.messages.Publish`
        """
        assert (publication_id not in self._event_store)
        evt = {
            'time_ns': time_ns(),
            'realm': session._realm,
            'session_id': session._session_id,
            'authid': session._authid,
            'authrole': session._authrole,
            'publication': publication_id,
            'topic': publish.topic,
            'args': publish.args,
            'kwargs': publish.kwargs
        }
        self._event_store[publication_id] = evt
        self.log.debug("Event {publication_id} stored in {store_type}-store",
                       store_type=self.STORE_TYPE,
                       publication_id=publication_id)

    def store_event_history(self, publication_id, subscription_id, receiver):
        """
        Store publication history for subscription.

        :param publication_id: The ID of the event publication to be persisted.
        :type publication_id: int

        :param subscription_id: The ID of the subscription the event (identified by the publication ID),
            was published to, because the event's topic matched the subscription.
        :type subscription_id: int
        """
        # assert(publication_id in self._event_store)
        # assert(subscription_id in self._event_history)

        if publication_id not in self._event_store:
            self.log.warn('INTERNAL WARNING: event for publication {publication_id} not in event store',
                          publication_id=publication_id)

        if subscription_id not in self._event_history:
            self.log.warn(
                'INTERNAL WARNING: subscription {subscription_id} for publication {publication_id} not in event store',
                subscription_id=subscription_id,
                publication_id=publication_id)
            return

        limit, history = self._event_history[subscription_id]

        # append event to history
        history.append(publication_id)

        if publication_id not in self._event_subscriptions:
            self._event_subscriptions[publication_id] = set()

        self._event_subscriptions[publication_id].add(subscription_id)

        self.log.debug(
            "Event {publication_id} history stored in {store_type}-store for subscription {subscription_id}",
            store_type=self.STORE_TYPE,
            publication_id=publication_id,
            subscription_id=subscription_id)

        # purge history if over limit
        if len(history) > limit:

            # remove leftmost event from history
            purged_publication_id = history.popleft()

            # remove the purged publication from event subscriptions
            self._event_subscriptions[purged_publication_id].remove(subscription_id)

            self.log.debug("Event {publication_id} purged from history for subscription {subscription_id}",
                           publication_id=purged_publication_id,
                           subscription_id=subscription_id)

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

    def maybe_queue_call(self, session, call, registration, authorization):
        # FIXME: match this against the config, not just plain accept queueing!
        if registration.id not in self._queued_calls:
            self._queued_calls[registration.id] = deque()

        self._queued_calls[registration.id].append(QueuedCall(session, call, registration, authorization))

        return True

    def get_queued_call(self, registration):
        if registration.id in self._queued_calls and self._queued_calls[registration.id]:
            return self._queued_calls[registration.id][0]

    def pop_queued_call(self, registration):
        if registration.id in self._queued_calls and self._queued_calls[registration.id]:
            return self._queued_calls[registration.id].popleft()
