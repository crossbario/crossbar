##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from typing import Dict
from collections.abc import Mapping, Sequence
from pprint import pformat

import six
import txaio

from crossbar.personality import Personality as CrossbarPersonality
from crossbar.personality import default_native_workers
from crossbar.common import checkconfig
from crossbar.node.node import NodeOptions
from crossbar.node.worker import RouterWorkerProcess

from crossbar.edge.node.node import FabricNode
from crossbar.edge.worker.realmstore import RealmStoreDatabase
from crossbar.edge.worker.router import ExtRouterController
from crossbar.edge.worker.hostmonitor import HostMonitor, HostMonitorProcess
from crossbar.edge.worker.xbrmm import MarketplaceController, MarketplaceControllerProcess
from crossbar.edge.webservice import RouterWebServicePairMe


def do_nothing(*args, **kw):
    return


# check blockchain configuration item (can be part of controller and market maker configurations)
def check_blockchain(personality, blockchain):
    # Examples:
    #
    # "blockchain": {
    #     "type": "ethereum",
    #     "gateway": {
    #         "type": "auto"
    #     }
    # }
    #
    # "blockchain": {
    #     "type": "ethereum",
    #     "gateway": {
    #         "type": "user",
    #         "http": "http://127.0.0.1:8545"
    #         "websocket": "ws://127.0.0.1:8545"
    #     },
    #     "from_block": 1,
    #     "chain_id": 5777
    # }
    #
    # "blockchain": {
    #     "type": "ethereum",
    #     "gateway": {
    #         "type": "infura",
    #         "network": "ropsten",
    #         "key": "${INFURA_PROJECT_ID}",
    #         "secret": "${INFURA_PROJECT_SECRET}"
    #     },
    #     "from_block": 6350652,
    #     "chain_id": 3
    # }
    checkconfig.check_dict_args(
        {
            'id': (False, [six.text_type]),
            'type': (True, [six.text_type]),
            'gateway': (True, [Mapping]),
            'key': (False, [six.text_type]),
            'from_block': (False, [int]),
            'chain_id': (False, [int]),
        }, blockchain, "blockchain configuration item {}".format(pformat(blockchain)))

    if blockchain['type'] not in ['ethereum']:
        raise checkconfig.InvalidConfigException('invalid type "{}" in blockchain configuration'.format(
            blockchain['type']))

    gateway = blockchain['gateway']
    if 'type' not in gateway:
        raise checkconfig.InvalidConfigException(
            'missing type in gateway item "{}" of blockchain configuration'.format(pformat(gateway)))

    if gateway['type'] not in ['infura', 'user', 'auto']:
        raise checkconfig.InvalidConfigException(
            'invalid type "{}" in gateway item of blockchain configuration'.format(gateway['type']))

    if gateway['type'] == 'infura':
        checkconfig.check_dict_args(
            {
                'type': (True, [six.text_type]),
                'network': (True, [six.text_type]),
                'key': (True, [six.text_type]),
                'secret': (True, [six.text_type]),
            }, gateway, "blockchain gateway configuration {}".format(pformat(gateway)))

        # allow to set value from environment variable
        gateway['key'] = checkconfig.maybe_from_env('blockchain.gateway["infura"].key',
                                                    gateway['key'],
                                                    hide_value=True)
        gateway['secret'] = checkconfig.maybe_from_env('blockchain.gateway["infura"].secret',
                                                       gateway['secret'],
                                                       hide_value=True)

    elif gateway['type'] == 'user':
        checkconfig.check_dict_args(
            {
                'type': (True, [six.text_type]),
                'http': (True, [six.text_type]),
                # 'websocket': (True, [six.text_type]),
            },
            gateway,
            "blockchain gateway configuration {}".format(pformat(gateway)))

    elif gateway['type'] == 'auto':
        checkconfig.check_dict_args({
            'type': (True, [six.text_type]),
        }, gateway, "blockchain gateway configuration {}".format(pformat(gateway)))

    else:
        # should not arrive here
        raise Exception('logic error')


