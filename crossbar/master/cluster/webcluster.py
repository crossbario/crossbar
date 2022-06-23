###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import uuid
from pprint import pformat
from typing import Optional, List, Dict, Tuple

import numpy as np

from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import CallDetails, PublishOptions, RegisterOptions

from crossbar.common import checkconfig
from crossbar.webservice import archive, wap
from crossbar._util import hl, hlid, hltype, hlval, get_free_tcp_port
from cfxdb.mrealm import WebCluster, WebClusterNodeMembership, WebService
from cfxdb.mrealm import cluster
from cfxdb.mrealm.application_realm import ApplicationRealmStatus

import txaio

txaio.use_twisted()
from txaio import time_ns, sleep, make_logger  # noqa
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall


class WebClusterMonitor(object):
    """
    Background monitor running periodically in the master node to monitor, check and apply
    necessary actions for web clusters.

    The monitor is started when a web cluster is started.
    """
    log = make_logger()

    def __init__(self, manager, webcluster_oid, interval=10.):
        self._manager = manager
        self._webcluster_oid = webcluster_oid
        self._interval = interval

        self._loop = None
        self._check_and_apply_in_progress = False

        self._workers = {}

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

    def get_cluster_workers(self, filter_online: bool = False) -> List[Tuple[str, str]]:
        """

        :param filter_online:
        :return:
        """
        res = []
        for node_oid, worker_id in self._workers:
            if not filter_online or self._workers[(node_oid, worker_id)]['status'] == 'started':
                res.append((node_oid, worker_id))
        return res

    @inlineCallbacks
    def _check_and_apply(self):
        if self._check_and_apply_in_progress:
            # we prohibit running the iteration multiple times concurrently. this might
            # happen when the iteration takes longer than the interval the monitor is set to
            self.log.info('{func} {action} for webcluster {webcluster} skipped! check & apply already in progress.',
                          action=hl('check & apply run skipped', color='red', bold=True),
                          func=hltype(self._check_and_apply),
                          webcluster=hlid(self._webcluster_oid))
            return
        else:
            self.log.info('{func} {action} for webcluster {webcluster} ..',
                          action=hl('check & apply run started', color='green', bold=True),
                          func=hltype(self._check_and_apply),
                          webcluster=hlid(self._webcluster_oid))
            self._check_and_apply_in_progress = True

        is_running_completely = True
        workers = {}
        try:
            # get all active (non-standby) nodes added to the webcluster
            active_memberships = []
            with self._manager.db.begin() as txn:
                # the webcluster itself
                webcluster = self._manager.schema.webclusters[txn, self._webcluster_oid]

                if webcluster.status in [cluster.STATUS_STARTING, cluster.STATUS_RUNNING]:
                    # the node memberships in the webcluster
                    active_memberships = [
                        m for m in self._manager.schema.webcluster_node_memberships.select(
                            txn, from_key=(webcluster.oid, uuid.UUID(bytes=b'\0' * 16)), return_keys=False)
                    ]

            for membership in active_memberships:
                node_oid = str(membership.node_oid)

                if membership.standby:
                    self.log.debug('{func} Web cluster node {node_oid} is configured for standby',
                                   func=hltype(self._check_and_apply),
                                   node_oid=hlid(node_oid))
                    continue

                # node run-time information, as maintained here in our master view of the external world
                node = self._manager._session.nodes.get(node_oid, None)

                if node and node.status == 'online':
                    self.log.debug('{func} Ok, web cluster node {node_oid} is running!',
                                   func=hltype(self._check_and_apply),
                                   node_oid=hlid(node_oid))

                    # we expect "parallel" workers to run on this node ..
                    for worker_index in range(membership.parallel or 1):

                        # run-time ID of web cluster worker, eg "clwrk-a276279d-5"
                        worker_id = 'cpw-{}-{}'.format(str(webcluster.oid)[:8], worker_index)

                        self.log.debug(
                            '{func} Performing checks for configured proxy worker {worker_index}/{parallel} [{worker_id}] ..',
                            func=hltype(self._check_and_apply),
                            worker_index=hlid(worker_index + 1),
                            worker_id=hlid(worker_id),
                            parallel=hlid(membership.parallel))

                        # worker run-time information (obtained by calling into the live node)
                        worker = None
                        try:
                            worker = yield self._manager._session.call('crossbarfabriccenter.remote.node.get_worker',
                                                                       node_oid, worker_id)
                        except ApplicationError as e:
                            if e.error != 'crossbar.error.no_such_worker':
                                # anything but "no_such_worker" is unexpected (and fatal)
                                raise
                            self.log.info(
                                'No Web cluster worker {worker_id} currently running on node {node_oid}: starting worker ..',
                                node_oid=hlid(node_oid),
                                worker_id=hlid(worker_id))
                        else:
                            self.log.debug(
                                '{func} Ok, web cluster worker {worker_id} already running on node {node_oid}!',
                                func=hltype(self._check_and_apply),
                                node_oid=hlid(node_oid),
                                worker_id=hlid(worker_id))

                        # if there isn't a worker running (with worker ID as we expect) already,
                        # start a new proxy worker ..
                        if not worker:
                            worker_options = None
                            try:
                                worker_started = yield self._manager._session.call(
                                    'crossbarfabriccenter.remote.node.start_worker', node_oid, worker_id, 'proxy',
                                    worker_options)
                                worker = yield self._manager._session.call(
                                    'crossbarfabriccenter.remote.node.get_worker', node_oid, worker_id)
                                self.log.info(
                                    '{func} Web cluster worker {worker_id} started on node {node_oid} [{worker_started}]',
                                    func=hltype(self._check_and_apply),
                                    node_oid=hlid(node_oid),
                                    worker_id=hlid(worker_id),
                                    worker_started=worker_started)
                            except:
                                self.log.failure()
                                is_running_completely = False

                        # we can only continue with transport(s) when we now have a worker started already
                        if worker:
                            transport = None

                            # FIXME: currently, we only have 1 transport on a web cluster worker (which is named "primary")
                            transport_id = 'primary'
                            try:
                                transport = yield self._manager._session.call(
                                    'crossbarfabriccenter.remote.proxy.get_proxy_transport', node_oid, worker_id,
                                    transport_id)
                            except ApplicationError as e:
                                if e.error != 'crossbar.error.no_such_object':
                                    # anything but "no_such_object" is unexpected (and fatal)
                                    raise
                                self.log.info(
                                    '{func} No Transport {transport_id} currently running for Web cluster worker {worker_id}: starting transport ..',
                                    func=hltype(self._check_and_apply),
                                    worker_id=hlid(worker_id),
                                    transport_id=hlid(transport_id))
                            else:
                                self.log.debug(
                                    '{func} Ok, transport {transport_id} already running on Web cluster worker {worker_id}',
                                    func=hltype(self._check_and_apply),
                                    worker_id=hlid(worker_id),
                                    transport_id=hlid(transport_id))

                            # if there isn't a transport started (with transport ID as we expect) already,
                            # start a new transport ..
                            if not transport:
                                transport_config = {
                                    'id': transport_id,
                                    'type': 'web',
                                    'endpoint': {
                                        'type': 'tcp',
                                        'port':
                                        int(webcluster.tcp_port) if webcluster.tcp_port else get_free_tcp_port(),
                                        'shared': webcluster.tcp_shared is True,
                                    },
                                    'paths': {},
                                    'options': {
                                        'access_log': webcluster.http_access_log is True,
                                        'display_tracebacks': webcluster.http_display_tracebacks is True,
                                        'hsts': webcluster.http_hsts is True,
                                    }
                                }
                                if webcluster.tcp_interface:
                                    transport_config['endpoint']['interface'] = webcluster.tcp_interface
                                if webcluster.tcp_backlog:
                                    transport_config['endpoint']['backlog'] = webcluster.tcp_backlog
                                if webcluster.http_hsts_max_age:
                                    transport_config['options']['hsts_max_age'] = webcluster.http_hsts_max_age
                                if webcluster.http_client_timeout:
                                    transport_config['options']['client_timeout'] = webcluster.http_client_timeout

                                try:
                                    transport_started = yield self._manager._session.call(
                                        'crossbarfabriccenter.remote.proxy.start_proxy_transport', node_oid, worker_id,
                                        transport_id, transport_config)
                                    transport = yield self._manager._session.call(
                                        'crossbarfabriccenter.remote.proxy.get_proxy_transport', node_oid, worker_id,
                                        transport_id)
                                    self.log.info(
                                        '{func} Transport {transport_id} started on Web cluster worker {worker_id} [{transport_started}]',
                                        func=hltype(self._check_and_apply),
                                        worker_id=hlid(worker_id),
                                        transport_id=hlid(transport_id),
                                        transport_started=transport_started)
                                except:
                                    self.log.failure()
                                    is_running_completely = False

                            # we can only continue with web services when we now have a transport started already
                            if transport:
                                # collect all web services defined for our (one) web transport, and collect
                                # in a path->webservice map
                                webservices = {}
                                with self._manager.db.begin() as txn:
                                    for webservice_oid in self._manager.schema.idx_webcluster_webservices.select(
                                            txn, from_key=(webcluster.oid, uuid.UUID(bytes=b'\0' * 16)),
                                            return_keys=False):
                                        webservice = self._manager.schema.webservices[txn, webservice_oid]
                                        if webservice:
                                            webservices[webservice.path] = webservice
                                        else:
                                            self.log.warn('No webservice object found for oid {webservice_oid}',
                                                          webservice_oid=webservice_oid)

                                for path, webservice in webservices.items():
                                    service = None
                                    try:
                                        service = yield self._manager._session.call(
                                            'crossbarfabriccenter.remote.proxy.get_web_transport_service', node_oid,
                                            worker_id, transport_id, path)
                                    except ApplicationError as e:
                                        # anything but "not_running" is unexpected (and fatal)
                                        if e.error != 'crossbar.error.not_running':
                                            raise
                                        self.log.info(
                                            '{func} No Web service currently running on path "{path}" for Web cluster worker {worker_id} web transport {transport_id}: starting web service ..',
                                            func=hltype(self._check_and_apply),
                                            path=hlval(path),
                                            worker_id=hlid(worker_id),
                                            transport_id=hlid(transport_id))
                                    else:
                                        self.log.debug(
                                            '{func} Ok, web service on path "{path}" is already running for Web cluster worker {worker_id} web transport {transport_id}',
                                            func=hltype(self._check_and_apply),
                                            path=hlval(path),
                                            worker_id=hlid(worker_id),
                                            transport_id=hlid(transport_id))

                                    if not service:
                                        webservice_config = webservice.marshal()
                                        webservice_config.pop('oid', None)
                                        webservice_config.pop('label', None)
                                        webservice_config.pop('description', None)
                                        webservice_config.pop('tags', None)
                                        webservice_config.pop('cluster_oid', None)
                                        webservice_config.pop('path', None)

                                        # FIXME: this shouldn't be there (but should be cluster_oid)
                                        webservice_config.pop('webcluster_oid', None)
                                        try:
                                            webservice_started = yield self._manager._session.call(
                                                'crossbarfabriccenter.remote.proxy.start_web_transport_service',
                                                node_oid, worker_id, transport_id, path, webservice_config)
                                            self.log.info(
                                                '{func} Web service started on transport {transport_id} and path "{path}" [{webservice_started}]',
                                                func=hltype(self._check_and_apply),
                                                transport_id=hlid(transport_id),
                                                path=hlval(path),
                                                webservice_started=webservice_started)
                                        except:
                                            self.log.failure()
                                            is_running_completely = False

                            with self._manager.db.begin() as txn:
                                for arealm_oid in self._manager.schema.idx_arealm_by_webcluster.select(
                                        txn,
                                        from_key=(webcluster.oid, ''),
                                        to_key=(uuid.UUID(int=int(webcluster.oid) + 1), ''),
                                        return_keys=False):
                                    arealm = self._manager.schema.arealms[txn, arealm_oid]
                                    if arealm and arealm.status == ApplicationRealmStatus.RUNNING and arealm.workergroup_oid:
                                        self.log.debug(
                                            '{func} node {node_id} - worker {worker_id} - webcluster "{webcluster_name}": backend router workergroup {workergroup_oid} is associated with this frontend web cluster for application realm "{arealm_name}"',
                                            func=hltype(self._check_and_apply),
                                            node_id=hlval(str(node.node_id)),
                                            worker_id=hlval(worker_id),
                                            webcluster_name=hlval(webcluster.name),
                                            arealm_name=hlval(arealm.name),
                                            arealm_oid=hlid(arealm_oid),
                                            workergroup_oid=hlid(arealm.workergroup_oid))

                        wk = (node_oid, worker['id'])
                        workers[wk] = worker
                else:
                    self.log.warn('{func} Web cluster node {node_oid} not running [status={status}]',
                                  func=hltype(self._check_and_apply),
                                  node_oid=hlid(node_oid),
                                  status=hl(node.status if node else 'offline'))
                    is_running_completely = False

            if webcluster.status in [cluster.STATUS_STARTING] and is_running_completely:
                with self._manager.db.begin(write=True) as txn:
                    webcluster = self._manager.schema.webclusters[txn, self._webcluster_oid]
                    webcluster.status = cluster.STATUS_RUNNING
                    webcluster.changed = time_ns()
                    self._manager.schema.webclusters[txn, webcluster.oid] = webcluster

                webcluster_started = {
                    'oid': str(webcluster.oid),
                    'status': cluster.STATUS_BY_CODE[webcluster.status],
                    'changed': webcluster.changed,
                }
                yield self._manager._session.publish('{}.on_webcluster_started'.format(self._manager._prefix),
                                                     webcluster_started,
                                                     options=self._manager._PUBOPTS)
        except:
            self.log.failure()

        self._workers = workers
        for node_oid, worker_id in self._workers:
            worker = self._workers[(node_oid, worker_id)]
            if worker:
                status = worker['status'].upper()
            else:
                status = 'MISSING'
            self.log.info(
                '{func} webcluster {webcluster_oid} worker {worker_id} on node {node_oid} has status {status}',
                func=hltype(self._check_and_apply),
                worker_id=hlid(worker_id),
                node_oid=hlid(node_oid),
                webcluster_oid=hlid(self._webcluster_oid),
                status=hlval(status))

        if is_running_completely:
            color = 'green'
            action = 'check & apply run completed successfully'
        else:
            color = 'red'
            action = 'check & apply run finished with problems left'

        self._check_and_apply_in_progress = False
        self.log.info('{func} {action} for webcluster {webcluster}!',
                      action=hl(action, color=color, bold=True),
                      func=hltype(self._check_and_apply),
                      webcluster=hlid(self._webcluster_oid))


