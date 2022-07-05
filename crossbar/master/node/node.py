###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import uuid
import json
import binascii
import pkg_resources
from pprint import pformat

import requests
import txaio

from twisted.internet.defer import DeferredList, inlineCallbacks, Deferred

import zlmdb

from autobahn import wamp
from autobahn import xbr
from autobahn.xbr import make_w3
from autobahn.wamp.types import ComponentConfig, RegisterOptions
from autobahn.wamp.request import Registration
from autobahn.twisted.wamp import ApplicationSession

from crossbar._util import hltype, hlid, hl, hlval
from crossbar.common import checkconfig

from crossbar._util import merge_config
from crossbar.node.node import Node
from crossbar.edge.node import node
from crossbar.master.node.roles import BUILTIN_ROLES
from crossbar.master.mrealm.mrealm import ManagementRealm
from cfxdb.globalschema import GlobalSchema

__all__ = ('FabricServiceNodeManager', 'FabricCenterNode')

_CFC_GLOBAL_REALM = 'crossbar.'


class License(object):
    def __init__(self, license_type):
        assert license_type in [20010]

        self._type = license_type

        if license_type == 20010:
            self._title = 'crossbar Trial'
            self._mrealms = 1
            self._routers = 2
            self._proxies = 2
            self._containers = 4
            self._guests = 4
            self._marketmakers = 1

    @property
    def type(self):
        return self._type

    @property
    def title(self):
        return self._title

    @property
    def mrealms(self):
        return self._mrealms

    @property
    def routers(self):
        return self._routers

    @property
    def containers(self):
        return self._containers

    @property
    def guests(self):
        return self._guests

    @property
    def proxies(self):
        return self._proxies

    @property
    def marketmakers(self):
        return self._marketmakers

    def marshal(self):
        obj = {
            'type': self._type,
            'title': self._title,
            'mrealms': self._mrealms,
            'routers': self._routers,
            'containers': self._containers,
            'guests': self._guests,
            'proxies': self._proxies,
            'marketmakers': self._marketmakers,
        }
        return obj

    def __str__(self):
        return '{}'.format(self.marshal())


