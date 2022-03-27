###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import uuid
import iso8601
import humanize
import pprint
from typing import Optional, Dict, List, Tuple, Any
from pprint import pformat

import six

import zlmdb

import nacl
import nacl.signing
import nacl.encoding

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredList, Deferred
from twisted.internet.task import LoopingCall
from twisted.web import client

import txaio
from txaio import make_logger, time_ns

from autobahn import wamp
from autobahn.util import utcnow
from autobahn.wamp.types import RegisterOptions, SubscribeOptions, CallDetails, PublishOptions, EventDetails
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationSession

from crossbar._util import hl, hlid, hlval, hltype
from crossbar.common.key import _read_node_key, _read_release_key

from cfxdb.mrealmschema import MrealmSchema
from cfxdb.globalschema import GlobalSchema

from crossbar.master.api import APIS
from crossbar.master.cluster import WebClusterManager, RouterClusterManager
from crossbar.master.mrealm.metadata import MetadataManager
from crossbar.master.arealm import ApplicationRealmManager

from cfxdb.log import MNodeLog, MWorkerLog

__all__ = ('MrealmController', )

client._HTTP11ClientFactory.noisy = False


class Node(object):
    """
    Run-time representation of CF nodes currently connected to this management realm.
    """

    LAST_ACTIVITY_NONE = 0
    LAST_ACTIVITY_CREATED = 1
    LAST_ACTIVITY_STARTED = 2
    LAST_ACTIVITY_READY = 3
    LAST_ACTIVITY_HEARTBEAT = 4
    LAST_ACTIVITY_CHECK = 5

    def __init__(self,
                 node_id=None,
                 heartbeat_counter=None,
                 heartbeat_time=None,
                 heartbeat_workers={},
                 status='online',
                 node_authid=None):
        self.node_id = node_id
        self.node_authid = node_authid
        self.status = status
        self.last_active = time_ns()
        self.last_activity = Node.LAST_ACTIVITY_CREATED

        self.heartbeat_counter = heartbeat_counter
        self.heartbeat_time = heartbeat_time or 0
        self.heartbeat_workers = heartbeat_workers

    def __str__(self):
        return pprint.pformat(self.marshal())

    def marshal(self):
        return {
            'id': self.node_id,
            'authid': self.node_authid,
            'status': self.status,
            'last_active': self.last_active,
            'last_activity': self.last_activity,

            # these data items are received from managed nodes
            'workers': self.heartbeat_workers,
            'counter': self.heartbeat_counter,
            'time': self.heartbeat_time,
        }


class Trace(object):
    def __init__(self, trace_id, traced_workers, trace_options, eligible_reader_roles, exclude_reader_roles, status):
        self.trace_id = trace_id
        self.traced_workers = traced_workers
        self.trace_options = trace_options
        self.eligible_reader_roles = eligible_reader_roles
        self.exclude_reader_roles = exclude_reader_roles
        self.status = status

    def marshal(self):
        return {
            'trace_id': self.trace_id,
            'traced_workers': self.traced_workers,
            'trace_options': self.trace_options,
            'eligible_reader_roles': self.eligible_reader_roles,
            'exclude_reader_roles': self.exclude_reader_roles,
            'status': self.status,
        }


