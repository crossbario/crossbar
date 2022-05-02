#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import uuid
from collections import deque

import zlmdb
import numpy as np

from txaio import use_twisted  # noqa
from txaio import make_logger, time_ns

from twisted.internet.defer import inlineCallbacks

from autobahn.util import hltype, hlval
from autobahn.twisted.util import sleep
from autobahn.wamp import message
from autobahn.wamp.types import SessionDetails, CloseDetails
from autobahn.wamp.interfaces import ISession

from crossbar.router.session import RouterSession
from crossbar.router.realmstore import QueuedCall
from crossbar.interfaces import IRealmStore

import cfxdb
from cfxdb.realmstore import RealmStore, Publication

__all__ = ('RealmStoreDatabase', )


class RealmStoreDatabase(object):
    """
    Database-backed realm store.
    """
    log = make_logger()

    GLOBAL_HISTORY_LIMIT = 100
    """
    The global history limit, in case not overridden.
    """

    STORE_TYPE = 'cfxdb'

    def __init__(self, personality, factory, config):
        """

        :param personality:
        :param factory:
        :param config: Realm store configuration item.
        """
        from twisted.internet import reactor

        self._reactor = reactor
        self._personality = personality
        self._factory = factory

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

        self._config = config

        self._type = self._config.get('type', None)
        assert self._type == self.STORE_TYPE

        self._db = zlmdb.Database(dbpath=dbpath, maxsize=maxsize, readonly=readonly, sync=sync)
        self._db.__enter__()
        self._schema = RealmStore.attach(self._db)

        self._running = False
        self._process_buffers_thread = None

        self._max_buffer = config.get('max-buffer', 10000)
        self._buffer_flush = config.get('buffer-flush', 200)
        self._buffer = []
        self._log_counter = 0

        # map: registration.id -> deque( (session, call, registration, authorization) )
        self._queued_calls = {}

        self.log.info(
            '{func} realm store initialized (type="{stype}", dbpath="{dbpath}", maxsize={maxsize}, '
            'readonly={readonly}, sync={sync})',
            func=hltype(self.__init__),
            stype=hlval(self._type),
            dbpath=dbpath,
            maxsize=maxsize,
            readonly=readonly,
            sync=sync)

    def type(self) -> str:
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.type`
        """
        return self._type

    def is_running(self) -> bool:
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.is_running`
        """
        return self._running

    @inlineCallbacks
    def start(self):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.start`
        """
        if self._running:
            raise RuntimeError('store is already running')
        else:
            self.log.info(
                '{func} starting realm store type="{stype}"',
                func=hltype(self.start),
                stype=hlval(self._type),
            )

        self._buffer = []
        self._log_counter = 0
        self._running = True
        self._process_buffers_thread = yield self._reactor.callInThread(self._process_buffers)
        self.log.info('{func} realm store ready!', func=hltype(self.start))

    def stop(self):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.stop`
        """
        if not self._running:
            raise RuntimeError('store is not running')
        else:
            self.log.info('{func} stopping realm store', func=hltype(self.start))

        self._running = False

        # FIXME: wait for _process_buffers_thread

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
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.attach_subscription_map`
        """
        for sub in self._config.get('event-history', []):
            uri = sub['uri']
            match = sub.get('match', u'exact')
            # observation, was_already_observed, was_first_observer
            subscription_map.add_observer(self, uri=uri, match=match)
            # subscription_id = observation.id

    def store_session_joined(self, session: ISession):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.store_session_joined`
        """
        self.log.info('{func} append new joined session for storing: session={session}',
                      func=hltype(self.store_session_joined),
                      session=session)

        # crossbar.router.session.RouterSession
        # crossbar.router.service.RouterServiceAgent
        # autobahn.twisted.wamp.ApplicationSession

        from pprint import pprint
        pprint(dir(session))

        ses = cfxdb.realmstore.Session()

        ses.oid = uuid.uuid4()
        ses.joined_at = np.datetime64(time_ns(), 'ns')
        ses.session = session.session_id
        ses.realm = session.realm
        ses.authid = session.authid
        ses.authrole = session.authrole
        ses.authmethod = session.authmethod
        ses.authprovider = session.authprovider
        ses.authextra = session.authextra
        ses.transport = session.transport.transport_details.marshal()

        # FIXME
        # ses.session_details = session.session_details.marshal()

        self._buffer.append([self._store_session_joined, ses])

    def _store_session_joined(self, txn, ses):

        # FIXME: use idx_sessions_by_session_id
        # if session._session_id:
        #     ses = self._schema.sessions[txn, session._session_id]
        #     if ses:
        #         self.log.warn('{klass}._store_session_joined(): session {session} already in store',
        #                       klass=self.__class__.__name__,
        #                       session=session._session_id)
        #         return
        # else:
        #     self.log.warn('{klass}._store_session_joined(): cannot store session without session ID',
        #                   klass=self.__class__.__name__)
        #     return

        # zlmdb._errors.NullValueConstraint: cannot insert NULL value into
        # non-nullable index "cfxdb.realmstore._session.Sessions::idx1"
        self._schema.sessions[txn, ses.oid] = ses

        self.log.info('{func} database record inserted: session={session}',
                      func=hltype(self._store_session_joined),
                      session=ses)

    def store_session_left(self, session, session_details, close_details):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.store_session_left`
        """
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

        # FIXME: use idx_sessions_by_session_id
        return

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
        Implements :meth:`crossbar._interfaces.IRealmStore.store_event`
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

        # FIXME: use idx_sessions_by_session_id
        # ses = self._schema.sessions[txn, session._session_id] if session._session_id else None
        # if not ses:
        #     self.log.info(
        #         'session {session} (realm={realm}, authid={authid}, authrole={authrole}) not in store - '
        #         'event on publication {publication_id} not stored!',
        #         session=session._session_id,
        #         authid=session._authid,
        #         authrole=session._authrole,
        #         realm=session._realm,
        #         publication_id=publication_id)

        pub = cfxdb.realmstore.Publication()

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
        Implements :meth:`crossbar._interfaces.IRealmStore.store_event_history`
        """
        assert type(publication_id) == int
        assert type(subscription_id) == int

        # FIXME: unexpected type <class 'backend.BackendSession'> for receiver
        # assert isinstance(receiver, RouterSession), 'unexpected type {} for receiver'.format(type(receiver))

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

        evt = cfxdb.realmstore.Event()
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
        Implements :meth:`crossbar._interfaces.IRealmStore.get_events`
        """
        assert type(subscription_id) == int
        assert limit is None or type(limit) == int

        return self.get_event_history(subscription_id, from_ts=0, until_ts=time_ns(), reverse=True, limit=limit)

    def get_event_history(self, subscription_id, from_ts, until_ts, reverse=False, limit=None):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.get_event_history`
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

                pub: Publication = self._schema.publications.select(txn, evt.publication)
                if pub:
                    res.append(pub.marshal())
                    i += 1
                    if i >= limit:
                        break

        return res

    def maybe_queue_call(self, session, call, registration, authorization):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.maybe_queue_call`
        """
        # FIXME: match this against the config, not just plain accept queueing!
        if registration.id not in self._queued_calls:
            self._queued_calls[registration.id] = deque()

        self._queued_calls[registration.id].append(QueuedCall(session, call, registration, authorization))

        return True

    def get_queued_call(self, registration):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.get_queued_call`
        """
        if registration.id in self._queued_calls and self._queued_calls[registration.id]:
            return self._queued_calls[registration.id][0]

    def pop_queued_call(self, registration):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.get_event_history`
        """
        if registration.id in self._queued_calls and self._queued_calls[registration.id]:
            return self._queued_calls[registration.id].popleft()


IRealmStore.register(RealmStoreDatabase)