class WebClusterManager(object):
    """
    Manages Web clusters, which runs Crossbar.io Web transport listening
    endpoints on many (frontend) workers over many nodes using applying
    a shared, common transport definition, such as regarding the Web services
    configured on URL paths of the Web transport.
    """
    log = make_logger()

    # publication options for management API events
    _PUBOPTS = PublishOptions(acknowledge=True)

    # map of allowed web services, see also crossbar.personality.Personality.WEB_SERVICE_CHECKERS
    _WEB_SERVICE_CHECKERS = {
        # none
        'path': checkconfig.check_web_path_service_path,
        'redirect': checkconfig.check_web_path_service_redirect,
        # resource
        'reverseproxy': checkconfig.check_web_path_service_reverseproxy,
        'nodeinfo': checkconfig.check_web_path_service_nodeinfo,
        'json': checkconfig.check_web_path_service_json,
        'cgi': checkconfig.check_web_path_service_cgi,
        'wsgi': checkconfig.check_web_path_service_wsgi,
        'static': checkconfig.check_web_path_service_static,
        'websocket': checkconfig.check_web_path_service_websocket,
        'websocket-reverseproxy': checkconfig.check_web_path_service_websocket_reverseproxy,
        # longpoll
        'caller': checkconfig.check_web_path_service_caller,
        'publisher': checkconfig.check_web_path_service_publisher,
        # webhook
        'archive': archive.RouterWebServiceArchive.check,
        'wap': wap.RouterWebServiceWap.check,
    }

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

        # will be set in session.register
        self._prefix = None

        # the management realm OID this webcluster manager operates for
        self._mrealm_oid = session._mrealm_oid

        # filled when started
        self._started = None

        # webcluster monitors, containing a map, for every webcluster in state STARTING or RUNNING
        # with objects of class WebClusterMonitor
        self._monitors = {}

    def get_webcluster_workers(self, webcluster_oid, filter_online=False):
        if webcluster_oid in self._monitors:
            return self._monitors[webcluster_oid].get_cluster_workers(filter_online=filter_online)

    @inlineCallbacks
    def start(self, prefix):
        """
        Start the Web-cluster manager.

        :return:
        """
        assert self._started is None, 'cannot start web cluster manager - already running!'
        assert self._prefix is None

        self._started = time_ns()

        # crossbarfabriccenter.mrealm.webcluster
        self._prefix = prefix[:-1] if prefix.endswith('.') else prefix

        regs = yield self._session.register(self,
                                            prefix='{}.'.format(self._prefix),
                                            options=RegisterOptions(details_arg='details'))
        procs = [reg.procedure for reg in regs]
        self.log.debug(
            'Web cluster manager {api} registered management procedures using prefix "{prefix}" [{func}]:\n\n{procs}\n',
            api=hl('Web cluster manager API', color='green', bold=True),
            func=hltype(self.start),
            prefix=hlval(self._prefix),
            procs=hl(pformat(procs), color='white', bold=True))

        # start all web cluster monitors ..
        cnt_started = 0
        cnt_skipped = 0
        dl = []
        with self.db.begin() as txn:
            webcluster_oids = self.schema.webclusters.select(txn, return_values=False)
            for webcluster_oid in webcluster_oids:
                webcluster = self.schema.webclusters[txn, webcluster_oid]
                if webcluster.status in [cluster.STATUS_STARTING, cluster.STATUS_RUNNING]:
                    monitor = WebClusterMonitor(self, webcluster_oid)
                    dl.append(monitor.start())
                    assert webcluster_oid not in self._monitors
                    self._monitors[webcluster_oid] = monitor
                    cnt_started += 1
                    self.log.info('{func}(prefix="{prefix}"): {action} for web cluster {webcluster_oid} in {status})',
                                  action=hl('cluster monitor started', color='green', bold=True),
                                  prefix=hlval(prefix),
                                  func=hltype(self.start),
                                  webcluster_oid=hlid(webcluster_oid),
                                  status=hlval(webcluster.status))
                else:
                    cnt_skipped += 1
                    self.log.info(
                        '{func}(prefix="{prefix}"): {action} for web cluster {webcluster_oid} in status {status}',
                        action=hl('cluster monitor skipped', color='green', bold=True),
                        prefix=hlval(prefix),
                        func=hltype(self.start),
                        webcluster_oid=hlid(webcluster_oid),
                        status=hlval(webcluster.status))
        self.log.info(
            'Web cluster manager has started monitors for {cnt_started} clusters ({cnt_skipped} skipped) [{func}]',
            cnt_started=hlval(cnt_started),
            cnt_skipped=hlval(cnt_skipped),
            func=hltype(self.start))

        self.log.info('Web cluster manager ready for management realm {mrealm_oid}! [{func}]',
                      mrealm_oid=hlid(self._mrealm_oid),
                      func=hltype(self.start))

        # return txaio.gather(dl)

    @inlineCallbacks
    def stop(self):
        """
        Stop the (currently running) Web-cluster manager.

        :return:
        """
        assert self._started > 0, 'cannot stop web cluster manager - currently not running!'

        # stop all web cluster monitors ..
        dl = []
        for webcluster_oid, webcluster_monitor in self._monitors.items():
            dl.append(webcluster_monitor.stop())
            del self._monitors[webcluster_oid]
        self._started = None
        self.log.info(
            'Ok, web cluster manager for management realm {mrealm_oid} stopped ({cnt_stopped} monitors stopped) [{func}]',
            mrealm_oid=hlid(self._mrealm_oid),
            cnt_stopped=len(dl),
            func=hltype(self.start))

        # return txaio.gather(dl)

    @wamp.register(None, check_types=True)
    def list_webclusters(self,
                         return_names: Optional[bool] = False,
                         details: Optional[CallDetails] = None) -> List[str]:
        """
        Returns list of web clusters defined. Detail information for a web cluster
        can be retrieved using :meth:`crossbar.master.cluster.webcluster.WebClusterManager.get_webcluster`.

        :param return_names: Return webcluster names instead of  object IDs

        :returns: List of WebCluster UUIDs (or names). For example:

            .. code-block:: json

                [
                    "4917ca20-acc5-497a-9801-b53db5db4d89"
                ]

            or with ``return_names``  set:

            .. code-block:: json

                [
                    "cluster1"
                ]
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(details={details})', func=hltype(self.list_webclusters), details=details)

        with self.db.begin() as txn:
            if return_names:
                webclusters = self.schema.webclusters.select(txn, return_keys=False)
                if webclusters:
                    return sorted([webcluster.name for webcluster in webclusters])
                else:
                    return []
            else:
                webcluster_oids = self.schema.webclusters.select(txn, return_values=False)
                if webcluster_oids:
                    # we now have a list of uuid.UUID objects: convert to strings
                    return [str(oid) for oid in webcluster_oids]
                else:
                    return []

    @wamp.register(None, check_types=True)
    def get_webcluster(self, webcluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return configuration and run-time status information for a web cluster (by object ID).

        :param routercluster_oid: Object ID of the web cluster to return.

        :return: Web cluster definition. For example:

            .. code-block:: json

                {
                    "changed": 1598388779771813358,
                    "description": null,
                    "http_access_log": null,
                    "http_client_timeout": null,
                    "http_display_tracebacks": null,
                    "http_hsts": null,
                    "http_hsts_max_age": null,
                    "label": null,
                    "name": "cluster1",
                    "oid": "4917ca20-acc5-497a-9801-b53db5db4d89",
                    "owner_oid": "8d6e3068-900a-4fa8-a6f5-0828c8d0ee24",
                    "status": "STOPPED",
                    "tags": null,
                    "tcp_backlog": null,
                    "tcp_interface": null,
                    "tcp_port": 8080,
                    "tcp_shared": true,
                    "tcp_version": null,
                    "tls_ca_certificates": null,
                    "tls_certificate": null,
                    "tls_chain_certificates": null,
                    "tls_ciphers": null,
                    "tls_dhparam": null,
                    "tls_key": null
                }
        """
        assert type(webcluster_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(webcluster_oid={webcluster_oid}, details={details})',
                      func=hltype(self.get_webcluster),
                      webcluster_oid=hlid(webcluster_oid),
                      details=details)

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid webcluster_oid: {}'.format(str(e)))

        with self.db.begin() as txn:
            webcluster = self.schema.webclusters[txn, webcluster_oid_]

        if webcluster:
            return webcluster.marshal()
        else:
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no webcluster with oid {}'.format(webcluster_oid_))

    @wamp.register(None, check_types=True)
    def get_webcluster_by_name(self, webcluster_name: str, details: Optional[CallDetails] = None) -> dict:
        """
        Return configuration and run-time status information for a web cluster (by name).

        See also the corresponding procedure :meth:`crossbar.master.cluster.webcluster.WebClusterManager.get_webcluster`
        which returns the same information, given and object ID rather than name.

        :param webcluster_name: Name of the web cluster to return.

        :return: Web cluster definition.
        """
        assert type(webcluster_name) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(webcluster_name="{webcluster_name}", details={details})',
                      func=hltype(self.get_webcluster_by_name),
                      webcluster_name=hlid(webcluster_name),
                      details=details)

        with self.db.begin() as txn:
            webcluster_oid = self.schema.idx_webclusters_by_name[txn, webcluster_name]
            if not webcluster_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no webcluster named {}'.format(webcluster_name))

            webcluster = self.schema.webclusters[txn, webcluster_oid]
            assert webcluster

        return webcluster.marshal()

    @wamp.register(None, check_types=True)
    async def create_webcluster(self, webcluster: dict, details: Optional[CallDetails] = None) -> dict:
        """
        Create a new web cluster definition ``webcluster``:

        Web listening endpoint:

        - ``tcp_version``: IP version, either 4 for 6
        - ``tcp_port``: IP listening port
        - ``tcp_shared``: enable TCP port sharing
        - ``tcp_interface``: listen on this interface
        - ``tcp_backlog``: TCP accept backlog queue size

        Web endpoint TLS configuration:

        - ``tls_key``: TLS server private key to use
        - ``tls_certificate``: TLS server certificate to use
        - ``tls_chain_certificates``: TLS certificate chain
        - ``tls_dhparam``: DH parameter file
        - ``tls_ciphers``: Ciphers list
        - ``tls_ca_certificates``: CA certificates to use

        Web transport options:

        - ``http_client_timeout``: HTTP client inactivity timeout
        - ``http_hsts``: enable HTTP strict transport security (HSTS)
        - ``http_hsts_max_age``: HSTS maximum age to announce
        - ``http_access_log``: enable Web request access logging
        - ``http_display_tracebacks``: enable tracebacks when running into Web errors

        :procedure: ``crossbarfabriccenter.mrealm.cluster.create_webcluster`` URI of WAMP procedure to call.
        :event: ``crossbarfabriccenter.mrealm.cluster.on_webcluster_created`` WAMP event published once the
            web cluster has been created.
        :error: ``wamp.error.invalid_configuration`` WAMP error returned when the web cluster
            configuration provided has a problem.
        :error: ``wamp.error.not_authorized`` WAMP error returned when the user is currently not allowed
            to created (another) web cluster.
        :error: ``crossbar.error.already_exists`` WAMP error returned when a web cluster named as contained
            in the configuration already exists.

        :param webcluster: Web cluster settings. For example:

            .. code-block:: json

                {
                    "name": "cluster1"
                }


        :return: Web cluster creation information. For example:

            .. code-block:: json

                {
                    "changed": 1598388333642427113,
                    "description": null,
                    "http_access_log": null,
                    "http_client_timeout": null,
                    "http_display_tracebacks": null,
                    "http_hsts": null,
                    "http_hsts_max_age": null,
                    "label": null,
                    "name": "cluster1",
                    "oid": "96e3d9a6-3e88-4205-8eec-2e7c338b2620",
                    "owner_oid": "c10a7e49-cea6-47ce-a003-74f7196d1763",
                    "status": "STOPPED",
                    "tags": null,
                    "tcp_backlog": null,
                    "tcp_interface": null,
                    "tcp_port": 8080,
                    "tcp_shared": true,
                    "tcp_version": null,
                    "tls_ca_certificates": null,
                    "tls_certificate": null,
                    "tls_chain_certificates": null,
                    "tls_ciphers": null,
                    "tls_dhparam": null,
                    "tls_key": null
                }
        """
        assert type(webcluster) == dict
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(webcluster="{webcluster}", details={details})',
                      func=hltype(self.create_webcluster),
                      webcluster=webcluster,
                      details=details)

        try:
            obj = WebCluster.parse(webcluster)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_configuration',
                                   'could not parse web cluster configuration ({})'.format(e))

        if obj.name is None:
            raise ApplicationError('wamp.error.invalid_configuration', 'missing "name" in web cluster configuration')
        else:
            if not checkconfig._CONFIG_ITEM_ID_PAT.match(obj.name):
                raise ApplicationError(
                    'wamp.error.invalid_configuration',
                    'invalid name "{}" in web cluster configuration (must match {})'.format(
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
            if self.schema.idx_webclusters_by_name[txn, obj.name]:
                raise ApplicationError('crossbar.error.already_exists',
                                       'duplicate name "{}" in web cluster configuration'.format(obj.name))

            self.schema.webclusters[txn, obj.oid] = obj

        self.log.info('new WebCluster object stored in database:\n{obj}', obj=obj)

        res_obj = obj.marshal()

        await self._session.publish('{}.on_webcluster_created'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_webcluster_created> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    async def delete_webcluster(self, webcluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Delete an web router cluster definition. The web cluster must be in status ``"STOPPED"``.


        :procedure: ``crossbarfabriccenter.webcluster.delete_webcluster`` URI of WAMP procedure to call.
        :event: ``crossbarfabriccenter.webcluster.on_webcluster_deleted`` WAMP event published once the web cluster has been deleted.
        :error: ``wamp.error.invalid_argument`` WAMP error returned when ``webcluster_oid`` was invalid.
        :error: ``crossbar.error.no_such_object`` WAMP error returned when ``webcluster_oid`` was not found.
        :error: ``crossbar.error.not_stopped`` WAMP error returned when web cluster is not in status ``STOPPED``.

        :param webcluster_oid: OID of the Web cluster to delete

        :returns: Deleted router cluster, for example:

            .. code-block:: json

                {
                    "changed": 1598391866736370655,
                    "description": null,
                    "http_access_log": null,
                    "http_client_timeout": null,
                    "http_display_tracebacks": null,
                    "http_hsts": null,
                    "http_hsts_max_age": null,
                    "label": null,
                    "name": "cluster1",
                    "oid": "90d46851-0ba4-4e3d-8d9d-7a117379b212",
                    "owner_oid": "8d6e3068-900a-4fa8-a6f5-0828c8d0ee24",
                    "status": "STOPPED",
                    "tags": null,
                    "tcp_backlog": null,
                    "tcp_interface": null,
                    "tcp_port": 8080,
                    "tcp_shared": true,
                    "tcp_version": null,
                    "tls_ca_certificates": null,
                    "tls_certificate": null,
                    "tls_chain_certificates": null,
                    "tls_ciphers": null,
                    "tls_dhparam": null,
                    "tls_key": null
                }
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}.delete_webcluster(webcluster_oid={webcluster_oid}, details={details})',
                      func=hltype(self.delete_webcluster),
                      webcluster_oid=hlid(webcluster_oid),
                      details=details)

        try:
            oid = uuid.UUID(webcluster_oid)
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
            cluster_obj = self.schema.webclusters[txn, oid]
            if cluster_obj:
                if cluster_obj.owner_oid != caller_oid:
                    raise ApplicationError('wamp.error.not_authorized',
                                           'only owner is allowed to delete router cluster')
                if cluster_obj.status != cluster.STATUS_STOPPED:
                    raise ApplicationError('crossbar.error.not_stopped')
                del self.schema.webclusters[txn, oid]
            else:
                raise ApplicationError('crossbar.error.no_such_object', 'no object with oid {} found'.format(oid))

        cluster_obj.changed = time_ns()
        self.log.info('WebCluster object deleted from database:\n{cluster_obj}', cluster_obj=cluster_obj)

        res_obj = cluster_obj.marshal()

        await self._session.publish('{}.on_webcluster_deleted'.format(self._prefix), res_obj, options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    async def start_webcluster(self, webcluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Start a web cluster.

        :param webcluster_oid: Object ID of web cluster to start.

        :return: Started web cluster, for example:

            .. code-block:: json

                {
                    "changed": 1598395797587541578,
                    "oid": "92f5f4c7-4175-4c72-a0a6-81467c343565",
                    "status": "STARTING",
                    "who": {
                        "authid": "superuser",
                        "authrole": "owner",
                        "session": 2587789023701533
                    }
                }
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(webcluster_oid="{webcluster_oid}", details={details})',
                      func=hltype(self.start_webcluster),
                      webcluster_oid=hlid(webcluster_oid),
                      details=details)

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
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
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no webcluster with oid {} found'.format(webcluster_oid_))

            if webcluster.owner_oid != caller_oid:
                raise ApplicationError('wamp.error.not_authorized', 'only owner is allowed to start a web cluster')

            if webcluster.status not in [cluster.STATUS_STOPPED, cluster.STATUS_PAUSED]:
                emsg = 'cannot start webcluster currently in state {}'.format(
                    cluster.STATUS_BY_CODE[webcluster.status])
                raise ApplicationError('crossbar.error.cannot_start', emsg)

            webcluster.status = cluster.STATUS_STARTING
            webcluster.changed = time_ns()

            self.schema.webclusters[txn, webcluster_oid_] = webcluster

        monitor = WebClusterMonitor(self, webcluster_oid_)
        monitor.start()
        assert webcluster_oid_ not in self._monitors
        self._monitors[webcluster_oid_] = monitor

        webcluster_starting = {
            'oid': str(webcluster.oid),
            'status': cluster.STATUS_BY_CODE[webcluster.status],
            'changed': webcluster.changed,
            'who': {
                'session': details.caller if details else None,
                'authid': details.caller_authid if details else None,
                'authrole': details.caller_authrole if details else None,
            }
        }
        await self._session.publish('{}.on_webcluster_starting'.format(self._prefix),
                                    webcluster_starting,
                                    options=self._PUBOPTS)

        return webcluster_starting

    @wamp.register(None, check_types=True)
    async def stop_webcluster(self, webcluster_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Stop a running web cluster.

        :procedure: ``crossbarfabriccenter.webcluster.stop_webcluster`` URI of WAMP procedure to call.
        :event: ``crossbarfabriccenter.webcluster.on_webcluster_stoppping`` WAMP event published once the web cluster is stopping.
        :error: ``wamp.error.invalid_argument`` WAMP error returned when ``webcluster_oid`` was invalid.
        :error: ``crossbar.error.no_such_object`` WAMP error returned when ``webcluster_oid`` was not found.
        :error: ``crossbar.error.cannot_stop`` WAMP error returned when web cluster is not in status ``RUNNING`` or ``STARTING``.

        :param webcluster_oid: Object ID of web cluster to stop.

        :return: Stopped web cluster, for example:

            .. code-block:: json

                {
                    "changed": 1598395878649535271,
                    "oid": "92f5f4c7-4175-4c72-a0a6-81467c343565",
                    "status": "STOPPING",
                    "who": {
                        "authid": "superuser",
                        "authrole": "owner",
                        "session": 1047738189758144
                    }
                }
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(webcluster_oid={webcluster_oid}, details={details})',
                      webcluster_oid=hlid(webcluster_oid),
                      func=hltype(self.stop_webcluster),
                      details=details)

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin(write=True) as txn:
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no webcluster with oid {} found'.format(webcluster_oid_))

            if webcluster.status not in [cluster.STATUS_STARTING, cluster.STATUS_RUNNING]:
                emsg = 'cannot stop webcluster currently in state {}'.format(cluster.STATUS_BY_CODE[webcluster.status])
                raise ApplicationError('crossbar.error.cannot_stop', emsg)

            webcluster.status = cluster.STATUS_STOPPING
            webcluster.changed = time_ns()

            self.schema.webclusters[txn, webcluster_oid_] = webcluster

        webcluster_stopping = {
            'oid': str(webcluster.oid),
            'status': cluster.STATUS_BY_CODE[webcluster.status],
            'changed': webcluster.changed,
            'who': {
                'session': details.caller if details else None,
                'authid': details.caller_authid if details else None,
                'authrole': details.caller_authrole if details else None,
            }
        }

        await self._session.publish('{}.on_webcluster_stopping'.format(self._prefix),
                                    webcluster_stopping,
                                    options=self._PUBOPTS)

        return webcluster_stopping

    @wamp.register(None, check_types=True)
    def list_webcluster_nodes(self,
                              webcluster_oid: str,
                              return_names: Optional[bool] = None,
                              filter_by_status: Optional[str] = None,
                              details: Optional[CallDetails] = None) -> List[str]:
        """
        List nodes currently associated with the given web cluster.

        :param webcluster_oid: The web cluster to list nodes for.
        :param return_names: Return web cluster node names (WAMP authid) instead of object IDs.
        :param filter_by_status: Filter nodes by this status, eg. ``"online"``.

        :return: List of node IDs of nodes associated with the web cluster, for example:

            .. code-block:: json

                [
                    "3c7584f7-b8db-4e9b-8508-7ab4d573265d",
                    "aa1d67de-d434-4bee-96ec-d0f576c12e02",
                    "b0b36b60-5712-40fd-8ae5-ac1177ea850c",
                    "cf0241bc-b9d9-4b81-a496-5873a74b5f0a"
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
        assert type(webcluster_oid) == str
        assert return_names is None or type(return_names) == bool
        assert filter_by_status is None or type(filter_by_status) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info(
            '{func}(webcluster_oid={webcluster_oid}, return_names={return_names}, filter_by_status={filter_by_status}, details={details})',
            func=hltype(self.list_webcluster_nodes),
            webcluster_oid=hlid(webcluster_oid),
            return_names=hlval(return_names),
            filter_by_status=hlval(filter_by_status),
            details=details)

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        node_oids = []
        with self.db.begin() as txn:
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no webcluster with oid {} found'.format(webcluster_oid_))
            for _, node_oid in self.schema.webcluster_node_memberships.select(txn,
                                                                              from_key=(webcluster_oid_,
                                                                                        uuid.UUID(bytes=b'\0' * 16)),
                                                                              return_values=False):
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
    async def add_webcluster_node(self,
                                  webcluster_oid: str,
                                  node_oid: str,
                                  config: Optional[dict] = None,
                                  details: Optional[CallDetails] = None) -> dict:
        """
        Add a node to a web cluster. The node-to-webcluster association can be configured in ``config``:

        .. code-block:: json

            {
                "parallel": 2,
                "standby": false
            }

        * ``parallel``: The parallelism (in CPU) that the node should receive.
        * ``standby``: Wheather to add this node as a standby node that only takes over work when active nodes fail.

        The web cluster will start and manage ``parallel`` proxy workers on the node.
        When ``standby`` is set (*NOT YET IMPLEMENTED*), the node will not become active
        immediately, but only be used and become active to replace a failed (active) node
        in the cluster.

        :param webcluster_oid: OID of the web cluster to which to add the node.
        :param node_oid: OID of the node to add to the cluster. A node can be added to more than one cluster.

        :return: Added node, for example:

            .. code-block:: json

                {
                    "cluster_oid": "92f5f4c7-4175-4c72-a0a6-81467c343565",
                    "node_oid": "b0b36b60-5712-40fd-8ae5-ac1177ea850c",
                    "parallel": 2,
                    "standby": null
                }
        """
        assert details is None or isinstance(details, CallDetails)

        self.log.info(
            '{func}(webcluster_oid={webcluster_oid}, node_oid={node_oid}, config={config}, details={details})',
            func=hltype(self.list_webcluster_nodes),
            webcluster_oid=hlid(webcluster_oid),
            node_oid=hlid(node_oid),
            config=config,
            details=details)

        config = config or {}
        config['cluster_oid'] = webcluster_oid
        config['node_oid'] = node_oid
        membership = WebClusterNodeMembership.parse(config)

        with self.gdb.begin() as txn:
            node = self.gschema.nodes[txn, membership.node_oid]
            if not node or node.mrealm_oid != self._session._mrealm_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no node with oid {} found'.format(membership.node_oid))

        with self.db.begin(write=True) as txn:
            webcluster = self.schema.webclusters[txn, membership.cluster_oid]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no webcluster with oid {} found'.format(membership.cluster_oid))

            self.schema.webcluster_node_memberships[txn, (membership.cluster_oid, membership.node_oid)] = membership

        res_obj = membership.marshal()
        self.log.info('node added to web cluster:\n{membership}', membership=res_obj)

        await self._session.publish('{}.on_webcluster_node_added'.format(self._prefix), res_obj, options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    async def remove_webcluster_node(self,
                                     webcluster_oid: str,
                                     node_oid: str,
                                     details: Optional[CallDetails] = None) -> dict:
        """
        Remove a node from a web cluster.

        :param webcluster_oid: OID of the web cluster from which to remove the node.
        :param node_oid: OID of the node to remove from the web cluster

        :return: Node removed from web cluster, for example:

            .. code-block:: json

                {
                    "cluster_oid": "92f5f4c7-4175-4c72-a0a6-81467c343565",
                    "node_oid": "cf0241bc-b9d9-4b81-a496-5873a74b5f0a",
                    "parallel": 2,
                    "standby": null
                }
        """
        assert type(webcluster_oid) == str
        assert type(node_oid) == str
        assert details is None or isinstance(details, CallDetails)

        try:
            node_oid_ = uuid.UUID(node_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        self.log.info('{func}(webcluster_oid={webcluster_oid}, node_oid={node_oid}, details={details})',
                      webcluster_oid=hlid(webcluster_oid_),
                      node_oid=hlid(node_oid_),
                      func=hltype(self.remove_webcluster_node),
                      details=details)

        with self.gdb.begin() as txn:
            node = self.gschema.nodes[txn, node_oid_]
            if not node or node.mrealm_oid != self._session._mrealm_oid:
                raise ApplicationError('crossbar.error.no_such_object', 'no node with oid {} found'.format(node_oid_))

        with self.db.begin(write=True) as txn:
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webcluster_oid_))

            membership = self.schema.webcluster_node_memberships[txn, (webcluster_oid_, node_oid_)]
            if not membership:
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no association between node {} and webcluster {} found'.format(node_oid_, webcluster_oid_))

            del self.schema.webcluster_node_memberships[txn, (webcluster_oid_, node_oid_)]

        res_obj = membership.marshal()
        self.log.info('node removed from web cluster:\n{res_obj}', membership=res_obj)

        await self._session.publish('{}.on_webcluster_node_removed'.format(self._prefix),
                                    res_obj,
                                    options=self._PUBOPTS)

        return res_obj

    @wamp.register(None, check_types=True)
    def get_webcluster_node(self, webcluster_oid: str, node_oid: str, details: Optional[CallDetails] = None) -> dict:
        """
        Get information (such as for example parallel degree) for the association
        of a node with a web cluster.

        :param webcluster_oid: Object ID of web cluster to return node association for.
        :param node_oid: Object ID of node to return association for.

        :return: Information for the association of the node with the webcluster, for example:

            .. code-block:: json

                {
                    "cluster_oid": "92f5f4c7-4175-4c72-a0a6-81467c343565",
                    "node_oid": "cf0241bc-b9d9-4b81-a496-5873a74b5f0a",
                    "parallel": 2,
                    "standby": null
                }
        """
        assert type(webcluster_oid) == str
        assert type(node_oid) == str
        assert details is None or isinstance(details, CallDetails)

        try:
            node_oid_ = uuid.UUID(node_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        self.log.info('{func}(webcluster_oid={webcluster_oid}, node_oid={node_oid}, details={details})',
                      webcluster_oid=hlid(webcluster_oid_),
                      node_oid=hlid(node_oid_),
                      func=hltype(self.get_webcluster_node),
                      details=details)

        with self.gdb.begin() as txn:
            node = self.gschema.nodes[txn, node_oid_]
            if not node or node.mrealm_oid != self._session._mrealm_oid:
                raise ApplicationError('crossbar.error.no_such_object', 'no node with oid {} found'.format(node_oid_))

        with self.db.begin() as txn:
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webcluster_oid_))

            membership = self.schema.webcluster_node_memberships[txn, (webcluster_oid_, node_oid_)]
            if not membership:
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no association between node {} and webcluster {} found'.format(node_oid_, webcluster_oid_))

        res_obj = membership.marshal()

        return res_obj

    @wamp.register(None, check_types=True)
    def list_webcluster_services(self,
                                 webcluster_oid: str,
                                 prefix: Optional[str] = None,
                                 details: Optional[CallDetails] = None) -> Dict[str, str]:
        """
        List webservices defined on a webcluster, optionally filtering by prefix.

        :param webcluster_oid: The web cluster for which to list currently defined web services.
        :param prefix: If provided, the path prefix for filtering web services.

        :return: A map with HTTP paths as keys and webservice ID as values, for example:

            .. code-block:: json

                {
                    "/": "92f5f4c7-4175-4c72-a0a6-81467c343565",
                    "info": "92f5f4c7-4175-4c72-a0a6-81467c343565",
                    "settings": "92f5f4c7-4175-4c72-a0a6-81467c343565",
                    "ws": "92f5f4c7-4175-4c72-a0a6-81467c343565"
                }
        """
        assert type(webcluster_oid) == str
        assert prefix is None or type(prefix) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(webcluster_oid={webcluster_oid}, prefix="{prefix}", details={details})',
                      webcluster_oid=hlid(webcluster_oid),
                      prefix=hlval(prefix),
                      func=hltype(self.list_webcluster_services),
                      details=details)

        if prefix:
            raise NotImplementedError('prefix option not yet implemented')

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin() as txn:
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webcluster_oid_))

            res = {}
            # FIXME: 1) to_key and 2) prefix option
            for (_, path), webservice_oid in self.schema.idx_webservices_by_path.select(txn,
                                                                                        from_key=(webcluster_oid_,
                                                                                                  '')):
                res[path] = str(webservice_oid)

            return res

    @wamp.register(None, check_types=True)
    async def add_webcluster_service(self,
                                     webcluster_oid: str,
                                     path: str,
                                     webservice: dict,
                                     details: Optional[CallDetails] = None) -> dict:
        """
        Add a Web service to a Web cluster.

        :param webcluster_oid: Web cluster to which to add the Web service.
        :param path: The path on which to add the webservice.
        :param webservice: Web service definition object.

        :returns: The web service added to the web cluster, for example:

            .. code-block:: json

                {
                    "description": null,
                    "directory": "..",
                    "label": null,
                    "oid": "4411eb80-006a-45a0-8624-52a7ee84d0ce",
                    "options": {
                        "enable_directory_listing": true
                    },
                    "path": "/",
                    "tags": null,
                    "type": "static",
                    "webcluster_oid": "92f5f4c7-4175-4c72-a0a6-81467c343565"
                }
        """
        assert type(webcluster_oid) == str
        assert type(path) == str
        assert type(webservice) == dict
        assert details is None or isinstance(details, CallDetails)

        self.log.info(
            '{func}(webcluster_oid={webcluster_oid}, path={path}, webservice={webservice}, details={details})',
            webcluster_oid=hlid(webcluster_oid),
            path=hlval(path),
            webservice=webservice,
            func=hltype(self.add_webcluster_service),
            details=details)

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
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

        if 'type' not in webservice:
            raise ApplicationError('wamp.error.invalid_argument', 'missing type in webservice')

        webservice_type = webservice['type']
        if webservice_type not in self._WEB_SERVICE_CHECKERS:
            raise ApplicationError('wamp.error.invalid_argument',
                                   'invalid webservice type "{}"'.format(webservice_type))

        if 'path' in webservice:
            assert webservice['path'] == path
            del webservice['path']

        _personality = self._worker.personality
        _check = self._WEB_SERVICE_CHECKERS[webservice_type]
        self.log.info('Checking web service configuration [personality={personality}, check={check}]:\n{webservice}',
                      personality=_personality,
                      check=_check,
                      webservice=pformat(webservice))

        try:
            _check(_personality, webservice)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument',
                                   'invalid webservice configuration for type "{}": {}'.format(webservice_type, e))

        try:
            webservice_obj = WebService.parse(webservice)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_configuration',
                                   'could not parse web cluster configuration ({})'.format(e))

        webservice_obj.oid = uuid.uuid4()
        webservice_obj.path = path
        webservice_obj.webcluster_oid = webcluster_oid_

        with self.db.begin(write=True) as txn:
            webcluster = self.schema.webclusters[txn, webservice_obj.webcluster_oid]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webservice_obj.webcluster_oid))

            if webcluster.owner_oid != caller_oid:
                raise ApplicationError('wamp.error.not_authorized',
                                       'only owner is allowed to add web service to a web cluster')

            if webcluster.status not in [cluster.STATUS_STOPPED, cluster.STATUS_PAUSED]:
                emsg = 'cannot add web service to webcluster currently in state {}'.format(
                    cluster.STATUS_BY_CODE[webcluster.status])
                raise ApplicationError('crossbar.error.cannot_start', emsg)

            self.schema.webservices[txn, webservice_obj.oid] = webservice_obj

            webcluster.changed = time_ns()
            self.schema.webclusters[txn, webcluster.oid] = webcluster

        self.log.info('New WebService object stored in database:\n{webservice_obj}', webservice_obj=webservice_obj)

        res_obj = webservice_obj.marshal()

        await self._session.publish('{}.on_webservice_added'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_webservice_added> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    async def remove_webcluster_service(self,
                                        webcluster_oid: str,
                                        webservice_oid: str,
                                        details: Optional[CallDetails] = None) -> dict:
        """
        Remove the Web service from the Web cluster.

        :param webcluster_oid: Object ID of the web cluster from which to remove the web service.
        :param webservice_oid: Object ID of the web service to remove.

        :return: The web service removed from the web cluster, for example:

            .. code-block:: json

                {
                    "description": null,
                    "label": null,
                    "oid": "96d30fa8-6df2-4888-9845-87db8884a062",
                    "path": "settings",
                    "tags": null,
                    "type": "json",
                    "value": [
                        1,
                        2,
                        3
                    ],
                    "webcluster_oid": "92f5f4c7-4175-4c72-a0a6-81467c343565"
                }
        """
        assert type(webcluster_oid) == str
        assert type(webservice_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info(
            '{klass}.remove_webcluster_service(webcluster_oid={webcluster_oid}, webservice_oid={webservice_oid}, details={details})',
            webcluster_oid=hlid(webcluster_oid),
            webservice_oid=hlid(webservice_oid),
            func=hltype(self.remove_webcluster_service),
            details=details)

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        try:
            webservice_oid_ = uuid.UUID(webservice_oid)
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
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webcluster_oid_))

            if webcluster.owner_oid != caller_oid:
                raise ApplicationError('wamp.error.not_authorized',
                                       'only owner is allowed to remove a web service from a web cluster')

            webservice = self.schema.webservices[txn, webservice_oid_]
            if not webservice:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webservice_oid_))

            del self.schema.webservices[txn, webservice_oid_]

        self.log.info('WebService object removed from database:\n{webservice}', webservice=webservice)

        res_obj = webservice.marshal()

        await self._session.publish('{}.on_webservice_removed'.format(self._prefix), res_obj, options=self._PUBOPTS)

        self.log.info('Management API event <on_webservice_removed> published:\n{res_obj}', res_obj=res_obj)

        return res_obj

    @wamp.register(None, check_types=True)
    def get_webcluster_service(self,
                               webcluster_oid: str,
                               webservice_oid: str,
                               details: Optional[CallDetails] = None) -> dict:
        """
        Get definition of a web service by ID.

        See also the corresponding procedure :meth:`crossbar.master.cluster.webcluster.WebClusterManager.get_webcluster_service_by_path`
        which returns the same information, given HTTP path rather than object ID.

        :param webcluster_oid: The web cluster running the web service to return.
        :param webservice_oid: The web service to return.

        :return: The web service definition, for example:

            .. code-block:: json

                {
                    "description": null,
                    "label": null,
                    "oid": "6cc51192-4259-4640-84cb-ee03b6f92fbf",
                    "path": "info",
                    "tags": null,
                    "type": "nodeinfo",
                    "webcluster_oid": "92f5f4c7-4175-4c72-a0a6-81467c343565"
                }
        """
        assert type(webcluster_oid) == str
        assert type(webservice_oid) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(webcluster_oid={webcluster_oid}, webservice_oid={webservice_oid}, details={details})',
                      webcluster_oid=hlid(webcluster_oid),
                      webservice_oid=hlid(webservice_oid),
                      func=hltype(self.get_webcluster_service),
                      details=details)

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        try:
            webservice_oid_ = uuid.UUID(webservice_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin() as txn:
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webcluster_oid_))

            webservice = self.schema.webservices[txn, webservice_oid_]
            if not webservice:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webservice_oid_))

        return webservice.marshal()

    @wamp.register(None, check_types=True)
    def get_webcluster_service_by_path(self,
                                       webcluster_oid: str,
                                       path: str,
                                       details: Optional[CallDetails] = None) -> dict:
        """
        Get definition of a web service by HTTP path.

        See also the corresponding procedure :meth:`crossbar.master.cluster.webcluster.WebClusterManager.get_webcluster_service`
        which returns the same information, given and object ID rather than HTTP path.

        :param webcluster_oid: The web cluster running the web service to return.
        :param path: HTTP path of web service to return.

        :return: see :meth:`crossbar.master.cluster.webcluster.WebClusterManager.get_webcluster_service`
        """
        assert type(webcluster_oid) == str
        assert type(path) == str
        assert details is None or isinstance(details, CallDetails)

        self.log.info('{func}(webcluster_oid={webcluster_oid}, path="{path}", details={details})',
                      webcluster_oid=hlid(webcluster_oid),
                      path=hlval(path),
                      func=hltype(self.get_webcluster_service_by_path),
                      details=details)

        try:
            webcluster_oid_ = uuid.UUID(webcluster_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid oid "{}"'.format(str(e)))

        with self.db.begin() as txn:
            webcluster = self.schema.webclusters[txn, webcluster_oid_]
            if not webcluster:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no object with oid {} found'.format(webcluster_oid_))

            webservice_oid = self.schema.idx_webservices_by_path[txn, (webcluster_oid_, path)]

            if not webservice_oid:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no webservice for path "{}" found'.format(path))

            webservice = self.schema.webservices[txn, webservice_oid]
            assert webservice

        return webservice.marshal()
