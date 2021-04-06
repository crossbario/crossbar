##############################################################################
#
#                        Crossbar.io FX
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from collections import deque

import zlmdb
import numpy as np

from twisted.internet.defer import inlineCallbacks

from txaio import time_ns
from autobahn.twisted.util import sleep
from autobahn.wamp import message
from autobahn.wamp.types import SessionDetails, CloseDetails

from crossbar.router.session import RouterSession
import cfxdb

__all__ = ('CfxDbRealmStore', )


class CfxDbQueuedCall(object):

    __slots__ = ('session', 'call', 'registration', 'authorization')

    def __init__(self, session, call, registration, authorization):
        self.session = session
        self.call = call
        self.registration = registration
        self.authorization = authorization


class CfxDbCallQueue(object):
    """
    ZLMDB-backed call queue.
    """

    GLOBAL_QUEUE_LIMIT = 1000
    """
    The global call queue limit, in case not overridden.
    """
    def __init__(self, reactor, db, schema, config):
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
        self.log = db.log

        self._reactor = reactor
        self._running = False
        self._db = db
        self._schema = schema

        # whole store configuration
        self._config = config

        # limit to call queue per registration
        self._limit = self._config.get('limit', self.GLOBAL_QUEUE_LIMIT)

        # map: registration.id -> deque( (session, call, registration, authorization) )
        self._queued_calls = {}

    def start(self):
        if self._running:
            raise RuntimeError('call queue is already running')
        self._queued_calls = {}
        self._running = True

    def stop(self):
        if not self._running:
            raise RuntimeError('call queue is not running')
        self._running = False

    def maybe_queue_call(self, session, call, registration, authorization):
        # FIXME: match this against the config, not just plain accept queueing!
        if registration.id not in self._queued_calls:
            self._queued_calls[registration.id] = deque()

        self._queued_calls[registration.id].append(CfxDbQueuedCall(session, call, registration, authorization))

        return True

    def get_queued_call(self, registration):
        if registration.id in self._queued_calls and self._queued_calls[registration.id]:
            return self._queued_calls[registration.id][0]

    def pop_queued_call(self, registration):
        if registration.id in self._queued_calls and self._queued_calls[registration.id]:
            return self._queued_calls[registration.id].popleft()


