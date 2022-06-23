###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import re
import uuid

import txaio
txaio.use_twisted()

from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep

import treq

# do not directly import fixtures, or session-scoped ones will get run twice.
from ..helpers import *

from autobahn.wamp.exception import ApplicationError



@inlineCallbacks
def _prepare(management_session, mrealm_id):
    nodes = {
        'node1': 'a35a92c77d5cc0d289749a895f91981834a78a2a47c8275081c587d1886f4528',
        'node2': '8ec0d95b623c59d606283c0f698b3e189329433c5f34d46769ee2707ef277d9d',
        'node3': '28d8696911a11399f29576ca10ac38a2d499f1264ccbea36d395184eb3049675',
    }

    new_mrealm = {
        'name': mrealm_id
    }

    result = yield management_session.call('crossbarfabriccenter.mrealm.get_mrealm_by_name', mrealm_id)
    if not result:
        result = yield management_session.call('crossbarfabriccenter.mrealm.create_mrealm', mrealm_id)
    print(hl(result, bold=True))

    yield sleep(.1)
    for node_id, pubkey in nodes.items():
        while True:
            try:
                result = yield management_session.call('crossbarfabriccenter.mrealm.pair_node', pubkey, mrealm_id, node_id, {})
                print(hl(result, bold=True))
            except ApplicationError as e:
                if e.error != 'fabric.node-already-paired':
                    raise
                else:
                    result = yield management_session.call('crossbarfabriccenter.mrealm.unpair_node_by_pubkey', pubkey)
                    print(hl(result, bold=True))
            break


# @pytest.mark.skip('FIXME: RuntimeError: Timeout waiting for crossbar to start')

@inlineCallbacks
def test_remote_container(cfx_master, cfx_edge1):
    mrealm = 'mrealm1'
    management_session, _ = yield functest_management_session(realm=mrealm)
    yield sleep(.1)

    # yield _prepare(management_session, mrealm)
    # yield sleep(.1)

    node_oids = yield management_session.call('crossbarfabriccenter.mrealm.get_nodes')
    assert node_oids
    node_id = node_oids[0]

    worker_id = 'worker1'
    worker_type = 'container'
    result = yield management_session.call('crossbarfabriccenter.remote.node.start_worker', node_id, worker_id, worker_type)
    print(hl(result, bold=True))
    yield sleep(.1)

    result = yield management_session.call('crossbarfabriccenter.remote.node.stop_worker', node_id, worker_id)
    print(hl(result, bold=True))
    yield sleep(.1)

    yield management_session.leave()


@inlineCallbacks
def test_remote_router(cfx_master, cfx_edge1, realm_config=None, transport_config=None):

    mrealm = 'mrealm1'

    worker_id = 'worker1'
    worker_type = 'router'
    realm_id = 'realm1'
    transport_id = 'transport1'

    management_session, _ = yield functest_management_session(realm=mrealm)
    yield sleep(.1)

    # yield _prepare(management_session, mrealm)
    # yield sleep(.1)

    node_oids = yield management_session.call('crossbarfabriccenter.mrealm.get_nodes')
    assert node_oids
    node_id = node_oids[0]

    result = yield management_session.call('crossbarfabriccenter.remote.node.start_worker', node_id, worker_id, worker_type)
    print(hl(result, bold=True))
    yield sleep(.1)

    if not realm_config:
        realm_config = {
            "name": realm_id,
            "options": {
                "enable_meta_api": True,
                "bridge_meta_api": False
            },
            "roles": [{
                "name": "anonymous",
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
                        "caller": False,
                        "publisher": False
                    },
                    "cache": True
                }]
            }]
        }

    result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_realm', node_id, worker_id, realm_id, realm_config)
    print(hl(result, bold=True))
    yield sleep(.1)

    for role_config in realm_config.get('roles', []):
        role_id = str(uuid.uuid4())
        result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_realm_role', node_id, worker_id, realm_id, role_id, role_config)
        print(hl(result, bold=True))

    if not transport_config:
        transport_config = {
            "type": "universal",
            "endpoint": {
                "type": "tcp",
                "port": 8080
            },
            "rawsocket": {},
            "websocket": {
                "ws": {
                    "type": "websocket"
                }
            },
            "web": {
                "paths": {
                    "/": {
                        "type": "nodeinfo"
                    }
                }
            }
        }

    result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_transport', node_id, worker_id, transport_id, transport_config)
    print(hl(result, bold=True))
    yield sleep(.1)

    ########### START Application Session Scope

    app_session1, _ = yield functest_app_session(realm=realm_id)
    app_session2, _ = yield functest_app_session(realm=realm_id)
    yield sleep(.1)

    def add2(a, b):
        result = a + b
        print(hl('add2({}, {}) -> {}'.format(a, b, result), color='green', bold=True))
        return result

    reg = yield app_session1.register(add2, 'com.example.add2')

    a, b = 2, 3
    result = yield app_session2.call('com.example.add2', a, b)
    print(hl('got add2({}, {}) result: {}'.format(a, b, result), color='green', bold=True))

    yield reg.unregister()
    yield app_session1.leave()

    ########### END   Application Session Scope

    result = yield management_session.call('crossbarfabriccenter.remote.router.stop_router_transport', node_id, worker_id, transport_id)
    print(hl(result, bold=True))
    yield sleep(.1)

    result = yield management_session.call('crossbarfabriccenter.remote.router.stop_router_realm', node_id, worker_id, realm_id)
    print(hl(result, bold=True))
    yield sleep(.1)

    result = yield management_session.call('crossbarfabriccenter.remote.node.stop_worker', node_id, worker_id)
    print(hl(result, bold=True))
    yield sleep(.1)

    yield management_session.leave()


