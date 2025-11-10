###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import uuid
from typing import Optional, List
from pprint import pformat

import numpy as np
from sortedcontainers import SortedDict

from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import CallDetails, PublishOptions, RegisterOptions

from crossbar.common import checkconfig
from crossbar._util import hl, hlid, hltype, hlval
from cfxdb.mrealm import RouterCluster, RouterClusterNodeMembership, RouterWorkerGroupClusterPlacement
from cfxdb.mrealm import cluster, RouterWorkerGroup, WorkerGroupStatus

import txaio

txaio.use_twisted()
from txaio import time_ns, sleep, make_logger  # noqa
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall


class RouterClusterMonitor(object):
    """
    Background monitor running periodically in the master node to monitor, check and apply
    necessary actions for router clusters.

    The monitor is started when a router cluster is started.
    """
    log = make_logger()

    def __init__(self, manager, routercluster_oid, interval=10.):
        self._manager = manager
        self._routercluster_oid = routercluster_oid
        self._interval = interval

        self._loop = None
        self._check_and_apply_in_progress = False

    @property
    def is_started(self):
        """

        :return:
        """
        return self._loop is not None and self._loop.running

    def start(self):
        """

        :return:
        """
        assert self._loop is None

        def _check_and_apply_wrapper():
            """Wrapper to add errback for error handling"""
            d = self._check_and_apply()
            d.addErrback(self._handle_check_and_apply_error)
            return d

        self._loop = LoopingCall(_check_and_apply_wrapper)
        self._loop.start(self._interval)

    def _handle_check_and_apply_error(self, failure):
        """
        Handle any unhandled errors from _check_and_apply to ensure the flag is reset.
        """
        self.log.failure(
            '{func} Unhandled error in check & apply for routercluster {routercluster} - will retry in next iteration',
            func=hltype(self._check_and_apply),
            routercluster=hlid(self._routercluster_oid),
            failure=failure)
        # Always reset the flag so next iteration can run
        self._check_and_apply_in_progress = False

    def stop(self):
        """

        :return:
        """
        assert self._loop is not None

        self._loop.stop()
        self._loop = None
        self._check_and_apply_in_progress = False

    @inlineCallbacks
    def _check_and_apply(self):
        if self._check_and_apply_in_progress:
            # we prohibit running the iteration multiple times concurrently. this might
            # happen when the iteration takes longer than the interval the monitor is set to
            self.log.warn(
                '{func} {action} for routercluster {routercluster} skipped! check & apply already in progress.',
                action=hl('check & apply run skipped', color='red', bold=True),
                func=hltype(self._check_and_apply),
                routercluster=hlid(self._routercluster_oid))
            return
        else:
            self.log.info('{func} {action} for routercluster {routercluster} ..',
                          action=hl('check & apply run started', color='green', bold=True),
                          func=hltype(self._check_and_apply),
                          routercluster=hlid(self._routercluster_oid))
            self._check_and_apply_in_progress = True

        is_running_completely = True
        try:
            # get all active (non-standby) nodes added to the routercluster
            active_memberships = []
            with self._manager.db.begin(write=False) as txn:
                # the routercluster itself
                routercluster = self._manager.schema.routerclusters[txn, self._routercluster_oid]

                if routercluster.status in [cluster.STATUS_STARTING, cluster.STATUS_RUNNING]:
                    # the node memberships in the routercluster
                    active_memberships = [
                        m for m in self._manager.schema.routercluster_node_memberships.select(
                            txn, from_key=(routercluster.oid, uuid.UUID(bytes=b'\0' * 16)), return_keys=False)
                    ]

            for membership in active_memberships:
                node_oid = str(membership.node_oid)

                # node run-time information, as maintained here in our master view of the external world
                node = self._manager._session.nodes.get(node_oid, None)

                if node and node.status == 'online':
                    self.log.info('{func} Ok, router cluster node {node_oid} is running!',
                                  func=hltype(self._check_and_apply),
                                  node_oid=hlid(node_oid))

                    # FIXME: check all workers we expect for data planes associated with this router cluster are running

                else:
                    self.log.warn('{func} Router cluster node {node_oid} not running [status={status}]',
                                  func=hltype(self._check_and_apply),
                                  node_oid=hlid(node_oid),
                                  status=hl(node.status if node else 'offline'))
                    is_running_completely = False

            # Check for workergroups without placements and create them if nodes are available
            # This handles the case where workergroups were created before nodes joined the cluster
            if active_memberships:
                with self._manager.db.begin(write=True) as txn:
                    # Get all workergroups for this cluster
                    workergroups = list(
                        self._manager.schema.idx_workergroup_by_cluster.select(txn,
                                                                               from_key=(self._routercluster_oid, ''),
                                                                               return_keys=False))

                    for wg_oid in workergroups:
                        workergroup = self._manager.schema.router_workergroups[txn, wg_oid]

                        # Create missing placements (function handles counting, node selection, and availability)
                        created_placements = self._manager._create_missing_placements(
                            txn, workergroup, session_nodes=self._manager._session.nodes)

                        if created_placements:
                            self.log.info('{func} Created {count} placement(s) for workergroup {wg_name}',
                                          func=hltype(self._check_and_apply),
                                          count=hlval(len(created_placements)),
                                          wg_name=hlval(workergroup.name))

            # Start workers for all placements
            # This ensures workers are running before we update transport principals
            success = yield self._start_placement_workers()
            if not success:
                is_running_completely = False

            # Update transport principals for all workergroups in this cluster
            # This ensures router and proxy nodes can authenticate to transports
            success = yield self._update_workergroup_transports()
            if not success:
                is_running_completely = False

            if routercluster.status in [cluster.STATUS_STARTING] and is_running_completely:
                with self._manager.db.begin(write=True) as txn:
                    routercluster = self._manager.schema.routerclusters[txn, self._routercluster_oid]
                    routercluster.status = cluster.STATUS_RUNNING
                    routercluster.changed = time_ns()
                    self._manager.schema.routerclusters[txn, routercluster.oid] = routercluster

                routercluster_started = {
                    'oid': str(routercluster.oid),
                    'status': cluster.STATUS_BY_CODE[routercluster.status],
                    'changed': routercluster.changed,
                }
                yield self._manager._session.publish('{}.on_routercluster_started'.format(self._manager._prefix),
                                                     routercluster_started,
                                                     options=self._manager._PUBOPTS)
        except:
            self.log.failure()

        if is_running_completely:
            color = 'green'
            action = 'check & apply run completed successfully'
        else:
            color = 'red'
            action = 'check & apply run finished with problems left'

        self._check_and_apply_in_progress = False
        self.log.info('{func} {action} for routercluster {routercluster}!',
                      action=hl(action, color=color, bold=True),
                      func=hltype(self._check_and_apply),
                      routercluster=hlid(self._routercluster_oid))

    @inlineCallbacks
    def _start_placement_workers(self):
        """
        Start workers for all placements in this router cluster.

        This is called before _update_workergroup_transport_principals to ensure
        workers are running before we try to configure transports on them.

        :return: True if all workers started successfully, False if any failed
        """
        is_success = True

        # Get all workergroups for this router cluster
        with self._manager.db.begin() as txn:
            workergroup_oids = list(
                self._manager.schema.idx_workergroup_by_cluster.select(txn,
                                                                       from_key=(self._routercluster_oid, ''),
                                                                       return_keys=False))

        # Process each workergroup
        for workergroup_oid in workergroup_oids:
            with self._manager.db.begin() as txn:
                workergroup = self._manager.schema.router_workergroups[txn, workergroup_oid]

                # Get all placements for this workergroup
                placements = []
                for placement_oid in self._manager.schema.idx_clusterplacement_by_workername.select(
                        txn,
                        from_key=(workergroup.oid, uuid.UUID(bytes=b'\0' * 16), uuid.UUID(bytes=b'\0' * 16), ''),
                        to_key=(uuid.UUID(int=(int(workergroup.oid) + 1)), uuid.UUID(bytes=b'\0' * 16),
                                uuid.UUID(bytes=b'\0' * 16), ''),
                        return_keys=False):
                    placement = self._manager.schema.router_workergroup_placements[txn, placement_oid]
                    placements.append(placement)

            # Start worker for each placement
            for placement in placements:
                node_oid = placement.node_oid
                worker_name = placement.worker_name

                # Skip if node not online
                node = self._manager._session.nodes.get(str(node_oid), None)
                if not node or node.status != 'online':
                    self.log.debug('{func} Skipping worker {worker_name} - node {node_oid} not online',
                                   func=hltype(self._start_placement_workers),
                                   worker_name=hlid(worker_name),
                                   node_oid=hlid(node_oid))
                    is_success = False
                    continue

                # Check if worker already exists
                try:
                    yield self._manager._session.call('crossbarfabriccenter.remote.node.get_worker', str(node_oid),
                                                      worker_name)

                    self.log.debug('{func} Worker {worker_name} already running on node {node_oid}',
                                   func=hltype(self._start_placement_workers),
                                   worker_name=hlid(worker_name),
                                   node_oid=hlid(node_oid))
                except ApplicationError as e:
                    if e.error == 'crossbar.error.no_such_worker':
                        # Worker doesn't exist - create it
                        self.log.info('{func} Starting worker {worker_name} on node {node_oid}',
                                      func=hltype(self._start_placement_workers),
                                      worker_name=hlid(worker_name),
                                      node_oid=hlid(node_oid))

                        worker_options = {
                            'env': {
                                'inherit': ['PYTHONPATH']
                            },
                            'title': 'Managed router worker {}'.format(worker_name),
                            'extra': {}
                        }

                        try:
                            yield self._manager._session.call('crossbarfabriccenter.remote.node.start_worker',
                                                              str(node_oid), worker_name, 'router', worker_options)

                            self.log.info('{func} Worker {worker_name} started on node {node_oid}',
                                          func=hltype(self._start_placement_workers),
                                          worker_name=hlid(worker_name),
                                          node_oid=hlid(node_oid))
                        except Exception as ex:
                            self.log.error('{func} Failed to start worker {worker_name}: {error}',
                                           func=hltype(self._start_placement_workers),
                                           worker_name=hlid(worker_name),
                                           error=str(ex))
                            is_success = False
                    else:
                        raise

        return is_success

    @inlineCallbacks
    def _update_workergroup_transports(self):
        """
        Update transports and their principals for all workergroups in this router cluster.

        This is called at the RouterCluster level (not per-realm) because:
        1. Transports are SHARED across all application realms on the same workergroup
        2. We need a single owner to manage the shared resource
        3. We can collect ALL application realms using each workergroup and set principals once

        For each workergroup, we:
        1. Collect all router nodes from placements
        2. Collect all application realms using this workergroup
        3. For each realm's webcluster, collect proxy nodes and router nodes
        4. Build complete principals
        5. Update transport on each placement if principals changed

        :return: True if all updates succeeded, False if any failed
        """
        is_success = True

        # Get all nodes from global database (we need pubkey and authid attributes)
        all_nodes = {}
        with self._manager.gdb.begin() as txn:
            for node in self._manager.gschema.nodes.select(txn, return_keys=False):
                # Only include nodes that are currently online (in session)
                if str(node.oid) in self._manager._session.nodes:
                    all_nodes[node.oid] = node

        self.log.info('{func} Found {count} online nodes in all_nodes: {node_list}',
                      func=hltype(self._update_workergroup_transports),
                      count=len(all_nodes),
                      node_list=[str(oid) for oid in all_nodes.keys()])

        # Get all workergroups for this router cluster
        with self._manager.db.begin() as txn:
            workergroup_oids = list(
                self._manager.schema.idx_workergroup_by_cluster.select(txn,
                                                                       from_key=(self._routercluster_oid, ''),
                                                                       return_keys=False))

        self.log.debug('{func} Checking transport principals for {count} workergroup(s)',
                       func=hltype(self._update_workergroup_transports),
                       count=len(workergroup_oids))

        # Process each workergroup
        for workergroup_oid in workergroup_oids:
            with self._manager.db.begin() as txn:
                workergroup = self._manager.schema.router_workergroups[txn, workergroup_oid]

                # Get all placements for this workergroup
                placements = []
                for placement_oid in self._manager.schema.idx_clusterplacement_by_workername.select(
                        txn,
                        from_key=(workergroup.oid, uuid.UUID(bytes=b'\0' * 16), uuid.UUID(bytes=b'\0' * 16), ''),
                        to_key=(uuid.UUID(int=(int(workergroup.oid) + 1)), uuid.UUID(bytes=b'\0' * 16),
                                uuid.UUID(bytes=b'\0' * 16), ''),
                        return_keys=False):
                    placement = self._manager.schema.router_workergroup_placements[txn, placement_oid]
                    placements.append(placement)

                # Get all application realms using this workergroup
                # Since there's no index, we need to iterate all arealms and filter
                arealm_oids = []
                for arealm in self._manager.schema.arealms.select(txn, return_keys=False):
                    if arealm.workergroup_oid == workergroup.oid:
                        arealm_oids.append(arealm.oid)

            if not placements:
                self.log.debug('{func} No placements for workergroup {wg_name}, skipping',
                               func=hltype(self._update_workergroup_transports),
                               wg_name=hlval(workergroup.name))
                continue

            # Build router node set from placements
            router_node_oids = set(p.node_oid for p in placements)
            router_nodes = {oid: all_nodes[oid] for oid in router_node_oids if oid in all_nodes}

            # Build rlink principals for this workergroup
            # Rlinks are realm-dependent but use the same principal for each realm - they authenticate at transport level,
            # then specify the realm in their HELLO message
            all_router_pubkeys = sorted([n.pubkey for n in router_nodes.values()])
            rlink_principals = {}
            for router_node in router_nodes.values():
                rlink_principals[router_node.authid] = {
                    'role': 'rlink',
                    'authorized_keys': all_router_pubkeys,
                }

            # Collect webcluster node OIDs across all realms (for proxy principals)
            all_webcluster_node_oids = set()

            # Collect webcluster nodes from all realms using this workergroup
            for arealm_oid in arealm_oids:
                with self._manager.db.begin() as txn:
                    arealm = self._manager.schema.arealms[txn, arealm_oid]
                    if not arealm:
                        continue

                # Collect webcluster nodes for this realm
                if arealm.webcluster_oid:
                    try:
                        wc_workers = self._manager._session._webcluster_manager.get_webcluster_workers(
                            arealm.webcluster_oid, filter_online=True)
                        for wc_node_oid, _wc_worker_id in wc_workers:
                            all_webcluster_node_oids.add(wc_node_oid)
                    except Exception:
                        # Fallback to DB membership if manager not available
                        with self._manager.db.begin() as txn:
                            for node_oid in self._manager.schema.idx_webcluster_node_memberships.select(
                                    txn,
                                    from_key=(arealm.webcluster_oid, uuid.UUID(bytes=b'\0' * 16)),
                                    to_key=(uuid.UUID(int=(int(arealm.webcluster_oid) + 1)),
                                            uuid.UUID(bytes=b'\0' * 16)),
                                    return_keys=False):
                                all_webcluster_node_oids.add(node_oid)

            # Build proxy principals (shared across all realms on this workergroup)
            # Proxy nodes authenticate via cryptosign-proxy which REPLACES the realm value
            # with the forwarded proxy_realm from authextra, so the realm field here doesn't matter
            proxy_principals = {}
            # Collect all authids from rlink principals to avoid overlap
            router_authids = set(rlink_principals.keys())

            self.log.info(
                '{func} Collected webcluster nodes for workergroup {wg_name}: {wc_count} nodes, router_authids={router_authids}',
                func=hltype(self._update_workergroup_transports),
                wg_name=hlid(workergroup.name),
                wc_count=len(all_webcluster_node_oids),
                router_authids=router_authids)

            for wc_node_oid in all_webcluster_node_oids:
                # Convert to UUID if it's a string (webcluster returns strings, all_nodes keyed by UUIDs)
                if isinstance(wc_node_oid, str):
                    wc_node_oid = uuid.UUID(wc_node_oid)

                if wc_node_oid in all_nodes:
                    wc_node = all_nodes[wc_node_oid]
                    # Only add if not already a router node (avoid overlap)
                    if wc_node.authid not in router_authids:
                        # For cryptosign-proxy: omit 'realm' (use HELLO realm), but set placeholder 'role'
                        # The cryptosign-proxy will replace the role with proxy_authrole from authextra
                        proxy_principals[wc_node.authid] = {
                            'role': 'proxy',  # Placeholder - will be replaced with proxy_authrole from authextra
                            'authorized_keys': [wc_node.pubkey],
                        }
                else:
                    self.log.warn('{func} Webcluster node {node_oid} not in all_nodes dict',
                                  func=hltype(self._update_workergroup_transports),
                                  node_oid=wc_node_oid)

            self.log.info(
                '{func} Built proxy_principals for workergroup {wg_name}: {principals}',
                func=hltype(self._update_workergroup_transports),
                wg_name=hlid(workergroup.name),
                principals=list(proxy_principals.keys()))

            # Update transport on each placement
            for placement in placements:
                node_oid = placement.node_oid
                worker_name = placement.worker_name
                transport_id = 'tnp_{}'.format(worker_name)

                # Skip if node not online
                node = self._manager._session.nodes.get(str(node_oid), None)
                if not node or node.status != 'online':
                    self.log.warn(
                        '{func} Node {node_oid} for worker {worker_name} not online (status={status}) - skipping transport update',
                        func=hltype(self._update_workergroup_transports),
                        node_oid=hlid(str(node_oid)),
                        worker_name=hlid(worker_name),
                        status=hl(node.status if node else 'not_in_nodes_dict'))
                    is_success = False
                    continue

                # Worker should already be running (started by _start_placement_workers)
                # If not, skip this placement
                try:
                    yield self._manager._session.call('crossbarfabriccenter.remote.node.get_worker', str(node_oid),
                                                      worker_name)
                except ApplicationError as e:
                    if e.error == 'crossbar.error.no_such_worker':
                        self.log.warn(
                            '{func} Worker {worker_name} not running on node {node_oid} - skipping transport update',
                            func=hltype(self._update_workergroup_transports),
                            worker_name=hlid(worker_name),
                            node_oid=hlid(node_oid))
                        is_success = False
                        continue
                    else:
                        raise

                try:
                    # Get current transport configuration
                    transport = yield self._manager._session.call(
                        'crossbarfabriccenter.remote.router.get_router_transport', str(node_oid), worker_name,
                        transport_id)

                    # If transport doesn't exist, get_router_transport should raise ApplicationError('crossbar.error.no_such_object')
                    # which will be caught below and trigger transport creation.
                    # If it returns a transport, verify it's the right type
                    if transport and transport.get('type') != 'rawsocket':
                        self.log.warn(
                            '{func} Transport {transport_id} on worker {worker_name} is not rawsocket (type={ttype}) - skipping',
                            func=hltype(self._update_workergroup_transports),
                            transport_id=hlid(transport_id),
                            worker_name=hlid(worker_name),
                            ttype=hl(transport.get('type')))
                        is_success = False
                        continue

                    # Build combined desired principals (rlinks + proxy)
                    desired_principals = {}
                    desired_principals.update(rlink_principals)
                    desired_principals.update(proxy_principals)

                    # Hot-reload principals without restarting transport
                    # This avoids dropping connections and changing the port
                    # With hot-reload, we can just push the desired state directly
                    # Note: We call this every iteration to ensure eventual consistency
                    if not desired_principals:
                        self.log.warn(
                            '{func} No principals to update for transport {transport_id} - skipping',
                            func=hltype(self._update_workergroup_transports),
                            transport_id=hlid(transport_id))
                        continue
                    
                    try:
                        yield self._manager._session.call(
                            'crossbarfabriccenter.remote.router.update_router_transport_principals',
                            str(node_oid), worker_name, transport_id, desired_principals)

                        self.log.info(
                            '{func} Successfully hot-updated transport {transport_id} principals: {principal_authids}',
                            func=hltype(self._update_workergroup_transports),
                            transport_id=hlid(transport_id),
                            principal_authids=list(desired_principals.keys()))
                    except Exception as e:
                        self.log.error(
                            '{func} Failed to hot-update transport {transport_id} principals: {error}',
                            func=hltype(self._update_workergroup_transports),
                            transport_id=hlid(transport_id),
                            error=str(e))
                        is_success = False

                except ApplicationError as e:
                    if e.error == 'crossbar.error.no_such_object':
                        # Transport not yet created - create it now
                        self.log.info(
                            '{func} Transport {transport_id} does not exist on worker {worker_name} - creating it',
                            func=hltype(self._update_workergroup_transports),
                            transport_id=hlid(transport_id),
                            worker_name=hlid(worker_name))

                        # Build combined desired principals (rlinks + proxy)
                        desired_principals = {}
                        desired_principals.update(rlink_principals)
                        desired_principals.update(proxy_principals)

                        # Create transport configuration
                        transport_config = {
                            'id': transport_id,
                            'type': 'rawsocket',
                            'endpoint': {
                                'type': 'tcp',
                                'portrange': [10000, 10100]  # Auto-assign port
                            },
                            'options': {},
                            'serializers': ['cbor'],
                            'auth': {
                                'cryptosign-proxy': {
                                    'type': 'static',
                                    'default-role': 'proxy',  # Placeholder - replaced by proxy_authrole from authextra
                                    'principals': desired_principals
                                }
                            }
                        }

                        try:
                            # Start transport with initial principals
                            transport_started = yield self._manager._session.call(
                                'crossbarfabriccenter.remote.router.start_router_transport', str(node_oid),
                                worker_name, transport_id, transport_config)

                            self.log.info(
                                '{func} Successfully created transport {transport_id} on worker {worker_name} with {count} principals',
                                func=hltype(self._update_workergroup_transports),
                                transport_id=hlid(transport_id),
                                worker_name=hlid(worker_name),
                                count=len(desired_principals))

                            # Update placement status with assigned port
                            tcp_listening_port = transport_started.get('config', {}).get('endpoint', {}).get('port', 0)
                            if tcp_listening_port:
                                with self._manager.db.begin(write=True) as txn:
                                    placement_obj = self._manager.schema.router_workergroup_placements[txn,
                                                                                                       placement.oid]
                                    if placement_obj:
                                        placement_obj.tcp_listening_port = tcp_listening_port
                                        placement_obj.status = WorkerGroupStatus.RUNNING
                                        placement_obj.changed = time_ns()
                                        self._manager.schema.router_workergroup_placements[
                                            txn, placement.oid] = placement_obj

                        except Exception as e:
                            self.log.error('{func} Failed to create transport {transport_id}: {error}',
                                           func=hltype(self._update_workergroup_transports),
                                           transport_id=hlid(transport_id),
                                           error=str(e))
                            is_success = False
                    else:
                        self.log.error('{func} Error checking transport {transport_id}: {error}',
                                       func=hltype(self._update_workergroup_transports),
                                       transport_id=hlid(transport_id),
                                       error=str(e))
                        is_success = False
                except Exception as e:
                    self.log.error('{func} Unexpected error updating transport {transport_id}: {error}',
                                   func=hltype(self._update_workergroup_transports),
                                   transport_id=hlid(transport_id),
                                   error=str(e))
                    is_success = False

        return is_success


