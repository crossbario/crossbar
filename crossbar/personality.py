#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import time
from collections.abc import Mapping
from typing import Dict

import txaio

txaio.use_twisted()

import crossbar
from crossbar.common import checkconfig
from crossbar.node import node
from crossbar.node.worker import RouterWorkerProcess, ContainerWorkerProcess, WebSocketTesteeWorkerProcess
from crossbar.worker.router import RouterController
from crossbar.worker import transport
from crossbar.worker.container import ContainerController
from crossbar.worker.testee import WebSocketTesteeController
from crossbar.worker.proxy import ProxyController, ProxyWorkerProcess
from crossbar.webservice import base
from crossbar.webservice import wsgi, rest, longpoll, websocket, misc, static, archive, wap, catalog
from crossbar.interfaces import IRealmStore, IInventory
from crossbar.router.realmstore import RealmStoreMemory
from crossbar.router.inventory import Inventory


def do_nothing(*args, **kw):
    return


def _check_proxy_config(personality, config):
    pass


def default_native_workers():
    factory = dict()
    factory['router'] = {
        'class': RouterWorkerProcess,
        'worker_class': RouterController,

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
    factory['container'] = {
        'class': ContainerWorkerProcess,
        'worker_class': ContainerController,

        # check a whole container worker configuration item (including components, ..)
        'checkconfig_item': checkconfig.check_container,

        # only check container worker options
        'checkconfig_options': checkconfig.check_container_options,
        'logname': 'Container',
        'topics': {
            'starting': 'crossbar.on_container_starting',
            'started': 'crossbar.on_container_started',
        }
    }
    factory['websocket-testee'] = {
        'class': WebSocketTesteeWorkerProcess,
        'worker_class': WebSocketTesteeController,

        # check a whole websocket testee worker configuration item
        'checkconfig_item': checkconfig.check_websocket_testee,

        # only check websocket testee worker worker options
        'checkconfig_options': checkconfig.check_websocket_testee_options,
        'logname': 'WebSocketTestee',
        'topics': {
            'starting': 'crossbar.on_websocket_testee_starting',
            'started': 'crossbar.on_websocket_testee_started',
        }
    }
    factory['proxy'] = {
        'process_class': ProxyWorkerProcess,
        'class': ProxyWorkerProcess,
        'worker_class': ProxyController,

        # FIXME: check a whole proxy worker configuration item (including transports, backends, ..)
        'checkconfig_item': _check_proxy_config,
        # FIXME: only check proxy worker options
        'checkconfig_options': do_nothing,  # checkconfig.check_native_worker_options,
        'logname': 'Proxy',
        'topics': {
            'starting': 'crossbar.on_proxy_starting',
            'started': 'crossbar.on_proxy_started',
        }
    }
    return factory


def create_realm_store(personality, factory, config) -> IRealmStore:
    """
    Factory for creating realm stores (which store call queues and event history).

    .. code-block:: json

        "store": {
            "type": "memory",   // type of realm store: "memory"
            "limit": 100,       // global default for limit on call queues / event history
            "call-queue": [
                {
                    "uri": "com.example.compute",
                    "match": "exact",
                    "limit": 1000   // procedure specific call queue limit
                }
            ],
            "event-history": [
                {
                    "uri": "com.example.oncounter",
                    "match": "exact",
                    "limit": 1000   // topic specific history limit
                }
            ]
        }

    :param personality: Node personality
    :type personality: :class:`crossbar.personality

    :param factory: Router factory
    :type factory: :class:`crossbar.router.router.RouterFactory`

    :param config: Realm store configuration item.
    :type config: dict
    """
    if not isinstance(config, Mapping):
        raise Exception('invalid type {} for realm store configuration item'.format(type(config)))

    if 'type' not in config:
        raise Exception('missing store type in realm store configuration item')

    store_type = config['type']

    if store_type not in personality.REALM_STORES:
        raise Exception('invalid or unavailable store type {}'.format(store_type))

    store_class = personality.REALM_STORES[store_type]
    store = store_class(personality, factory, config)

    return store


def create_realm_inventory(personality, factory, config) -> IInventory:
    """

    .. code-block:: json

        {
            "version": 2,
            "workers": [
                {
                    "type": "router",
                    "realms": [
                        {
                            "name": "realm1",
                            "inventory": {
                                "type": "wamp.eth",
                                "catalogs": [
                                    {
                                        "name": "pydefi",
                                        "filename": "../schema/trading.bfbs"
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

    :param personality: Node personality
    :type personality: :class:`crossbar.personality`

    :param factory: Router factory
    :type factory: :class:`crossbar.router.router.RouterFactory`

    :param config: FbsRepository configuration
    :type config: dict, for example:
        .. code-block:: json
            {
                "type": "wamp.eth",
                "catalogs": [
                    {
                        "name": "pydefi",
                        "filename": "../schema/trading.bfbs"
                    }
                ]
            }

    :return: A new realm inventory object.
    """
    inventory = Inventory.from_config(personality, factory, config)
    return inventory


_TITLE = "Crossbar.io"

# sudo apt install figlet && figlet -f smslant "Crossbar FX"
_BANNER = r"""
    :::::::::::::::::
          :::::          _____                 __              _
    :::::   :   :::::   / ___/______  ___ ___ / /  ___ _____  (_)__
    :::::::   :::::::  / /__/ __/ _ \(_-<(_-</ _ \/ _ `/ __/ / / _ \
    :::::   :   :::::  \___/_/  \___/___/___/_.__/\_,_/_/ (_)_/\___/
          :::::
    :::::::::::::::::   {title} v{version} [{build}]

    Copyright (c) 2013-{year} Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
"""

_DESC = """Crossbar.io is a decentralized data plane for XBR/WAMP based application
service and data routing, built on Crossbar.io OSS."""


class Personality(object):
    """
    Software personality for Crossbar.io OSS.

    This is a policy class that configures various parts of Crossbar.io's
    behavior.
    """

    log = txaio.make_logger()

    NAME = 'standalone'

    TITLE = _TITLE

    DESC = _DESC

    BANNER = _BANNER.format(title=_TITLE,
                            version=crossbar.__version__,
                            build=crossbar.__build__,
                            year=time.strftime('%Y'))

    LEGAL = ('crossbar', 'LEGAL')
    LICENSE = ('crossbar', 'LICENSE')
    LICENSE_FOR_API = ('crossbar', 'LICENSE-FOR-API')
    LICENSES_OSS = ('crossbar', 'LICENSES-OSS')

    # a list of directories to serach Jinja2 templates for
    # rendering various web resources. this must be a list
    # of _pairs_ to be used with pkg_resources.resource_filename()!
    TEMPLATE_DIRS = [('crossbar', 'webservice/templates')]

    WEB_SERVICE_CHECKERS: Dict[str, object] = {
        'none': None,
        'path': checkconfig.check_web_path_service_path,
        'redirect': checkconfig.check_web_path_service_redirect,
        'resource': checkconfig.check_web_path_service_resource,
        'reverseproxy': checkconfig.check_web_path_service_reverseproxy,
        'nodeinfo': checkconfig.check_web_path_service_nodeinfo,
        'json': checkconfig.check_web_path_service_json,
        'cgi': checkconfig.check_web_path_service_cgi,
        'wsgi': checkconfig.check_web_path_service_wsgi,
        'static': checkconfig.check_web_path_service_static,
        'websocket': checkconfig.check_web_path_service_websocket,
        'websocket-reverseproxy': checkconfig.check_web_path_service_websocket_reverseproxy,
        'longpoll': checkconfig.check_web_path_service_longpoll,
        'caller': checkconfig.check_web_path_service_caller,
        'publisher': checkconfig.check_web_path_service_publisher,
        'webhook': checkconfig.check_web_path_service_webhook,
        'archive': archive.RouterWebServiceArchive.check,
        'wap': wap.RouterWebServiceWap.check,
        'catalog': catalog.RouterWebServiceCatalog.check,
    }

    WEB_SERVICE_FACTORIES: Dict[str, object] = {
        'none': base.RouterWebService,  # renders to 404
        'path': base.RouterWebServiceNestedPath,
        'redirect': base.RouterWebServiceRedirect,
        'resource': base.RouterWebServiceTwistedWeb,
        'reverseproxy': base.RouterWebServiceReverseWeb,
        'nodeinfo': misc.RouterWebServiceNodeInfo,
        'json': misc.RouterWebServiceJson,
        'cgi': misc.RouterWebServiceCgi,
        'wsgi': wsgi.RouterWebServiceWsgi,
        'static': static.RouterWebServiceStatic,
        'websocket': websocket.RouterWebServiceWebSocket,
        'websocket-reverseproxy': websocket.RouterWebServiceWebSocketReverseProxy,
        'longpoll': longpoll.RouterWebServiceLongPoll,
        'caller': rest.RouterWebServiceRestCaller,
        'publisher': rest.RouterWebServiceRestPublisher,
        'webhook': rest.RouterWebServiceWebhook,
        'archive': archive.RouterWebServiceArchive,
        'wap': wap.RouterWebServiceWap,
        'catalog': catalog.RouterWebServiceCatalog,
    }

    EXTRA_AUTH_METHODS: Dict[str, object] = {}

    REALM_STORES: Dict[str, object] = {'memory': RealmStoreMemory}

    Node = node.Node
    NodeOptions = node.NodeOptions

    WorkerKlasses = [RouterController, ContainerController, WebSocketTesteeController]

    native_workers = default_native_workers()

    create_router_transport = transport.create_router_transport

    create_realm_store = create_realm_store

    create_realm_inventory = create_realm_inventory

    RouterWebTransport = transport.RouterWebTransport

    RouterTransport = transport.RouterTransport

    #
    # configuration related functions
    #

    # config
    check_config = checkconfig.check_config

    # config files
    upgrade_config_file = checkconfig.upgrade_config_file
    convert_config_file = checkconfig.convert_config_file
    check_config_file = checkconfig.check_config_file

    # top level
    check_controller = checkconfig.check_controller
    check_controller_options = checkconfig.check_controller_options
    check_node_key = checkconfig.check_node_key
    check_worker = checkconfig.check_worker

    # native workers
    check_manhole = checkconfig.check_manhole

    # router worker
    check_router = checkconfig.check_router
    check_router_options = checkconfig.check_router_options
    check_router_realm = checkconfig.check_router_realm
    check_router_realm_role = checkconfig.check_router_realm_role
    check_router_component = checkconfig.check_router_component

    # container worker
    check_container = checkconfig.check_container
    check_container_options = checkconfig.check_container_options
    check_container_component = checkconfig.check_container_component

    # guest worker
    check_guest = checkconfig.check_guest

    # testee worker
    check_websocket_testee = checkconfig.check_websocket_testee
    check_websocket_testee_options = checkconfig.check_websocket_testee_options

    # listening transports
    check_router_transport = checkconfig.check_router_transport
    check_listening_endpoint = checkconfig.check_listening_endpoint
    check_listening_transport_universal = checkconfig.check_listening_transport_universal
    check_listening_transport_websocket = checkconfig.check_listening_transport_websocket
    check_listening_transport_web = checkconfig.check_listening_transport_web

    # web services
    check_paths = checkconfig.check_paths
    check_web_path_service = checkconfig.check_web_path_service

    # authentication
    check_transport_auth = checkconfig.check_transport_auth
    check_transport_cookie = checkconfig.check_transport_cookie

    # connecting transports
    check_connecting_endpoint = checkconfig.check_connecting_endpoint
    check_connecting_transport = checkconfig.check_connecting_transport

    # check_listening_transport_websocket = checkconfig.check_listening_transport_websocket
    check_listening_transport_rawsocket = checkconfig.check_listening_transport_rawsocket
    # check_listening_transport_universal = checkconfig.check_listening_transport_universal
    # check_listening_transport_web = checkconfig.check_listening_transport_web
    check_listening_transport_mqtt = checkconfig.check_listening_transport_mqtt
    check_listening_transport_flashpolicy = checkconfig.check_listening_transport_flashpolicy
    check_listening_transport_websocket_testee = checkconfig.check_listening_transport_websocket_testee
    check_listening_transport_stream_testee = checkconfig.check_listening_transport_stream_testee

    check_listening_endpoint_onion = checkconfig.check_listening_endpoint_onion