class CfxDbEventStore(object):
    """
    ZLMDB-backed event store.
    """

    GLOBAL_HISTORY_LIMIT = 100
    """
    The global history limit, in case not overridden.
    """

    STORE_TYPE = 'zlmdb'

    def __init__(self, reactor, db, schema, config):
        self.log = db.log

        self._reactor = reactor
        self._running = False
        self._db = db
        self._schema = schema

        self._config = config
        self._max_buffer = config.get('max-buffer', 10000)

        self._buffer_flush = config.get('buffer-flush', 200)
        self._buffer = []

        self._log_counter = 0

    @inlineCallbacks
    def start(self):
        if self._running:
            raise RuntimeError('store is already running')
        else:
            self.log.info('Starting CfxDbEventStore ..')
        self._buffer = []
        self._log_counter = 0
        self._running = True
        yield self._reactor.callInThread(self._process_buffers)

    def stop(self):
        if not self._running:
            raise RuntimeError('store is not running')
        else:
            self.log.info('Stopping CfxDbEventStore ..')
        self._running = False
        self._buffer = []
        self._log_counter = 0

    @inlineCallbacks
    def _process_buffers(self):
        self.log.debug('ZLMDB buffer background writer starting')
        while self._running:
            cnt, errs, duration_ms = self._process_buffer()
            if cnt > 0:
                self.log.debug('ZLMDB buffer background writer processed {cnt} records in {duration_ms} ms',
                               cnt=cnt,
                               duration_ms=duration_ms)
            if errs > 0:
                self.log.warn('ZLMDB buffer background writer encountered {errs} errors', errs=errs)
            if duration_ms < self._buffer_flush:
                sleep_ms = int(self._buffer_flush - duration_ms)
            else:
                sleep_ms = self._buffer_flush
            self.log.debug('Throttling buffer background writer (sleeping {sleep_ms} ms)', sleep_ms=sleep_ms)
            yield sleep(float(sleep_ms) / 1000.)
        self.log.debug('ZLMDB buffer background writer ended')

    def _process_buffer(self):
        buffer = self._buffer
        self._buffer = []
        self.log.debug('Processing {cnt} buffered records', cnt=len(buffer))
        cnt = 0
        errs = 0
        started = time_ns()
        with self._db.begin(write=True) as txn:
            for rec in buffer:
                func = rec[0]
                args = rec[1:]
                try:
                    func(txn, *args)
                    cnt += 1
                except:
                    self.log.failure()
                    errs += 1
            ended = time_ns()
        duration_ms = int((ended - started) / 1000000)
        return cnt, errs, duration_ms

    def attach_subscription_map(self, subscription_map):
        for sub in self._config.get('event-history', []):
            uri = sub['uri']
            match = sub.get('match', u'exact')
            # observation, was_already_observed, was_first_observer
            subscription_map.add_observer(self, uri=uri, match=match)
            # subscription_id = observation.id

    def store_session_joined(self, session, session_details):
        self.log.debug('{klass}.store_session_join(session={session}, session_details={session_details})',
                       klass=self.__class__.__name__,
                       session=session,
                       session_details=session_details)

        # FIXME
        # crossbar.router.service.RouterServiceAgent
        # assert isinstance(session, RouterSession) or isinstance(session, RouterApplicationSession), 'invalid type {} for session'.format(type(session))
        # assert isinstance(session_details, SessionDetails)

        self._buffer.append([self._store_session_joined, session, session_details])

    def _store_session_joined(self, txn, session, session_details):

        if session._session_id:
            ses = self._schema.sessions[txn, session._session_id]
            if ses:
                self.log.warn('{klass}._store_session_joined(): session {session} already in store',
                              klass=self.__class__.__name__,
                              session=session._session_id)
                return
        else:
            self.log.warn('{klass}._store_session_joined(): cannot store session without session ID',
                          klass=self.__class__.__name__)
            return

        self.log.info(
            '{klass}._store_session_joined(): realm="{realm}", session={session}, authid="{authid}", authrole="{authrole}"',
            klass=self.__class__.__name__,
            realm=session._realm,
            session=session._session_id,
            authid=session._authid,
            authrole=session._authrole)

        ses = cfxdb.eventstore.Session()

        ses.joined_at = time_ns()
        ses.realm = session._realm
        ses.session = session._session_id
        ses.authid = session._authid
        ses.authrole = session._authrole

        self._schema.sessions[txn, session._session_id] = ses

        self.log.debug('store_session_joined: session {session} saved', session=ses)

    def store_session_left(self, session, session_details, close_details):
        self.log.debug(
            '{klass}.store_session_left(session={session}, session_details={session_details}, close_details={close_details})',
            klass=self.__class__.__name__,
            session=session,
            session_details=session_details,
            close_details=close_details)

        assert isinstance(session, RouterSession), 'session must be RouterSession, not {}'.format(type(session))
        assert isinstance(session_details, SessionDetails), 'session_details must be SessionDetails, not {}'.format(
            type(session_details))
        assert isinstance(close_details,
                          CloseDetails), 'close_details must be CloseDetails, not {}'.format(type(close_details))

        self._buffer.append([self._store_session_left, session, session_details, close_details])

    def _store_session_left(self, txn, session, session_details, close_details):

        ses = self._schema.sessions[txn, session_details.session]
        if not ses:
            self.log.warn('{klass}._store_session_left(): session {session} not in store',
                          klass=self.__class__.__name__,
                          session=session_details.session)
            return

        self.log.debug('{klass}._store_session_left(): store_session_left: session {session} loaded',
                       klass=self.__class__.__name__,
                       session=ses)

        ses.left_at = time_ns()

        self._schema.sessions[txn, session_details.session] = ses

        self.log.debug('{klass}._store_session_left(): store_session_left: session {session} updated',
                       klass=self.__class__.__name__,
                       session=ses)

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
        # FIXME: builtins.AssertionError: invalid type <class 'crossbar.router.service.RouterServiceAgent'> for "session"
        # assert isinstance(session, RouterSession), 'invalid type {} for "session"'.format(type(session))
        assert type(publication_id) == int, 'invalid type {} for "publication_id"'.format(type(publication_id))
        assert isinstance(publish, message.Publish), 'invalid type {} for "publish"'.format(type(publish))

        self._buffer.append([self._store_event, session, publication_id, publish])

    def _store_event(self, txn, session, publication_id, publish):

        pub = self._schema.publications[txn, publication_id]
        if pub:
            raise Exception('duplicate event for publication_id={}'.format(publication_id))

        ses = self._schema.sessions[txn, session._session_id] if session._session_id else None
        if not ses:
            self.log.info(
                'session {session} (realm={realm}, authid={authid}, authrole={authrole}) not in store - event on publication {publication_id} not stored!',
                session=session._session_id,
                authid=session._authid,
                authrole=session._authrole,
                realm=session._realm,
                publication_id=publication_id)

        pub = cfxdb.eventstore.Publication()

        pub.timestamp = time_ns()
        pub.publication = publication_id
        pub.publisher = session._session_id

        pub.topic = publish.topic

        # FIXME: runs into pmap assert
        pub.args = list(publish.args) if type(publish.args) == tuple else publish.args

        pub.kwargs = publish.kwargs
        pub.payload = publish.payload
        pub.acknowledge = publish.acknowledge
        pub.retain = publish.retain
        pub.exclude_me = publish.exclude_me
        pub.exclude = publish.exclude
        pub.exclude_authid = publish.exclude_authid
        pub.exclude_authrole = publish.exclude_authrole
        pub.eligible = publish.eligible
        pub.eligible_authid = publish.eligible_authid
        pub.eligible_authrole = publish.eligible_authrole
        pub.enc_algo = publish.enc_algo
        pub.enc_key = publish.enc_key
        pub.enc_serializer = publish.enc_serializer

        self._schema.publications[txn, publication_id] = pub

    def store_event_history(self, publication_id, subscription_id, receiver):
        """
        Store publication history for subscription.

        :param publication_id: The ID of the event publication to be persisted.
        :type publication_id: int

        :param subscription_id: The ID of the subscription the event (identified by the publication ID),
            was published to, because the event's topic matched the subscription.
        :type subscription_id: int

        :param receiver: The receiving session.
        :type receiver: :class:`crossbar.router.session.RouterSession`
        """
        assert type(publication_id) == int
        assert type(subscription_id) == int
        assert isinstance(receiver, RouterSession)

        self._buffer.append([self._store_event_history, publication_id, subscription_id, receiver])

    def _store_event_history(self, txn, publication_id, subscription_id, receiver):

        # FIXME
        pub = self._schema.publications[txn, publication_id]
        if not pub:
            self.log.debug('no publication {publication_id} in store (schema.publications)',
                           publication_id=publication_id)
            return

        # FIXME
        # sub = self._schema.subscriptions[txn, subscription_id]
        # if not sub:
        #     self.log.warn('no subscription_id {subscription_id} in store (schema.subscriptions)', subscription_id=subscription_id)
        #     return

        receiver_session_id = receiver._session_id
        if not receiver_session_id:
            self.log.warn('no session ID for receiver (anymore) - will not store event!')
            return

        evt = cfxdb.eventstore.Event()
        evt.timestamp = time_ns()
        evt.subscription = subscription_id
        evt.publication = publication_id
        evt.receiver = receiver_session_id

        # FIXME
        # evt.retained = None
        # evt.acknowledged_delivery = None

        evt_key = (evt.subscription, np.datetime64(evt.timestamp, 'ns'))

        self._schema.events[txn, evt_key] = evt

    def get_events(self, subscription_id, limit=None):
        """
        Retrieve given number of last events for a given subscription.

        If no events are yet stored, an empty list ``[]`` is returned.
        If no history is maintained at all for the given subscription, ``None`` is returned.

        This procedure is called by the service session of Crossbar.io and
        exposed under the WAMP meta API procedure ``wamp.subscription.get_events``.

        :param subscription_id: The ID of the subscription to retrieve events for.
        :type subscription_id: int

        :param limit: Limit number of events returned.
        :type limit: int

        :return: List of events: at most ``limit`` events in reverse chronological order.
        :rtype: list or None
        """
        assert type(subscription_id) == int
        assert limit is None or type(limit) == int

        return self.get_event_history(subscription_id, from_ts=0, until_ts=time_ns(), reverse=True, limit=limit)

    def get_event_history(self, subscription_id, from_ts, until_ts, reverse=False, limit=None):
        """
        Retrieve event history for time range for a given subscription.

        If no history is maintained for the given subscription, None is returned.

        :param subscription_id: The ID of the subscription to retrieve events for.
        :type subscription_id: int

        :param from_ts: Filter events from this date (epoch time in ns).
        :type from_ts: int

        :param until_ts: Filter events until before this date (epoch time in ns).
        :type until_ts: int
        """
        assert type(subscription_id) == int
        assert type(from_ts) == int
        assert type(until_ts) == int
        assert type(reverse) == bool
        assert limit is None or type(limit) == int

        # FIXME
        # from_key = (subscription_id, np.datetime64(from_ts, 'ns'))
        from_key = (subscription_id, from_ts)
        # to_key = (subscription_id, np.datetime64(until_ts, 'ns'))
        to_key = (subscription_id, until_ts)

        with self._db.begin() as txn:
            res = []
            i = 0

            for evt in self._schema.events.select(txn,
                                                  from_key=from_key,
                                                  to_key=to_key,
                                                  return_keys=False,
                                                  reverse=True,
                                                  limit=limit):

                pub = self._schema.publications.select(txn, evt.publication)
                if pub:
                    res.append(pub.marshal())
                    i += 1
                    if i >= limit:
                        break

        return res