class RouterClusterManager(object):
    """
    Manages Router clusters, which runs Crossbar.io Web transport listening
    endpoints on many (frontend) workers over many nodes using applying
    a shared, common transport definition, such as regarding the Web services
    configured on URL paths of the Web transport.

    - routercluster
      - routercluster nodes
      - routercluster workergroup
    """
    log = make_logger()

    # publication options for management API events
    _PUBOPTS = PublishOptions(acknowledge=True)

    def __init__(self, session, globaldb, globalschema, db, schema, reactor=None):
        """

        :param session: Backend of user created management realms.
        :type session: :class:`crossbar.master.mrealm.controller.MrealmController`

        :param globaldb: Global database handle.
        :type globaldb: :class:`zlmdb.Database`

        :param globalschema: Global database schema.
        :type globalschema: :class:`cfxdb.globalschema.GlobalSchema`

        :param db: Management realm database handle.
        :type db: :class:`zlmdb.Database`

        :param schema: Management realm database schema.
        :type schema: :class:`cfxdb.mrealmschema.MrealmSchema`
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

        # the management realm OID this routercluster manager operates for
        self._mrealm_oid = session._mrealm_oid

        # URI prefix for WAMP procedures/topics, filled when started
        self._prefix = None

        # filled when started
        self._started = None

        # router cluster monitors, containing a map, for every routercluster in state STARTING or RUNNING
        # with objects of class RouterClusterMonitor
        self._monitors = {}

    def _create_worker_placement(self, txn, workergroup, routercluster_oid, node_oid, worker_name):
        """
        Create a single worker group placement on a specific node.

        This is a helper function used by _create_missing_placements.

        :param txn: Database transaction
        :param workergroup: RouterWorkerGroup object
        :param routercluster_oid: OID of the router cluster
        :param node_oid: OID of the node on which to create the placement
        :param worker_name: Name for the worker (e.g., "workergroup_realm1_1")
        :return: Created RouterWorkerGroupClusterPlacement object
        """
        placement = RouterWorkerGroupClusterPlacement()
        placement.oid = uuid.uuid4()
        placement.worker_group_oid = workergroup.oid
        placement.cluster_oid = routercluster_oid
        placement.node_oid = node_oid
        placement.worker_name = worker_name
        placement.status = WorkerGroupStatus.STOPPED
        placement.changed = time_ns()
        placement.tcp_listening_port = 0

        self.schema.router_workergroup_placements[txn, placement.oid] = placement

        self.log.info('Created placement {worker_name} on node {node_oid} for workergroup {wg_name}',
                      worker_name=hlval(placement.worker_name),
                      node_oid=hlid(node_oid),
                      wg_name=hlval(workergroup.name))

        return placement

    def _create_missing_placements(self, txn, workergroup, session_nodes=None):
        """
        Create missing worker placements for a workergroup, distributing them across available nodes.

        This function:
        1. Counts existing placements for the workergroup
        2. Determines how many placements are needed (workergroup.scale - existing)
        3. Collects available online nodes with their current placement counts
        4. Creates missing placements, distributing them evenly across nodes

        This implements the placement distribution strategy: placements are distributed
        evenly across nodes by always selecting the node with the fewest current placements.

        This is used by both add_routercluster_workergroup (during initial workergroup creation)
        and RouterClusterMonitor._check_and_apply (when creating placements for existing workergroups).

        :param txn: Database transaction
        :param workergroup: RouterWorkerGroup object
        :param session_nodes: Optional session.nodes dict for checking online status (used by monitor)
        :return: List of created placement objects (empty list if no placements needed/possible)
        """
        # Count existing placements for this workergroup
        existing_placements = list(
            self.schema.idx_clusterplacement_by_workername.select(txn,
                                                                  from_key=(workergroup.oid,
                                                                            uuid.UUID(bytes=b'\0' * 16),
                                                                            uuid.UUID(bytes=b'\0' * 16), ''),
                                                                  to_key=(uuid.UUID(int=(int(workergroup.oid) + 1)),
                                                                          uuid.UUID(bytes=b'\0' * 16),
                                                                          uuid.UUID(bytes=b'\0' * 16), ''),
                                                                  return_keys=False))

        placements_needed = workergroup.scale - len(existing_placements)

        # No placements needed
        if placements_needed <= 0:
            return []

        # Collect all nodes in the cluster with their current placement counts
        nodes = SortedDict()
        for _, node_oid in self.schema.routercluster_node_memberships.select(
                txn,
                from_key=(workergroup.cluster_oid, uuid.UUID(bytes=b'\0' * 16)),
                to_key=(uuid.UUID(int=(int(workergroup.cluster_oid) + 1)), uuid.UUID(bytes=b'\0' * 16)),
                return_values=False):

            # If session_nodes provided, only include online nodes
            if session_nodes:
                node_oid_str = str(node_oid)
                node_obj = session_nodes.get(node_oid_str, None)
                if not node_obj or node_obj.status != 'online':
                    continue

            # Count existing placements on this node for this workergroup
            node_placement_count = len(
                list(
                    self.schema.idx_clusterplacement_by_workername.select(
                        txn,
                        from_key=(workergroup.oid, workergroup.cluster_oid, node_oid, ''),
                        to_key=(workergroup.oid, workergroup.cluster_oid, uuid.UUID(int=(int(node_oid) + 1)), ''),
                        return_keys=False)))
            nodes[node_oid] = node_placement_count

        # No nodes available
        if not nodes:
            self.log.warn('Cannot create placements for workergroup {wg_name} - no nodes available',
                          wg_name=hlval(workergroup.name))
            return []

        # Create the missing placements
        created_placements = []
        next_worker_index = len(existing_placements) + 1

        for i in range(placements_needed):
            # Select node with fewest placements (strategy: load balancing)
            placement_node_oid, placement_node_cnt = nodes.peekitem(0)

            # Generate worker name
            worker_name = '{}_{}'.format(workergroup.name, next_worker_index + i)

            # Create the placement
            placement = self._create_worker_placement(txn, workergroup, workergroup.cluster_oid, placement_node_oid,
                                                      worker_name)

            created_placements.append(placement)

            # Update node count for next iteration
            nodes[placement_node_oid] += 1

        self.log.info('Created {count} placement(s) for workergroup {wg_name} (now has {existing}/{scale} placements)',
                      count=hlval(len(created_placements)),
                      wg_name=hlval(workergroup.name),
                      existing=hlval(len(existing_placements) + len(created_placements)),
                      scale=hlval(workergroup.scale))

        return created_placements

    @inlineCallbacks
    def start(self, prefix):
        """
        Start this router cluster manager, including all monitors of router clusters defined.

        :return:
        """
        assert self._started is None, 'cannot start router cluster manager - already running!'
        assert self._prefix is None

        self._started = time_ns()

        # crossbarfabriccenter.mrealm.routercluster
        self._prefix = prefix[:-1] if prefix.endswith('.') else prefix

        # register management procedures
        regs = yield self._session.register(self,
                                            prefix='{}.'.format(self._prefix),
                                            options=RegisterOptions(details_arg='details'))
        procs = [reg.procedure for reg in regs]
        self.log.info(
            'Router cluster manager registered {api} management procedures using prefix "{prefix}" [{func}]:\n\n{procs}\n',
            api=hl('Router cluster manager API', color='green', bold=True),
            func=hltype(self.start),
            prefix=hlval(self._prefix),
            procs=hl(pformat(procs), color='white', bold=True))

        # start all router cluster monitors
        cnt_started = 0
        cnt_skipped = 0
        dl = []
        with self.db.begin() as txn:
            routercluster_oids = self.schema.routerclusters.select(txn, return_values=False)
            for routercluster_oid in routercluster_oids:
                routercluster = self.schema.routerclusters[txn, routercluster_oid]
                if routercluster.status in [cluster.STATUS_STARTING, cluster.STATUS_RUNNING]:
                    assert routercluster_oid not in self._monitors
                    monitor = RouterClusterMonitor(self, routercluster_oid)
                    dl.append(monitor.start())
                    self._monitors[routercluster_oid] = monitor
                    cnt_started += 1
                    self.log.info(
                        'Router cluster monitor started for router cluster {routercluster_oid} in status {status} [{func}]',
                        func=hltype(self.start),
                        routercluster_oid=hlid(routercluster_oid),
                        status=hlval(routercluster.status))
                else:
                    cnt_skipped += 1
                    self.log.info(
                        'Router cluster monitor skipped for router cluster {routercluster_oid} in status {status} [{func}]',
                        func=hltype(self.start),
                        routercluster_oid=hlid(routercluster_oid),
                        status=hlval(routercluster.status))
        self.log.info(
            'Router cluster manager has started monitors for {cnt_started} clusters ({cnt_skipped} skipped) [{func}]',
            cnt_started=hlval(cnt_started),
            cnt_skipped=hlval(cnt_skipped),
            func=hltype(self.start))

        self.log.info('Router cluster manager for management realm {mrealm_oid} ready [{func}]',
                      mrealm_oid=hlid(self._mrealm_oid),
                      func=hltype(self.start))

        # return txaio.gather(dl)

    def stop(self):
        """
        Stop the currently running router cluster manager. This will stop all monitors for router clusters.

        :return:
        """
        assert self._started > 0, 'cannot stop router cluster manager - currently not running!'

        # stop all router cluster monitors ..
        dl = []
        for routercluster_oid, routercluster_monitor in self._monitors.items():
            dl.append(routercluster_monitor.stop())
            del self._monitors[routercluster_oid]
        self._started = None
        self.log.info(
            'Ok, router cluster manager for management realm {mrealm_oid} stopped ({cnt_stopped} monitors stopped) [{func}]',
            mrealm_oid=hlid(self._mrealm_oid),
            cnt_stopped=len(dl),
            func=hltype(self.start))

        # return txaio.gather(dl)

    @wamp.register(None, check_types=True)
    def list_routerclusters(self,
                            return_names: Optional[bool] = None,
                            details: Optional[CallDetails] = None) -> List[str]:
        """
        Returns list of router clusters defined. Detail information for a router cluster
        can be retrieved using :meth:`crossbar.master.cluster.routercluster.RouterClusterManager.get_routercluster`.

        :param return_names: Return router clusters names instead of object IDs.

        :return: List of router clusters object IDs or names. For example:

            .. code-block:: json

                [
                    "634e0725-df03-4daf-becd-1de60dd2b0b3",
                    "7dc55a4e-e52a-4bea-a8b4-daf869cc417f"
                ]

            or with ``return_names``  set:

            .. code-block:: json

                [
                    "cluster1"
                ]
        """
        self.log.info('{func}(details={details})', func=hltype(self.list_routerclusters), details=details)

        with self.db.begin() as txn:
            if return_names:
                routerclusters = self.schema.routerclusters.select(txn, return_keys=False)
                if routerclusters:
                    return sorted([routercluster.name for routercluster in routerclusters])
                else:
                    return []
            else:
                routercluster_oids = self.schema.routerclusters.select(txn, return_values=False)
                if routercluster_oids:
                    # we now have a list of uuid.UUID objects: convert to strings
                    return [str(oid) for oid in routercluster_oids]
                else:
                    return []

    @wamp.register(None, check_types=True)
    def get_routercluster(self, routercluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return configuration and run-time status information for a router cluster (by object ID).

        :param routercluster_oid: Object ID of the router cluster to return.

        :return: Router cluster definition. For example, initially, after a router cluster has been created:

            .. code-block:: json

                {
                    "changed": 1598273658338443875,
                    "description": null,
                    "label": null,
                    "name": "cluster2",
                    "oid": "634e0725-df03-4daf-becd-1de60dd2b0b3",
                    "status": "STOPPED",
                    "tags": null
                }
        """
        self.log.info('{func}(routercluster_oid={routercluster_oid}, details={details})',
                      func=hltype(self.get_routercluster),
                      routercluster_oid=hlid(routercluster_oid),
                      details=details)

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid routercluster_oid: {}'.format(str(e)))

        with self.db.begin() as txn:
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]

        if routercluster:
            return routercluster.marshal()
        else:
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no routercluster with oid {}'.format(routercluster_oid_))

    @wamp.register(None, check_types=True)
    def get_routercluster_by_name(self, routercluster_name: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return configuration and run-time status information for a router cluster (by name).

        See also the corresponding procedure :meth:`crossbar.master.cluster.routercluster.RouterClusterManager.get_routercluster`
        which returns the same information, given and object ID rather than name.

        :param routercluster_name: Name of the router cluster to return.

        :return: Router cluster definition.
        """
        self.log.info('{func}(routercluster_name="{routercluster_name}", details={details})',
                      func=hltype(self.get_routercluster_by_name),
                      routercluster_name=hlid(routercluster_name),
                      details=details)

        with self.db.begin() as txn:
            routercluster_oid = self.schema.idx_routerclusters_by_name[txn, routercluster_name]
            if not routercluster_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no routercluster named {}'.format(routercluster_name))

            routercluster = self.schema.routerclusters[txn, routercluster_oid]
            assert routercluster

        return routercluster.marshal()

    @wamp.register(None, check_types=True)
    async def create_routercluster(self, routercluster: dict, details: Optional[CallDetails] = None) -> dict:
        """
        Create a new router cluster definition.

        :procedure: ``crossbarfabriccenter.mrealm.cluster.create_routercluster`` URI of WAMP procedure to call.
        :event: ``crossbarfabriccenter.mrealm.cluster.on_routercluster_created`` WAMP event published once the
            router cluster has been created.
        :error: ``wamp.error.invalid_configuration`` WAMP error returned when the router cluster
            configuration provided has a problem.
        :error: ``wamp.error.not_authorized`` WAMP error returned when the user is currently not allowed
            to created (another) router cluster.
        :error: ``crossbar.error.already_exists`` WAMP error returned when a router cluster named as contained
            in the configuration already exists.

        :param routercluster: Router cluster settings. For example:

            .. code-block:: json

                {
                    "name": "cluster5"
                }

        :return: Router cluster creation information. For example:

            .. code-block:: json

                {
                    "changed": 1598379288123799334,
                    "description": null,
                    "label": null,
                    "name": "cluster5",
                    "oid": "3eccb1fd-251b-4eda-bee9-06b3d24b1c5e",
                    "owner_oid": "f1c62815-56b2-484f-bb5a-a66a788c2aff",
                    "status": "STOPPED",
                    "tags": null
                }
        """
        self.log.info('{func}(routercluster="{routercluster}", details={details})',
                      func=hltype(self.create_routercluster),
                      routercluster=routercluster,
                      details=details)

        try:
            obj = RouterCluster.parse(routercluster)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_configuration',
                                   'could not parse router cluster configuration ({})'.format(e))

        if obj.name is None:
            raise ApplicationError('wamp.error.invalid_configuration',
                                   'missing "name" in router cluster configuration')
        else:
            if not checkconfig._CONFIG_ITEM_ID_PAT.match(obj.name):
                raise ApplicationError(
                    'wamp.error.invalid_configuration',
                    'invalid name "{}" in router cluster configuration (must match {})'.format(
                        obj.name, checkconfig._CONFIG_ITEM_ID_PAT_STR))

        obj.oid = uuid.uuid4()
        obj.status = cluster.STATUS_BY_NAME['STOPPED']
        obj.changed = np.datetime64(time_ns(), 'ns')

        if details and details.caller_authid:
            with self.gdb.begin() as txn:
                caller_oid = self.gschema.idx_users_by_email[txn, details.caller_authid]
                if not caller_oid:
                    raise ApplicationError('wamp.error.no_such_principal',
                                           'no user found for authid "{}"'.format(details.caller_authid))
            obj.owner_oid = caller_oid
        else:
            raise ApplicationError('wamp.error.no_such_principal', 'cannot map user - no caller authid available')

        with self.db.begin(write=True) as txn:
            if self.schema.idx_routerclusters_by_name[txn, obj.name]:
                raise ApplicationError('crossbar.error.already_exists',
                                       'duplicate name "{}" in router cluster configuration'.format(obj.name))

            self.schema.routerclusters[txn, obj.oid] = obj

        self.log.info('new RouterCluster object stored in database:\n{obj}', obj=obj)

        res_obj = obj.marshal()

        await self._session.publish('{}.on_routercluster_created'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_routercluster_created> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    async def delete_routercluster(self, routercluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Delete an existing router cluster definition. The router cluster must be in status ``"STOPPED"``.

        :procedure: ``crossbarfabriccenter.routercluster.delete_routercluster`` URI of WAMP procedure to call.
        :event: ``crossbarfabriccenter.routercluster.on_routercluster_deleted`` WAMP event published once the router cluster has been deleted.
        :error: ``wamp.error.invalid_argument`` WAMP error returned when ``routercluster_oid`` was invalid.
        :error: ``crossbar.error.no_such_object`` WAMP error returned when ``routercluster_oid`` was not found.
        :error: ``crossbar.error.not_stopped`` WAMP error returned when router cluster is not in status ``STOPPED``.

        :param routercluster_oid: OID of the router cluster to delete

        :returns: Deleted router cluster, for example:

            .. code-block:: json

                {
                    "changed": 1598380973225053489,
                    "description": null,
                    "label": null,
                    "name": "cluster5",
                    "oid": "3eccb1fd-251b-4eda-bee9-06b3d24b1c5e",
                    "owner_oid": "f1c62815-56b2-484f-bb5a-a66a788c2aff",
                    "status": "STOPPED",
                    "tags": null
                }
        """
        self.log.info('{func}.delete_routercluster(routercluster_oid={routercluster_oid}, details={details})',
                      func=hltype(self.delete_routercluster),
                      routercluster_oid=hlid(routercluster_oid),
                      details=details)

        try:
            oid = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        if details and details.caller_authid:
            with self.gdb.begin() as txn:
                caller_oid = self.gschema.idx_users_by_email[txn, details.caller_authid]
                if not caller_oid:
                    raise ApplicationError('wamp.error.no_such_principal',
                                           'no user found for authid "{}"'.format(details.caller_authid))
        else:
            raise ApplicationError('wamp.error.no_such_principal', 'cannot map user - no caller authid available')

        with self.db.begin(write=True) as txn:
            cluster_obj = self.schema.routerclusters[txn, oid]
            if cluster_obj:
                if cluster_obj.owner_oid != caller_oid:
                    raise ApplicationError('wamp.error.not_authorized',
                                           'only owner is allowed to delete router cluster')
                if cluster_obj.status != cluster.STATUS_STOPPED:
                    raise ApplicationError('crossbar.error.not_stopped')
                del self.schema.routerclusters[txn, oid]
            else:
                raise ApplicationError('crossbar.error.no_such_object', 'no object with oid {} found'.format(oid))

        cluster_obj.changed = time_ns()
        self.log.info('RouterCluster object deleted from database:\n{cluster}', cluster=cluster_obj)

        res_obj = cluster_obj.marshal()
        await self._session.publish('{}.on_routercluster_deleted'.format(self._prefix), res_obj, options=self._PUBOPTS)
        return res_obj

    @wamp.register(None, check_types=True)
    async def start_routercluster(self, routercluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Start a router cluster

        :param routercluster_oid: Object ID of router cluster to start.

        :return: Started router cluster, for example:

            .. code-block:: json

                {
                    "changed": 1598402748823470105,
                    "oid": "ad6cfb53-3712-4683-8b15-f48a6d71d410",
                    "status": "STARTING",
                    "who": {
                        "authid": "superuser",
                        "authrole": "owner",
                        "session": 6761363113437744
                    }
                }
        """
        self.log.info('{func}(routercluster_oid="{routercluster_oid}", details={details})',
                      func=hltype(self.start_routercluster),
                      routercluster_oid=hlid(routercluster_oid),
                      details=details)

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        if details and details.caller_authid:
            with self.gdb.begin() as txn:
                caller_oid = self.gschema.idx_users_by_email[txn, details.caller_authid]
                if not caller_oid:
                    raise ApplicationError('wamp.error.no_such_principal',
                                           'no user found for authid "{}"'.format(details.caller_authid))
        else:
            raise ApplicationError('wamp.error.no_such_principal', 'cannot map user - no caller authid available')

        with self.db.begin(write=True) as txn:
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]
            if not routercluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no routercluster with oid {} found'.format(routercluster_oid_))

            if routercluster.owner_oid != caller_oid:
                raise ApplicationError('wamp.error.not_authorized', 'only owner is allowed to start a router cluster')

            if routercluster.status not in [cluster.STATUS_STOPPED, cluster.STATUS_PAUSED]:
                emsg = 'cannot start routercluster currently in state {}'.format(
                    cluster.STATUS_BY_CODE[routercluster.status])
                raise ApplicationError('crossbar.error.cannot_start', emsg)

            routercluster.status = cluster.STATUS_STARTING
            routercluster.changed = time_ns()

            self.schema.routerclusters[txn, routercluster_oid_] = routercluster

        monitor = RouterClusterMonitor(self, routercluster_oid_)
        monitor.start()
        assert routercluster_oid_ not in self._monitors
        self._monitors[routercluster_oid_] = monitor

        routercluster_starting = {
            'oid': str(routercluster.oid),
            'status': cluster.STATUS_BY_CODE[routercluster.status],
            'changed': routercluster.changed,
            'who': {
                'session': details.caller if details else None,
                'authid': details.caller_authid if details else None,
                'authrole': details.caller_authrole if details else None,
            }
        }
        await self._session.publish('{}.on_routercluster_starting'.format(self._prefix),
                                    routercluster_starting,
                                    options=self._PUBOPTS)

        return routercluster_starting

    @wamp.register(None, check_types=True)
    async def stop_routercluster(self, routercluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Stop a running router cluster.

        :param routercluster_oid: Object ID of router cluster to stop.

        :return: Stopped router cluster, for example:

            .. code-block:: json

                {
                    "changed": 1598402964397396934,
                    "oid": "ad6cfb53-3712-4683-8b15-f48a6d71d410",
                    "status": "STOPPING",
                    "who": {
                        "authid": "superuser",
                        "authrole": "owner",
                        "session": 8299909547427073
                    }
                }
        """
        self.log.info('{func}(routercluster_oid={routercluster_oid}, details={details})',
                      routercluster_oid=hlid(routercluster_oid),
                      func=hltype(self.stop_routercluster),
                      details=details)

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin(write=True) as txn:
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]
            if not routercluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no routercluster with oid {} found'.format(routercluster_oid_))

            if routercluster.status not in [cluster.STATUS_STARTING, cluster.STATUS_RUNNING]:
                emsg = 'cannot stop routercluster currently in state {}'.format(
                    cluster.STATUS_BY_CODE[routercluster.status])
                raise ApplicationError('crossbar.error.cannot_start', emsg)

            routercluster.status = cluster.STATUS_STOPPING
            routercluster.changed = time_ns()

            self.schema.routerclusters[txn, routercluster_oid_] = routercluster

        routercluster_stopping = {
            'oid': str(routercluster.oid),
            'status': cluster.STATUS_BY_CODE[routercluster.status],
            'changed': routercluster.changed,
            'who': {
                'session': details.caller if details else None,
                'authid': details.caller_authid if details else None,
                'authrole': details.caller_authrole if details else None,
            }
        }

        await self._session.publish('{}.on_routercluster_stopping'.format(self._prefix),
                                    routercluster_stopping,
                                    options=self._PUBOPTS)

        return routercluster_stopping

    @wamp.register(None, check_types=True)
    def stat_routercluster(self, routercluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        *NOT YET IMPLEMENTED*

        Get current status and statistics for given router cluster.

        :param routercluster_oid: The router cluster to return status and statistics for.

        :return: Current status and statistics for given router cluster.
        """
        self.log.info('{func}(routercluster_oid={routercluster_oid}, details={details})',
                      func=hltype(self.stat_routercluster),
                      routercluster_oid=hlid(routercluster_oid),
                      details=details)

        raise NotImplementedError()

    @wamp.register(None, check_types=True)
    def list_routercluster_nodes(self,
                                 routercluster_oid: str,
                                 return_names: Optional[bool] = None,
                                 filter_by_status: Optional[str] = None,
                                 details: Optional[CallDetails] = None) -> List[str]:
        """
        List nodes currently associated with the given router cluster.

        :param routercluster_oid: The router cluster to list nodes for.
        :param return_names: Return routercluster names instead of  object IDs
        :param filter_by_status: Filter nodes by this status, eg. ``"online"``.

        :return: List of node IDs of nodes associated with the router cluster. For example:

            .. code-block:: json

                [
                    "0afb5897-d8da-433a-9214-ed64e8da50b9",
                    "2f656d47-5251-44bb-a507-6cebc533eb50",
                    "7ddf39c5-6752-4467-9497-3f1758b2ac5e",
                    "879d05f3-e3d3-4bce-894e-a281e4782a0b"
                ]

            or with ``return_names`` set:

            .. code-block:: json

                [
                    "node1",
                    "node2",
                    "node3",
                    "node4"
                ]
        """
        self.log.info(
            '{func}(routercluster_oid={routercluster_oid}, return_names={return_names}, filter_by_status={filter_by_status}, details={details})',
            func=hltype(self.list_routercluster_nodes),
            routercluster_oid=hlid(routercluster_oid),
            return_names=hlval(return_names),
            filter_by_status=hlval(filter_by_status),
            details=details)

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        node_oids = []
        with self.db.begin() as txn:
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]
            if not routercluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no routercluster with oid {} found'.format(routercluster_oid_))
            for _, node_oid in self.schema.routercluster_node_memberships.select(
                    txn, from_key=(routercluster_oid_, uuid.UUID(bytes=b'\0' * 16)), return_values=False):
                node_oids.append(node_oid)

        if filter_by_status:
            node_oids_ = []
            for node_oid in node_oids:
                node = self._session.nodes.get(str(node_oid), None)
                if node and node.status == filter_by_status:
                    node_oids_.append(node_oid)
            node_oids = node_oids_

        if return_names:
            node_authids = []
            with self.gdb.begin() as txn:
                for node_oid in node_oids:
                    node = self.gschema.nodes[txn, node_oid]
                    if node and node.authid:
                        node_authids.append(node.authid)
            res = sorted(node_authids)
        else:
            res = [str(node_oid) for node_oid in node_oids]

        return res

    @wamp.register(None, check_types=True)
    async def add_routercluster_node(self,
                                     routercluster_oid: str,
                                     node_oid: str,
                                     config: Optional[dict] = None,
                                     details: Optional[CallDetails] = None) -> dict:
        """
        Add a node to a router cluster. You can configure the node association for the
        cluster using ``config``:

        - ``hardlimit``: hard limit on node utilization (number of workers run on this node)
        - ``softlimit``: soft limit on node utilization (number of workers run on this node)

        :param routercluster_oid: OID of the router cluster to which to add the node.
        :param node_oid: OID of the node to add to the cluster. A node can be added to more than one cluster.

        :return: Added node, for example:

            .. code-block:: json

                {
                    "cluster_oid": "ad6cfb53-3712-4683-8b15-f48a6d71d410",
                    "node_oid": "6009c4d1-b5e5-4ca8-aee3-0da28b5a08b2",
                    "hardlimit": null,
                    "softlimit": null
                }
        """
        self.log.info(
            '{func}(routercluster_oid={routercluster_oid}, node_oid={node_oid}, config={config}, details={details})',
            func=hltype(self.list_routercluster_nodes),
            routercluster_oid=hlid(routercluster_oid),
            node_oid=hlid(node_oid),
            config=config,
            details=details)

        config = config or {}
        config['cluster_oid'] = routercluster_oid
        config['node_oid'] = node_oid
        membership = RouterClusterNodeMembership.parse(config)

        with self.gdb.begin() as txn:
            node = self.gschema.nodes[txn, membership.node_oid]
            if not node or node.mrealm_oid != self._session._mrealm_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no node with oid {} found'.format(membership.node_oid))

        with self.db.begin(write=True) as txn:
            routercluster = self.schema.routerclusters[txn, membership.cluster_oid]
            if not routercluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no routercluster with oid {} found'.format(membership.cluster_oid))

            self.schema.routercluster_node_memberships[txn, (membership.cluster_oid, membership.node_oid)] = membership

        res_obj = membership.marshal()
        self.log.info('node added to router cluster:\n{membership}', membership=res_obj)

        await self._session.publish('{}.on_routercluster_node_added'.format(self._prefix),
                                    res_obj,
                                    options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    async def remove_routercluster_node(self,
                                        routercluster_oid: str,
                                        node_oid: str,
                                        details: Optional[CallDetails] = None) -> dict:
        """
        Remove a node from a router cluster.

        :param routercluster_oid: OID of the router cluster from which to remove the node.
        :param node_oid: OID of the node to remove from the router cluster

        :return: Node removed from router cluster, for example:

            .. code-block:: json

                {
                    "cluster_oid": "ad6cfb53-3712-4683-8b15-f48a6d71d410",
                    "node_oid": "6009c4d1-b5e5-4ca8-aee3-0da28b5a08b2",
                    "hardlimit": null,
                    "softlimit": null
                }
        """
        try:
            node_oid_ = uuid.UUID(node_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        self.log.info('{func}(routercluster_oid={routercluster_oid}, node_oid={node_oid}, details={details})',
                      routercluster_oid=hlid(routercluster_oid_),
                      node_oid=hlid(node_oid),
                      func=hltype(self.remove_routercluster_node),
                      details=details)

        with self.gdb.begin() as txn:
            node = self.gschema.nodes[txn, node_oid_]
            if not node or node.mrealm_oid != self._session._mrealm_oid:
                raise ApplicationError('crossbar.error.no_such_object', 'no node with oid {} found'.format(node_oid_))

        with self.db.begin(write=True) as txn:
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]
            if not routercluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(routercluster_oid_))

            membership = self.schema.routercluster_node_memberships[txn, (routercluster_oid_, node_oid_)]
            if not membership:
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no association between node {} and routercluster {} found'.format(node_oid_, routercluster_oid_))

            # Delete the node membership from the cluster
            del self.schema.routercluster_node_memberships[txn, (routercluster_oid_, node_oid_)]

            # CRITICAL FIX: Delete all worker placements for this node in all workergroups of this cluster
            # This fixes the bug where stale placements prevent realms from redistributing when nodes rejoin
            deleted_placements = 0

            # Get all workergroups in this router cluster
            for workergroup_oid in self.schema.idx_router_workergroups_by_cluster.select(
                    txn, from_key=(routercluster_oid_, ), return_values=False):

                # Find all placements for this workergroup on the node being removed
                # idx_clusterplacement_by_workername: (workergroup_oid, cluster_oid, node_oid, worker_name) -> placement_oid
                placement_oids_to_delete = []
                for placement_oid in self.schema.idx_clusterplacement_by_workername.select(
                        txn,
                        from_key=(workergroup_oid, routercluster_oid_, node_oid_, ''),
                        to_key=(workergroup_oid, routercluster_oid_, uuid.UUID(int=(int(node_oid_) + 1)), ''),
                        return_keys=False):
                    placement_oids_to_delete.append(placement_oid)

                # Delete each placement
                for placement_oid in placement_oids_to_delete:
                    del self.schema.router_workergroup_placements[txn, placement_oid]
                    deleted_placements += 1
                    self.log.debug(
                        'Deleted stale worker placement {placement_oid} for node {node_oid} in workergroup {workergroup_oid}',
                        placement_oid=hlid(placement_oid),
                        node_oid=hlid(node_oid_),
                        workergroup_oid=hlid(workergroup_oid))

            if deleted_placements > 0:
                self.log.info(
                    'Cleaned up {count} stale worker placement(s) for node {node_oid} being removed from router cluster {cluster_oid}',
                    count=hlval(deleted_placements),
                    node_oid=hlid(node_oid_),
                    cluster_oid=hlid(routercluster_oid_))

        res_obj = membership.marshal()
        self.log.info('node removed from router cluster:\n{res_obj}', membership=res_obj)

        await self._session.publish('{}.on_routercluster_node_removed'.format(self._prefix),
                                    res_obj,
                                    options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    def get_routercluster_node(self,
                               routercluster_oid: str,
                               node_oid: str,
                               details: Optional[CallDetails] = None) -> dict:
        """
        Get information (such as for example parallel degree) for the association
        of a node with a routercluster.

        :param routercluster_oid: The router cluster to which the node was added.
        :param node_oid: The node to return.

        :return: Information for the association of the node with the routercluster. For example:

            .. code-block:: json

                {
                    "cluster_oid": "ad6cfb53-3712-4683-8b15-f48a6d71d410",
                    "node_oid": "d87b502c-83d9-4cce-87be-0bb1bbd9539a",
                    "hardlimit": null,
                    "softlimit": null
                }
        """
        try:
            node_oid_ = uuid.UUID(node_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        self.log.info('{func}(routercluster_oid={routercluster_oid}, node_oid={node_oid}, details={details})',
                      routercluster_oid=hlid(routercluster_oid_),
                      node_oid=hlid(node_oid_),
                      func=hltype(self.get_routercluster_node),
                      details=details)

        with self.gdb.begin() as txn:
            node = self.gschema.nodes[txn, node_oid_]
            if not node or node.mrealm_oid != self._session._mrealm_oid:
                raise ApplicationError('crossbar.error.no_such_object', 'no node with oid {} found'.format(node_oid_))

        with self.db.begin() as txn:
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]
            if not routercluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(routercluster_oid_))

            membership = self.schema.routercluster_node_memberships[txn, (routercluster_oid_, node_oid_)]
            if not membership:
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no association between node {} and routercluster {} found'.format(node_oid_, routercluster_oid_))

        res_obj = membership.marshal()

        return res_obj

    @wamp.register(None, check_types=True)
    def list_routercluster_workergroups(self,
                                        routercluster_oid: str,
                                        return_names: Optional[bool] = None,
                                        filter_by_status: Optional[str] = None,
                                        details: Optional[CallDetails] = None) -> List[str]:
        """
        List worker groups in a router cluster. Detail information for a router cluster worker group
        can be retrieved using :meth:`crossbar.master.cluster.routercluster.RouterClusterManager.get_routercluster_workergroup`.

        :param routercluster_oid: The object ID of the router cluster to list router worker groups for.
        :param return_names: If set, return router worker group names instead of object IDs.
        :param filter_by_status: If set, only return worker group in this status.

        :return: List of router cluster worker group object IDs, for example:

            .. code-block:: json

                [
                    "5c295684-7f7f-4560-b175-7466ed957c2e"
                ]

        or with ``return_names`` set:

            .. code-block:: json

                [
                    "mygroup1"
                ]
        """
        self.log.info('{func}(routercluster_oid={routercluster_oid}, details={details})',
                      routercluster_oid=hlid(routercluster_oid),
                      func=hltype(self.list_routercluster_workergroups),
                      details=details)

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        workergroups = []
        with self.db.begin() as txn:
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]
            if not routercluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(routercluster_oid))

            # Use index "idx_workergroup_by_cluster": (cluster_oid, workergroup_name) -> workergroup_oid
            from_key = (routercluster_oid_, '')
            to_key = (uuid.UUID(int=(int(routercluster_oid_) + 1)), '')
            for (_,
                 workergroup_name), workergroup_oid in self.schema.idx_workergroup_by_cluster.select(txn,
                                                                                                     from_key=from_key,
                                                                                                     to_key=to_key):
                if return_names:
                    workergroups.append(workergroup_name)
                else:
                    workergroups.append(str(workergroup_oid))

            return workergroups

    @wamp.register(None, check_types=True)
    async def add_routercluster_workergroup(self,
                                            routercluster_oid: str,
                                            workergroup: dict,
                                            details: Optional[CallDetails] = None) -> dict:
        """
        Add a Router worker group to a Router cluster. The ``workergroup`` can be configured:

        .. code-block:: json

            {
                "name": "mygroup1",
                "scale": 4
            }

        :param routercluster_oid: Router cluster to which to add the router worker group.
        :param workergroup: Web service definition object.

        :returns: Router cluster worker group creation information, for example:

            .. code-block:: json

                {
                    "changed": 1598452531613401997,
                    "cluster_oid": "b99833d5-0f03-4759-b1ed-b7059e81b2d8",
                    "description": null,
                    "label": null,
                    "name": "mygroup1",
                    "oid": "5c295684-7f7f-4560-b175-7466ed957c2e",
                    "scale": 4,
                    "status": "STOPPED",
                    "tags": null
                }
        """
        self.log.info('{func}(routercluster_oid={routercluster_oid}, workergroup={workergroup}, details={details})',
                      routercluster_oid=hlid(routercluster_oid),
                      workergroup=pformat(workergroup),
                      func=hltype(self.add_routercluster_workergroup),
                      details=details)

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin(write=True) as txn:
            # get routercluster on which to create a new workergroup
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]
            if not routercluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(routercluster_oid_))

            # create new workergroup object
            workergroup_obj = RouterWorkerGroup.parse(workergroup)
            workergroup_obj.oid = uuid.uuid4()
            workergroup_obj.cluster_oid = routercluster_oid_
            workergroup_obj.status = WorkerGroupStatus.STOPPED
            workergroup_obj.changed = time_ns()

            # if no explicit workergroup name was given, auto-assign a name
            if not workergroup_obj.name:
                workergroup_obj.name = 'cwg_{}'.format(str(workergroup_obj.oid)[:8])

            # store workergroup in database
            self.schema.router_workergroups[txn, workergroup_obj.oid] = workergroup_obj
            self.log.info('New router worker group object stored in database:\n{workergroup}',
                          workergroup=pformat(workergroup_obj.marshal()))

            # Create and store workergroup worker placements on nodes for the new workergroup
            # NOTE: If no nodes are in the cluster yet, we skip creating placements here.
            # The monitor will automatically create placements when nodes join the cluster later.
            created_placements = self._create_missing_placements(txn, workergroup_obj)

            if created_placements:
                self.log.info('Created {count} worker placement(s) for new workergroup {workergroup_name}',
                              count=hlval(len(created_placements)),
                              workergroup_name=hlval(workergroup_obj.name))
            else:
                self.log.warn(
                    'No nodes currently in router cluster {routercluster_oid} - placements for workergroup {workergroup_name} will be created automatically when nodes join',
                    routercluster_oid=hlid(routercluster_oid_),
                    workergroup_name=hlval(workergroup_obj.name))

        res_obj = workergroup_obj.marshal()

        await self._session.publish('{}.on_workergroup_added'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_workergroup_added> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    async def remove_routercluster_workergroup(self,
                                               routercluster_oid: str,
                                               workergroup_oid: str,
                                               details: Optional[CallDetails] = None) -> dict:
        """
        Remove a router worker group from a router cluster.

        :param routercluster_oid: The object ID of the router cluster to remove a router worker group from.
        :param workergroup_oid: The object ID of the router worker group to remove.

        :return: Removed router worker group, for example:

            .. code-block:: json

                {
                    "changed": 1598455166431307344,
                    "cluster_oid": "b99833d5-0f03-4759-b1ed-b7059e81b2d8",
                    "description": null,
                    "label": null,
                    "name": "mygroup1",
                    "oid": "fa5498b7-c660-4a5b-81f5-95f9223a19f5",
                    "scale": 4,
                    "status": "STOPPED",
                    "tags": null
                }
        """
        self.log.info(
            '{func}(routercluster_oid={routercluster_oid}, workergroup_oid={workergroup_oid}, details={details})',
            routercluster_oid=hlid(routercluster_oid),
            workergroup_oid=hlid(workergroup_oid),
            func=hltype(self.remove_routercluster_workergroup),
            details=details)

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid routercluster_oid "{}"'.format(str(e)))

        try:
            workergroup_oid_ = uuid.UUID(workergroup_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid workergroup_oid "{}"'.format(str(e)))

        if details and details.caller_authid:
            with self.gdb.begin() as txn:
                caller_oid = self.gschema.idx_users_by_email[txn, details.caller_authid]
                if not caller_oid:
                    raise ApplicationError('wamp.error.no_such_principal',
                                           'no user found for authid "{}"'.format(details.caller_authid))
        else:
            raise ApplicationError('wamp.error.no_such_principal', 'cannot map user - no caller authid available')

        with self.db.begin(write=True) as txn:
            routercluster = self.schema.routerclusters[txn, routercluster_oid_]
            if routercluster:
                if routercluster.owner_oid != caller_oid:
                    raise ApplicationError('wamp.error.not_authorized',
                                           'only owner is allowed to modify router cluster')
                if routercluster.status != cluster.STATUS_STOPPED:
                    raise ApplicationError('crossbar.error.not_stopped')
            else:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(routercluster_oid_))

            workergroup = self.schema.router_workergroups[txn, workergroup_oid_]
            if not workergroup:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no workergroup with oid {} found'.format(workergroup_oid_))

            # FIXME: check that the worker group has no running application realms

            # CRITICAL FIX: Delete all worker placements for this workergroup
            # This fixes the bug where stale placements remain when workergroups are deleted
            deleted_placements = 0

            # Find all placements for this workergroup
            # idx_clusterplacement_by_workername: (workergroup_oid, cluster_oid, node_oid, worker_name) -> placement_oid
            placement_oids_to_delete = []
            for placement_oid in self.schema.idx_clusterplacement_by_workername.select(
                    txn,
                    from_key=(workergroup_oid_, uuid.UUID(bytes=b'\0' * 16), uuid.UUID(bytes=b'\0' * 16), ''),
                    to_key=(uuid.UUID(int=(int(workergroup_oid_) + 1)), uuid.UUID(bytes=b'\0' * 16),
                            uuid.UUID(bytes=b'\0' * 16), ''),
                    return_keys=False):
                placement_oids_to_delete.append(placement_oid)

            # Delete each placement
            for placement_oid in placement_oids_to_delete:
                del self.schema.router_workergroup_placements[txn, placement_oid]
                deleted_placements += 1
                self.log.debug('Deleted worker placement {placement_oid} for workergroup {workergroup_oid}',
                               placement_oid=hlid(placement_oid),
                               workergroup_oid=hlid(workergroup_oid_))

            if deleted_placements > 0:
                self.log.info('Cleaned up {count} worker placement(s) for workergroup {workergroup_oid} being removed',
                              count=hlval(deleted_placements),
                              workergroup_oid=hlid(workergroup_oid_))

            del self.schema.router_workergroups[txn, workergroup_oid_]

        self.log.info('router cluster work group object removed from database:\n{workergroup}',
                      workergroup=workergroup)

        res_obj = workergroup.marshal()

        await self._session.publish('{}.on_workergroup_removed'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_workergroup_removed> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    def get_routercluster_workergroup(self,
                                      routercluster_oid: str,
                                      workergroup_oid: str,
                                      details: Optional[CallDetails] = None) -> dict:
        """
        Get definition of a router worker group in a cluster by ID.

        :param routercluster_oid: The router cluster running the router worker group to return.
        :param workergroup_oid: The router worker group to return.

        :return: The router cluster worker group, for example:

            .. code-block:: json

                {
                    "changed": 1598452531613401997,
                    "cluster_oid": "b99833d5-0f03-4759-b1ed-b7059e81b2d8",
                    "description": null,
                    "label": null,
                    "name": "mygroup1",
                    "oid": "5c295684-7f7f-4560-b175-7466ed957c2e",
                    "scale": 4,
                    "status": "STOPPED",
                    "tags": null
                }
        """
        self.log.info(
            '{func}(routercluster_oid={routercluster_oid}, workergroup_oid={workergroup_oid}, details={details})',
            routercluster_oid=hlid(routercluster_oid),
            workergroup_oid=hlid(workergroup_oid),
            func=hltype(self.get_routercluster_workergroup),
            details=details)

        try:
            routercluster_oid_ = uuid.UUID(routercluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        try:
            workergroup_oid_ = uuid.UUID(workergroup_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin() as txn:
            workergroup = self.schema.router_workergroups[txn, workergroup_oid_]
            if not workergroup:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no worker group with oid {} found'.format(workergroup_oid_))

        if workergroup.cluster_oid != routercluster_oid_:
            raise ApplicationError(
                'crossbar.error.no_such_object',
                'worker group with oid {} found, but not associated with given router cluster'.format(
                    workergroup_oid_))

        return workergroup.marshal()

    @wamp.register(None, check_types=True)
    def get_routercluster_workergroup_by_name(self,
                                              routercluster_name: str,
                                              workergroup_name: str,
                                              details: Optional[CallDetails] = None) -> dict:
        """
        Get definition of a router worker group in a cluster by name.

        See also :meth:`crossbar.master.cluster.routercluster.RouterClusterManager.get_routercluster_workergroup`.

        :param routercluster_name: The router cluster running the router worker group to return.
        :param workergroup_name: The router worker group to return.

        :return: The router cluster worker group.
        """
        self.log.info(
            '{func}(routercluster_name="{routercluster_name}", workergroup_name="{workergroup_name}", details={details})',
            routercluster_name=hlval(routercluster_name),
            workergroup_name=hlval(workergroup_name),
            func=hltype(self.get_routercluster_workergroup),
            details=details)

        with self.db.begin() as txn:
            routercluster_oid = self.schema.idx_routerclusters_by_name[txn, routercluster_name]
            if not routercluster_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no routercluster named {}'.format(routercluster_name))

            workergroup_oid = self.schema.idx_workergroup_by_cluster[txn, (routercluster_oid, workergroup_name)]
            if not workergroup_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no workergroup named {}'.format(workergroup_name))

            workergroup = self.schema.router_workergroups[txn, workergroup_oid]
            assert workergroup

        return workergroup.marshal()

    @wamp.register(None, check_types=True)
    def stat_routercluster_workergroup(self,
                                       routercluster_oid: str,
                                       workergroup_oid: str,
                                       details: Optional[CallDetails] = None) -> dict:
        """
        *NOT YET IMPLEMENTED*

        Return current status and statistics for the router worker group.

        :param routercluster_oid: The router cluster running the web service to return status and statistics for.
        :param workergroup_oid: The worker group to return status and statistics for.

        :return: Current status and statistics information for the router worker group.
        """
        self.log.info(
            '{func}(routercluster_oid={routercluster_oid}, workergroup_oid={workergroup_oid}, details={details})',
            func=hltype(self.stat_routercluster_workergroup),
            routercluster_oid=hlid(routercluster_oid),
            workergroup_oid=hlid(workergroup_oid),
            details=details)

        raise NotImplementedError()