# check database configuration item (can be part of controller, markets worker and market maker configurations)
def check_database(personality, database):
    checkconfig.check_dict_args(
        {
            'type': (True, [six.text_type]),
            'path': (True, [six.text_type]),
            'maxsize': (False, six.integer_types),
        }, database, "database configuration")

    if database['type'] not in ['cfxdb']:
        raise checkconfig.InvalidConfigException('invalid type "{}" in database configuration'.format(
            database['type']))

    if 'maxsize' in database:
        # maxsize must be between 1MB and 1TB
        if database['maxsize'] < 2**20 or database['maxsize'] > 2**40:
            raise checkconfig.InvalidConfigException(
                'invalid maxsize {} in database configuration - must be between 1MB and 1TB'.format(
                    database['maxsize']))


def check_controller_fabric(personality, fabric):
    """
    Check controller Fabric configuration override (which essentially is only
    for debugging purposes or for people running Crossbar.io Service on-premise)

    :param fabric: The Fabric configuration to check.
    :type fabric: dict
    """
    if not isinstance(fabric, Mapping):
        raise checkconfig.InvalidConfigException(
            "'fabric' in controller configuration must be a dictionary ({} encountered)\n\n".format(type(fabric)))

    for k in fabric:
        if k not in ['transport', 'heartbeat']:
            raise checkconfig.InvalidConfigException(
                "encountered unknown attribute '{}' in 'fabric' in controller configuration".format(k))

    if 'transport' in fabric:
        checkconfig.check_connecting_transport(personality, fabric['transport'])

    if 'heartbeat' in fabric:
        heartbeat = fabric['heartbeat']
        checkconfig.check_dict_args(
            {
                'startup_delay': (False, [int, float]),
                'heartbeat_period': (False, [int, float]),
                'include_system_stats': (False, [bool]),
                'send_workers_heartbeats': (False, [bool]),
                'aggregate_workers_heartbeats': (False, [bool]),
            }, heartbeat, "heartbeat configuration: {}".format(pformat(heartbeat)))


def check_controller(personality, controller, ignore=[]):
    res = checkconfig.check_controller(personality, controller, ['fabric', 'blockchain', 'enable_docker'] + ignore)

    if 'fabric' in controller:
        check_controller_fabric(personality, controller['fabric'])

    if 'blockchain' in controller:
        check_blockchain(personality, controller['blockchain'])

    if 'enable_docker' in controller:
        enable_docker = controller['enable_docker']
        if type(enable_docker) != bool:
            raise checkconfig.InvalidConfigException('invalid type "{}" for "enable_docker" in controller'.format(
                type(enable_docker)))

    return res


def check_controller_options(personality, options, ignore=[]):
    return checkconfig.check_controller_options(personality, options, ignore)


def check_hostmonitor_options(personality, options):
    checkconfig.check_native_worker_options(personality, options, ignore=['interval', 'monitors'])

    # polling interval of sensors in ms
    interval = options.get('interval', 500)
    if type(interval) not in six.integer_types:
        raise checkconfig.InvalidConfigException(
            'invalid type "{}" for "interval" in host monitor configuration (must be an integer for ms)'.format(
                type(interval)))

    monitors = options.get('monitors', {})
    if not isinstance(monitors, Mapping):
        raise checkconfig.InvalidConfigException(
            'invalid type "{}" for "monitors" in host monitor configuration (must be a dict)'.format(type(monitors)))
    for monitor in monitors:
        # FIXME: check if we know the monitor, and monitor
        # specific configuration is valid
        pass


# check native worker options of market maker workers
def check_markets_worker_options(personality, options):
    checkconfig.check_native_worker_options(personality, options, ignore=[])


# check market maker configuration items (as part of market maker workers)
def check_market_maker(personality, maker):
    maker = dict(maker)
    checkconfig.check_dict_args(
        {
            'id': (True, [six.text_type]),
            'key': (True, [six.text_type]),
            'database': (True, [Mapping]),
            'connection': (True, [Mapping]),
            'blockchain': (False, [Mapping]),
        }, maker, "market maker configuration {}".format(pformat(maker)))

    check_database(personality, dict(maker['database']))

    checkconfig.check_dict_args({
        'realm': (True, [six.text_type]),
        'transport': (True, [Mapping]),
    }, dict(maker['connection']), "market maker connection configuration")
    checkconfig.check_connecting_transport(personality, dict(maker['connection']['transport']))

    if 'blockchain' in maker:
        check_blockchain(personality, maker['blockchain'])


