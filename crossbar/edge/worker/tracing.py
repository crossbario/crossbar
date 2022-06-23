##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import six
import uuid
import math
from datetime import datetime
from collections import deque

from txaio import make_logger, time_ns, perf_counter_ns

from twisted.internet.task import LoopingCall

from autobahn import util
from autobahn.wamp import message

__all__ = ('FabricRouterTrace', )

# import pyarrow as pa
# import pyarrow.parquet as pq
#
# pd.Timestamp (np.datetime64[ns])
# pa.Array.from_buffers
# pa.RecordBatch.from_arrays
# pa.Table.from_batches
# pq.ParquetFile.write_table

# a = pa.array([random.randint(0, 2**32-1) for i in range(1000)], type=pa.uint64())

# https://arrow.apache.org/docs/python/generated/pyarrow.Table.html#pyarrow.Table
# https://arrow.apache.org/docs/python/generated/pyarrow.RecordBatch.html#pyarrow.RecordBatch
# https://arrow.apache.org/docs/python/generated/pyarrow.Array.html#pyarrow.Array


class TracedMessage(object):

    __slots__ = (
        'ts',
        'pc',
        'seq',
        'realm',
        'direction',
        'session_id',
        'authid',
        'authrole',
        'msg',
    )

    def __init__(self, seq, realm, direction, session_id, authid, authrole, msg):
        self.ts = time_ns()
        self.pc = perf_counter_ns()
        self.seq = seq
        self.realm = realm
        self.direction = direction
        self.session_id = session_id
        self.authid = authid
        self.authrole = authrole
        self.msg = msg

    def marshal(self, include_message=False):
        obj = {
            u'ts': self.ts,
            u'pc': self.pc,
            u'seq': self.seq,
            u'realm': self.realm,
            u'direction': self.direction,
            u'session_id': self.session_id,
            u'authid': self.authid,
            u'authrole': self.authrole,
            u'msg_type': six.text_type(self.msg.__class__.__name__),
            u'correlation': self.msg.correlation_id,
            u'correlation_uri': self.msg.correlation_uri,
            u'correlation_is_anchor': self.msg.correlation_is_anchor,
            u'correlation_is_last': self.msg.correlation_is_last,
            u'enc_algo': self.msg.enc_algo if hasattr(self.msg, 'enc_algo') else None,
            u'enc_key': self.msg.enc_key if hasattr(self.msg, 'enc_key') else None,
            u'enc_serializer': self.msg.enc_serializer if hasattr(self.msg, 'enc_serializer') else None,
        }

        # track msg serialization sizes
        serializations = {}
        for ser, val in self.msg._serialized.items():
            serializations[ser.NAME] = len(val)
        obj[u'serializations'] = serializations

        if include_message:
            # forward raw WAMP message
            obj[u'msg'] = self.msg.marshal()

        return obj


class TracedAction(object):

    __slots__ = ('correlation_id', 'correlation_uri', 'ts', 'pc', 'seq', 'realm', 'action', 'originator', 'responders',
                 'originator_enc', 'responders_enc', 'success')

    def __init__(self, correlation_id, correlation_uri, seq, realm, action, originator, responders):
        self.correlation_id = correlation_id
        self.correlation_uri = correlation_uri
        self.ts = time_ns()
        self.pc = perf_counter_ns()
        self.seq = seq
        self.realm = realm
        self.action = action
        self.originator = originator
        self.responders = responders
        self.success = None

    def marshal(self):
        obj = {
            u'ts': self.ts,
            u'pc': self.pc,
            u'seq': self.seq,
            u'realm': self.realm,
            u'action': self.action,
            u'correlation_id': self.correlation_id,
            u'correlation_uri': self.correlation_uri,
            u'originator': self.originator,
            u'responders': self.responders,
            u'success': self.success,
        }

        return obj


