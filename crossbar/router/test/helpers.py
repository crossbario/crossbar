#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.twisted.wamp import WampRawSocketClientFactory, ApplicationSessionFactory
# from autobahn.twisted.wamp import WampWebSocketClientFactory
from autobahn.wamp.types import ComponentConfig

from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceAgent
from crossbar.worker.types import RouterRealm
from crossbar.router.role import RouterRoleStaticAuth
from crossbar.router.protocol import WampRawSocketServerFactory, WampWebSocketServerFactory
from crossbar.router.unisocket import UniSocketServerFactory

from twisted.test.iosim import connect, FakeTransport


def make_router():
    """
    Make a router, and return it and a RawSocket factory.
    """
    # create a router factory
    router_factory = RouterFactory('node1', 'worker1', None)

    # create a router session factory
    session_factory = RouterSessionFactory(router_factory)

    # Create a new WebSocket factory
    websocket_server_factory = WampWebSocketServerFactory(session_factory, '.', {}, None)

    # Create a new RawSocket factory
    rawsocket_server_factory = WampRawSocketServerFactory(session_factory, {})

    # Create a new UniSocket factory
    server_factory = UniSocketServerFactory(websocket_factory_map={'/': websocket_server_factory},
                                            rawsocket_factory=rawsocket_server_factory)

    return router_factory, server_factory, session_factory


def add_realm_to_router(router_factory, session_factory, realm_name='default', realm_options={}):

    opts = dict(realm_options)
    opts.update({'name': realm_name})

    # start a realm
    realm = RouterRealm(None, None, opts)
    router = router_factory.start_realm(realm)

    extra = {}
    session_config = ComponentConfig(realm_name, extra)
    realm.session = RouterServiceAgent(session_config, router)

    # allow everything
    default_permissions = {
        'uri': '',
        'match': 'prefix',
        'allow': {
            'call': True,
            'register': True,
            'publish': True,
            'subscribe': True
        }
    }

    router = router_factory.get(realm_name)
    router.add_role(RouterRoleStaticAuth(router, 'anonymous', default_permissions=default_permissions))

    session_factory.add(realm.session, router, authrole='trusted')

    return router


def make_router_and_realm(realm_name='default'):

    router_factory, server_factory, session_factory = make_router()
    router = add_realm_to_router(router_factory, session_factory, realm_name)
    return router, server_factory, session_factory


def connect_application_session(server_factory, MyApplicationSession, component_config=None):
    """
    Connect an ApplicationSession class to the given server factory.
    """
    application_session_factory = ApplicationSessionFactory(component_config)
    application_session_factory.session = MyApplicationSession

    client_factory = WampRawSocketClientFactory(application_session_factory)
    # client_factory = WampWebSocketClientFactory(application_session_factory)

    server_protocol = server_factory.buildProtocol(None)
    client_protocol = client_factory.buildProtocol(None)

    server_transport = FakeTransport(server_protocol, True)
    client_transport = FakeTransport(client_protocol, False)

    pump = connect(server_protocol, server_transport, client_protocol, client_transport, debug=False)

    return client_protocol._session, pump
