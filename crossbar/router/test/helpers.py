#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
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
    router_factory = RouterFactory(None, None)

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


def add_realm_to_router(router_factory, session_factory, realm_name=u'default',
                        realm_options={}):

    opts = dict(realm_options)
    opts.update({u'name': realm_name})

    # start a realm
    realm = RouterRealm(None, None, opts)
    router = router_factory.start_realm(realm)

    extra = {}
    session_config = ComponentConfig(realm_name, extra)
    realm.session = RouterServiceAgent(session_config, router)

    # allow everything
    default_permissions = {
        u'uri': u'',
        u'match': u'prefix',
        u'allow': {
            u'call': True,
            u'register': True,
            u'publish': True,
            u'subscribe': True
        }
    }

    router = router_factory.get(realm_name)
    router.add_role(RouterRoleStaticAuth(router, 'anonymous', default_permissions=default_permissions))

    session_factory.add(realm.session, router, authrole=u'trusted')

    return router


def make_router_and_realm(realm_name=u'default'):

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

    pump = connect(server_protocol, server_transport, client_protocol,
                   client_transport, debug=False)

    return client_protocol._session, pump
