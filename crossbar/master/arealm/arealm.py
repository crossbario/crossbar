###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import uuid
from typing import Optional, List, Dict
from pprint import pformat

import numpy as np

import cfxdb.mrealm.types
from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import CallDetails, PublishOptions, RegisterOptions

from crossbar._util import hl, hlid, hltype, hlval
import zlmdb
from cfxdb.mrealm import ApplicationRealm, ApplicationRealmRoleAssociation, Role, Permission, \
    WorkerGroupStatus, Principal, Credential, RouterWorkerGroupClusterPlacement, Node

import txaio

txaio.use_twisted()
from txaio import time_ns, sleep, make_logger  # noqa
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall


class ApplicationRealmMonitor(object):
    """
    Background monitor running periodically in the master node to monitor, check and apply
    necessary actions for application realms.

    The monitor is started when an application realm is started (on a router worker group already
    running on a router cluster).
    """
    log = make_logger()

    def __init__(self, manager, arealm_oid, interval=10.):
        """

        :param manager: The application realm manager that has started and is hosting this monitor.
        :type manager: :class:`crossbar.master.arealm.ApplicationRealmManager`

        :param arealm_oid: Application realm object ID (not WAMP realm name).
        :type arealm_oid: :class:`uuid.UUID`

        :param interval: Run this monitor periodically every `interval` seconds.
        :type interval: float
        """
        # the arealm manager this monitor is started from
        self._manager = manager

        # the arealm this monitor is working for
        self._arealm_oid = arealm_oid

        # the interval (in seconds) this monitor will check the arealm
        self._interval = interval

        # when this monitor is running, the looping call periodically executed
        self._loop = None

        # while self._loop is being executed (which happens every self._interval secs),
        # this flag is set
        self._check_and_apply_in_progress = False

    @property
    def is_started(self):
        """

        :return: Flag indicating whether this monitor is currently running.
        """
        return self._loop is not None and self._loop.running

    def start(self):
        """
        Start this monitor. The monitor will run in the background every `interval` seconds
        until stopped.

        .. note::
            Should the monitor iteration exceed 'interval` seconds run-time, the monitor
            will skip the next iteration(s). In other words, the monitor iteration loop
            automatically prohibits being run twice in parallel.
        :return:
        """
        assert self._loop is None

        self._loop = LoopingCall(self._check_and_apply)
        self._loop.start(self._interval)

    def stop(self):
        """
        Stop running this monitor.
        """
        assert self._loop is not None

        self._loop.stop()
        self._loop = None
        self._check_and_apply_in_progress = False

    @inlineCallbacks
    def _check_and_apply(self):
        """
        Run one iteration of the background monitor check & apply cycle.

        - _apply_routercluster_placements (L194)
        - _apply_webcluster_backends (L232)
            - _apply_webcluster_routes
        """
        if self._check_and_apply_in_progress:
            # we prohibit running the iteration multiple times concurrently. this might
            # happen when the iteration takes longer than the interval the monitor is set to
            self.log.warn(
                '{func} {action} for application realm {arealm_oid} skipped! check & apply already in progress.',
                action=hl('check & apply run skipped', color='red', bold=True),
                func=hltype(self._check_and_apply),
                arealm_oid=hlid(self._arealm_oid))
            return
        else:
            self.log.info('{func} {action} for application realm {arealm_oid} ..',
                          action=hl('check & apply run started', color='green', bold=True),
                          func=hltype(self._check_and_apply),
                          arealm_oid=hlid(self._arealm_oid))
            self._check_and_apply_in_progress = True

        # collect information on resources that ought to be running for the arealm
        with self._manager.db.begin() as txn:
            arealm = self._manager.schema.arealms[txn, self._arealm_oid]

            # the object must be in database, otherwise this is a logic error
            assert arealm

            # only process arealm when status is STATUS_STARTING or STATUS_RUNNING
            if arealm.status in [ApplicationRealm.STATUS_STARTING, ApplicationRealm.STATUS_RUNNING]:

                # collect roles associated with the arealm
                roles = []
                for _, role_oid in self._manager.schema.arealm_role_associations.select(
                        txn, from_key=(self._arealm_oid, uuid.UUID(bytes=b'\0' * 16)), return_values=False):
                    role = self._manager.schema.roles[txn, role_oid]
                    roles.append(role)

                # get the routercluster workergroup for this arealm
                if arealm.workergroup_oid:
                    workergroup = self._manager.schema.router_workergroups[txn, arealm.workergroup_oid]

                    # the object must be in database, otherwise this is a logic error
                    assert workergroup

                    # get all workergroup worker placements for this workergroup
                    workergroup_placements: List[RouterWorkerGroupClusterPlacement] = []

                    # idx_clusterplacement_by_workername: (workergroup_oid, cluster_oid, node_oid, worker_name)
                    #                                       -> placement_oid
                    for placement_oid in self._manager.schema.idx_clusterplacement_by_workername.select(
                            txn,
                            from_key=(workergroup.oid, uuid.UUID(bytes=b'\0' * 16), uuid.UUID(bytes=b'\0' * 16), ''),
                            to_key=(uuid.UUID(int=(int(workergroup.oid) + 1)), uuid.UUID(bytes=b'\0' * 16),
                                    uuid.UUID(bytes=b'\0' * 16), ''),
                            return_keys=False):
                        placement = self._manager.schema.router_workergroup_placements[txn, placement_oid]
                        workergroup_placements.append(placement)

                else:
                    self.log.warn('{func} application realm in status {status}, but no worker group associated!',
                                  func=hltype(self._check_and_apply),
                                  status=hlval(ApplicationRealm.STATUS_BY_CODE[arealm.status]))
                    self._check_and_apply_in_progress = False
                    return
            else:
                self.log.warn('{func} {action} for application realm {arealm_oid} (status is {arealm_status})',
                              action=hl('check & apply skipped', color='yellow', bold=True),
                              func=hltype(self._check_and_apply),
                              arealm_oid=hlid(self._arealm_oid),
                              arealm_status=arealm.status)
                self._check_and_apply_in_progress = False
                return

        # whenever we encounter a resource not running or in error, this flag is set False
        is_running_completely = True

        # map of nodes this router worker group runs workers on
        placement_nodes = {}

        if workergroup_placements:
            self.log.info(
                '{func} Applying {cnt_placements} worker placements for router cluster worker group {workergroup_oid}, arealm {arealm_oid}',
                func=hltype(self._check_and_apply),
                cnt_placements=hlval(len(workergroup_placements)),
                workergroup_oid=hlid(arealm.workergroup_oid),
                arealm_oid=hlid(arealm.oid))

            with self._manager.gdb.begin() as txn:
                for node in self._manager.gschema.nodes.select(txn, return_keys=False):
                    placement_nodes[node.oid] = node

            # apply routercluster worker placements for nodes/workers involved
            success = yield self._apply_routercluster_placements(arealm, workergroup, workergroup_placements,
                                                                 placement_nodes)
            if not success:
                is_running_completely = False
        else:
            self.log.warn(
                '{func} no placements configured for router cluster worker group {workergroup_oid} and arealm {arealm_oid}!',
                func=hltype(self._check_and_apply),
                workergroup_oid=hlid(arealm.workergroup_oid),
                arealm_oid=hlid(arealm.oid))
            is_running_completely = False

        # if the application realm has a (frontend) webcluster assigned (to accept incoming client
        # connections), setup proxy backend connections and routes to the router workers in the
        # router worker group of the application realm
        if arealm and arealm.webcluster_oid and workergroup_placements:
            # get list of nodes/workers for the webcluster, eg:
            #
            # [('309fa904-9f32-47b9-901c-33ec78b0c582', 'cpw-edc6ba18-0'),
            #  ('309fa904-9f32-47b9-901c-33ec78b0c582', 'cpw-edc6ba18-1'),
            #  ('4f19d9e0-4b28-45fc-bbb0-8e46e6d79376', 'cpw-edc6ba18-0'),
            #  ('4f19d9e0-4b28-45fc-bbb0-8e46e6d79376', 'cpw-edc6ba18-1')]
            #
            wc_workers = self._manager._session._webcluster_manager.get_webcluster_workers(arealm.webcluster_oid,
                                                                                           filter_online=True)
            self.log.debug('{func} Ok, found {cnt_workers} running web cluster workers ..',
                           func=hltype(self._check_and_apply),
                           cnt_workers=len(wc_workers) if wc_workers else 0)

            # on each webcluster worker, setup backend connections and routes to all router workers of
            # the router worker group of this application realm
            for wc_node_oid, wc_worker_id in wc_workers:
                success = yield self._apply_webcluster_connections(wc_node_oid, wc_worker_id, workergroup_placements,
                                                                   placement_nodes, arealm)
                if not success:
                    is_running_completely = False
        else:
            self.log.warn('{func} application realm in status {status}, but no web cluster associated!',
                          func=hltype(self._check_and_apply),
                          status=hlval(ApplicationRealm.STATUS_BY_CODE[arealm.status]))
            is_running_completely = False

        # if the status is STATUS_STARTING and we have indeed completed startup in this iteration,
        # update the status in the database and publish an event
        if arealm.status in [ApplicationRealm.STATUS_STARTING] and is_running_completely:
            with self._manager.db.begin(write=True) as txn:
                arealm = self._manager.schema.arealms[txn, self._arealm_oid]
                arealm.status = ApplicationRealm.STATUS_RUNNING
                arealm.changed = time_ns()
                self._manager.schema.arealms[txn, arealm.oid] = arealm

            arealm_started = {
                'oid': str(arealm.oid),
                'status': ApplicationRealm.STATUS_BY_CODE[arealm.status],
                'changed': arealm.changed,
            }
            yield self._manager._session.publish('{}.on_arealm_started'.format(self._manager._prefix),
                                                 arealm_started,
                                                 options=self._manager._PUBOPTS)

        if is_running_completely:
            color = 'green'
            action = 'check & apply run completed successfully'
        else:
            color = 'red'
            action = 'check & apply run finished with problems left'

        self._check_and_apply_in_progress = False
        self.log.info('{func} {action} for application realm {arealm_oid}!',
                      action=hl(action, color=color, bold=True),
                      func=hltype(self._check_and_apply),
                      arealm_oid=hlid(self._arealm_oid))

    @inlineCallbacks
    def _apply_webcluster_connections(self, wc_node_oid, wc_worker_id, workergroup_placements, placement_nodes,
                                      arealm):
        """
        For given webcluster worker ``(wc_node_oid, wc_worker_id)``, setup backend connections and routes
        to all router workers ``workergroup_placements`` of the router worker group of the given
        application realm ``arealm``.
        """
        is_running_completely = True

        # iterate over all router worker placements in the router cluster worker group.
        # for each placement on the given (wc_node_oid, wc_worker_id) webcluster worker, we need to setup:
        #   - a connection and
        #   - routes
        for placement in workergroup_placements:
            self.log.debug('{func} applying router cluster worker group placement:\n{placement}',
                           func=hltype(self._apply_webcluster_connections),
                           placement=pformat(placement.marshal()))

            # the router worker this placement targets
            node_oid = placement.node_oid
            worker_name = placement.worker_name
            tcp_listening_port = placement.tcp_listening_port

            node_authid = placement_nodes[node_oid].authid
            node_cluster_ip = placement_nodes[node_oid].cluster_ip

            # we will name the connection on our proxy worker along the target node/worker
            connection_id = 'cnc_{}_{}'.format(node_authid, worker_name)

            # check if a connection with the respective name is already running
            try:
                connection = yield self._manager._session.call(
                    'crossbarfabriccenter.remote.proxy.get_proxy_connection', str(wc_node_oid), wc_worker_id,
                    connection_id)
            except ApplicationError as e:
                if e.error != 'crossbar.error.no_such_object':
                    # anything but "no_such_object" is unexpected (and fatal)
                    raise
                is_running_completely = False
                connection = None
                self.log.warn(
                    '{func} No connection {connection_id} currently running for web cluster (proxy) worker {wc_worker_id} on node {wc_node_oid}: starting backend connection ..',
                    func=hltype(self._apply_webcluster_connections),
                    wc_node_oid=hlid(wc_node_oid),
                    wc_worker_id=hlid(wc_worker_id),
                    connection_id=hlid(connection_id))
            else:
                self.log.debug(
                    '{func} Ok, connection {connection_id} already running on web cluster (proxy) worker {wc_worker_id} on node {wc_node_oid}',
                    func=hltype(self._apply_webcluster_connections),
                    wc_node_oid=hlid(wc_node_oid),
                    wc_worker_id=hlid(wc_worker_id),
                    connection_id=hlid(connection_id))

            # if no connection is running, and if the target placement has a TCP port configured,
            # start a new connection on the proxy worker
            #
            # see: :class:`crossbar.worker.proxy.ProxyConnection`
            #
            if not connection and tcp_listening_port:
                # transport configuration for proxy worker -> router worker connections
                config = {
                    "transport": {
                        "type": "rawsocket",
                        "endpoint": {
                            "type": "tcp",
                            # we assume the authid for the node was set to the hostname of that node, and
                            # that the node is reachable using this hostname from other nodes (eg inside a
                            # private network)
                            "host": node_cluster_ip,
                            "port": tcp_listening_port
                        },
                        "url": "ws://{}".format(node_authid),
                        "serializer": "cbor"
                    },
                    "auth": {
                        # must use cryptosign-proxy, NOT anonymous-proxy, since we run
                        # over TCP, not UDS, and to IP addresses on different hosts
                        "cryptosign-proxy": {
                            "type": "static"
                        }
                    }
                }
                connection = yield self._manager._session.call(
                    'crossbarfabriccenter.remote.proxy.start_proxy_connection', str(wc_node_oid), wc_worker_id,
                    connection_id, config)

                self.log.info('{func} Proxy backend connection started:\n{connection}',
                              func=hltype(self._apply_webcluster_connections),
                              connection=connection)

            # if by now we do have a connection on the proxy worker, setup all routes (for the arealm)
            # using the connection
            #
            # see: :class:`crossbar.worker.proxy.ProxyRoute`
            #
            if connection:
                # proxy routes use "realm name" as key (not a synthetic ID)
                realm_name = arealm.name
                routes = []

                try:
                    routes = yield self._manager._session.call(
                        'crossbarfabriccenter.remote.proxy.list_proxy_realm_routes', str(wc_node_oid), wc_worker_id,
                        realm_name)
                except ApplicationError as e:
                    if e.error != 'crossbar.error.no_such_object':
                        # anything but "no_such_object" is unexpected (and fatal)
                        raise
                    is_running_completely = False
                    self.log.warn(
                        '{func} No route for realm "{realm_name}" currently running for web cluster (proxy) worker {wc_worker_id} on node {wc_node_oid}: starting backend route ..',
                        func=hltype(self._apply_webcluster_connections),
                        wc_node_oid=hlid(wc_node_oid),
                        wc_worker_id=hlid(wc_worker_id),
                        realm_name=hlval(realm_name))
                else:
                    self.log.debug(
                        '{func} Ok, route for realm "{realm_name}" already running on web cluster (proxy) worker {wc_worker_id} on node {wc_node_oid}',
                        func=hltype(self._apply_webcluster_connections),
                        wc_node_oid=hlid(wc_node_oid),
                        wc_worker_id=hlid(wc_worker_id),
                        realm_name=hlval(realm_name))

                if (not routes or len(routes) != len(workergroup_placements)):
                    new_routes, _is_running_completely = yield self._apply_webcluster_routes(
                        workergroup_placements,
                        wc_node_oid,
                        wc_worker_id,
                        arealm,
                        placement_nodes,
                    )
                    routes.extend(new_routes)
                    if is_running_completely:
                        is_running_completely = _is_running_completely

        return is_running_completely

    @inlineCallbacks
    def _apply_webcluster_routes(self, workergroup_placements, wc_node_oid, wc_worker_id, arealm,
                                 placement_nodes_keys):
        is_running_completely = True
        realm_name = arealm.name
        try:
            routes = yield self._manager._session.call(
                'crossbarfabriccenter.remote.proxy.list_proxy_realm_routes',
                str(wc_node_oid),
                wc_worker_id,
                realm_name,
            )

        except ApplicationError as e:
            if e.error != 'crossbar.error.no_such_object':
                # anything but "no_such_object" is unexpected (and fatal)
                raise
            is_running_completely = False
            self.log.info(
                '{func} No routes for realm "{realm_name}" currently running for web cluster (proxy) worker {wc_worker_id} on node {wc_node_oid}: starting backend routes ..',
                func=hltype(self._apply_webcluster_routes),
                wc_node_oid=hlid(wc_node_oid),
                wc_worker_id=hlid(wc_worker_id),
                realm_name=hlval(realm_name))
            routes = []

        # FIXME: proxy routes for all realms X roles
        for placement in workergroup_placements:

            # can placement.node_oid *not* be in this map?
            node_authid = placement_nodes_keys[placement.node_oid].authid
            connection_id = 'cnc_{}_{}'.format(node_authid, placement.worker_name)

            # config = {'anonymous': connection_id}
            config = {}
            from_key = (arealm.oid, uuid.UUID(bytes=b'\x00' * 16))
            to_key = (uuid.UUID(int=(int(arealm.oid) + 1)), uuid.UUID(bytes=b'\x00' * 16))
            with self._manager.db.begin() as txn:
                for _, role_oid in self._manager.schema.arealm_role_associations.select(txn,
                                                                                        from_key=from_key,
                                                                                        to_key=to_key,
                                                                                        return_values=False):
                    role = self._manager.schema.roles[txn, role_oid]
                    config[role.name] = connection_id

            # existing = any(route['config'].get(role.name, None) == connection_id for route in routes)

            try:
                route = yield self._manager._session.call('crossbarfabriccenter.remote.proxy.start_proxy_realm_route',
                                                          str(wc_node_oid), wc_worker_id, realm_name, config)
            except Exception as e:
                self.log.error('Proxy route failed: {e}', e=e)
            else:
                self.log.info(
                    '{func} Proxy backend route started:\n{route}',
                    func=hltype(self._apply_webcluster_routes),
                    route=route,
                )
                routes.append(route)
        returnValue((routes, is_running_completely))

    @inlineCallbacks
    def _apply_routercluster_placements(self, arealm: cfxdb.mrealm.ApplicationRealm,
                                        workergroup: cfxdb.mrealm.RouterWorkerGroup,
                                        workergroup_placements: List[RouterWorkerGroupClusterPlacement],
                                        placement_nodes: Dict[uuid.UUID, Node]):
        """
        Apply worker placements for workergroup of routercluster.

        :param arealm: Application realm to process placements for.
        :param workergroup: Router worker group to process placements for.
        :param workergroup_placements: List of placements.
        :param placement_nodes: Map of node object IDs to pair of node public key and authid.
        """
        # this flag will remain true as long as we could process all placements successfully
        is_running_completely = True

        # I) iterate over all placements sequentially
        for placement in workergroup_placements:
            self.log.info('{func} Applying router cluster worker group placement:\n{placement}',
                          func=hltype(self._apply_routercluster_placements),
                          placement=pformat(placement.marshal()))

            # place the worker on this node and (router) worker
            node_oid = placement.node_oid
            worker_name = placement.worker_name

            # get run-time information for the node (as maintained here in our master view of the external world)
            # instance of crossbar.master.mrealm.controller.Node
            node = self._manager._session.nodes.get(str(node_oid), None)

            # the node must be found and must be currently online for us to manage it
            if node and node.status == 'online':
                node_authid = placement_nodes[node_oid].authid

                self.log.debug('{func} Ok, router cluster node "{node_authid}" ({node_oid}) is running!',
                               func=hltype(self._apply_routercluster_placements),
                               node_authid=hlid(node_authid),
                               node_oid=hlid(node_oid))

                # II.1) get worker run-time information (obtained by calling into the live node)
                worker = None
                try:
                    worker = yield self._manager._session.call('crossbarfabriccenter.remote.node.get_worker',
                                                               str(node_oid), worker_name)
                except ApplicationError as e:
                    if e.error != 'crossbar.error.no_such_worker':
                        # anything but "no_such_worker" is unexpected (and fatal)
                        raise
                    self.log.warn(
                        '{func} No router cluster worker {worker_name} currently running on node {node_oid}: starting worker ..',
                        func=hltype(self._apply_routercluster_placements),
                        node_oid=hlid(node_oid),
                        worker_name=hlid(worker_name))
                except:
                    self.log.failure()
                    raise
                else:
                    self.log.debug(
                        '{func} Ok, router cluster worker {worker_name} already running on node {node_oid}!',
                        func=hltype(self._apply_routercluster_placements),
                        node_oid=hlid(node_oid),
                        worker_name=hlid(worker_name))

                # II.2) if there isn't a worker running (with worker ID as we expect) already, start a new router worker
                if not worker:
                    worker_options = {
                        'env': {
                            'inherit': ['PYTHONPATH']
                        },
                        'title': 'Managed router worker {}'.format(worker_name),
                        'extra': {}
                    }
                    try:
                        worker_started = yield self._manager._session.call(
                            'crossbarfabriccenter.remote.node.start_worker', str(node_oid), worker_name, 'router',
                            worker_options)
                        worker = yield self._manager._session.call('crossbarfabriccenter.remote.node.get_worker',
                                                                   str(node_oid), worker_name)
                        self.log.info(
                            '{func} Router cluster worker {worker_name} started on node {node_oid} [{worker_started}]',
                            func=hltype(self._apply_routercluster_placements),
                            node_oid=hlid(node_oid),
                            worker_name=hlid(worker['id']),
                            worker_started=worker_started)
                    except:
                        self.log.failure()
                        is_running_completely = False

                # we can only continue with transport(s) when we now have a worker started already
                if worker:

                    transport_id = 'tnp_{}'.format(worker_name)
                    transport = None

                    # III.1) get transport run-time information (obtained by calling into the live node)
                    try:
                        transport = yield self._manager._session.call(
                            'crossbarfabriccenter.remote.router.get_router_transport', str(node_oid), worker_name,
                            transport_id)
                    except ApplicationError as e:
                        if e.error != 'crossbar.error.no_such_object':
                            # anything but "no_such_object" is unexpected (and fatal)
                            raise
                        self.log.info(
                            '{func} No Transport {transport_id} currently running for Web cluster worker {worker_name}: starting transport ..',
                            func=hltype(self._apply_routercluster_placements),
                            worker_name=hlid(worker_name),
                            transport_id=hlid(transport_id))
                    else:
                        self.log.debug(
                            '{func} Ok, transport {transport_id} already running on Web cluster worker {worker_name}',
                            func=hltype(self._apply_routercluster_placements),
                            worker_name=hlid(worker_name),
                            transport_id=hlid(transport_id))

                    # III.2) if there isn't a transport started (with transport ID as we expect) already,
                    # start a new transport
                    if not transport:

                        # FIXME: allow to configure transport type TCP vs UDS
                        USE_UDS = False

                        if USE_UDS:
                            # https://serverfault.com/a/641387/117074
                            UNIX_PATH_MAX = 108
                            transport_path = os.path.abspath('{}.sock'.format(transport_id))
                            if len(transport_path) > UNIX_PATH_MAX:
                                raise RuntimeError(
                                    'unix domain socket path too long! was {}, but maximum is {}'.format(
                                        len(transport_path), UNIX_PATH_MAX))
                            transport_config = {
                                'id': transport_id,
                                'type': 'rawsocket',
                                'endpoint': {
                                    'type': 'unix',
                                    'path': transport_path
                                },
                                'options': {
                                    "max_message_size": 1048576
                                },
                                'serializers': ['cbor'],
                                'auth': {
                                    # use anonymous-proxy authentication for UDS based connections (on localhost only)
                                    'anonymous-proxy': {
                                        'type': 'static'
                                    }
                                }
                            }
                        else:
                            principals = {}
                            all_pubkeys = [node.pubkey for node in placement_nodes.values()]
                            for node in placement_nodes.values():
                                principal = {
                                    'realm': arealm.name,
                                    'role': 'rlink',
                                    'authorized_keys': all_pubkeys,
                                }
                                principals[node.authid] = principal

                            transport_config = {
                                'id': transport_id,
                                'type': 'rawsocket',
                                'endpoint': {
                                    'type': 'tcp',
                                    # let the router worker auto-assign a listening port from this range
                                    'portrange': [10000, 10100]
                                },
                                'options': {
                                    "max_message_size": 1048576
                                },
                                'serializers': ['cbor'],
                                'auth': {
                                    # use cryptosign-proxy authentication for TCP based connections
                                    'cryptosign-proxy': {
                                        'type': 'static',
                                        'principals': principals
                                    }
                                }
                            }

                        try:
                            transport_started = yield self._manager._session.call(
                                'crossbarfabriccenter.remote.router.start_router_transport', str(node_oid),
                                worker_name, transport_id, transport_config)
                            transport = yield self._manager._session.call(
                                'crossbarfabriccenter.remote.router.get_router_transport', str(node_oid), worker_name,
                                transport_id)
                            self.log.info(
                                '{func} Transport {transport_id} started on router cluster worker {worker_name} [{transport_started}]',
                                func=hltype(self._apply_routercluster_placements),
                                worker_name=hlid(worker_name),
                                transport_id=hlid(transport_id),
                                transport_started=transport_started)
                        except:
                            self.log.failure()
                            is_running_completely = False
                        else:
                            # when a new transport was started with an auto-assigned portrange, grab the
                            # actual TCP listening port that was selected on the target node
                            tcp_listening_port = transport_started['config']['endpoint']['port']

                            with self._manager.db.begin(write=True) as txn:
                                placement = self._manager.schema.router_workergroup_placements[txn, placement.oid]
                                placement.changed = time_ns()
                                placement.status = WorkerGroupStatus.RUNNING
                                placement.tcp_listening_port = tcp_listening_port
                                self._manager.schema.router_workergroup_placements[txn, placement.oid] = placement

                            self.log.info('{func} Ok, placement {placement_oid} updated:\n{placement}',
                                          func=hltype(self._apply_routercluster_placements),
                                          placement_oid=hlid(placement.oid),
                                          placement=placement)

                    # IV.1) get arealm run-time information (obtained by calling into the live node)

                    runtime_realm_id = 'rlm_{}'.format(str(arealm.oid)[:8])
                    running_arealm = None

                    try:
                        running_arealm = yield self._manager._session.call(
                            'crossbarfabriccenter.remote.router.get_router_realm', str(node_oid), worker_name,
                            runtime_realm_id)
                    except ApplicationError as e:
                        if e.error != 'crossbar.error.no_such_object':
                            # anything but "no_such_object" is unexpected (and fatal)
                            raise
                        self.log.info(
                            '{func} No application realm {runtime_realm_id} currently running for router cluster worker {worker_name}: starting application realm ..',
                            func=hltype(self._apply_routercluster_placements),
                            worker_name=hlid(worker_name),
                            runtime_realm_id=hlid(runtime_realm_id))
                    else:
                        self.log.debug(
                            '{func} Ok, application realm {runtime_realm_id} already running on router cluster worker {worker_name}',
                            func=hltype(self._apply_routercluster_placements),
                            worker_name=hlid(worker_name),
                            runtime_realm_id=hlid(runtime_realm_id))

                    # IV.2) if there isn't an arealm started (with realm ID as we expect) already,
                    # start a new arealm
                    if not running_arealm:
                        realm_config = {
                            "name":
                            arealm.name,

                            # built-in (reserved) roles
                            "roles": [{
                                "name":
                                "rlink",
                                "permissions": [{
                                    "uri": "",
                                    "match": "prefix",
                                    "allow": {
                                        "call": True,
                                        "register": True,
                                        "publish": True,
                                        "subscribe": True
                                    },
                                    "disclose": {
                                        "caller": True,
                                        "publisher": True
                                    },
                                    "cache": True
                                }]
                            }]
                        }
                        try:
                            # start the application realm on the remote node worker
                            realm_started = yield self._manager._session.call(
                                'crossbarfabriccenter.remote.router.start_router_realm', str(node_oid), worker_name,
                                runtime_realm_id, realm_config)
                            running_arealm = yield self._manager._session.call(
                                'crossbarfabriccenter.remote.router.get_router_realm', str(node_oid), worker_name,
                                runtime_realm_id)
                            self.log.info(
                                '{func} Application realm {runtime_realm_id} started on router cluster worker {worker_name} [{realm_started}]',
                                func=hltype(self._apply_routercluster_placements),
                                worker_name=hlid(worker_name),
                                runtime_realm_id=hlid(running_arealm['id']),
                                realm_started=realm_started)
                        except:
                            self.log.failure()
                            is_running_completely = False
                        else:
                            # start all built-in (reserved) roles on the remote node worker
                            i = 1
                            for role in realm_config['roles']:
                                runtime_role_id = 'rle_{}_builtin_{}'.format(str(arealm.oid)[:8], i)
                                role_started = yield self._manager._session.call(
                                    'crossbarfabriccenter.remote.router.start_router_realm_role', str(node_oid),
                                    worker_name, runtime_realm_id, runtime_role_id, role)
                                running_role = yield self._manager._session.call(
                                    'crossbarfabriccenter.remote.router.get_router_realm_role', str(node_oid),
                                    worker_name, runtime_realm_id, runtime_role_id)
                                self.log.info(
                                    '{func} Application realm role {runtime_role_id} started on router cluster worker {worker_name} [{role_started}]',
                                    func=hltype(self._apply_routercluster_placements),
                                    worker_name=hlid(worker_name),
                                    runtime_role_id=hlid(running_role['id']),
                                    role_started=role_started)
                                i += 1

                    if running_arealm:
                        # start all roles defined in the realm configuration on the remote node worker
                        from_key = (arealm.oid, uuid.UUID(bytes=b'\x00' * 16))
                        to_key = (uuid.UUID(int=(int(arealm.oid) + 1)), uuid.UUID(bytes=b'\x00' * 16))

                        with self._manager.db.begin() as txn:
                            for _, role_oid in self._manager.schema.arealm_role_associations.select(
                                    txn, from_key=from_key, to_key=to_key, return_values=False):
                                role = self._manager.schema.roles[txn, role_oid]

                                # make sure role name is not reserved
                                assert role.name not in [
                                    'rlink'
                                ], 'use of reserved role name "rlink" in role {}'.format(role_oid)

                                runtime_role_id = 'rle_{}'.format(str(role.oid)[:8])
                                try:
                                    running_role = yield self._manager._session.call(
                                        'crossbarfabriccenter.remote.router.get_router_realm_role', str(node_oid),
                                        worker_name, runtime_realm_id, runtime_role_id)
                                except ApplicationError as e:
                                    if e.error != 'crossbar.error.no_such_object':
                                        # anything but "no_such_object" is unexpected (and fatal)
                                        raise
                                    self.log.info(
                                        '{func} No role {runtime_role_id} currently running for router cluster worker {worker_name}: starting role ..',
                                        func=hltype(self._apply_routercluster_placements),
                                        worker_name=hlid(worker_name),
                                        runtime_role_id=hlid(runtime_role_id))

                                    permissions = []
                                    from_key2 = (role.oid, '')
                                    to_key2 = (uuid.UUID(int=(int(role.oid) + 1)), '')
                                    for permission_oid in self._manager.schema.idx_permissions_by_uri.select(
                                            txn, from_key=from_key2, to_key=to_key2, return_keys=False):
                                        permission = self._manager.schema.permissions[txn, permission_oid]
                                        permissions.append({
                                            'uri':
                                            permission.uri,
                                            'match':
                                            Permission.MATCH_TYPES_TOSTR[permission.match]
                                            if permission.match else None,
                                            'allow': {
                                                'call': permission.allow_call or False,
                                                'register': permission.allow_register or False,
                                                'publish': permission.allow_publish or False,
                                                'subscribe': permission.allow_subscribe or False
                                            },
                                            'disclose': {
                                                'caller': permission.disclose_caller or False,
                                                'publisher': permission.disclose_publisher or False
                                            },
                                            'cache':
                                            permission.cache or False
                                        })

                                    runtime_role_config = {'name': role.name, 'permissions': permissions}

                                    role_started = yield self._manager._session.call(
                                        'crossbarfabriccenter.remote.router.start_router_realm_role', str(node_oid),
                                        worker_name, runtime_realm_id, runtime_role_id, runtime_role_config)

                                    self.log.info(
                                        '{func} Application realm role {runtime_role_id} started on router cluster worker {worker_name} [{role_started}]',
                                        func=hltype(self._apply_routercluster_placements),
                                        worker_name=hlid(worker_name),
                                        runtime_role_id=hlid(runtime_role_id),
                                        role_started=role_started)
                                else:
                                    self.log.debug(
                                        '{func} Ok, role {runtime_role_id} already running for router cluster worker {worker_name} [{running_role}].',
                                        func=hltype(self._apply_routercluster_placements),
                                        worker_name=hlid(worker_name),
                                        runtime_role_id=hlid(runtime_role_id),
                                        running_role=running_role)

                    # IV.3) if we have a running application realm by now, start router-to-router links
                    # between this worker, and every other worker in this router worker group
                    if running_arealm:
                        for other_placement in workergroup_placements:
                            other_node_oid = placement.node_oid
                            other_worker_name = other_placement.worker_name
                            assert other_node_oid
                            assert other_worker_name

                            with self._manager.gdb.begin() as txn2:
                                other_node = self._manager.gschema.nodes[txn2, other_node_oid]

                            self.log.info(
                                '{func} Rlink other node worker is on node {other_node_oid}, worker {other_worker_name}, cluster_ip {cluster_ip}:\n{other_node}',
                                other_node_oid=hlid(other_node_oid),
                                other_worker_name=hlid(other_worker_name),
                                cluster_ip=hlval(other_node.cluster_ip) if other_node else None,
                                other_node=pformat(other_node.marshal()) if other_node else None,
                                func=hltype(self._apply_routercluster_placements))
                            assert other_node

                            # don't create rlinks back to a router worker itself (only all _other_
                            # router workers in the same router worker group)
                            if other_node_oid != node_oid or other_worker_name != worker_name:
                                self.log.debug(
                                    '{func} Verifying rlink from {node_oid} / {worker_name} to {other_node_oid} / {other_worker_name} ..',
                                    func=hltype(self._apply_routercluster_placements),
                                    node_oid=hlid(node_oid),
                                    worker_name=hlid(worker_name),
                                    other_node_oid=hlid(other_node_oid),
                                    other_worker_name=hlid(other_worker_name))

                                # get run-time information for the node (as maintained here in our master view of the external world)
                                # instance of crossbar.master.mrealm.controller.Node
                                other_node_status = self._manager._session.nodes.get(str(other_node_oid), None)

                                if other_node_status and other_node_status.status == 'online':

                                    # get worker run-time information (obtained by calling into the live node)
                                    worker = None
                                    try:
                                        worker = yield self._manager._session.call(
                                            'crossbarfabriccenter.remote.node.get_worker', str(other_node_oid),
                                            other_worker_name)
                                    except ApplicationError as e:
                                        if e.error != 'crossbar.error.no_such_worker':
                                            # anything but "no_such_worker" is unexpected (and fatal)
                                            raise
                                    except:
                                        self.log.failure()
                                        raise
                                    else:
                                        self.log.debug(
                                            '{func} Ok, rlink target router worker {worker_name} is running on node {node_oid}!',
                                            func=hltype(self._check_and_apply),
                                            node_oid=hlid(other_node_oid),
                                            worker_name=hlid(other_worker_name))

                                    runtime_rlink_id = 'rlk_{}_{}_{}_{}'.format(
                                        str(arealm.oid)[:8], worker_name,
                                        str(other_node_oid)[:8], other_worker_name)
                                    running_rlink = None
                                    realm_name = arealm.name

                                    try:
                                        running_rlink = yield self._manager._session.call(
                                            'crossbarfabriccenter.remote.router.get_router_realm_link',
                                            str(other_node_oid), other_worker_name, runtime_realm_id, runtime_rlink_id)
                                    except ApplicationError as e:
                                        if e.error not in [
                                                'crossbar.error.no_such_object', 'wamp.error.no_such_procedure'
                                        ]:
                                            # anything but "no_such_object" is unexpected (and fatal)
                                            raise
                                        self.log.warn(
                                            '{func} No rlink {runtime_rlink_id} currently running for router cluster worker {worker_name}: starting rlink ..',
                                            func=hltype(self._apply_routercluster_placements),
                                            worker_name=hlid(worker_name),
                                            runtime_rlink_id=hlid(runtime_rlink_id))
                                    else:
                                        self.log.info(
                                            '{func} Ok, rlink {runtime_rlink_id} already running on router cluster worker {worker_name}',
                                            func=hltype(self._apply_routercluster_placements),
                                            worker_name=hlid(worker_name),
                                            runtime_rlink_id=hlid(runtime_rlink_id))

                                    if not running_rlink:
                                        if not other_placement.tcp_listening_port or not other_node.cluster_ip:
                                            self.log.warn(
                                                '{func} Missing rlink target cluster listening port or IP in placement (cluster_ip={cluster_ip}, tcp_listening_port={tcp_listening_port})',
                                                cluster_ip=hlval(other_node.cluster_ip),
                                                tcp_listening_port=hlval(other_placement.tcp_listening_port),
                                                func=hltype(self._check_and_apply))
                                            is_running_completely = False
                                        else:
                                            rlink_config = {
                                                'realm': realm_name,
                                                'authid': node_authid,
                                                'transport': {
                                                    'type':
                                                    'rawsocket',
                                                    'endpoint': {
                                                        'type': 'tcp',
                                                        'host': other_node.cluster_ip,
                                                        'port': other_placement.tcp_listening_port
                                                    },
                                                    'serializer':
                                                    'cbor',
                                                    'url':
                                                    'rs://{}:{}'.format(other_node.cluster_ip,
                                                                        other_placement.tcp_listening_port),
                                                },
                                                'forward_local_invocations': True,
                                                'forward_remote_invocations': False,
                                                'forward_local_events': True,
                                                'forward_remote_events': False,
                                            }
                                            rlink_started = yield self._manager._session.call(
                                                'crossbarfabriccenter.remote.router.start_router_realm_link',
                                                str(other_node_oid), other_worker_name, runtime_realm_id,
                                                runtime_rlink_id, rlink_config)

                                            running_rlink = yield self._manager._session.call(
                                                'crossbarfabriccenter.remote.router.get_router_realm_link',
                                                str(other_node_oid), other_worker_name, runtime_realm_id,
                                                runtime_rlink_id)

                                            self.log.info(
                                                '{func} Rlink {runtime_rlink_id} started on router cluster worker {worker_name}:\n{rlink_started}\n{running_rlink}',
                                                func=hltype(self._apply_routercluster_placements),
                                                rlink_started=pformat(rlink_started),
                                                running_rlink=pformat(running_rlink),
                                                worker_name=hlid(worker_name),
                                                runtime_rlink_id=hlid(runtime_rlink_id))

            else:
                if node:
                    self.log.warn('{func} Router cluster node {node_oid} not running [status={status}]',
                                  func=hltype(self._apply_routercluster_placements),
                                  node_oid=hlid(node_oid),
                                  status=hl(node.status if node else 'offline'))
                else:
                    self.log.warn('{func} Router cluster node {node_oid} from placement not found! [nodes={nodes}]',
                                  func=hltype(self._apply_routercluster_placements),
                                  node_oid=node_oid,
                                  nodes=list(self._manager._session.nodes.keys()))

                # if we are missing a node we expect, we didn't run completely successfully
                is_running_completely = False

        # if we processed everything (we expected) successfully, then return True
        returnValue(is_running_completely)