@inlineCallbacks
def test_remote_web(cfx_master, cfx_edge1, transport_config=None):

    mrealm = 'mrealm1'

    worker_id = 'worker1'
    worker_type = 'router'
    transport_id = 'transport1'

    management_session, _ = yield functest_management_session(realm=mrealm)
    yield sleep(.1)

    node_oids = yield management_session.call('crossbarfabriccenter.mrealm.get_nodes')
    assert node_oids
    node_id = node_oids[0]

    result = yield management_session.call('crossbarfabriccenter.remote.node.start_worker', node_id, worker_id, worker_type)
    print(hl(result, bold=True))
    yield sleep(.1)

    if not transport_config:
        transport_config = {
            "type": "web",
            "endpoint": {
                "type": "tcp",
                "port": 8080
            },
            "paths": {
                "/": {
                    "type": "nodeinfo"
                }
            }
        }

    result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_transport', node_id, worker_id, transport_id, transport_config)
    print(hl(result, bold=True))
    yield sleep(.1)

    response = yield treq.get('http://localhost:8080')
    result = yield response.text()
    assert '<title>Crossbar.io application router</title>' in result
    assert '<td>Node Started</td>' in result
    print(hl(result[:80], color='green', bold=True))

    result = yield management_session.call('crossbarfabriccenter.remote.router.stop_router_transport', node_id, worker_id, transport_id)
    print(hl(result, bold=True))
    yield sleep(.1)

    result = yield management_session.call('crossbarfabriccenter.remote.node.stop_worker', node_id, worker_id)
    print(hl(result, bold=True))
    yield sleep(.1)

    yield management_session.leave()


@inlineCallbacks
def test_remote_web_service(cfx_master, cfx_edge1, transport_config=None):

    # test configuration
    mrealm = 'mrealm1'
    worker_id = 'worker1'
    worker_type = 'router'
    transport_id = 'transport1'

    # connect management session
    management_session, _ = yield functest_management_session(realm=mrealm)
    yield sleep(.1)

    # get first node
    node_oids = yield management_session.call('crossbarfabriccenter.mrealm.get_nodes')
    assert node_oids
    node_id = node_oids[0]

    # start a worker
    result = yield management_session.call('crossbarfabriccenter.remote.node.start_worker', node_id, worker_id, worker_type)
    print(hl(result, bold=True))
    yield sleep(.1)

    # start a web transport
    if not transport_config:
        transport_config = {
            "type": "web",
            "endpoint": {
                "type": "tcp",
                "port": 8080
            },
            "paths": {}
        }
    result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_transport', node_id, worker_id, transport_id, transport_config)
    print(hl(result, bold=True))
    yield sleep(.1)

    # check that we get a 404 since we haven't got any web services configured
    response = yield treq.get('http://localhost:8080/info')
    result = yield response.text()
    assert '<title>404 - No Such Resource</title>' in result
    print(hl(result[:80], color='green', bold=True))

    # now dynamically add a "nodeinfo" resource to "/info"
    path = 'info'
    config = {
        'type': 'nodeinfo'
    }
    result = yield management_session.call('crossbarfabriccenter.remote.router.start_web_transport_service', node_id, worker_id, transport_id, path, config)
    print(hl(result, bold=True))
    yield sleep(.1)

    # check that we get the expected response
    response = yield treq.get('http://localhost:8080/info')
    result = yield response.text()
    assert '<title>Crossbar.io application router</title>' in result
    assert '<td>Node Started</td>' in result
    print(hl(result[:80], color='green', bold=True))

    # stop the web service
    result = yield management_session.call('crossbarfabriccenter.remote.router.stop_web_transport_service', node_id, worker_id, transport_id, path)
    print(hl(result, bold=True))

    # check that we get a 404 since we have stopped the web service
    response = yield treq.get('http://localhost:8080/info')
    result = yield response.text()
    assert '<title>404 - No Such Resource</title>' in result
    print(hl(result[:80], color='green', bold=True))

    # stop the web transport
    result = yield management_session.call('crossbarfabriccenter.remote.router.stop_router_transport', node_id, worker_id, transport_id)
    print(hl(result, bold=True))
    yield sleep(.1)

    # stop the worker
    result = yield management_session.call('crossbarfabriccenter.remote.node.stop_worker', node_id, worker_id)
    print(hl(result, bold=True))
    yield sleep(.1)

    yield management_session.leave()