class FabricServiceNodeManager(ApplicationSession):
    """
    CFC Node manager. This is responsible for starting and stopping
    management realms
    """

    log = txaio.make_logger()

    def __init__(self, config, reactor, personality, node):
        # base ctor
        super(ApplicationSession, self).__init__(config=config)

        self._reactor = reactor
        self.personality = personality
        self._node = node

        # database and schema
        self._db = None
        self._schema = None

        # XBR API Hub
        self._xbr = None

    async def onJoin(self, details: ComponentConfig):

        # handles to controller database and schema (already initialized/attached in node)
        #
        ready = self.config.extra['ready']
        cbdir = self.config.extra['cbdir']
        config = self.config.extra.get('database', {})

        # create database and attach tables to database slots
        #
        dbpath = config.get('path', '.db-controller')
        assert type(dbpath) == str
        dbpath = os.path.join(cbdir, dbpath)

        maxsize = config.get('maxsize', 128 * 2**20)
        assert type(maxsize) == int
        # allow maxsize 128kiB to 128GiB
        assert maxsize >= 128 * 1024 and maxsize <= 128 * 2**30

        self.log.info('{klass} starting [dbpath={dbpath}, maxsize={maxsize}]',
                      klass=self.__class__.__name__,
                      dbpath=hlid(dbpath),
                      maxsize=hlid(maxsize))

        # self._db = zlmdb.Database(dbpath=dbpath, maxsize=maxsize, readonly=False, sync=True, context=self)
        self._db = zlmdb.Database.open(dbpath=dbpath, maxsize=maxsize, readonly=False, sync=True, context=self)
        self._db.__enter__()
        self._schema = GlobalSchema.attach(self._db)

        # initialize all currently existing mrealms
        try:
            await self._initialize_mrealms()
        except Exception:
            self.log.failure()
            raise

        # expose api on this object fo CFC clients
        domains = [(_CFC_GLOBAL_REALM, self.register)]
        for prefix, register in domains:
            registrations = await register(self, prefix=prefix, options=RegisterOptions(details_arg='details'))
            for reg in registrations:
                if type(reg) == Registration:
                    self.log.info('Registered CFC Global Realm "{realm}" API <{proc}>',
                                  proc=reg.procedure,
                                  realm=self._realm)
                else:
                    self.log.error('Error: <{}>'.format(reg.value.args[0]))

        # we are ready to roll
        self.log.info('{note} {klass}',
                      note=hl('Ok, master node "{}" booted and ready!'.format(self._node._node_id),
                              color='red',
                              bold=True),
                      klass=hltype(self.onJoin))

        ready.callback(self)

    def onLeave(self, details):
        pass

    async def _initialize_mrealms(self, parallel=False):

        self._router_realms = {}
        self._container_workers = {}

        with self._db.begin() as txn:
            mrealms = list(self._schema.mrealms.select(txn, return_keys=False))

        if mrealms:
            self.log.info('Initializing {cnt_mrealms} management realms (parallel={parallel}) ..',
                          cnt_mrealms=hlval(len(mrealms)),
                          parallel=hlval(parallel))
            if parallel:
                dl = []
                for mrealm in mrealms:
                    dl.append(self._initialize_mrealm(mrealm))
                if dl:
                    await DeferredList(dl)
            else:
                for mrealm in mrealms:
                    await self._initialize_mrealm(mrealm)
            self.log.info('Ok, completed initializing {cnt_mrealms} management realms.',
                          cnt_mrealms=hlval(len(mrealms)))
        else:
            self.log.info('No management realms no initialize. Done.')

    async def _initialize_mrealm(self, mrealm):
        """
        Initializes a single management realm:

        1. start a respective realm on the router worker of this master node. Currently there is only one
           router worker statically configured (named "cfrouter1").
        2. start a couple of roles on the management realm (see BUILTIN_ROLES)
        3.

        :param mrealm: The management realm to initialize.
        :type mrealm: :class:`cfxdb.mrealm.management_realm.ManagementRealm`

        :return:
        """

        self.log.debug('{klass}._initialize_mrealm(mrealm={mrealm})', klass=self.__class__.__name__, mrealm=mrealm)
        # WAMP realm name of the realm to start
        realm_name = mrealm.name

        # router and container worker for realm to start
        router_id = mrealm.cf_router_worker or 'cfrouter1'
        container_id = mrealm.cf_container_worker or 'cfcontainer1'

        self.log.info(
            hl('Initializing management realm "{}" [router_id="{}", container_id="{}"] ..'.format(
                realm_name, router_id, container_id),
               color='red',
               bold=True))

        # start the management realm and roles on the configured router worker
        if realm_name not in self._router_realms:
            realm_config = {
                'name': realm_name,
                'options': {
                    'enable_meta_api': True,

                    # FIXME: enabling this will break stopping and restarting an mrealm, as the
                    # procedures registered eg by the RouterServiceAgent session will stick around!
                    'bridge_meta_api': False,
                }
            }
            realm_id = realm_name
            await self.call('crossbar.worker.{}.start_router_realm'.format(router_id), realm_id, realm_config)

            for role_id in ['owner-role', 'backend-role', 'node-role', 'public-role']:
                await self.call('crossbar.worker.{}.start_router_realm_role'.format(router_id), realm_id, role_id,
                                BUILTIN_ROLES[role_id])

            self._router_realms[realm_name] = True
        else:
            self.log.warn('Management realm "{realm_name}" already initialized (skipped starting realm)',
                          realm_name=realm_name)

        # start the configured container worker (if not yet started)
        if container_id not in self._container_workers:
            container_options = {
                "pythonpath": [".."],
                "expose_shared": True,
                "expose_controller": True,
                # "shutdown": "shutdown-on-last-component-stopped",
                "shutdown": "shutdown-manual",
                # "restart": "restart-on-failed"
                "restart": "restart-always"
            }
            await self.call('crossbar.start_worker', container_id, 'container', container_options)

            self._container_workers[container_id] = {}
        else:
            self.log.warn(
                'Management realm "{realm_name}" backend container "{container_id}" already running (skipped starting container)',
                realm_name=realm_name,
                container_id=container_id)

        # start the management realm backend in the configured container worker
        component_id = realm_name
        if component_id not in self._container_workers[container_id]:
            mrealm_backend_extra = {
                'mrealm': str(mrealm.oid),
                'database': {
                    # the mrealm database path contains the mrealm UUID
                    'dbfile': os.path.join(self.config.extra['cbdir'], '.db-mrealm-{}'.format(mrealm.oid)),

                    # hard-code max mrealm database size to 2GB
                    # https://github.com/crossbario/crossbar/issues/235
                    'maxsize': 2**30 * 2,
                },
                'controller-database': {
                    # forward controller database parameters, so that the mrealm backend can _also_ open
                    # the controller database (read-only)
                    'dbfile': self._db.dbpath,
                    'maxsize': self._db.maxsize,
                },
            }
            component_config = {
                'type': 'class',
                'classname': 'crossbar.master.mrealm.MrealmController',
                'realm': realm_name,
                'transport': {
                    # we connect back to the master router over UDS/RawSocket/CBOR
                    'type': 'rawsocket',
                    'endpoint': {
                        'type': 'unix',
                        'path': 'sock1'
                    },
                    'serializer': 'cbor',
                },
                'extra': mrealm_backend_extra
            }
            await self.call('crossbar.worker.{}.start_component'.format(container_id), component_id, component_config)

            self._container_workers[container_id][component_id] = True
        else:
            self.log.warn(
                'Management realm "{realm_name}" backend component "{component_id}" already running (skipped starting container component)',
                realm_name=realm_name,
                component_id=component_id)

        self.log.info('{note} {func}',
                      note=hl('Ok, management realm "{}" initialized!'.format(realm_name), color='red', bold=True),
                      func=hltype(self._initialize_mrealm))

    @wamp.register(None)
    async def activate_realm(self, mrealm_obj, details=None):
        mrealm = ManagementRealm.parse(mrealm_obj)
        self.log.info('Calling initialize_realm with ({})'.format(mrealm.name))
        await self._initialize_mrealm(mrealm)

    @wamp.register(None)
    async def deactivate_realm(self, mrealm_obj, details=None):
        mrealm = ManagementRealm.parse(mrealm_obj)

        realm_name = mrealm.name
        router_id = 'cfrouter1'
        container_id = 'cfcontainer1'

        if realm_name in self._router_realms:
            self.log.info('Deactivate realm ({}) - start'.format(realm_name))

            # stop the management component
            if True:
                await self.call('crossbar.worker.{}.stop_component'.format(container_id), realm_name)
                del self._container_workers[container_id][realm_name]

            # stop the router roles
            if True:
                for role_id in ['owner-role', 'backend-role', 'node-role', 'public-role']:
                    await self.call('crossbar.worker.{}.stop_router_realm_role'.format(router_id), realm_name, role_id)

            #  stop the realm
            if True:
                await self.call('crossbar.worker.{}.stop_router_realm'.format(router_id), realm_name)
                del self._router_realms[realm_name]

            self.log.info('Management realm "{realm_name}" deactivated (complete)', realm_name=realm_name)
        else:
            self.log.warn('Management realm "{realm_name}" not active (skipped deactivation)', realm_name=realm_name)