class ApplicationRealmManager(object):
    """
    Application realm manager. Application realms serve as isolated WAMP routing namespaces
    together with client authentication and authorization configuration.

    Application realms can have the following entities added:

    * application roles with permissions
    * application principals with credentials

    An application realm can be started on a router worker group run on a router cluster.
    """
    log = make_logger()

    # publication options for management API events
    _PUBOPTS = PublishOptions(acknowledge=True)

    def __init__(self,
                 session,
                 globaldb: zlmdb.Database,
                 globalschema: cfxdb.globalschema.GlobalSchema,
                 db: zlmdb.Database,
                 schema: cfxdb.mrealmschema.MrealmSchema,
                 reactor=None):
        """

        :param session: Backend of user created management realms.

        :param globaldb: Global database handle.

        :param globalschema: Global database schema.

        :param db: Management realm database handle.

        :param schema: Management realm database schema.
        """
        self._session = session

        # ContainerController
        self._worker = session.config.controller

        # node personality
        self._personality = self._worker.personality

        # twisted reactor
        self._reactor = self._worker._reactor
        # if not reactor:
        #     from twisted.internet import reactor
        # self._reactor = reactor

        # global database handle & schema

        # global (node level) database handle & schema
        self.gdb = globaldb
        self.gschema = globalschema

        # mrealm database handle & schema
        self.db = db
        self.schema = schema

        # will be set in session.register
        self._prefix = None

        # the management realm OID this manager operates for
        self._mrealm_oid = session._mrealm_oid

        # filled when started
        self._started = None

        # application realm monitors, containing a map, for every application realm in state STARTING or RUNNING
        # with objects of class ApplicationRealmMonitor
        self._monitors: Dict[uuid.UUID, ApplicationRealmMonitor] = {}

    @inlineCallbacks
    def start(self, prefix):
        assert self._started is None, 'cannot start arealm manager - already running!'
        assert self._prefix is None

        self._started = time_ns()
        # crossbarfabriccenter.mrealm.arealm
        self._prefix = prefix[:-1] if prefix.endswith('.') else prefix

        regs = yield self._session.register(self,
                                            prefix='{}.'.format(self._prefix),
                                            options=RegisterOptions(details_arg='details'))
        procs = [reg.procedure for reg in regs]
        self.log.info(
            'Mrealm controller {api} registered management procedures prefix "{prefix}" [{func}]:\n\n{procs}\n',
            api=hl('Application realm manager API', color='green', bold=True),
            func=hltype(self.start),
            prefix=hlval(self._prefix),
            procs=hl(pformat(procs), color='white', bold=True))

        # start all application realm monitors ..
        cnt_started = 0
        cnt_skipped = 0
        dl = []
        with self.db.begin() as txn:
            arealm_oids = self.schema.arealms.select(txn, return_values=False)
            for arealm_oid in arealm_oids:
                arealm = self.schema.arealms[txn, arealm_oid]
                if arealm.status in [ApplicationRealm.STATUS_STARTING, ApplicationRealm.STATUS_RUNNING]:
                    assert arealm_oid not in self._monitors
                    monitor = ApplicationRealmMonitor(self, arealm_oid)
                    dl.append(monitor.start())
                    self._monitors[arealm_oid] = monitor
                    cnt_started += 1
                    self.log.info(
                        '{func}(prefix="{prefix}"): {action} for application realm {arealm_oid} in {status})',
                        action=hl('cluster monitor started', color='green', bold=True),
                        prefix=hlval(prefix),
                        func=hltype(self.start),
                        arealm_oid=hlid(arealm_oid),
                        status=hlval(arealm.status))
                else:
                    cnt_skipped += 1
                    self.log.info(
                        '{func}(prefix="{prefix}"): {action} for application realm {arealm_oid} in status {status}',
                        action=hl('cluster monitor skipped', color='green', bold=True),
                        prefix=hlval(prefix),
                        func=hltype(self.start),
                        arealm_oid=hlid(arealm_oid),
                        status=hlval(arealm.status))
        self.log.info(
            'Application realm manager has started monitors for {cnt_started} application realms ({cnt_skipped} skipped) [{func}]',
            cnt_started=hlval(cnt_started),
            cnt_skipped=hlval(cnt_skipped),
            func=hltype(self.start))

        self.log.info('Application realm manager ready for management realm {mrealm_oid}! [{func}]',
                      mrealm_oid=hlid(self._mrealm_oid),
                      func=hltype(self.start))

        # return txaio.gather(dl)

    @inlineCallbacks
    def stop(self):
        assert self._started > 0, 'cannot stop arealm manager - currently not running!'

        # stop all application realm monitors ..
        dl = []
        for arealm_oid, arealm_monitor in self._monitors.items():
            dl.append(arealm_monitor.stop())
            del self._monitors[arealm_oid]
        self._started = None
        self.log.info(
            'Ok, application realm manager for management realm {mrealm_oid} stopped ({cnt_stopped} monitors stopped) [{func}]',
            mrealm_oid=hlid(self._mrealm_oid),
            cnt_stopped=len(dl),
            func=hltype(self.start))

        # return txaio.gather(dl)

    @wamp.register(None, check_types=True)
    def list_arealms(self, return_names: Optional[bool] = None, details: Optional[CallDetails] = None) -> List[str]:
        """
        Returns list of application realms defined. Detail information for an application realm
        can be retrieved using :meth:`crossbar.master.arealm.ApplicationRealmManager.get_arealm`.

        :param return_names: Return application realm names instead of  object IDs

        :return: List of application realm object IDs or names. For example:

            .. code-block:: json

                ["788cda65-a41d-49ae-b09a-b51967a34915",
                 "4b051f7a-1733-4784-aade-35dbdab6a234",
                 "0bb832f4-9fd0-4916-8ef1-a5799564f5fc"]
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(details={details})', func=hltype(self.list_arealms), details=details)

        with self.db.begin() as txn:
            if return_names:
                arealms = self.schema.arealms.select(txn, return_keys=False)
                if arealms:
                    return sorted([arealm.name for arealm in arealms])
                else:
                    return []
            else:
                arealm_oids = self.schema.arealms.select(txn, return_values=False)
                if arealm_oids:
                    # we now have a list of uuid.UUID objects: convert to strings
                    return [str(oid) for oid in arealm_oids]
                else:
                    return []

    @wamp.register(None, check_types=True)
    def get_arealm(self, arealm_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return configuration and run-time status information for an application realm (by object ID).

        :param arealm_oid: Object ID of the application realm to return.

        :return: Application realm definition. For example, initially, after an application
            realm has been created:

            .. code-block:: json

                {"bridge_meta_api": true,
                 "changed": null,
                 "description": null,
                 "enable_meta_api": true,
                 "label": null,
                 "name": "myrealm1",
                 "oid": "f1b58365-f936-4c4f-a820-9c5ed06eacfb",
                 "owner": null,
                 "status": "STOPPED",
                 "tags": null,
                 "webcluster_oid": null,
                 "workergroup_oid": null}

            Once the application realm has been started on a router worker group and web cluster,
            the ``status``, ``webcluster_oid`` and ``workergroup_oid`` attributes will change
            accordingly:

            .. code-block:: json

                {"bridge_meta_api": true,
                 "changed": null,
                 "description": null,
                 "enable_meta_api": true,
                 "label": null,
                 "name": "myrealm1",
                 "oid": "f1b58365-f936-4c4f-a820-9c5ed06eacfb",
                 "owner": null,
                 "status": "RUNNING",
                 "tags": null,
                 "webcluster_oid": "2f279b0f-e65a-4d7d-bef2-983f3b723e95",
                 "workergroup_oid": "74ba0f88-eb7d-4810-a901-4a6d611d7519"}

        """
        assert type(arealm_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid={arealm_oid}, details={details})',
                      func=hltype(self.get_arealm),
                      arealm_oid=hlid(arealm_oid),
                      details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid arealm_oid: {}'.format(str(e)))

        with self.db.begin() as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]

        if arealm:
            return arealm.marshal()
        else:
            raise ApplicationError('crossbar.error.no_such_object', 'no arealm with oid {}'.format(arealm_oid_))

    @wamp.register(None, check_types=True)
    def get_arealm_by_name(self, arealm_name: str, details: Optional[CallDetails] = None):
        """
        Return configuration and run-time status information for an application realm (by name).

        See also the corresponding procedure :meth:`crossbar.master.arealm.ApplicationRealmManager.get_arealm`
        which returns the same information, given and object ID rather than name.

        :param arealm_name: Name (WAMP realm) of the application realm to return.

        :return: Application realm definition.
        """
        assert type(arealm_name) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_name="{arealm_name}", details={details})',
                      func=hltype(self.get_arealm_by_name),
                      arealm_name=hlid(arealm_name),
                      details=details)

        with self.db.begin() as txn:
            arealm_oid = self.schema.idx_arealms_by_name[txn, arealm_name]
            if not arealm_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm named {}'.format(arealm_name))

            arealm = self.schema.arealms[txn, arealm_oid]
            assert arealm

        return arealm.marshal()

    @wamp.register(None, check_types=True)
    async def create_arealm(self, arealm: dict, details: Optional[CallDetails] = None) -> dict:
        """
        Create a new application realm definition.

        :procedure: ``crossbarfabriccenter.mrealm.arealm.create_arealm`` URI of WAMP procedure to call.
        :event: ``crossbarfabriccenter.mrealm.arealm.on_arealm_created`` WAMP event published once the
            application realm has been created.
        :error: ``wamp.error.invalid_configuration`` WAMP error returned when the application realm
            configuration provided has a problem.
        :error: ``wamp.error.not_authorized`` WAMP error returned when the user is currently not allowed
            to created (another) application realm.

        :param arealm: Application realm definition. For example:

            .. code-block:: json

                {
                    "name": "myrealm1",
                    "enable_meta_api": true,
                    "bridge_meta_api": true
                }

        :return: Application realm creation information.
        """
        assert type(arealm) == dict
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm="{arealm}", details={details})',
                      func=hltype(self.create_arealm),
                      arealm=arealm,
                      details=details)

        obj = ApplicationRealm.parse(arealm)

        # object ID of new application realm
        obj.oid = uuid.uuid4()

        if details and details.caller_authid:
            with self.gdb.begin() as txn:
                caller_oid = self.gschema.idx_users_by_email[txn, details.caller_authid]
                if not caller_oid:
                    raise ApplicationError('wamp.error.no_such_principal',
                                           'no user found for authid "{}"'.format(details.caller_authid))
            obj.owner_oid = caller_oid
        else:
            raise ApplicationError('wamp.error.no_such_principal', 'cannot map user - no caller authid available')

        # unless and until the application realm is started, no router worker
        # group or web cluster is assigned
        obj.workergroup_oid = None
        obj.webcluster_oid = None

        # if this arealm is federated, it is associated with a specific XBR datamarket
        if obj.datamarket_oid:
            # FIXME: check for datamarket_oid ..
            self.log.info('new application realm is associated datamarket_oid {datamarket_oid}',
                          datamarket_oid=hlid(obj.datamarket_oid))

        # set initial status of application realm
        obj.status = ApplicationRealm.STATUS_STOPPED
        obj.changed = np.datetime64(time_ns(), 'ns')

        with self.db.begin(write=True) as txn:
            self.schema.arealms[txn, obj.oid] = obj

        self.log.info('new application realm object stored in database:\n{obj}', obj=obj)

        res_obj = obj.marshal()

        await self._session.publish('{}.on_arealm_created'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_arealm_created> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    async def delete_arealm(self, arealm_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Delete an existing application realm definition.

        :procedure: ``crossbarfabriccenter.mrealm.arealm.delete_arealm`` URI of WAMP procedure to call.
        :event: ``crossbarfabriccenter.mrealm.arealm.on_arealm_deleted`` WAMP event published once the application realm has been deleted.
        :error: ``wamp.error.invalid_argument`` WAMP error returned when ``arealm_oid`` was invalid.
        :error: ``crossbar.error.no_such_object`` WAMP error returned when ``arealm_oid`` was not found.
        :error: ``crossbar.error.not_stopped`` WAMP error returned when application realm is not in status ``STOPPED``.

        :param arealm_oid: OID of the application realm to delete

        :returns: Application realm deletion information.
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid={arealm_oid}, details={details})',
                      func=hltype(self.delete_arealm),
                      arealm_oid=hlid(arealm_oid),
                      details=details)

        try:
            oid = uuid.UUID(arealm_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin(write=True) as txn:
            arealm = self.schema.arealms[txn, oid]
            if arealm:
                if arealm.status != ApplicationRealm.STATUS_STOPPED:
                    raise ApplicationError(
                        'crossbar.error.not_stopped',
                        'application realm with oid {} found, but currently in status "{}"'.format(oid, arealm.status))
                del self.schema.arealms[txn, oid]
            else:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(oid))

        self.log.info('Application realm object deleted from database:\n{arealm}', arealm=arealm)

        arealm_obj = arealm.marshal()

        await self._session.publish('{}.on_arealm_deleted'.format(self._prefix), arealm_obj, options=self._PUBOPTS)

        return arealm_obj

    @wamp.register(None, check_types=True)
    async def start_arealm(self,
                           arealm_oid: str,
                           router_workergroup_oid: str,
                           webcluster_oid: str,
                           details: Optional[CallDetails] = None) -> dict:
        """
        Start an application realm on a router cluster worker group and webcluster.

        The webcluster is responsible for accepting frontend client connections, performing
        WAMP authentication, selecting a backend router worker (from the router worker group) and
        forward application traffic of the connected frontend session to the backend router worker.

        Clients will be able to authenticate (to the frontend webcluster) using any credentials
        defined on the application realm. When a client successfully authenticates using one of the
        credentials defined, it will be identified as the principal on the application realm
        associated with the credential.

        A principal in turn will have an associated role defined, and the permissions on that role
        ultimately then determine the rights granted to the client to perform respective WAMP actions
        (eg call "com.example.add2" or subscribe "com.example.onevent1") on URIs within the
        application realm.

        The application realm monitor will take care of:

        1. start the application realm on all router workers on nodes of the respective router worker group
        2. start all roles defined for the application realm on those router workers
        3. start router-to-router links between the router workers in the router worker group for the respective application realm
        4. start backend connections and routes to the router workers from the proxy workers of the webcluster
        5. configure credentials for the principals on the application realm in the proxy workers of the webcluster

        :param arealm_oid: The application realm to start.
        :param router_workergroup_oid: The router cluster worker group to start the application realm on.
        :param webcluster_oid: The web cluster to serve as a frontend layer for the application realm.

        :return: Application realm start information.
        """
        self.log.info(
            '{func}(arealm_oid="{arealm_oid}", router_workergroup_oid="{router_workergroup_oid}", details={details})',
            func=hltype(self.start_arealm),
            arealm_oid=hlid(arealm_oid),
            router_workergroup_oid=hlid(router_workergroup_oid),
            details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid arealm_oid "{}"'.format(arealm_oid))

        try:
            router_workergroup_oid_ = uuid.UUID(router_workergroup_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument',
                                   'invalid workergroup_oid "{}"'.format(router_workergroup_oid))

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid webcluster_oid "{}"'.format(webcluster_oid))

        with self.db.begin(write=True) as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(arealm_oid_))

            router_workergroup = self.schema.router_workergroups[txn, router_workergroup_oid_]
            if not router_workergroup:
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no router cluster worker group with oid {} found'.format(router_workergroup_oid_))

            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no webcluster with oid {} found'.format(webcluster_oid_))

            if arealm.status not in [cfxdb.mrealm.types.STATUS_STOPPED, cfxdb.mrealm.types.STATUS_PAUSED]:
                emsg = 'cannot start arealm currently in state {}'.format(
                    cfxdb.mrealm.types.STATUS_BY_CODE[arealm.status])
                raise ApplicationError('crossbar.error.cannot_start', emsg)

            arealm.status = cfxdb.mrealm.types.STATUS_STARTING
            arealm.workergroup_oid = router_workergroup_oid_
            arealm.webcluster_oid = webcluster_oid_
            arealm.changed = np.datetime64(time_ns(), 'ns')

            self.schema.arealms[txn, arealm_oid_] = arealm

        assert arealm_oid not in self._monitors
        monitor = ApplicationRealmMonitor(self, arealm_oid_)
        monitor.start()
        self._monitors[arealm_oid_] = monitor

        arealm_starting = {
            'oid': str(arealm.oid),
            'status': cfxdb.mrealm.types.STATUS_BY_CODE[arealm.status],
            'router_workergroup_oid': str(router_workergroup_oid_),
            'changed': int(arealm.changed) if arealm.changed else None,
            'who': {
                'session': details.caller if details else None,
                'authid': details.caller_authid if details else None,
                'authrole': details.caller_authrole if details else None,
            }
        }
        await self._session.publish('{}.on_arealm_starting'.format(self._prefix),
                                    arealm_starting,
                                    options=self._PUBOPTS)

        return arealm_starting

    @wamp.register(None, check_types=True)
    async def stop_arealm(self, arealm_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Stop a currently running application realm. This will stop router workers started
        in the worker group assigned for the application realm, and remove the association
        with the proxy workers of the web cluster responsible for the application realm.

        :event: ``crossbarfabriccenter.mrealm.arealm.on_arealm_stopping`` WAMP event published once the application realm is stopping.
        :error: ``wamp.error.invalid_argument`` WAMP error returned when ``arealm_oid`` was invalid.
        :error: ``crossbar.error.no_such_object`` WAMP error returned when ``arealm_oid`` was not found.
        :error: ``crossbar.error.cannot_stop`` WAMP error returned when application realm cannot be stopped,
            because it is not in status ``RUNNING`` or ``STARTING``.

        :param arealm_oid: The application realm to stop.

        :return: Application realm stopping information.
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid={arealm_oid}, details={details})',
                      arealm_oid=hlid(arealm_oid),
                      func=hltype(self.stop_arealm),
                      details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin(write=True) as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(arealm_oid_))

            if arealm.status not in [cfxdb.mrealm.types.STATUS_STARTING, cfxdb.mrealm.types.STATUS_RUNNING]:
                emsg = 'cannot stop arealm currently in state {}'.format(
                    cfxdb.mrealm.types.STATUS_BY_CODE[arealm.status])
                raise ApplicationError('crossbar.error.cannot_stop', emsg)

            arealm.status = cfxdb.mrealm.types.STATUS_STOPPING
            arealm.changed = np.datetime64(time_ns(), 'ns')

            self.schema.arealms[txn, arealm_oid_] = arealm

        arealm_stopping = {
            'oid': str(arealm.oid),
            'status': cfxdb.mrealm.types.STATUS_BY_CODE[arealm.status],
            'changed': arealm.changed,
            'who': {
                'session': details.caller if details else None,
                'authid': details.caller_authid if details else None,
                'authrole': details.caller_authrole if details else None,
            }
        }

        await self._session.publish('{}.on_arealm_stopping'.format(self._prefix),
                                    arealm_stopping,
                                    options=self._PUBOPTS)

        return arealm_stopping

    @wamp.register(None, check_types=True)
    def stat_arealm(self, arealm_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        *NOT YET IMPLEMENTED*

        Get current status and statistics for given application realm.

        :param arealm_oid: The application realm to return status and statistics for.

        :return: Current status and statistics for given routercluster.
        """
        assert type(arealm_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid={arealm_oid}, details={details})',
                      func=hltype(self.stat_arealm),
                      arealm_oid=hlid(arealm_oid),
                      details=details)

        raise NotImplementedError()

    @wamp.register(None, check_types=True)
    def list_router_workers(self, arealm_oid: str, details: Optional[CallDetails] = None) -> List[str]:
        """
        *NOT YET IMPLEMENTED*

        When an application realm has been started on a router workergroup and is running,
        the list of router workers (in the router worker group) the application realm
        is hosted on.

        :param arealm_oid: Object ID of application realm to list router workers for.

        :return: List of router workers in the router worker group running the application realm.
        """
        raise NotImplementedError()

    @wamp.register(None, check_types=True)
    def list_principals(self,
                        arealm_oid: str,
                        return_names: Optional[bool] = None,
                        details: Optional[CallDetails] = None) -> List[str]:
        """
        List all principals defined on this application realm.

        :param arealm_oid: Object ID of application realm to list principals for.
        :param return_names: Return principal names (WAMP authids) rather than object IDs.

        :return: List of principal object IDs or names.
        """
        assert type(arealm_oid) == str
        assert return_names is None or type(return_names) == bool
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid={arealm_oid}, details={details})',
                      func=hltype(self.list_principals),
                      arealm_oid=hlid(arealm_oid),
                      details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(arealm_oid))

        with self.db.begin() as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(arealm_oid_))

            if return_names:
                res = []
                for _, principal_name in self.schema.idx_principals_by_name.select(
                        txn,
                        from_key=(arealm_oid_, ''),
                        to_key=(uuid.UUID(int=(int(arealm_oid_) + 1)), ''),
                        return_values=False):
                    res.append(principal_name)
                return sorted(res)
            else:
                res = []
                for principal_oid in self.schema.idx_principals_by_name.select(
                        txn,
                        from_key=(arealm_oid_, ''),
                        to_key=(uuid.UUID(int=(int(arealm_oid_) + 1)), ''),
                        return_keys=False):
                    res.append(str(principal_oid))
                return res

    @wamp.register(None, check_types=True)
    def get_principal(self, arealm_oid: str, principal_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return definition of principal.

        :param arealm_oid: Object ID of application realm the principal is defined on.
        :param principal_oid: Object ID of the principal to return.

        :return: Principal definition.
        """
        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(arealm_oid))

        try:
            principal_oid_ = uuid.UUID(principal_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(principal_oid))

        with self.db.begin() as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(arealm_oid_))

            principal = self.schema.principals[txn, principal_oid_]
            if not principal or principal.arealm_oid != arealm_oid_:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no principal with oid {} found in application realm'.format(principal_oid_))

        obj = principal.marshal()
        return obj

    @wamp.register(None, check_types=True)
    def get_principal_by_name(self, arealm_oid: str, principal_name: str, details: Optional[CallDetails] = None):
        """
        Return definition of principal by principal name (WAMP authid).

        :param arealm_oid: Object ID of application realm the principal is defined on.
        :param principal_oid: Object ID of the principal to return.

        :return: Principal definition.
        """
        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(arealm_oid))

        with self.db.begin() as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(arealm_oid_))

            principal_oid = self.schema.idx_principals_by_name[txn, (arealm_oid_, principal_name)]
            if not principal_oid:
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no principal with name (authid) "{}" found in application realm'.format(principal_name))

            principal = self.schema.principals[txn, principal_oid]
            if not principal or principal.arealm_oid != arealm_oid_:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no principal with oid {} found in application realm'.format(principal_oid))

        obj = principal.marshal()
        return obj

    @wamp.register(None, check_types=True)
    async def add_principal(self, arealm_oid: str, principal: dict, details: Optional[CallDetails] = None) -> dict:
        """
        Add a new principal to the given application realm.

        :param arealm_oid: Object ID of application realm to add the principal to.
        :param principal: Principal definition.

        :return: Principal addition information.
        """
        assert type(principal) == dict
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid="{arealm_oid}", principal={principal}, details={details})',
                      func=hltype(self.add_principal),
                      arealm_oid=hlid(arealm_oid),
                      principal=principal,
                      details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(arealm_oid))

        role_oid = principal.get('role_oid', None)
        assert role_oid is not None and type(role_oid) == str
        try:
            role_oid_ = uuid.UUID(role_oid)
        except:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(role_oid))

        try:
            obj = Principal.parse(principal)
        except Exception as e:
            raise ApplicationError('crossbar.error.invalid_config', 'invalid configuration. {}'.format(e))

        obj.oid = uuid.uuid4()
        obj.modified = np.datetime64(time_ns(), 'ns')
        obj.arealm_oid = arealm_oid_
        obj.role_oid = role_oid_

        with self.db.begin(write=True) as txn:
            arealm = self.schema.arealms[txn, obj.arealm_oid]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(obj.arealm_oid))

            role = self.schema.roles[txn, obj.role_oid]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object', 'no role with oid {} found'.format(role_oid_))
            principal_oid = self.schema.idx_principals_by_name[txn, (obj.arealm_oid, obj.authid)]
            if principal_oid:
                raise ApplicationError(
                    'crossbar.error.already_exists',
                    'principal with name (authid) "{}" already exist in application realm'.format(obj.authid))

            self.schema.principals[txn, obj.oid] = obj

        self.log.info('new principal object stored in database:\n{obj}', obj=obj)

        res_obj = obj.marshal()

        await self._session.publish('{}.on_principal_created'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_principal_created> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    def remove_principal(self, arealm_oid: str, principal_oid: str, details: Optional[CallDetails] = None):
        """
        Remove a principal from the given application realm.

        :param arealm_oid: Object ID of application realm from which to remove the principal.
        :param principal_oid: Object ID of the principal to remove.

        :return: Principal removal information.
        """
        raise NotImplementedError()

    @wamp.register(None, check_types=True)
    def list_principal_credentials(self,
                                   arealm_oid: str,
                                   principal_oid: str,
                                   details: Optional[CallDetails] = None) -> List[str]:
        """
        List credentials for a principal.

        :param arealm_oid: Object ID of application realm of the principal to list credentials for.
        :param principal_oid: Object ID of the principal to list credentials for.

        :return: List of credential object IDs or names (WAMP authids).
        """
        assert type(arealm_oid) == str
        assert type(principal_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid={arealm_oid}, principal_oid={principal_oid}, details={details})',
                      func=hltype(self.list_principal_credentials),
                      arealm_oid=hlid(arealm_oid),
                      principal_oid=hlid(principal_oid),
                      details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid arealm_oid "{}"'.format(arealm_oid))

        try:
            principal_oid_ = uuid.UUID(principal_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid principal_oid "{}"'.format(principal_oid))

        with self.db.begin() as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(arealm_oid_))

            principal = self.schema.principals[txn, principal_oid_]
            if not principal or principal.arealm_oid != arealm_oid_:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no principal with oid {} found in application realm'.format(principal_oid_))

            res = []
            for credential_oid in self.schema.idx_credentials_by_principal.select(
                    txn,
                    from_key=(principal_oid_, np.datetime64(0, 'ns')),
                    to_key=(uuid.UUID(int=(int(principal_oid_) + 1)), np.datetime64(0, 'ns')),
                    return_keys=False):
                res.append(str(credential_oid))
            return res

    @wamp.register(None, check_types=True)
    def get_principal_credential(self,
                                 arealm_oid: str,
                                 principal_oid: str,
                                 credential_oid: str,
                                 details: Optional[CallDetails] = None) -> dict:
        """
        Return definition of a credential of a principal.

        :param arealm_oid: Object ID of application realm of the principal to return a credential for.
        :param principal_oid: Object ID of the principal to get a credentials for.
        :param credential_oid: Object ID of the credential to return.

        :return: Credential detail information.
        """
        raise NotImplementedError()

    @wamp.register(None, check_types=True)
    def add_principal_credential(self,
                                 arealm_oid: str,
                                 principal_oid: str,
                                 credential: dict,
                                 details: Optional[CallDetails] = None) -> dict:
        """
        Add credentials to a principal.

        :param arealm_oid: Object ID of application realm of the principal to add a credential for.
        :param principal_oid: Object ID of the principal to add a credentials for.
        :param credential: Credential configuration. Examples:

            **WAMP-anonymous:**

            .. code-block:: json

                {
                    "authmethod": "anonymous"
                }

            **WAMP-ticket:**

            .. code-block:: json

                {
                    "authmethod": "ticket",
                    "secret": "secret123"
                }

            **WAMP-wampcra:**

            .. code-block:: json

                {
                    "authmethod": "wampcra",
                    "secret": "secret123",
                    "salt": "salt456",
                    "iterations": 100,
                    "keylen": 16
                }

            **WAMP-scram:**

            .. code-block:: json

                {
                    "authmethod": "scram",
                    "kdf": "pbkdf2",
                    "iterations": 100,
                    "memory": 0,
                    "stored-key": "",
                    "server-key": ""
                }

            **WAMP-cryptosign:**

            .. code-block:: json

                {
                    "authmethod": "cryptosign",
                    "authconfig": {
                        "authorized_keys": [
                            "92b450bb5fb168b396ad2bde633825662665b4cb73c1243ce5e834971c9354f5"
                        ]
                    }
                }

            **WAMP-tls:** *NOT YET IMPLEMENTED*

            .. code-block:: json

                {
                    "authmethod": "tls"
                }

            **WAMP-cookie:** *NOT YET IMPLEMENTED*

            .. code-block:: json

                {
                    "authmethod": "cookie"
                }

        :return: Credential addition information.
        """
        self.log.info(
            '{func}(arealm_oid="{arealm_oid}", principal_oid="{principal_oid}", credential={credential}, details={details})',
            func=hltype(self.add_principal_credential),
            arealm_oid=hlid(arealm_oid),
            principal_oid=hlid(principal_oid),
            credential=pformat(credential),
            details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid arealm_oid "{}"'.format(arealm_oid))

        try:
            principal_oid_ = uuid.UUID(principal_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid principal_oid "{}"'.format(principal_oid))

        with self.db.begin(write=True) as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(arealm_oid_))

            principal = self.schema.principals[txn, principal_oid_]
            if not principal or principal.arealm_oid != arealm_oid_:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no principal with oid {} found in application realm'.format(principal_oid_))

            try:
                credential_ = Credential.parse(credential)
            except Exception as e:
                raise ApplicationError('crossbar.error.invalid_config', 'invalid configuration. {}'.format(e))

            credential_.oid = uuid.uuid4()
            credential_.created = np.datetime64(time_ns(), 'ns')
            credential_.realm = arealm.name
            credential_.authid = principal.authid
            credential_.principal_oid = principal_oid_

            if self.schema.idx_credentials_by_auth[txn,
                                                   (credential_.authmethod, credential_.realm, credential_.authid)]:
                raise ApplicationError(
                    'crossbar.error.already_running',
                    'duplicate credential for authmethod "{}", realm "{}" and authid "{}" in application realm'.format(
                        credential_.authmethod, credential_.realm, credential_.authid))

            self.schema.credentials[txn, credential_.oid] = credential_

        return credential_.marshal()

    @wamp.register(None, check_types=True)
    def remove_principal_credential(self,
                                    arealm_oid: str,
                                    principal_oid: str,
                                    credential_oid: str,
                                    details: Optional[CallDetails] = None) -> dict:
        """
        Remove credentials from a principal.

        :param arealm_oid: Object ID of application realm of the principal to remove a credential from.
        :param principal_oid: Object ID of the principal to remove a credentials from.
        :param credential_oid: Object ID of the credential to remove.

        :return: Credential removal information.
        """
        raise NotImplementedError()

    @wamp.register(None, check_types=True)
    def list_roles(self, return_names: Optional[bool] = None, details: Optional[CallDetails] = None) -> List[str]:
        """
        Returns list of roles defined.

        :param return_names: Return roles names instead of  object IDs

        :return: List of role object IDs or names.
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(return_names={return_names}, details={details})',
                      func=hltype(self.list_roles),
                      return_names=hlval(return_names),
                      details=details)

        with self.db.begin() as txn:
            if return_names:
                roles = self.schema.roles.select(txn, return_keys=False)
                if roles:
                    return sorted([role.name for role in roles])
                else:
                    return []
            else:
                role_oids = self.schema.roles.select(txn, return_values=False)
                if role_oids:
                    # we now have a list of uuid.UUID objects: convert to strings
                    return [str(oid) for oid in role_oids]
                else:
                    return []

    @wamp.register(None, check_types=True)
    def get_role(self, role_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return configuration information for a role.

        :param role_oid: Object ID of the role to return.

        :return: Role definition.
        """
        assert type(role_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(role_oid={role_oid}, details={details})',
                      func=hltype(self.get_role),
                      role_oid=hlid(role_oid),
                      details=details)

        try:
            role_oid_ = uuid.UUID(role_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid role_oid: {}'.format(str(e)))

        with self.db.begin() as txn:
            role = self.schema.roles[txn, role_oid_]

        if role:
            return role.marshal()
        else:
            raise ApplicationError('crossbar.error.no_such_object', 'no role with oid {}'.format(role_oid_))

    @wamp.register(None, check_types=True)
    def get_role_by_name(self, role_name: str, details: Optional[CallDetails] = None):
        """
        Return configuration information for a role given by name.

        :param role_name: The name of the role to return the definition for.

        :return: Role definition.
        """
        assert type(role_name) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(role_name="{role_name}", details={details})',
                      func=hltype(self.get_role_by_name),
                      role_name=hlid(role_name),
                      details=details)

        with self.db.begin() as txn:
            role_oid = self.schema.idx_roles_by_name[txn, role_name]
            if not role_oid:
                raise ApplicationError('crossbar.error.no_such_object', 'no role named "{}"'.format(role_name))

            role = self.schema.roles[txn, role_oid]
            assert role

        return role.marshal()

    @wamp.register(None, check_types=True)
    async def create_role(self, role: dict, details: Optional[CallDetails] = None) -> dict:
        """
        Create a new Role definition.

        :param role: Role definition.

        :return: Role creation information.
        """
        assert type(role) == dict
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(role="{role}", details={details})',
                      func=hltype(self.create_role),
                      role=role,
                      details=details)

        obj = Role.parse(role)
        obj.oid = uuid.uuid4()
        obj.created = np.datetime64(time_ns(), 'ns')

        with self.db.begin(write=True) as txn:
            self.schema.roles[txn, obj.oid] = obj

        self.log.info('new role object stored in database:\n{obj}', obj=obj)

        res_obj = obj.marshal()

        await self._session.publish('{}.on_role_created'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_role_created> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    async def delete_role(self, role_oid: str, details: Optional[CallDetails] = None):
        """
        Delete an existing Role definition.

        :procedure: ``crossbarfabriccenter.mrealm.arealm.delete_role``
        :event: ``crossbarfabriccenter.mrealm.arealm.on_role_deleted``
        :error: ``wamp.error.invalid_argument``
        :error: ``crossbar.error.no_such_object``

        :param role_oid: OID of the Role to delete

        :returns: Role deletin information.
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(role_oid={role_oid}, details={details})',
                      func=hltype(self.delete_role),
                      role_oid=hlid(role_oid),
                      details=details)

        try:
            oid = uuid.UUID(role_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin(write=True) as txn:
            obj = self.schema.roles[txn, oid]
            if obj:
                del self.schema.roles[txn, oid]
            else:
                raise ApplicationError('crossbar.error.no_such_object', 'no object with oid {} found'.format(oid))

        self.log.info('Role object deleted from database:\n{obj}', obj=obj)

        res_obj = obj.marshal()

        await self._session.publish('{}.on_role_deleted'.format(self._prefix), res_obj, options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    def list_role_permissions(self,
                              role_oid: str,
                              prefix: Optional[str] = None,
                              details: Optional[CallDetails] = None) -> List[str]:
        """
        List permissions in a role.

        :param role_oid: The role to get permissions for.
        :param prefix: WAMP URI prefix of permission to filter for.

        :return: List of permissions object IDs of this role.
        """
        self.log.info('{func}(role_oid={role_oid}, prefix="{prefix}", details={details})',
                      func=hltype(self.list_role_permissions),
                      role_oid=hlid(role_oid),
                      prefix=hlval(prefix),
                      details=details)

        try:
            role_oid_ = uuid.UUID(role_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid role_oid "{}"'.format(role_oid_))

        with self.db.begin() as txn:
            role = self.schema.roles[txn, role_oid_]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object', 'no role with oid {} found'.format(role_oid_))

            res = []
            from_key = (role_oid_, prefix if prefix else '')
            to_key = (uuid.UUID(int=(int(role_oid_) + 1)), '')
            for permission_oid in self.schema.idx_permissions_by_uri.select(txn,
                                                                            from_key=from_key,
                                                                            to_key=to_key,
                                                                            return_keys=False):
                res.append(str(permission_oid))

        return res

    @wamp.register(None, check_types=True)
    async def add_role_permission(self,
                                  role_oid: str,
                                  uri: str,
                                  permission: dict,
                                  details: Optional[CallDetails] = None) -> dict:
        """
        Add a permission to a role.

        :param arealm_oid: OID of the application realm to which to add the role permission.
        :param uri: WAMP URI (pattern) of the permission to add.
        :param permission: Permission definition

        :return: Permission addition information.
        """
        assert details is None or isinstance(details, CallDetails)

        try:
            role_oid_ = uuid.UUID(role_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid role_oid "{}"'.format(role_oid))

        self.log.info('{func}(role_oid={role_oid}, uri="{uri}", permission={permission}, details={details})',
                      func=hltype(self.add_role_permission),
                      role_oid=hlid(role_oid_),
                      uri=hlval(uri),
                      permission=permission,
                      details=details)

        role_permission = Permission.parse(permission)
        role_permission.oid = uuid.uuid4()
        role_permission.role_oid = role_oid_
        role_permission.uri = uri

        with self.db.begin(write=True) as txn:
            role = self.schema.roles[txn, role_permission.role_oid]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(role_permission.role_oid))

            self.schema.permissions[txn, role_permission.oid] = role_permission

        res_obj = role_permission.marshal()
        self.log.info('role added to permission:\n{permission}', permission=res_obj)

        await self._session.publish('{}.on_permission_added'.format(self._prefix), res_obj, options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    async def remove_role_permission(self,
                                     role_oid: str,
                                     permission_oid: str,
                                     details: Optional[CallDetails] = None) -> dict:
        """
        Remove a permission from a role.

        :param role_oid: Object ID of the role from which to remove the permission.
        :param permission_oid: Object ID of the permission to remove.

        :return: Permission removal information.
        """
        assert type(role_oid) == str
        assert type(permission_oid) == str
        assert details is None or isinstance(details, CallDetails)

        try:
            role_oid_ = uuid.UUID(role_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid role_oid "{}"'.format(role_oid))

        try:
            permission_oid_ = uuid.UUID(permission_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid permission_oid "{}"'.format(permission_oid))

        self.log.info('{func}(role_oid={role_oid}, permission_oid={permission_oid}, details={details})',
                      role_oid=hlid(role_oid_),
                      permission_oid=hlid(permission_oid_),
                      func=hltype(self.remove_role_permission),
                      details=details)

        with self.db.begin(write=True) as txn:
            role = self.schema.roles[txn, role_oid_]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object', 'no role with oid {} found'.format(role_oid_))

            role_permission = self.schema.permissions[txn, permission_oid_]
            del self.schema.permissions[txn, permission_oid_]

        res_obj = role_permission.marshal()
        self.log.info('role removed from arealm:\n{res_obj}', membership=res_obj)

        await self._session.publish('{}.on_arealm_role_removed'.format(self._prefix), res_obj, options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    def get_role_permission(self, role_oid: str, permission_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Get information for the permission on a role.

        :param role_oid: Object ID of the role to retrieve the permission for.
        :param permission_oid: Object ID of the permission to retrieve.

        :return: Permission definition.
        """
        assert type(role_oid) == str
        assert type(permission_oid) == str
        assert details is None or isinstance(details, CallDetails)

        try:
            role_oid_ = uuid.UUID(role_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid role_oid "{}"'.format(role_oid))

        try:
            permission_oid_ = uuid.UUID(permission_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid permission_oid "{}"'.format(permission_oid))

        self.log.info('{func}(role_oid={role_oid}, permission_oid={permission_oid}, details={details})',
                      role_oid=hlid(role_oid),
                      permission_oid=hlid(permission_oid),
                      func=hltype(self.get_role_permission),
                      details=details)

        with self.db.begin() as txn:
            role = self.schema.roles[txn, role_oid_]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object', 'no role with oid {} found'.format(role_oid_))

            permission = self.schema.permissions[txn, permission_oid_]
            if not permission:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no arealm permission oid {} found'.format(permission_oid_))

        res_obj = permission.marshal()

        return res_obj

    @wamp.register(None, check_types=True)
    def get_role_permissions_by_uri(self,
                                    role_oid: str,
                                    prefix: Optional[str] = None,
                                    details: Optional[CallDetails] = None) -> List[Dict]:
        """
        Get information for the permission on a role.

        :param role_oid: Object ID of the role to retrieve the permission for.
        :param permission_oid: Object ID of the permission to retrieve.

        :return: Permission definition.
        """
        self.log.info('{func}(role_oid={role_oid}, prefix={prefix}, details={details})',
                      role_oid=hlid(role_oid),
                      prefix=hlval(prefix),
                      func=hltype(self.get_role_permission),
                      details=details)

        try:
            role_oid_ = uuid.UUID(role_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid role_oid "{}"'.format(role_oid))

        with self.db.begin() as txn:
            role = self.schema.roles[txn, role_oid_]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object', 'no role with oid {} found'.format(role_oid_))

            res = []
            from_key = (role_oid_, prefix if prefix else '')
            to_key = (uuid.UUID(int=(int(role_oid_) + 1)), '')
            for permission_oid in self.schema.idx_permissions_by_uri.select(txn,
                                                                            from_key=from_key,
                                                                            to_key=to_key,
                                                                            return_keys=False):
                permission = self.schema.permissions[txn, permission_oid]
                res.append(permission.marshal())

        return res

    @wamp.register(None, check_types=True)
    def list_arealm_roles(self,
                          arealm_oid: str,
                          return_names: Optional[bool] = None,
                          details: Optional[CallDetails] = None) -> List[str]:
        """
        List roles currently associated with the given application realm.

        :param arealm_oid: The application realm to list roles for.

        :return: List of role object IDs of roles associated with the application realm.
        """
        self.log.info('{func}(arealm_oid={arealm_oid}, return_names={return_names}, details={details})',
                      func=hltype(self.list_arealm_roles),
                      arealm_oid=hlid(arealm_oid),
                      return_names=return_names,
                      details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(arealm_oid))

        with self.db.begin() as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(arealm_oid_))

            res = []
            for _, role_oid in self.schema.arealm_role_associations.select(txn,
                                                                           from_key=(arealm_oid_,
                                                                                     uuid.UUID(bytes=b'\x00' * 16)),
                                                                           to_key=(arealm_oid_,
                                                                                   uuid.UUID(bytes=b'\xff' * 16)),
                                                                           return_values=False):
                if return_names:
                    role = self.schema.roles[txn, role_oid]
                    res.append(role.name)
                else:
                    res.append(str(role_oid))
            return res

    @wamp.register(None, check_types=True)
    async def add_arealm_role(self,
                              arealm_oid: str,
                              role_oid: str,
                              config: Optional[dict] = None,
                              details: Optional[CallDetails] = None) -> dict:
        """
        Add a role to an application realm.

        :param arealm_oid: OID of the application realm to which to add the role.
        :param role_oid: OID of the role to add to the application realm.
            A role can be added to more than one application realm.
        :param config:

        :return:
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid={arealm_oid}, role_oid={role_oid}, config={config}, details={details})',
                      func=hltype(self.add_arealm_role),
                      arealm_oid=hlid(arealm_oid),
                      role_oid=hlid(role_oid),
                      config=config,
                      details=details)

        config = config or {}
        config['arealm_oid'] = arealm_oid
        config['role_oid'] = role_oid
        association = ApplicationRealmRoleAssociation.parse(config)

        with self.db.begin(write=True) as txn:
            arealm = self.schema.arealms[txn, association.arealm_oid]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no application realm with oid {} found'.format(association.arealm_oid))

            role = self.schema.roles[txn, association.role_oid]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no role with oid {} found'.format(association.role_oid))

            self.schema.arealm_role_associations[txn, (association.arealm_oid, association.role_oid)] = association

        res_obj = association.marshal()
        self.log.info('role added to application realm:\n{association}', association=res_obj)

        await self._session.publish('{}.on_arealm_role_added'.format(self._prefix), res_obj, options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    async def remove_arealm_role(self, arealm_oid: str, role_oid: str, details: Optional[CallDetails] = None):
        """
        Remove a role from an application realm.

        :param arealm_oid: Object ID of the application realm to remove the role from.
        :param role_oid: Object ID of the role to remove from the application realm.

        :return: Application realm role removal information.
        """
        assert type(arealm_oid) == str
        assert type(role_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(arealm_oid={arealm_oid}, role_oid={role_oid}, details={details})',
                      arealm_oid=hlid(arealm_oid),
                      role_oid=hlid(role_oid),
                      func=hltype(self.remove_arealm_role),
                      details=details)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(arealm_oid))

        try:
            role_oid_ = uuid.UUID(role_oid)
        except Exception:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(role_oid))

        with self.db.begin(write=True) as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no arealm with oid {} found'.format(arealm_oid_))

            role = self.schema.roles[txn, role_oid_]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object', 'no role with oid {} found'.format(role_oid_))

            arealm_role_association = self.schema.arealm_role_associations[txn, (arealm_oid_, role_oid_)]
            if not arealm_role_association:
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no role association for (arealm_oid={}, role_oid={}) found'.format(arealm_oid_, role_oid_))

            del self.schema.arealm_role_associations[txn, (arealm_oid_, role_oid_)]

        res_obj = arealm_role_association.marshal()
        self.log.info('role removed from arealm:\n{res_obj}', membership=res_obj)

        await self._session.publish('{}.on_arealm_role_removed'.format(self._prefix), res_obj, options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    def get_arealm_role(self, arealm_oid: str, role_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Get information for the association of a role with an application realm.

        :param arealm_oid: The application realm for which to return the association for.
        :param role_oid: The role for which to return the association for.

        :return: Application realm role association removal information.
        """
        assert type(arealm_oid) == str
        assert type(role_oid) == str
        assert details is None or isinstance(details, CallDetails)

        try:
            arealm_oid_ = uuid.UUID(arealm_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid arealm_oid "{}"'.format(str(e)))

        try:
            role_oid_ = uuid.UUID(role_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid role_oid "{}"'.format(str(e)))

        self.log.info('{func}(arealm_oid={arealm_oid}, role_oid={role_oid}, details={details})',
                      arealm_oid=hlid(arealm_oid_),
                      role_oid=hlid(role_oid_),
                      func=hltype(self.get_arealm_role),
                      details=details)

        with self.db.begin() as txn:
            arealm = self.schema.arealms[txn, arealm_oid_]
            if not arealm:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no arealm with oid {} found'.format(arealm_oid_))

            role = self.schema.roles[txn, role_oid_]
            if not role:
                raise ApplicationError('crossbar.error.no_such_object', 'no role with oid {} found'.format(role_oid_))

            association = self.schema.arealm_role_associations[txn, (arealm_oid_, role_oid_)]
            if not association:
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no association between role {} and arealm {} found'.format(arealm_oid, role_oid_))

        res_obj = association.marshal()

        return res_obj
