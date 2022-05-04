#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import uuid
from collections import deque
from typing import Dict, List, Any, Optional, Tuple

import zlmdb
import numpy as np

from txaio import use_twisted  # noqa
from txaio import make_logger, time_ns

from twisted.internet.defer import inlineCallbacks

from autobahn.util import hltype, hlval
from autobahn.twisted.util import sleep
from autobahn.wamp import message
from autobahn.wamp.types import CloseDetails, SessionDetails, TransportDetails
from autobahn.wamp.message import Publish
from autobahn.wamp.interfaces import ISession

from crossbar.router.observation import UriObservationMap
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

    def store_session_joined(self, session: ISession, details: SessionDetails):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.store_session_joined`
        """
        self.log.debug('{func} new session joined session={session}, details={details}',
                       func=hltype(self.store_session_joined),
                       session=session,
                       details=details)

        ses = cfxdb.realmstore.Session()
        ses.oid = uuid.uuid4()
        ses.joined_at = np.datetime64(time_ns(), 'ns')
        ses.session = details.session
        ses.realm = details.realm
        ses.authid = details.authid
        ses.authrole = details.authrole
        ses.authmethod = details.authmethod
        ses.authprovider = details.authprovider
        ses.authextra = details.authextra

        # the client frontend transport, both in router-based and proxy-router setups
        ses.transport = details.transport.marshal()

        # in proxy-router setups, this transport is the proxy-to-router transport,
        # whereas in plain router-based setups, this is the same as above.
        ptd = session._transport.transport_details.marshal()

        # FIXME: we should have a better way to recognize proxy-router setups
        if ptd != ses.transport:
            ses.proxy_transport = ptd

        # FIXME: fill with the proxy-to-router authentication of the proxy itself
        ses.proxy_node_oid = None
        ses.proxy_node_authid = None
        ses.proxy_worker_name = None
        ses.proxy_worker_pid = None

        self._buffer.append([self._store_session_joined, ses])

    def _store_session_joined(self, txn: zlmdb.Transaction, ses: cfxdb.realmstore.Session):

        # FIXME: use idx_sessions_by_session_id to check there is no session with (session_id, joined_at) yet

        self._schema.sessions[txn, ses.oid] = ses

        cnt = self._schema.sessions.count(txn)
        self.log.info('{func} database record inserted [total={total}] session={session}',
                      func=hltype(self._store_session_joined),
                      total=hlval(cnt),
                      session=ses)

    def store_session_left(self, session: ISession, details: CloseDetails):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.store_session_left`
        """
        self.log.debug('{func} session left session={session}, details={details}',
                       func=hltype(self.store_session_left),
                       session=session,
                       details=details)

        self._buffer.append([self._store_session_left, session, details])

    def _store_session_left(self, txn: zlmdb.Transaction, session: ISession, details: CloseDetails):

        # FIXME: apparently, session ID is already erased at this point:(
        _session_id = session._session_id

        # FIXME: move left_at to autobahn.wamp.types.CloseDetails
        _left_at = np.datetime64(time_ns(), 'ns')

        # lookup session by WAMP session ID and find the most recent session
        # according to joined_at timestamp
        session_obj = None
        _from_key = (_session_id, np.datetime64(0, 'ns'))
        _to_key = (_session_id, np.datetime64(time_ns(), 'ns'))
        for session_oid in self._schema.idx_sessions_by_session_id.select(txn,
                                                                          from_key=_from_key,
                                                                          to_key=_to_key,
                                                                          reverse=True,
                                                                          return_keys=False,
                                                                          return_values=True):
            session_obj = self._schema.sessions[txn, session_oid]

            # if we have an index, that index must always resolve to an indexed record
            assert session_obj

            # we only want the most recent session
            break

        if session_obj:
            # FIXME: also store other CloseDetails attributes
            session_obj.left_at = _left_at

            self.log.info('{func} database record session={session} updated: left_at={left_at}',
                          func=hltype(self._store_session_left),
                          left_at=hlval(_left_at),
                          session=hlval(_session_id))
        else:
            self.log.warn('{func} could not update database record for session={session}: record not found!',
                          func=hltype(self._store_session_left),
                          session=hlval(_session_id))

    def get_session_by_session_id(self,
                                  session_id: int,
                                  joined_before: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.get_session_by_session_id`
        """
        if joined_before:
            _joined_before = np.datetime64(joined_before, 'ns')
        else:
            _joined_before = np.datetime64(time_ns(), 'ns')
        _from_key = (session_id, np.datetime64(0, 'ns'))
        _to_key = (session_id, _joined_before)

        # check if we have a record store for the session
        session: Optional[cfxdb.realmstore.Session] = None
        with self._db.begin() as txn:
            # lookup session by WAMP session ID and find the most recent session
            # according to joined_at timestamp
            for session_oid in self._schema.idx_sessions_by_session_id.select(txn,
                                                                              from_key=_from_key,
                                                                              to_key=_to_key,
                                                                              reverse=True,
                                                                              return_keys=False,
                                                                              return_values=True):
                session = self._schema.sessions[txn, session_oid]

                # if we have an index, that index must always resolve to an indexed record
                assert session

                # we only want the most recent session
                break

        if session:
            # extract info from database table to construct session details and return
            td = TransportDetails.parse(session.transport)
            sd = SessionDetails(
                realm=session.realm,
                session=session.session,
                authid=session.authid,
                authrole=session.authrole,
                authmethod=session.authmethod,
                authprovider=session.authprovider,
                authextra=session.authextra,
                # FIXME
                serializer=None,
                resumed=False,
                resumable=False,
                resume_token=None,
                transport=td)
            res = sd.marshal()
            return res
        else:
            return None

    def get_sessions_by_authid(self, authid: str) -> Optional[List[Tuple[str, int]]]:
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.get_sessions_by_authid`
        """

    def attach_subscription_map(self, subscription_map: UriObservationMap):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.attach_subscription_map`
        """
        for sub in self._config.get('event-history', []):
            uri = sub['uri']
            match = sub.get('match', u'exact')
            # observation, was_already_observed, was_first_observer
            subscription_map.add_observer(self, uri=uri, match=match)
            # subscription_id = observation.id

    def store_event(self, session: ISession, publication_id: int, publish: Publish):
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

    def store_event_history(self, publication_id: int, subscription_id: int, receiver: ISession):
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

    def get_events(self, subscription_id: int, limit: Optional[int] = None):
        """
        Implements :meth:`crossbar._interfaces.IRealmStore.get_events`
        """
        assert type(subscription_id) == int
        assert limit is None or type(limit) == int

        return self.get_event_history(subscription_id, from_ts=0, until_ts=time_ns(), reverse=True, limit=limit)

    def get_event_history(self,
                          subscription_id: int,
                          from_ts: int,
                          until_ts: int,
                          reverse: Optional[bool] = None,
                          limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
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
                    if limit is not None and i >= limit:
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