class CfxDbRealmStore(object):
    """
    CFXDB realm store.
    """

    event_store = None
    """
    Store for event history.
    """

    call_store = None
    """
    Store for call queueing.
    """
    def __init__(self, personality, factory, config):
        """

        :param config: Realm store configuration item.
        :type config: Mapping
        """
        dbpath = config.get('path', None)
        assert type(dbpath) == str

        maxsize = config.get('maxsize', 128 * 2**20)
        assert type(maxsize) == int
        # allow maxsize 128kiB to 128GiB
        assert maxsize >= 128 * 1024 and maxsize <= 128 * 2**30

        readonly = config.get('readonly', False)
        assert type(readonly) == bool

        sync = config.get('sync', True)
        assert type(sync) == bool

        self.log = personality.log

        self._db = zlmdb.Database(dbpath=dbpath, maxsize=maxsize, readonly=readonly, sync=sync)
        self._db.__enter__()
        self._schema = cfxdb.schema.Schema.attach(self._db)

        from twisted.internet import reactor

        self.event_store = CfxDbEventStore(reactor, self._db, self._schema, config)
        self.call_store = CfxDbCallQueue(reactor, self._db, self._schema, config)

        self.log.info(
            'Realm store initialized (type=zlmdb, dbpath="{dbpath}", maxsize={maxsize}, readonly={readonly}, sync={sync})',
            dbpath=dbpath,
            maxsize=maxsize,
            readonly=readonly,
            sync=sync)

    @inlineCallbacks
    def start(self):
        self.log.info('Starting realm store ..')
        yield self.event_store.start()
        self.call_store.start()
        self.log.info('Realm store ready')