# check native worker configuration of maker maker workers
def check_markets_worker(personality, config):

    for k in config:
        if k not in ['id', 'type', 'options', 'makers']:
            raise checkconfig.InvalidConfigException(
                'encountered unknown attribute "{}" in XBR markets worker configuration'.format(k))

    if 'id' in config:
        checkconfig.check_id(config['id'])

    if 'options' not in config:
        raise checkconfig.InvalidConfigException('missing attribute "database" in XBR markets worker configuration')

    check_markets_worker_options(personality, config['options'])

    if 'extra' not in config['options']:
        raise checkconfig.InvalidConfigException(
            'missing attribute "options.extra" in XBR markets worker configuration')

    extra = config['options']['extra']

    if 'database' not in extra:
        raise checkconfig.InvalidConfigException(
            'missing attribute "options.extra.database" in XBR markets worker configuration')

    check_database(personality, extra['database'])

    if 'blockchain' not in extra:
        raise checkconfig.InvalidConfigException(
            'missing attribute "options.extra.blockchain" in XBR markets worker configuration')

    check_blockchain(personality, extra['blockchain'])

    makers = config.get('makers', [])

    if not isinstance(makers, Sequence):
        raise checkconfig.InvalidConfigException("'makers' items must be lists ({} encountered)\n\n{}".format(
            type(makers), pformat(config)))

    for maker in makers:
        check_market_maker(personality, maker)


_native_workers = default_native_workers()

# Override existing worker type: router workers
_native_workers.update({
    'router': {
        'class': RouterWorkerProcess,
        'worker_class': ExtRouterController,

        # check a whole router worker configuration item (including realms, transports, ..)
        'checkconfig_item': checkconfig.check_router,

        # only check router worker options
        'checkconfig_options': checkconfig.check_router_options,
        'logname': 'Router',
        'topics': {
            'starting': 'crossbar.on_router_starting',
            'started': 'crossbar.on_router_started',
        }
    }
})

# New worker type: host monitor
_native_workers.update({
    'hostmonitor': {
        'process_class': HostMonitor,
        'class': HostMonitorProcess,
        'worker_class': HostMonitor,

        # FIXME: check a whole hostmonitor configuration item
        'checkconfig_item': do_nothing,
        # FIXME: only check hostmonitor worker options
        'checkconfig_options': check_hostmonitor_options,
        'logname': 'Hostmonitor',
        'topics': {
            'starting': 'crossbar.on_hostmonitor_starting',
            'started': 'crossbar.on_hostmonitor_started',
        }
    }
})

# New worker type: XBR Market Maker ("xbrmm")
_native_workers.update({
    'xbrmm': {
        'process_class': MarketplaceController,
        'class': MarketplaceControllerProcess,
        'worker_class': MarketplaceController,
        'checkconfig_item': check_markets_worker,
        'checkconfig_options': check_markets_worker_options,
        'logname': 'XBRMM',
        'topics': {
            'starting': 'crossbar.on_xbrmm_starting',
            'started': 'crossbar.on_xbrmm_started',
        }
    }
})


class Personality(CrossbarPersonality):

    log = txaio.make_logger()

    NAME = 'edge'

    TEMPLATE_DIRS = [('crossbar', 'edge/webservice/templates')] + CrossbarPersonality.TEMPLATE_DIRS

    WEB_SERVICE_CHECKERS: Dict[str, object] = {
        'pairme': RouterWebServicePairMe.check,
        **CrossbarPersonality.WEB_SERVICE_CHECKERS
    }

    WEB_SERVICE_FACTORIES: Dict[str, object] = {
        'pairme': RouterWebServicePairMe,
        **CrossbarPersonality.WEB_SERVICE_FACTORIES
    }

    REALM_STORES: Dict[str, object] = {'cfxdb': RealmStoreDatabase, **CrossbarPersonality.REALM_STORES}

    check_controller = check_controller
    check_controller_options = check_controller_options

    check_market_maker = check_market_maker

    Node = FabricNode
    NodeOptions = NodeOptions

    native_workers = _native_workers