class FabricRouterTrace(object):
    """

    How it works:

    A trace is always run from a router worker process. The router code calls
    into maybe_trace_rx_msg/maybe_trace_tx_msg to trace messages as they are received
    and sent to/from the router. These 2 functions check if the message is to be traced
    in the first place, and if so, create a trace record and append that to a in-memory
    list in the same (main) thread. Every 10-100ms, a looping call will trigger that
    will then take the buffered messages in the list and forward that to a background
    thread where it is written to a LMDB database file specific to this trace.
    """

    log = make_logger()

    def __init__(self,
                 session,
                 trace_id,
                 on_trace_period_finished=None,
                 trace_level=u'message',
                 trace_app_payload=False,
                 batching_period=200,
                 persist=False,
                 duration=None,
                 limit=60):
        """

        :param trace_id: The ID assigned to the trace within the router-realm.
        :type trace_id: str

        :param trace_app_payload: Flag to control tracing of the actual
            app _payload_ (args, kwargs)
        :type trace_app_payload: bool

        :param batching_period: The batching period in ms.
        :type batching_period: int

        :param persist: Flag to control trace persistence (to disk, that is LMDB).
        :type persist: bool

        :param duration: Run time of the trace in secs. If given, the trace will be automatically
            stopped after this time. Otherwise a trace needs to be stopped explicitly.
        :type duration: int

        :param limit: Limit in secs of the history kept for the trace.
        :type limit: int
        """
        self._session = session
        self._trace_id = trace_id
        self._on_trace_period_finished = on_trace_period_finished
        self._trace_level = trace_level
        self._trace_app_payload = trace_app_payload
        self._batching_period = batching_period
        self._persist = persist
        self._duration = duration
        self._limit = limit
        self._status = u'created'

        if persist:
            self._persistent_id = str(uuid.uuid4())
        else:
            self._persistent_id = None

        self._started = None
        self._ended = None

        self._seq = 0
        self._period = 0
        self._period_ts = None

        # the current batch of tracing records for trace_level==u'message'
        self._current_batch = []

        # for trace_level==u'action', map of
        # open actions: correlation => instance of TracedAction
        self._open_actions = {}

        # the accumulated data for the trace
        max_periods = int(math.ceil(float(limit) * 1000. / float(batching_period)))
        self._trace = deque(maxlen=max_periods)

        # the looping call the accumulates the current batch
        self._batch_looper = None

    def _batch_loop(self):

        period = {
            u'finished_ts': time_ns(),
            u'finished_pc': perf_counter_ns(),
            u'period': self._period,
            u'period_start': util.utcstr(self._period_ts),
        }

        current_batch = self._current_batch

        if current_batch:
            period[u'first_seq'] = current_batch[0].seq
            period[u'last_seq'] = current_batch[-1].seq
        else:
            period[u'first_seq'] = None
            period[u'last_seq'] = None

        # fire user callback with current batch
        if self._on_trace_period_finished:
            self._on_trace_period_finished(self._trace_id, period, current_batch)

        # append current batch to history
        self._trace.append((period, current_batch))

        # next period
        self._period += 1
        self._period_ts = datetime.utcnow()
        if current_batch:
            self._current_batch = []

    def start(self):
        if self._status == u'created':
            self._status = u'running'
            self._started = datetime.utcnow()
            self._period_ts = self._started
            self._batch_looper = LoopingCall(self._batch_loop)
            self._batch_looper.start(float(self._batching_period) / 1000.)
        else:
            self.log.warn('skip starting of Trace not in status "created", but "{status}"', status=self._status)

    def stop(self):
        if self._status == u'running':
            if self._batch_looper:
                if self._batch_looper.running:
                    self._batch_looper.stop()
                self._batch_looper = None
            self._status = u'stopped'
            self._ended = datetime.utcnow()
        else:
            self.log.warn('skip stopping of Trace not in status "running", but "{status}"', status=self._status)

    def marshal(self):
        if self._started:
            if self._ended:
                runtime = (self._ended - self._started).total_seconds()
            else:
                runtime = (datetime.utcnow() - self._started).total_seconds()
        else:
            runtime = None

        data = {
            u'id': self._trace_id,
            u'node_id': self._session._node_id,
            u'worker_id': self._session._worker_id,
            u'persistent_id': self._persistent_id,
            u'status': self._status,
            u'started': util.utcstr(self._started) if self._started else None,
            u'ended': util.utcstr(self._ended) if self._ended else None,
            u'runtime': runtime,
            u'options': {
                u'trace_level': self._trace_level,
                u'trace_app_payload': self._trace_app_payload,
                u'batching_period': self._batching_period,
                u'persist': self._persist,
                u'duration': self._duration,
                u'limit': self._limit
            },
            u'next_period': self._period,
            u'next_seq': self._seq,
        }
        return data

    def get_data(self, from_seq, to_seq, limit):
        # FIXME: implement selection for sequence range / limit
        res = []
        for period, batch in self._trace:
            if batch:
                if self._trace_level == u'message':
                    res.extend([trace_record.marshal(self._trace_app_payload) for trace_record in batch])
                elif self._trace_level == u'action':
                    res.extend([traced_action.marshal() for traced_action in batch])
                else:
                    raise Exception('logic error')
            if len(res) > limit:
                res = res[:limit]
                break
        return res

    def maybe_trace_rx_msg(self, session, msg):
        self._maybe_trace_msg(session, msg, u'rx')

    def maybe_trace_tx_msg(self, session, msg):
        self._maybe_trace_msg(session, msg, u'tx')

    def _maybe_trace_msg(self, session, msg, direction):
        # FIXME: implement tracing filters
        is_traced = self._status == u'running'

        if is_traced:
            self.log.debug('{direction}: {msg}', direction=direction.upper(), msg=msg)

            if self._trace_level == u'message':
                trace_record = TracedMessage(self._seq, session._realm, direction, session._session_id,
                                             session._authid, session._authrole, msg)

                self._current_batch.append(trace_record)
                self._seq += 1

            elif self._trace_level == u'action':
                if msg.correlation_is_anchor:

                    # RPC/PubSub related actions
                    if isinstance(msg, message.Call) or \
                       isinstance(msg, message.Register) or \
                       isinstance(msg, message.Unregister) or \
                       isinstance(msg, message.Publish) or \
                       isinstance(msg, message.Subscribe) or \
                       isinstance(msg, message.Unsubscribe):
                        _action = six.text_type(msg.__class__.__name__)
                    else:
                        _action = None

                    if _action:
                        traced_action = TracedAction(msg.correlation_id, msg.correlation_uri, self._seq,
                                                     session._realm, _action, session._session_id, [])

                        self._open_actions[msg.correlation_id] = traced_action
                        self._seq += 1
                        self.log.debug('New TRACE ACTION: {traced_action}', traced_action=traced_action)

                if isinstance(msg, message.Invocation) or isinstance(msg, message.Event):
                    if msg.correlation_id in self._open_actions:
                        response = {
                            'session_id': session._session_id,
                            'authid': session._authid,
                            'authrole': session._authid,
                            'enc_algo': msg.enc_algo,
                            'enc_key': msg.enc_key,
                            'enc_serializer': msg.enc_serializer,
                        }
                        self._open_actions[msg.correlation_id].responders.append(response)

                if msg.correlation_is_last:
                    if msg.correlation_id in self._open_actions:
                        traced_action = self._open_actions[msg.correlation_id]
                        traced_action.success = not isinstance(msg, message.Error)
                        del self._open_actions[msg.correlation_id]
                        self._current_batch.append(traced_action)
                        self.log.debug('TRACE ACTION finished: {traced_action}', traced_action=traced_action)

            else:
                raise Exception('internal error: invalid trace level "{}"'.format(self._trace_level))