class MrealmController(ApplicationSession):
    """
    Backend of user created management realms.

    When a management realm is created, one instance of this component is started.
    This management realm component is then running continuously during the lifetime
    of the management realm.
    """

    log = make_logger()

    def onUserError(self, fail, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ISession.onUserError`
        """
        if isinstance(fail.value, ApplicationError):
            self.log.debug('{klass}.onUserError(): "{msg}"',
                           klass=self.__class__.__name__,
                           msg=fail.value.error_message())
        else:
            self.log.error(
                '{klass}.onUserError(): "{msg}"\n{traceback}',
                klass=self.__class__.__name__,
                msg=msg,
                traceback=txaio.failure_format_traceback(fail),
            )

    def __init__(self, config=None):
        ApplicationSession.__init__(self, config)

        # comes from "crossbar/master/node/node.py" (L299, L282)
        assert config.extra

        self._uri_prefix = 'crossbarfabriccenter.mrealm.'
        self._nodes = None
        self._node_oid_by_name = None
        self._sessions = None
        self._traces = None

        # background loop run periodically to health check and send heartbeats for this controller
        self._tick_loop = None

        # background loop run periodically to check & apply mrealm-level resources
        self._check_and_apply_loop = None
        self._check_and_apply_in_progress = False

        # Release (public) key
        self._release_pubkey_hex = _read_release_key()['hex']

        # Node key
        self._node_key_hex = _read_node_key('.', private=True)['hex']
        self._node_key = nacl.signing.SigningKey(self._node_key_hex, encoder=nacl.encoding.HexEncoder)

        assert 'mrealm' in config.extra and type(config.extra['mrealm'] == str)
        self._mrealm_oid = uuid.UUID(config.extra['mrealm'])

        # controller database
        #
        dbcfg = config.extra.get('controller-database', {})
        assert dbcfg and type(dbcfg) == dict

        dbfile = dbcfg.get('dbfile', None)
        assert dbfile and type(dbfile) == six.text_type

        maxsize = dbcfg.get('maxsize', None)
        assert maxsize and type(maxsize) in six.integer_types
        assert maxsize >= 2**20 and maxsize < 2**30 * 10  # 1 MB - 10 GB maximum size

        self.gdb = zlmdb.Database(dbpath=dbfile, maxsize=maxsize, readonly=False, sync=True)
        self.gdb.__enter__()
        self.gschema: GlobalSchema = GlobalSchema.attach(self.gdb)

        self.log.info('global database initialized [dbfile={dbfile}, maxsize={maxsize}]',
                      dbfile=hlval(dbfile),
                      maxsize=hlval(maxsize))

        # mrealm database
        #
        dbcfg = config.extra.get('database', {})
        assert dbcfg and type(dbcfg) == dict

        dbfile = dbcfg.get('dbfile', None)
        assert dbfile and type(dbfile) == six.text_type

        maxsize = dbcfg.get('maxsize', None)
        assert maxsize and type(maxsize) in six.integer_types
        assert maxsize >= 2**20 and maxsize < 2**30 * 10  # 1 MB - 10 GB maximum size

        self.db = zlmdb.Database(dbpath=dbfile, maxsize=maxsize, readonly=False, sync=True)
        self.db.__enter__()
        self.schema = MrealmSchema.attach(self.db)

        self.log.info('management realm database initialized [dbfile={dbfile}, maxsize={maxsize}]',
                      dbfile=hlid(dbfile),
                      maxsize=hlval(maxsize))

        self._metadata_manager = MetadataManager(self, self.db, self.schema)
        self._webcluster_manager = WebClusterManager(self, self.gdb, self.gschema, self.db, self.schema)
        self._routercluster_manager = RouterClusterManager(self, self.gdb, self.gschema, self.db, self.schema)
        self._arealm_manager = ApplicationRealmManager(self, self.gdb, self.gschema, self.db, self.schema)

    @property
    def nodes(self):
        """
        Returns handle to map of currently connected nodes. The map is indexed by ``node_id``.

        :return: Map of node object ID to :class:`crossbar.master.mrealm.controller.Node`
        :rtype: dict
        """
        return self._nodes

    def node(self, node_authid):
        """
        Get node by node authid (rather than oid).

        :param node_authid:
        :return:
        """
        with self.gdb.begin() as txn:
            node_oid = self.gschema.idx_nodes_by_authid[txn, (self._mrealm_oid, node_authid)]

        # currently, nodes are indexed by str-type UUID in the run-time map
        node_oid = str(node_oid)

        return self._nodes.get(node_oid, None)

    def map_node_oid_to_authid(self, node_oid):
        """
        Map node object ID to node authid. This referes to any node for which there is a run-time representation
        currently active, regardless of whether this node is currently online or not.

        :param node_oid:
        :return:
        """
        node_oid = uuid.UUID(node_oid)
        with self.gdb.begin() as txn:
            node = self.gschema.nodes[txn, node_oid]
        if node:
            self.log.debug('{func}: mapped node object ID {node_oid} to node authid "{node_authid}"',
                           func=hltype(self.map_node_oid_to_authid),
                           node_oid=hlid(node_oid),
                           node_authid=hlid(node.authid))
            return node.authid
        else:
            self.log.warn('{func}: could not map node object ID {node_oid} to any node authid',
                          func=hltype(self.map_node_oid_to_authid),
                          node_oid=hlid(node_oid))
            return None

    @inlineCallbacks
    def onJoin(self, details):
        # initialize this mrealm run-time representation
        try:
            yield self._initialize(details)
        except:
            # immediately close down if there is any error during mrealm initialization
            self.log.failure()
            self.leave()
        else:
            self.log.info('Management controller started for management realm "{realm}" {func}',
                          func=hltype(self.onJoin),
                          realm=hlid(details.realm))

        # initialize Metadata manager
        yield self._metadata_manager.start(prefix=self._uri_prefix + 'metadata.')

        # initialize Web cluster manager
        yield self._webcluster_manager.start(prefix=self._uri_prefix + 'webcluster.')

        # initialize router cluster manager
        yield self._routercluster_manager.start(prefix=self._uri_prefix + 'routercluster.')

        # initialize application realm manager
        yield self._arealm_manager.start(prefix=self._uri_prefix + 'arealm.')

        self.log.info(
            'Management realm controller ready for management realm {mrealm_oid}! (realm="{realm}", session={session}, authid="{authid}", authrole="{authrole}")  [{func}]',
            mrealm_oid=hlid(self._mrealm_oid),
            realm=hlval(details.realm),
            session=hlval(details.session),
            authid=hlval(details.authid),
            authrole=hlval(details.authrole),
            func=hltype(self.onJoin))

    def onLeave(self, details):
        # first, stop background "check nodes" task
        if self._check_and_apply_loop:
            if self._check_and_apply_loop.running:
                self._check_and_apply_loop.stop()
            self._check_and_apply_loop = None

        # next, stop own heartbeat task
        if self._tick_loop:
            if self._tick_loop.running:
                self._tick_loop.stop()
            self._tick_loop = None

        return ApplicationSession.onLeave(self, details)

    @inlineCallbacks
    def _initialize(self, details):
        # "self.config.extra" comes from "crossbar/master/node/node.py"
        self.log.debug('{klass} starting realm "{realm}" with config:\n{config}',
                       klass=self.__class__.__name__,
                       realm=self._realm,
                       config=pprint.pformat(self.config.extra))

        self._started = utcnow()

        self._nodes = {}
        self._nodes_shutdown = {}
        self._node_oid_by_name = {}
        self._sessions = {}
        self._traces = {}

        # subscribe to node lifecycle events
        yield self.subscribe(self._on_node_ready, 'crossbarfabriccenter.node..on_ready',
                             SubscribeOptions(match='wildcard', details=True))

        # we subscribe to CF node heartbeat events, to track when we have last heard of a specific
        # node, and also to react (after some time) should be neither receive an "on_shutdown" nor
        # an "on_leave" event, so we can purge the node from our active list.
        yield self.subscribe(self._on_node_heartbeat, 'crossbarfabriccenter.node.on_heartbeat',
                             SubscribeOptions(details=True))
        yield self.subscribe(self._on_worker_heartbeat, 'crossbarfabriccenter.node.on_worker_heartbeat',
                             SubscribeOptions(details=True))

        # when a CF node is gracefully shut down, we will receive this event. when the CF node
        # is killed, see "session lifecycle events" below.
        yield self.subscribe(self._on_node_shutdown, 'crossbarfabriccenter.node..on_shutdown',
                             SubscribeOptions(match='wildcard', details=True))

        # subscribe to session lifecycle events.
        yield self.subscribe(self._on_session_startup, 'wamp.session.on_join', SubscribeOptions(details=True))

        # eg when a CF node is hard-killed, the management session will simply get lost, which
        # is detected by CFC router, and a WAMP session leave meta event is published. however,
        # no "on_shutdown" event is published! the CF node has been killed and had no chance to
        # send out any management events. hence we must react to this event.
        yield self.subscribe(self._on_session_shutdown, 'wamp.session.on_leave', SubscribeOptions(details=True))

        # produce CFCs own heartbeat on the management realm
        self._tick = 1
        tick_topic = '{}on_tick'.format(self._uri_prefix)

        @inlineCallbacks
        def on_tick():
            if self.is_attached():
                ticked = {'now': utcnow(), 'tick': self._tick}
                yield self.publish(tick_topic, ticked, options=PublishOptions(acknowledge=True))
            else:
                self.log.warn(
                    'cannot send tick to CF node (topic="{tick_topic}", mrealm="{mrealm}""): management realm controller session no longer attached!',
                    tick_topic=tick_topic,
                    mrealm=self._realm)
            self._tick += 1

        self._tick_loop = LoopingCall(on_tick)
        self._tick_loop.start(5)

        self._check_and_apply_loop = LoopingCall(self.check_and_apply)
        self._check_and_apply_loop.start(10)

        # CFC public API
        #
        # register the public, user facing API of CFC. this is the API that
        # user management components, our own CLI (cbsh) or CFC Web user interface
        # will call into. since this is public API, special care should be taken
        # with the design, keeping the API surface limited, logical and extensible

        # management controller top-level API (on this object)
        regs = yield self.register(self, prefix=self._uri_prefix, options=RegisterOptions(details_arg='details'))
        procs = [reg.procedure for reg in regs]
        self.log.debug('Mrealm controller {api} registered management procedures [{func}]:\n\n{procs}\n',
                       api=hl('Realm Home API', color='green', bold=True),
                       func=hltype(self._initialize),
                       procs=hl(pformat(procs), color='white', bold=True))

        # different remoting APIs for node management
        self._apis = APIS

        # setup procedures of APIs
        all_regs = []
        for api in self._apis:
            regs = api.register(self)
            all_regs.extend(regs)

        regs = yield DeferredList(all_regs)
        procs = [reg.procedure for _, reg in regs]
        self.log.debug('Mrealm controller {api} registered management procedures [{func}]:\n\n{procs}\n',
                       api=hl('Node Remoting API', color='magenta', bold=True),
                       func=hltype(self._initialize),
                       procs=hl(pformat(procs), color='white', bold=True))

        # setup topics of APIs
        all_subs = []
        for api in self._apis:
            subs = api.subscribe(self)
            all_subs.extend(subs)

        subs = yield DeferredList(all_subs)
        topics = [sub.topic for _, sub in subs]
        self.log.debug('Mrealm controller {api} subscribed management topics [{func}]:\n\n{topics}\n',
                       api=hl('Node Remoting API', color='magenta', bold=True),
                       func=hltype(self._initialize),
                       topics=hl(pformat(topics), color='white', bold=True))

        # initialize tracing API
        yield self._init_trace_api()

    @inlineCallbacks
    def check_and_apply(self):
        if self._check_and_apply_in_progress:
            self.log.info('{func} {action} for mrealm {mrealm} skipped! check & apply already in progress.',
                          action=hl('check & apply run skipped', color='red', bold=True),
                          func=hltype(self.check_and_apply),
                          mrealm=hlid(self._mrealm_oid))
            return
        else:
            self.log.info('{func} {action} for mrealm {mrealm} ..',
                          action=hl('check & apply run started', color='green', bold=True),
                          func=hltype(self.check_and_apply),
                          mrealm=hlid(self._mrealm_oid))
            self._check_and_apply_in_progress = True

        if not self.is_attached():
            return

        is_running_completely = True
        cnt_nodes_online = 0
        cnt_nodes_offline = 0
        for node_id in self._nodes:
            try:
                node_status = yield self.call('crossbarfabriccenter.remote.node.get_status', node_id)
            except Exception as e:
                cnt_nodes_offline += 1
                is_running_completely = False

                if isinstance(e, ApplicationError) and e.error == 'wamp.error.no_such_procedure':
                    if self._nodes[node_id].status == 'offline':
                        # this is "expected" - we already knew that the node is offline, and hence the call is failing
                        # because of "no_such_procedure" is exactly what will happen as the node is offline
                        self.log.warn(
                            '{action} [status={status}] {func}',
                            action=hl('Warning, managed node "{}" still not connected or operational'.format(node_id),
                                      color='red',
                                      bold=False),
                            status=hlval(self._nodes[node_id].status),
                            func=hltype(self.check_and_apply))
                    else:
                        if self._nodes[node_id].status == 'online':
                            self._nodes_shutdown[node_id] = time_ns()

                            # mark node as offline in run-time map
                            self._nodes[node_id].status = 'offline'

                            # publish management event
                            yield self._publish_on_node_shutdown_yield(self._nodes[node_id])

                            self.log.info('{action} [oid={node_oid}, session={session_id}, status={status}] {func}',
                                          action=hl('Warning: managed node "{}" became offline'.format(node_id),
                                                    color='red',
                                                    bold=True),
                                          node_oid=hlid(node_id),
                                          session_id=hlid(None),
                                          status=hlval(self._nodes[node_id].status),
                                          func=hltype(self.check_and_apply))

                        else:
                            self.log.warn('{func}: unexpected run-time node status {status} for node {node_id}',
                                          node_id=hlid(node_id),
                                          func=hltype(self.check_and_apply),
                                          status=hlval(self._nodes[node_id].status))
                        self._nodes[node_id].status = 'offline'
                else:
                    self._nodes[node_id].status = 'offline'
                    self.log.warn('{action} [status={status}] {func}',
                                  action=hl('Warning: check on managed node "{}" failed: {}'.format(node_id, e),
                                            color='red',
                                            bold=True),
                                  status=hlval(self._nodes[node_id].status),
                                  func=hltype(self.check_and_apply))
            else:
                cnt_nodes_online += 1
                self._nodes[node_id].heartbeat_workers = node_status['workers_by_type']
                self._nodes[node_id].last_activity = Node.LAST_ACTIVITY_CHECK
                self._nodes[node_id].last_active = time_ns()
                if self._nodes[node_id].status == 'online':
                    self.log.info('{action} [status={status}] {func}',
                                  action=hl('Ok, managed node "{}" is still healthy'.format(node_id),
                                            color='green',
                                            bold=False),
                                  status=hlval(self._nodes[node_id].status),
                                  func=hltype(self.check_and_apply))
                else:
                    self.log.info('{action} [status={status} -> "{new_status}"] {func}',
                                  action=hl('Ok, managed node "{}" became healthy (again)'.format(node_id),
                                            color='yellow',
                                            bold=True),
                                  status=hlval(self._nodes[node_id].status),
                                  new_status=hlval('online'),
                                  func=hltype(self.check_and_apply))
                    self._nodes[node_id].status = 'online'

                    # publish "on_node_ready" management event
                    yield self._publish_on_node_ready_yield(self._nodes[node_id])

        if is_running_completely:
            color = 'green'
            action = 'check & apply run completed successfully'
        else:
            color = 'red'
            action = 'check & apply run finished with problems left'

        self._check_and_apply_in_progress = False
        self.log.info(
            '{func} {action} for mrealm {mrealm}: {cnt_nodes_online} nodes online, {cnt_nodes_offline} nodes offline.',
            action=hl(action, color=color, bold=True),
            func=hltype(self.check_and_apply),
            mrealm=hlid(self._mrealm_oid),
            cnt_nodes_online=hlval(cnt_nodes_online),
            cnt_nodes_offline=hlval(cnt_nodes_offline))

    async def _publish_on_node_ready(self, node):
        options = PublishOptions(acknowledge=True)
        uri = '{}on_node_ready'.format(self._uri_prefix)
        obj = node.marshal()

        await self.publish(uri, node.node_id, obj, options=options)

        await self.config.controller.publish(uri, node.node_id, obj, options=options)
        self.log.debug(
            '.. forward published event to controller for managed node {node_id} (uri={uri}, session_id={session_id}, realm={realm}, authid={authid}, authrole={authrole})',
            node_id=node.node_id,
            uri=uri,
            session_id=self.config.controller._session_id,
            realm=self.config.controller._realm,
            authid=self.config.controller._authid,
            authrole=self.config.controller._authrole,
        )

    @inlineCallbacks
    def _publish_on_node_ready_yield(self, node):
        # FIXME: this is a super hack: we need a twisted thing here in "on_check_nodes". Keep synced to "_publish_on_node_shutdown"!
        options = PublishOptions(acknowledge=True)
        uri = '{}on_node_ready'.format(self._uri_prefix)
        obj = node.marshal()

        yield self.publish(uri, node.node_id, obj, options=options)

        yield self.config.controller.publish(uri, node.node_id, obj, options=options)
        self.log.debug(
            '.. forward published event to controller for managed node {node_id} (uri={uri}, session_id={session_id}, realm={realm}, authid={authid}, authrole={authrole})',
            node_id=node.node_id,
            uri=uri,
            session_id=self.config.controller._session_id,
            realm=self.config.controller._realm,
            authid=self.config.controller._authid,
            authrole=self.config.controller._authrole,
        )

    async def _publish_on_node_shutdown(self, node):
        options = PublishOptions(acknowledge=True)
        uri = '{}on_node_shutdown'.format(self._uri_prefix)
        obj = node.marshal()

        await self.publish(uri, node.node_id, obj, options=options)

        await self.config.controller.publish(uri, node.node_id, obj, options=options)
        self.log.debug(
            '.. forward published event to controller for managed node {node_id} (uri={uri}, session_id={session_id}, realm={realm}, authid={authid}, authrole={authrole})',
            node_id=node.node_id,
            uri=uri,
            session_id=self.config.controller._session_id,
            realm=self.config.controller._realm,
            authid=self.config.controller._authid,
            authrole=self.config.controller._authrole,
        )

    @inlineCallbacks
    def _publish_on_node_shutdown_yield(self, node):
        # FIXME: this is a super hack: we need a twisted thing here in "on_check_nodes". Keep synced to "_publish_on_node_shutdown"!
        options = PublishOptions(acknowledge=True)
        uri = '{}on_node_shutdown'.format(self._uri_prefix)
        obj = node.marshal()

        yield self.publish(uri, node.node_id, obj, options=options)

        yield self.config.controller.publish(uri, node.node_id, obj, options=options)
        self.log.debug(
            '.. forward published event to controller for managed node {node_id} (uri={uri}, session_id={session_id}, realm={realm}, authid={authid}, authrole={authrole})',
            node_id=node.node_id,
            uri=uri,
            session_id=self.config.controller._session_id,
            realm=self.config.controller._realm,
            authid=self.config.controller._authid,
            authrole=self.config.controller._authrole,
        )

    async def _on_node_ready(self, ready_info=None, details: Optional[CallDetails] = None):
        node_id = ready_info.get('node_id', None) if ready_info else None
        self.log.info('Node "{node_id}" is ready: {ready_info} {details}',
                      node_id=node_id,
                      ready_info=ready_info,
                      details=details)

        if node_id in self._nodes:
            self.log.warn('Node-ready event for "{node_id}", but node not already in active node list found!',
                          node_id=node_id)

        _node = Node(node_id)
        _node.last_activity = Node.LAST_ACTIVITY_READY
        _node.last_active = time_ns()

        self._nodes[node_id] = _node

        await self._publish_on_node_ready(_node)

        self.log.debug('{func}: completed!', func=hltype(self._on_node_ready))

    async def _on_worker_heartbeat(self, node_authid, worker_id, heartbeat, details: Optional[CallDetails] = None):
        """
        Receive heartbeats from workers run on CF nodes managed by this CFC instances. By default,
         CF node workers will send one hearbeat every 10 seconds.

        :param node_authid: The node ID (UUID in the master database).
        :type node_authid: str

        :param worker_id: The local worker ID on the remote CF node (_not_ the UUID of the worker
            in the master database)
        :type worker_id: str

        :param heartbeat: Node heartbeat.
        :type heartbeat: dict

        :param details: Event details.
        :type details: :class:`autobahn.wamp.types.EventDetails`
        """
        assert type(node_authid) == str
        assert type(worker_id) == str
        assert type(heartbeat) == dict
        assert details is None or isinstance(details, EventDetails)

        started = time_ns()

        heartbeat_time = heartbeat.get('timestamp', None)
        heartbeat_seq = heartbeat.get('seq', None)
        self.log.debug(
            'Heartbeat from worker "{worker_id}" on node "{node_authid}" [heartbeat_seq={heartbeat_seq}, time={heartbeat_time}, publisher={publisher}, authid={authid}]',
            node_authid=hlid(node_authid),
            worker_id=hlid(worker_id),
            heartbeat_seq=hlid(heartbeat_seq),
            heartbeat_time=hlid(heartbeat_time),
            publisher=hlid(details.publisher) if details else None,
            authid=hlid(details.publisher_authid) if details else None)

        self.log.debug('Raw worker heartbeat: \n{heartbeat}', heartbeat=pprint.pformat(heartbeat))

        with self.gdb.begin() as txn:
            node_oid = self.gschema.idx_nodes_by_authid[txn, (self._mrealm_oid, node_authid)]
            node = self.gschema.nodes[txn, node_oid]

        node_oid = str(node_oid)

        mrealm_id = node.mrealm_oid
        mworker_log = MWorkerLog.parse(mrealm_id, uuid.UUID(node_oid), worker_id, heartbeat)
        self.log.debug('Parsed worker heartbeat: \n{mworker_log}', mworker_log=pprint.pformat(mworker_log.marshal()))

        with self.db.begin(write=True) as txn:
            self.schema.mworker_logs[txn,
                                     (mworker_log.timestamp, mworker_log.node_id, mworker_log.worker_id)] = mworker_log

        ended = time_ns()
        runtime = int(round((ended - started) / 1000000.))

        # taking longer than 250ms means: sth is likely wrong ..
        if runtime > 250:
            self.log.warn(
                'Worker heartbeat excessive processing time {runtime} ms! [node_oid="{node_oid}", worker_id="{worker_id}", timestamp="{timestamp}", sent="{sent}", seq={seq}]',
                runtime=runtime,
                timestamp=mworker_log.timestamp,
                sent=mworker_log.sent,
                seq=mworker_log.seq,
                node_oid=node_oid,
                worker_id=worker_id)
        else:
            self.log.debug(
                'Worker heartbeat processed and stored in {runtime} ms [node_oid="{node_oid}", worker_id="{worker_id}", timestamp="{timestamp}", sent="{sent}", seq={seq}]',
                runtime=runtime,
                timestamp=mworker_log.timestamp,
                sent=mworker_log.sent,
                seq=mworker_log.seq,
                node_oid=node_oid,
                worker_id=worker_id)

        self.log.debug('{func}: completed!', func=hltype(self._on_worker_heartbeat))

    async def _on_node_heartbeat(self, node_authid, heartbeat, details: Optional[CallDetails] = None):
        """
        Receive heartbeats from CF nodes managed by this CFC instances. By default,
         CF nodes will send one hearbeat every 10 seconds.

        :param node_authid: The node WAMP auth ID.
        :type node_authid: str

        :param heartbeat: Node heartbeat.
        :type heartbeat: dict

        :param details: Event details.
        :type details: :class:`autobahn.wamp.types.EventDetails`
        """
        assert type(node_authid) == str
        assert type(heartbeat) == dict
        assert details is None or isinstance(details, EventDetails)

        started = time_ns()

        heartbeat_time = heartbeat.get('timestamp', None)
        assert type(heartbeat_time) == int

        heartbeat_seq = heartbeat.get('seq', None)
        assert type(heartbeat_seq) == int

        heartbeat_pubkey = heartbeat.get('pubkey', None)
        assert type(heartbeat_pubkey) == str and len(heartbeat_pubkey) == 64

        heartbeat_workers = heartbeat.get('workers', {})
        assert type(heartbeat_workers) == dict
        for worker_type in heartbeat_workers:
            # FIXME:
            ALLOWED_WORKER_TYPES = [
                'controller', 'router', 'container', 'guest', 'proxy', 'hostmonitor', 'xbrmm', 'xbr_marketmaker',
                'marketplace'
            ]
            assert worker_type in ALLOWED_WORKER_TYPES, 'invalid worker type "{}" (valid types: {})'.format(
                worker_type, ALLOWED_WORKER_TYPES)
            assert type(heartbeat_workers[worker_type]) == int

        self.log.debug(
            'Heartbeat from node "{node_authid}" with workers {heartbeat_workers} [heartbeat_seq={heartbeat_seq}, time={heartbeat_time}, publisher={publisher}, authid={authid}]',
            node_authid=hlid(node_authid),
            heartbeat_workers=heartbeat_workers,
            heartbeat_seq=hlid(heartbeat_seq),
            heartbeat_time=hlid(heartbeat_time),
            publisher=hlid(details.publisher) if details else None,
            authid=hlid(details.publisher_authid) if details else None)

        self.log.debug('Raw node heartbeat:\n{heartbeat}', heartbeat=pprint.pformat(heartbeat))

        with self.gdb.begin() as txn:
            node_oid = self.gschema.idx_nodes_by_authid[txn, (self._mrealm_oid, node_authid)]
            node = self.gschema.nodes[txn, node_oid]

        # currently, nodes are indexed by str-type UUID in the run-time map
        node_oid = str(node_oid)

        if node_oid not in self._nodes:
            self.log.warn(
                'Heartbeat received from "{node_oid}", but node not found in online list (node will now be marked as online)',
                node_oid=node_oid)
            node_shutdown = self._nodes_shutdown.get(node_oid, None)
            if not node_shutdown or (time_ns() - node_shutdown) > (60 * 10**9):

                # create run-time representation of node
                _node = Node(node_oid, heartbeat_seq, heartbeat_time, heartbeat_workers)
                _node.last_activity = Node.LAST_ACTIVITY_HEARTBEAT
                _node.last_active = time_ns()
                self._nodes[node_oid] = _node

                # publish "on_node_ready" management event
                await self._publish_on_node_ready(_node)

                self.log.info('{action} [oid={node_oid}, session={session_id}, status={status}] {func}',
                              action=hl('Success: managed node "{}" is now online'.format(node_authid),
                                        color='green',
                                        bold=True),
                              node_oid=hlid(node_oid),
                              session_id=hlid(details.publisher) if details else None,
                              status=hlval(self._nodes[node_oid].status),
                              func=hltype(self._on_node_heartbeat))
        else:
            self._nodes[node_oid].heartbeat_counter = heartbeat_seq
            self._nodes[node_oid].heartbeat_time = heartbeat_time
            self._nodes[node_oid].heartbeat_workers = heartbeat_workers
            self._nodes[node_oid].last_activity = Node.LAST_ACTIVITY_HEARTBEAT
            self._nodes[node_oid].last_active = time_ns()

            if self._nodes[node_oid].status == 'online':
                self.log.debug('{action} [oid={node_oid}, session={session_id}, status={status}] {func}',
                               action=hl('Ok, managed node "{}" is still alive'.format(node_authid),
                                         color='green',
                                         bold=False),
                               node_oid=hlid(node_oid),
                               session_id=hlid(details.publisher) if details else None,
                               status=hlval(self._nodes[node_oid].status),
                               func=hltype(self._on_node_heartbeat))
            else:
                self.log.info('{action} [oid={node_oid}, session={session_id}, status={status}] {func}',
                              action=hl('Ok, managed node "{}" became alive (again) [status={} -> online]'.format(
                                  node_authid, self._nodes[node_oid].status),
                                        color='yellow',
                                        bold=True),
                              node_oid=hlid(node_oid),
                              session_id=hlid(details.publisher) if details else None,
                              status=hlval(self._nodes[node_oid].status),
                              func=hltype(self._on_node_heartbeat))
                self._nodes[node_oid].status = 'online'

        # heartbeat['authid'] = details.publisher_authid
        heartbeat['authid'] = node_authid
        heartbeat['node_id'] = node_oid
        heartbeat['session'] = details.publisher if details else None

        mrealm_id = node.mrealm_oid
        mnode_log = MNodeLog.parse(mrealm_id, uuid.UUID(node_oid), heartbeat)
        self.log.debug('Parsed node heartbeat:\n{heartbeat}', heartbeat=pprint.pformat(mnode_log.marshal()))

        # this is the pubkey under which an aggregate usage record (see below) will be stored
        if node.pubkey == heartbeat_pubkey:
            with self.db.begin(write=True) as txn:
                self.schema.mnode_logs[txn, (mnode_log.timestamp, mnode_log.node_id)] = mnode_log

            self.log.debug('{msg} [timestamp={timestamp}, node_id={node_id}]',
                           msg=hl('New node HEARTBEAT persisted in database -> checking for pubkey="{}"'.format(
                               node.pubkey),
                                  bold=True),
                           timestamp=hlid(mnode_log.timestamp),
                           node_id=hlid(mnode_log.node_id))

            ended = time_ns()
            runtime = int(round((ended - started) / 1000000.))

            # taking longer than 250ms means: sth is likely wrong ..
            if runtime > 250:
                self.log.warn(
                    'Node heartbeat excessive processing time {runtime} ms! [{node_oid}, timestamp={timestamp}, sent="{sent}", seq={seq}]',
                    runtime=runtime,
                    timestamp=mnode_log.timestamp,
                    sent=mnode_log.sent,
                    seq=mnode_log.seq,
                    node_oid=node_oid)
            else:
                self.log.debug(
                    'Node heartbeat processed and stored in {runtime} ms [node_id={node_oid}, timestamp={timestamp}, sent="{sent}", seq={seq}]',
                    runtime=runtime,
                    timestamp=mnode_log.timestamp,
                    sent=mnode_log.sent,
                    seq=mnode_log.seq,
                    node_oid=node_oid)
        else:
            self.log.warn('heartbeat pubkey does not match pubkey for node matching node_id!')

        self.log.debug('{func}: completed!', func=hltype(self._on_node_heartbeat))

    async def _on_node_shutdown(self, shutdown_info, details: Optional[CallDetails] = None):
        node_authid = shutdown_info.get('node_id', None)
        self.log.info('node "{node_authid}" has shut down: {shutdown_info} {details}',
                      node_authid=node_authid,
                      shutdown_info=shutdown_info,
                      details=details)

        with self.gdb.begin() as txn:
            node_oid = self.gschema.idx_nodes_by_authid[txn, (self._mrealm_oid, node_authid)]

        if not node_oid:
            self.log.warn('{func}: unrecognised node shutdown for "{node_authid}" - could not find node for authid',
                          func=hltype(self._on_session_shutdown),
                          node_authid=hlid(node_authid))
            return

        node_oid = str(node_oid)
        if node_oid not in self._nodes:
            self.log.warn('{func}: unrecognised node shutdown for "{node_authid}" - node not in run-time map',
                          func=hltype(self._on_node_shutdown),
                          node_authid=hlid(node_authid))
            return

        if node_oid in self._nodes:
            self._nodes_shutdown[node_oid] = time_ns()

            # mark node as offline in run-time map
            self._nodes[node_oid].status = 'offline'

            # publish management event
            await self._publish_on_node_shutdown(self._nodes[node_oid])

        self.log.debug('{func}: completed!', func=hltype(self._on_node_shutdown))

    async def _on_session_startup(self, session, details: Optional[CallDetails] = None):
        if session.get('authrole') == 'node':
            session_id = session.get('session')
            node_authid = session.get('authid')

            self._sessions[session_id] = node_authid
            with self.gdb.begin() as txn:
                node_oid = self.gschema.idx_nodes_by_authid[txn, (self._mrealm_oid, node_authid)]

            # currently, nodes are indexed by str-type UUID in the run-time map
            node_oid = str(node_oid)

            # create run-time representation of node
            if node_oid not in self._nodes:
                _node = Node(node_oid)
                _node.last_activity = Node.LAST_ACTIVITY_STARTED
                _node.last_active = time_ns()
                _node.status = 'online'
                self._nodes[node_oid] = _node

                # publish "on_node_ready" management event
                await self._publish_on_node_ready(_node)

                self.log.info('{action} [oid={node_oid}, session={session_id}, status={status}] {func}',
                              action=hl('Success: managed node "{}" is now online'.format(node_authid),
                                        color='green',
                                        bold=True),
                              node_oid=hlid(node_oid),
                              session_id=hlid(session_id),
                              status=hlval(self._nodes[node_oid].status),
                              func=hltype(self._on_session_startup))

        self.log.debug('{func}: completed!', func=hltype(self._on_session_startup))

    async def _on_session_shutdown(self, session_id, details: Optional[CallDetails] = None):
        node_authid = self._sessions.get(session_id)

        # we are only interested in session closes from management uplinks
        if not node_authid:
            self.log.debug('{func}: unrecognised session close for "{session_id}" - could not map session to authid',
                           func=hltype(self._on_session_shutdown),
                           session_id=hlid(session_id))
            return

        with self.gdb.begin() as txn:
            node_oid = self.gschema.idx_nodes_by_authid[txn, (self._mrealm_oid, node_authid)]

        if not node_oid:
            self.log.warn('{func}: unrecognised session close for "{session_id}" - could not find node for authid',
                          func=hltype(self._on_session_shutdown),
                          session_id=hlid(session_id))
            return

        node_oid = str(node_oid)
        if node_oid not in self._nodes:
            self.log.warn('{func}: unrecognised session close for "{session_id}" - node not in run-time map',
                          func=hltype(self._on_session_shutdown),
                          session_id=hlid(session_id))
            return

        self._nodes_shutdown[node_oid] = time_ns()

        # mark node as offline in run-time map
        self._nodes[node_oid].status = 'offline'

        # publish management event
        await self._publish_on_node_shutdown(self._nodes[node_oid])

        self.log.info('{action} [oid={node_oid}, session={session_id}, status={status}] {func}',
                      action=hl('Warning: managed node "{}" became offline'.format(node_authid),
                                color='red',
                                bold=True),
                      node_oid=hlid(node_oid),
                      session_id=hlid(session_id),
                      status=hlval(self._nodes[node_oid].status),
                      func=hltype(self._on_session_shutdown))

    def _check_node_id(self, node_id, status='online'):
        if node_id not in self._nodes:
            raise Exception('no such node: "{node_id}"', node_id=node_id)

        node = self._nodes[node_id]

        if status is not None and node.status != status:
            raise Exception('node "{}" not in status "{}"'.format(node_id, status))

        return node

    def _check_worker_id(self, node_id, worker_id, status='online'):
        self._check_node_id(node_id, status)

    @wamp.register(None, check_types=True)
    def get_status(self, details: Optional[CallDetails] = None) -> dict:
        """
        Get management realm status.

        :returns: Status information object.
        """
        now = utcnow()
        uptime_secs = (iso8601.parse_date(now) - iso8601.parse_date(self._started)).total_seconds()
        uptime_secs_str = humanize.naturaldelta(uptime_secs)
        res = {
            'type': 'management',
            'realm': self._realm,
            'now': utcnow(),
            'started': self._started,
            'uptime': uptime_secs_str,
            'tick': self._tick
        }
        return res

    @wamp.register(None, check_types=True)
    def get_nodes(self,
                  status: Optional[str] = None,
                  return_names: Optional[bool] = None,
                  details: Optional[CallDetails] = None) -> List[str]:
        """
        Returns list of nodes.

        :param status: Filter nodes for this status (``"online"``, ``"offline"``).
        :param return_names: Return node names (``authid``) instead of  object IDs.

        :returns: List of node IDs or node names.
        """
        self.log.info('{func}(status={status}, details.caller_authid={caller_authid})',
                      status=hlval(status),
                      func=hltype(self.get_nodes),
                      caller_authid=hlval(details.caller_authid if details else None))

        with self.gdb.begin() as txn:
            from_key = (self._mrealm_oid, '')
            to_key = (uuid.UUID(int=(int(self._mrealm_oid) + 1)), '')
            node_oids = list(
                self.gschema.idx_nodes_by_authid.select(txn, from_key=from_key, to_key=to_key, return_keys=False))

        if status:
            if status == 'offline':
                res = [node_oid for node_oid in node_oids if str(node_oid) not in self._nodes]
            elif status == 'online':
                res = [
                    node_oid for node_oid in node_oids
                    if (str(node_oid) in self._nodes and self._nodes[str(node_oid)].status == status)
                ]
            else:
                raise Exception('logic error')
        else:
            res = node_oids

        if return_names:
            res_ = []
            with self.gdb.begin() as txn:
                for node_oid in res:
                    node = self.gschema.nodes[txn, node_oid]
                    if node and node.authid:
                        res_.append(node.authid)
        else:
            res_ = [str(node_oid) for node_oid in res]

        return res_

    @wamp.register(None, check_types=True)
    def get_node(self, node_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return information about node. The procedure will raise an `crossbar.error.no_such_object` error
        when no node with the given authid can be found.

        :param node_oid: The object ID of the node to get information for, eg `"5616c7cc-31b5-4021-8cd9-b7769d3f0dd3"`.

        :returns: Node information object.
        """
        try:
            _node_oid = uuid.UUID(node_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid node_oid: {}'.format(str(e)))

        self.log.info('{func}(node_oid="{node_oid}")', node_oid=hlid(_node_oid), func=hltype(self.get_node))

        with self.gdb.begin() as txn:
            node = self.gschema.nodes[txn, _node_oid]
            if not node:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no node with object ID {} in management realm'.format(node_oid))

        node_obj = node.marshal()

        if node_oid in self._nodes:
            node = self._nodes[node_oid]
            node_obj['heartbeat'] = node.heartbeat_counter
            node_obj['timestamp'] = node.heartbeat_time
            node_obj['status'] = node.status
        else:
            node_obj['heartbeat'] = None
            node_obj['timestamp'] = None
            node_obj['status'] = 'offline'

        return node_obj

    @wamp.register(None, check_types=True)
    def get_node_by_authid(self, node_authid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return node information by node (auth)id. The procedure will raise an `crossbar.error.no_such_object` error
        when no node with the given authid can be found.

        :param node_authid: The WAMP authid the node is authenticated under.

        :returns: Node information object.
        """
        self.log.info('{func}(node_authid="{node_authid}")',
                      node_authid=hlid(node_authid),
                      func=hltype(self.get_node_by_authid))

        with self.gdb.begin() as txn:
            node_oid = self.gschema.idx_nodes_by_authid[txn, (self._mrealm_oid, node_authid)]
            if not node_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no node with authid {} in management realm'.format(node_authid))

        node_obj = self.get_node(str(node_oid), details)
        return node_obj

    @inlineCallbacks
    def _init_trace_api(self):
        @inlineCallbacks
        def on_trace_data(node_id, worker_id, trace_id, period, trace_data, details: Optional[CallDetails] = None):
            self.log.debug(
                'Trace "{trace_id}" on node "{node_id}" / worker "{worker_id}":\n\nperiod = {period}\n\ntrace_data = {trace_data}\n\n',
                node_id=node_id,
                worker_id=worker_id,
                trace_id=trace_id,
                period=pprint.pformat(period),
                trace_data=pprint.pformat(trace_data))
            trace = self._traces.get(trace_id, None)
            if trace:

                # beware, we are searching for a list, not a tuple here
                if [node_id, worker_id] in self._traces[trace_id].traced_workers:

                    publish_options = PublishOptions(eligible_authrole=trace.eligible_reader_roles,
                                                     exclude_authrole=trace.exclude_reader_roles,
                                                     acknowledge=True)

                    yield self.publish('crossbarfabriccenter.mrealm.tracing.on_trace_data',
                                       node_id,
                                       worker_id,
                                       trace_id,
                                       period,
                                       trace_data,
                                       options=publish_options)

        yield self.subscribe(on_trace_data, 'crossbarfabriccenter.remote.tracing.on_trace_data',
                             SubscribeOptions(details=True))

        self.log.debug('central tracing API initialized')

    @inlineCallbacks
    @wamp.register(None, check_types=True)
    def get_trace_data(self,
                       trace_id: str,
                       limit: Optional[int] = None,
                       details: Optional[CallDetails] = None) -> Deferred:
        self.log.info('get_trace_data(trace_id="{trace_id}", limit="{limit}")', trace_id=trace_id, limit=limit)

        trace = self._traces.get(trace_id, None)
        if trace:
            if trace.eligible_reader_roles and details:
                if details.caller_authrole not in trace.eligible_reader_roles:
                    raise ApplicationError(u"crossbar.error.no_such_object", "No trace with ID '{}'".format(trace_id))
            if trace.exclude_reader_roles and details:
                if details.caller_authrole in trace.exclude_reader_roles:
                    raise ApplicationError(u"crossbar.error.no_such_object", "No trace with ID '{}'".format(trace_id))
        else:
            raise ApplicationError(u"crossbar.error.no_such_object", "No trace with ID '{}'".format(trace_id))

        dl = []
        for node_id, worker_id in trace.traced_workers:
            node = self._nodes.get(node_id, None)
            if node and node.status == 'online':
                d = self.call('crossbarfabriccenter.remote.tracing.get_trace_data',
                              node_id,
                              worker_id,
                              trace_id,
                              0,
                              limit=limit)
                dl.append(d)
            else:
                dl.append(defer.fail('node not online'))

        trace_data_results = yield DeferredList(dl)
        result: Dict[str, Any] = {}
        for (node_id, worker_id), (success, data) in six.moves.zip(trace.traced_workers, trace_data_results):
            if node_id not in result:
                result[node_id] = {}
            result[node_id][worker_id] = {'success': success, 'data': data}
        returnValue(result)

    @wamp.register(None, check_types=True)
    def get_trace(self, trace_id: str, details: Optional[CallDetails] = None) -> Optional[dict]:
        """
        Get detail information about a previously created trace. When the trace
        doesn't exist, `None` is returned.

        Note: The trace information is only returned when the caller has
        read-access (at least), otherwise `None` is returned (silently).

        :param trace_id: The ID of the trace to retrieve information for.

        :returns: A trace information object.
        """
        trace = self._traces.get(trace_id, None)
        if trace:
            if trace.eligible_reader_roles and details:
                if details.caller_authrole not in trace.eligible_reader_roles:
                    self.log.debug(
                        'get_trace({trace_id}) -> trace found, but not authorized (role "{caller_authrole}" is not eligible)!',
                        trace_id=trace_id,
                        caller_authrole=details.caller_authrole if details else None)
                    return None
            if trace.exclude_reader_roles and details:
                if details.caller_authrole in trace.exclude_reader_roles:
                    self.log.debug(
                        'get_trace({trace_id}) -> trace found, but not authorized (role "{caller_authrole}" is excluded)!',
                        trace_id=trace_id,
                        caller_authrole=details.caller_authrole if details else None)
                    return None
            return trace.marshal()
        else:
            self.log.debug('get_trace({trace_id}) -> no such trace', trace_id=trace_id)
            return None

    @wamp.register(None, check_types=True)
    def get_traces(self, details: Optional[CallDetails] = None) -> List[str]:
        """
        Get IDs of trace defined.

        Note: Only IDs of traces to which the caller has read-access (at least) are returned.

        :returns: List of trace IDs.
        """
        trace_ids = []
        for trace in self._traces.values():
            if trace.eligible_reader_roles and details:
                if details.caller_authrole not in trace.eligible_reader_roles:
                    self.log.info(
                        'get_traces() -> trace "{trace_id}" found, but not authorized (role "{caller_authrole}" is not eligible)!',
                        trace_id=trace.trace_id,
                        caller_authrole=details.caller_authrole)
                    continue
            if trace.exclude_reader_roles and details:
                if details.caller_authrole in trace.exclude_reader_roles:
                    self.log.info(
                        'get_traces() -> trace "{trace_id}" found, but not authorized (role "{caller_authrole}" is excluded)!',
                        trace_id=trace.trace_id,
                        caller_authrole=details.caller_authrole)
                    continue
            trace_ids.append(trace.trace_id)
        return sorted(trace_ids)

    @wamp.register(None, check_types=True)
    def create_trace(self,
                     trace_id: str,
                     traced_workers: List[Tuple[str, str]],
                     trace_options: Optional[Dict] = None,
                     eligible_reader_roles: Optional[List[str]] = None,
                     exclude_reader_roles: Optional[List[str]] = None,
                     details: Optional[CallDetails] = None) -> dict:
        """
        Create a new trace.

        :param trace_id: The ID of the trace to create (must be unique within the management realm).

        :param traced_workers: A list of pairs `(node_id, worker_id)` with node and (router) worker IDs
            on which the trace is to be run.

        :param trace_options: Tracing options for the trace.

        :param eligible_reader_roles: If given, allow read access to the trace only for callers
            authenticated under a WAMP authrole FROM this list - otherwise allow any role (=public)!

        :param exclude_reader_roles: If given, allow read access to the trace only for callers
            authenticated under a WAMP authrole NOT FROM this list - otherwise allow any role (=public)!

        :returns: Trace started information.
        """
        if trace_id in self._traces:
            raise Exception('trace with ID "{}" already exists (status "{}")'.format(
                trace_id, self._traces[trace_id].status))

        status = 'stopped'
        trace = Trace(trace_id, traced_workers, trace_options, eligible_reader_roles, exclude_reader_roles, status)
        self._traces[trace_id] = trace

        trace_created: Dict[str, Any] = {
            # FIXME
        }

        publish_options = PublishOptions(eligible_authrole=trace.eligible_reader_roles,
                                         exclude_authrole=trace.exclude_reader_roles)

        self.publish('{}tracing.on_trace_created'.format(self._uri_prefix),
                     trace_id,
                     trace_created,
                     options=publish_options)

        return trace_created

    @inlineCallbacks
    @wamp.register(None, check_types=True)
    def start_trace(self, trace_id: str, details: Optional[CallDetails] = None) -> Deferred:
        """
        Start a previously created trace.

        :param trace_id: The ID of the trace to start.
        :type trace_id: str

        :returns: dict: Trace started information.
        """
        trace = self._traces.get(trace_id, None)
        if not trace:
            raise Exception('no trace with ID "{}" exists'.format(trace_id))

        if trace.status != 'stopped':
            raise Exception('cannot start trace with ID "{}" currently in status "{}"'.format(trace_id, trace.status))

        trace.status = 'starting'

        publish_options = PublishOptions(eligible_authrole=trace.eligible_reader_roles,
                                         exclude_authrole=trace.exclude_reader_roles)

        self.publish('{}tracing.on_trace_starting'.format(self._uri_prefix), trace_id, options=publish_options)

        traces_started = []
        traces_failed = []

        for node_id, worker_id in trace.traced_workers:
            node = self._nodes.get(node_id, None)
            if node and node.status == 'online':

                try:
                    # stop any currently online traces (we don't want to get data from orphaned traces)
                    traces = yield self.call('crossbarfabriccenter.remote.tracing.get_traces', node_id, worker_id)
                    if trace_id in traces:
                        _trace = yield self.call('crossbarfabriccenter.remote.tracing.get_trace', node_id, worker_id,
                                                 trace_id)
                        if _trace['status'] == 'running':
                            trace_stopped = yield self.call('crossbarfabriccenter.remote.tracing.stop_trace', node_id,
                                                            worker_id, trace_id)
                            self.log.info(
                                'Trace "{trace_id}" on node "{node_id}" / worker "{worker_id}" stopped:\n{trace_stopped}',
                                trace_stopped=trace_stopped,
                                trace_id=trace_id,
                                node_id=node_id,
                                worker_id=worker_id)

                    # start fresh trace
                    trace_started = yield self.call('crossbarfabriccenter.remote.tracing.start_trace',
                                                    node_id,
                                                    worker_id,
                                                    trace_id,
                                                    trace_options=trace.trace_options)
                    self.log.info(
                        'Trace "{trace_id} on node "{node_id}" / worker "{worker_id}" started with options {trace_options}:\n{trace_started}"',
                        node_id=node_id,
                        worker_id=worker_id,
                        trace_id=trace_id,
                        trace_options=trace.trace_options,
                        trace_started=trace_started)

                    traces_started.append(trace_started)
                except Exception as e:
                    self.log.failure()
                    traces_failed.append({
                        'node_id': node_id,
                        'node_status': node.status,
                        'worker_id': worker_id,
                        'error': str(e)
                    })
            else:
                node_status = node.status if node else 'offline'
                self.log.warn('trace "{trace_id}": skipping to start trace on node "{node_id}" in status "{status}"',
                              node_id=node_id,
                              trace_id=trace_id,
                              status=node_status)
                traces_failed.append({'node_id': node_id, 'node_status': node_status, 'worker_id': worker_id})

        trace.status = 'running'

        trace_started = {
            'started': traces_started,
            'failed': traces_failed,
        }

        self.publish('{}tracing.on_trace_started'.format(self._uri_prefix),
                     trace_id,
                     trace_started,
                     options=publish_options)

        returnValue(trace_started)

    @inlineCallbacks
    @wamp.register(None, check_types=True)
    def stop_trace(self, trace_id: str, details: Optional[CallDetails] = None) -> Deferred:
        """
        Stop a running trace.

        :param trace_id: The ID of the trace to stop.

        :returns: Trace stopped information.
        """
        trace = self._traces.get(trace_id, None)
        if not trace:
            raise Exception('no trace with ID "{}" exists'.format(trace_id))

        if trace.status not in ['running', 'stopping_failed']:
            raise Exception('cannot stop trace with ID "{}" currently in status "{}"'.format(trace_id, trace.status))

        trace.status = 'stopping'

        publish_options = PublishOptions(eligible_authrole=trace.eligible_reader_roles,
                                         exclude_authrole=trace.exclude_reader_roles)

        self.publish('{}tracing.on_trace_stopping'.format(self._uri_prefix), trace_id, options=publish_options)

        traces_stopped = []
        traces_failed = []

        for node_id, worker_id in trace.traced_workers:
            node = self._nodes.get(node_id, None)
            if node and node.status == 'online':

                try:
                    traces = yield self.call('crossbarfabriccenter.remote.tracing.get_traces', node_id, worker_id)
                    if trace_id in traces:
                        _trace = yield self.call('crossbarfabriccenter.remote.tracing.get_trace', node_id, worker_id,
                                                 trace_id)
                        if _trace['status'] == 'running':
                            trace_stopped = yield self.call('crossbarfabriccenter.remote.tracing.stop_trace', node_id,
                                                            worker_id, trace_id)
                            traces_stopped.append(trace_stopped)
                            self.log.info(
                                'Trace "{trace_id}" on node "{node_id}" / worker "{worker_id}" stopped:\n{trace_stopped}',
                                trace_stopped=trace_stopped,
                                trace_id=trace_id,
                                node_id=node_id,
                                worker_id=worker_id)
                except Exception as e:
                    self.log.failure()
                    traces_failed.append({
                        'node_id': node_id,
                        'node_status': node.status,
                        'worker_id': worker_id,
                        'error': str(e)
                    })
            else:
                node_status = node.status if node else 'offline'
                self.log.warn('trace "{trace_id}": skipping to stop trace on node "{node_id}" in status "{status}"',
                              node_id=node_id,
                              trace_id=trace_id,
                              status=node_status)
                traces_failed.append({'node_id': node_id, 'node_status': node_status, 'worker_id': worker_id})

        if len(traces_failed):
            trace.status = 'stopping_failed'
        else:
            trace.status = 'stopped'

        trace_stopped = {
            'stopped': traces_stopped,
            'failed': traces_failed,
        }

        self.publish('{}tracing.on_trace_stopped'.format(self._uri_prefix),
                     trace_id,
                     trace_stopped,
                     options=publish_options)

        returnValue(trace_stopped)

    @wamp.register(None, check_types=True)
    def delete_trace(self, trace_id: str, details: Optional[CallDetails] = None) -> dict:
        """
        Delete a previously created (and currently stopped) trace.

        :param trace_id: The ID of the trace to delete.
        :returns: Trace deletion information.
        """
        trace = self._traces.get(trace_id, None)
        if not trace:
            raise Exception('no trace with ID "{}" exists'.format(trace_id))

        if trace.status not in ['stopped', 'stopping_failed']:
            raise Exception('cannot delete trace with ID "{}" currently in status "{}"'.format(trace_id, trace.status))

        trace_deleted: Dict[str, Any] = {
            # FIXME
        }

        publish_options = PublishOptions(eligible_authrole=trace.eligible_reader_roles,
                                         exclude_authrole=trace.exclude_reader_roles)

        self.publish('{}tracing.on_trace_deleted'.format(self._uri_prefix),
                     trace_id,
                     trace_deleted,
                     options=publish_options)

        del self._traces[trace_id]

        return trace_deleted
