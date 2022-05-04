###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
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

        self._loop = LoopingCall(self._check_and_apply)
        self._loop.start(self._interval)

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

            del self.schema.routercluster_node_memberships[txn, (routercluster_oid_, node_oid_)]

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

            # collect all node OIDs currently associated with the router cluster
            # into a dict sorted by the current number of placements
            nodes = SortedDict()
            for _, node_oid in self.schema.routercluster_node_memberships.select(
                    txn,
                    from_key=(routercluster_oid_, uuid.UUID(bytes=b'\0' * 16)),
                    to_key=(uuid.UUID(int=(int(routercluster_oid_) + 1)), uuid.UUID(bytes=b'\0' * 16)),
                    return_values=False):

                # count current number of placements associated with given node
                cnt = 0
                for _ in self.schema.idx_workergroup_by_placement.select(
                        txn,
                        from_key=(workergroup_obj.cluster_oid, node_oid, uuid.UUID(bytes=b'\0' * 16)),
                        to_key=(workergroup_obj.cluster_oid, uuid.UUID(int=(int(node_oid) + 1)),
                                uuid.UUID(bytes=b'\0' * 16)),
                        return_keys=False):
                    cnt += 1

                # the dict is sorted ascending by cnt, that is nodes.peekitem(0)
                # will be a node with the smallest current number of placements
                nodes[node_oid] = cnt

            # create and store workergroup worker placements on nodes for the new workergroup
            for i in range(workergroup_obj.scale):
                # new placement on a node with smallest number of current placements
                placement_node_oid, placement_node_cnt = nodes.peekitem(0)

                self.log.info(
                    'Router worker placement selected node {placement_node_oid} with current worker count {placement_node_cnt}',
                    placement_node_oid=hlid(placement_node_oid),
                    placement_node_cnt=hlval(placement_node_cnt))

                placement = RouterWorkerGroupClusterPlacement()
                placement.oid = uuid.uuid4()
                placement.worker_group_oid = workergroup_obj.oid
                placement.cluster_oid = routercluster_oid_
                placement.node_oid = placement_node_oid
                placement.worker_name = '{}_{}'.format(workergroup_obj.name, i + 1)
                placement.status = WorkerGroupStatus.STOPPED
                placement.changed = time_ns()
                placement.tcp_listening_port = 0

                self.schema.router_workergroup_placements[txn, placement.oid] = placement

                # keep track of new placement in our sorted dict
                nodes[placement_node_oid] += 1

                self.log.info('New router worker group placement object stored in database:\n{placement}',
                              placement=pformat(placement.marshal()))

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
            # FIXME: remove all router worker group placements from self.schema.router_workergroup_placements

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