class FabricCenterNode(node.FabricNode):
    """
    Crossbar.io Master node personality.
    """
    DEFAULT_CONFIG_PATH = 'master/node/config.json'
    """
    Builtin default master node configuration.
    """
    def __init__(self, personality, cbdir=None, reactor=None, native_workers=None, options=None):
        node.FabricNode.__init__(self, personality, cbdir, reactor, native_workers, options)

        # master node embedded DB
        self._db = None
        self._schema = None

        # Web3 blockchain connection (if configured)
        self._w3 = None

        # the node license under which this master node will be running (instance of :class:License)
        self._license = None

    def load_config(self, configfile=None):
        """
        Load the node configuration of CFC itself. The base node configuration
        is built into CFC, but can be overridden (partially) and extended
        by providing a regular, local node configuration file.

        When such a file exists:

        - and it contains a controller section, these take precedence over
        the builtin values.
        - and it contains a workers section (a list of workers), these are
        _added_ to the builtin workers.
        """
        config_source = Node.CONFIG_SOURCE_EMPTY

        # 1/4: load builtin master node configuration as default
        #
        config_path = pkg_resources.resource_filename('crossbar', self.DEFAULT_CONFIG_PATH)
        with open(config_path) as f:
            config = json.load(f)

        # no need to check the builtin config (at run-time)
        # self.personality.check_config(self.personality, config)

        # remember config source
        config_source += Node.CONFIG_SOURCE_DEFAULT
        self.log.info('Built-in master node configuration loaded')

        # 2/4: allow extending/overriding the node configuration
        # with a local master node configuration file (eg for TLS setup)
        if configfile:
            config_path = os.path.abspath(os.path.join(self._cbdir, configfile))
            with open(config_path) as f:
                custom_config = json.load(f)

            # as an overriding config file does not need to be a fully valid config in itself,
            # do _not_ check it ..
            # self.personality.check_config(self.personality, custom_config)

            # .. instead, we merge the config from the local file into the already
            # loaded default config (see above)
            config = merge_config(config, custom_config)

            # remember config source
            config_source += Node.CONFIG_SOURCE_LOCALFILE
            self.log.info('Local master node configuration merged from "{config_path}"',
                          config_path=hlval(config_path))

        # 3/4: allow extending/overriding the node configuration
        # with a remote master node configuration file from blockchain/IPFS
        if config.get('controller', {}).get('blockchain', None):
            blockchain_config = config['controller']['blockchain']
            gateway_config = blockchain_config['gateway']

            # setup Web3 connection from blockchain gateway configuration
            self._w3 = make_w3(gateway_config)

            # configure new Web3 connection as provider for XBR
            xbr.setProvider(self._w3)

            if self._w3.isConnected():
                self.log.info('Connected to Ethereum network {network} at gateway "{gateway_url}"',
                              network=self._w3.net.version,
                              gateway_url=gateway_config['http'])

                # try to find node by node public key on-chain
                xbr_node_id = xbr.xbrnetwork.functions.getNodeByKey(self.key.public_key()).call()
                if xbr_node_id != b'\x00' * 16:
                    assert (len(xbr_node_id) == 16)

                    # get node domain, type, configuration and license as stored on-chain
                    xbr_node_domain = xbr.xbrnetwork.functions.getNodeDomain(xbr_node_id).call()
                    xbr_node_type = xbr.xbrnetwork.functions.getNodeType(xbr_node_id).call()
                    xbr_node_config = xbr.xbrnetwork.functions.getNodeConfig(xbr_node_id).call()

                    # FIXME: for testing use hard-coded "trial license" (no. 20010)
                    xbr_node_license = 20010
                    # xbr_node_license = xbr.xbrnetwork.functions.getNodeLicense(xbr_node_id).call()

                    self.log.info(
                        'Node is configured for XBR (xbr_node_id="{xbr_node_id}", xbr_node_domain="{xbr_node_domain}", xbr_node_type="{xbr_node_type}", xbr_node_license="{xbr_node_license}", xbr_node_config="{xbr_node_config}")',
                        xbr_node_id=hlid('0x' + binascii.b2a_hex(xbr_node_id).decode()),
                        xbr_node_domain=hlid('0x' + binascii.b2a_hex(xbr_node_domain).decode()),
                        xbr_node_type=hlid(xbr_node_type),
                        xbr_node_config=hlid(xbr_node_config),
                        xbr_node_license=hlid(xbr_node_license))

                    self._license = License(xbr_node_license)
                    self.log.info('Node is registered in the XBR network with license type={license}',
                                  license=self._license.type)

                    # if a (hash of a) configuration is set on-chain for the master node, fetch the
                    # configuration content for the hash from IPFS
                    if xbr_node_config:
                        if 'IPFS_GATEWAY_URL' in os.environ:
                            ipfs_gateway_url = os.environ['IPFS_GATEWAY_URL']
                            self.log.info(
                                'Using explicit IPFS gateway URL {ipfs_gateway_url} from environment variable IPFS_GATEWAY_URL',
                                ipfs_gateway_url=hlid(ipfs_gateway_url))
                        else:
                            ipfs_gateway_url = 'https://ipfs.infura.io:5001'
                            self.log.info('Using default IPFS Infura gateway URL {ipfs_gateway_url}',
                                          ipfs_gateway_url=hlid(ipfs_gateway_url))

                        ipfs_config_url = '{}/api/v0/cat?arg={}&encoding=json'.format(
                            ipfs_gateway_url, xbr_node_config)
                        resp = requests.get(ipfs_config_url)

                        xbr_node_config_data = resp.json()

                        from pprint import pprint
                        pprint(xbr_node_config_data)

                        self.personality.check_config(self.personality, xbr_node_config_data)

                        if 'controller' not in xbr_node_config_data:
                            xbr_node_config_data['controller'] = {}

                        if 'id' not in xbr_node_config_data['controller']:
                            xbr_node_config_data['controller']['id'] = str(uuid.UUID(bytes=xbr_node_id))
                            self.log.info('Deriving node ID {node_id} from XBR network node ID',
                                          node_id=hlid(xbr_node_config_data['controller']['id']))
                        else:
                            self.log.info('Setting node ID {node_id} from XBR network node configuration',
                                          node_id=hlid(xbr_node_config_data['controller']['id']))

                        self._config = xbr_node_config_data

                        self.log.info('Node configuration loaded from XBR network (xbr_node_id="{xbr_node_id}")',
                                      xbr_node_id=hlid('0x' + binascii.b2a_hex(xbr_node_id).decode()))
                    else:
                        self.log.debug(
                            'There is no node configuration stored in XBR network (xbr_node_id="{xbr_node_id}")',
                            xbr_node_id=hlid('0x' + binascii.b2a_hex(xbr_node_id).decode()))

                    config_source = self.CONFIG_SOURCE_XBRNETWORK
                else:
                    self.log.warn('Could not find node public key on blockchain yet')
            else:
                self.log.warn('Could not connect to Ethereum blockchain')

        # 4/4: check and set the final merged master node configuration
        #
        self.personality.check_config(self.personality, config)
        self._config = config

        self.log.debug('Master node config after (effective after merge):\n{config}', config=pformat(config))

        return config_source, config_path

    @inlineCallbacks
    def start(self, node_id=None):
        self.log.info('{note} [{method}]',
                      note=hl('Starting node (initialize master-node personality) ..', color='green', bold=True),
                      method=hltype(FabricCenterNode.start))
        res = yield node.FabricNode.start(self, node_id)
        return res

    @inlineCallbacks
    def boot(self):
        self.log.info('Booting node {method}', method=hltype(FabricCenterNode.boot))

        # get fabric controller configuration
        #
        controller_config_extra = self._config.get('controller', {}).get('fabric-center', {})

        # apply node config
        #
        yield self.boot_from_config(self._config)
        self._local_config_applied = True

        # start node manager
        #
        extra = {
            'cbdir': self._cbdir,
            'database': controller_config_extra.get('database', {}),
            'ready': Deferred(),
        }
        config = ComponentConfig(self._realm, extra)
        self._bridge_session = FabricServiceNodeManager(config=config,
                                                        reactor=self._reactor,
                                                        personality=self.personality,
                                                        node=self)
        router = self._router_factory.get(self._realm)
        self._router_session_factory.add(self._bridge_session, router, authrole='trusted')
        yield extra['ready']

    def _add_extra_controller_components(self, controller_options):
        self.log.debug('FabricCenterNode._add_extra_controller_components: no extra controller components added')

    def _set_shutdown_triggers(self, controller_options):
        # CFC workers are not supposed to exit with error, so we shutdown when a worker
        # exits with error (and rely on systemd to restart CFC) - OR if we explicitly
        # ask the node to shutdown (eg CTRL-C it)

        # self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_SHUTDOWN_REQUESTED]
        # self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT]
        # self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR]
        self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_LAST_WORKER_EXIT]

    def _add_worker_role(self, worker_auth_role, options):
        worker_role_config = {
            # each (native) worker is authenticated under a worker-specific authrole
            "name":
            worker_auth_role,
            "permissions": [
                # the worker requires these permissions to work:
                {
                    # management API provided by the worker. note that the worker management API is provided under
                    # the URI prefix "crossbar.worker.<worker_id>". note that the worker is also authenticated
                    # under authrole <worker_auth_role> on realm "crossbar"
                    "uri": worker_auth_role,
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
                },
                {
                    # controller procedure called by the worker (to check for controller status)
                    "uri": "crossbar.get_status",
                    "match": "exact",
                    "allow": {
                        "call": True,
                        "register": False,
                        "publish": False,
                        "subscribe": False
                    },
                    "disclose": {
                        "caller": True,
                        "publisher": True
                    },
                    "cache": True
                }
            ]
        }
        # if configured to expose the controller connection within the worker (to make it available
        # in user code such as dynamic authenticators and router/container components), also add
        # permissions to actually use the (local) node management API
        if options.get('expose_controller', True):
            vendor_permissions = {
                "uri": "crossbar.",
                "match": "prefix",
                "allow": {
                    "call": True,
                    "register": False,
                    "publish": False,
                    "subscribe": True
                },
                "disclose": {
                    "caller": True,
                    "publisher": True
                },
                "cache": True
            }
            worker_role_config["permissions"].append(vendor_permissions)
            vendor_permissions = {
                "uri": "crossbarfabriccenter.",
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
            }
            worker_role_config["permissions"].append(vendor_permissions)

        self._router_factory.add_role(self._realm, worker_role_config)

        self.log.info('worker-specific role "{authrole}" added on node management router realm "{realm}" {func}',
                      func=hltype(self._add_worker_role),
                      authrole=hlid(worker_role_config['name']),
                      realm=hlid(self._realm))
