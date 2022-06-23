###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import txaio
txaio.use_twisted()

from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep

import treq

# do not directly import fixtures, or session-scoped ones will get run twice.
from ..helpers import *


@inlineCallbacks
def test_remote_web_service_shared(cfx_master, cfx_edge1, transport_config=None):

    # test configuration
    N = 4
    mrealm = 'mrealm1'
    worker_id = 'worker{}'
    worker_type = 'router'
    transport_id = 'transport1'

    # connect management session
    management_session, _ = yield functest_management_session(realm=mrealm)
    yield sleep(.1)

    # get first node
    node_oids = yield management_session.call('crossbarfabriccenter.mrealm.get_nodes')
    assert node_oids
    node_id = node_oids[0]

    if not transport_config:
        transport_config = {
            "type": "web",
            "endpoint": {
                "type": "tcp",
                "port": 8080,
                "shared": True,
            },
            "paths": {
                "/": {
                    "type": "nodeinfo"
                }
            }
        }
    for i in range(N):
        _worker_id = worker_id.format(i)

        # start a worker
        result = yield management_session.call('crossbarfabriccenter.remote.node.start_worker', node_id, _worker_id, worker_type)
        print(hl(result, bold=True))

        # start a web transport
        result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_transport', node_id, _worker_id, transport_id, transport_config)
        print(hl(result, bold=True))
    yield sleep(.1)

    # FIXME: get rid of this shit noise (also https://twistedmatrix.com/trac/ticket/9235)
    # Starting factory _HTTP11ClientFactory(<function HTTPConnectionPool._newConnection.<locals>.quiescentCallback at 0x7fbfcb094c80>, <HostnameEndpoint localhost:8080>)
    # Stopping factory _HTTP11ClientFactory(<function HTTPConnectionPool._newConnection.<locals>.quiescentCallback at 0x7fbfcb041ea0>, <HostnameEndpoint localhost:8080>)
    results = {}
    for i in range(N * 16):
        response = yield treq.get('http://localhost:8080/', persistent=False)
        result = yield response.text()
        for line in result.splitlines():
            line = line.strip()
            if 'router worker with PID' in line:
                line = line.split('PID')[-1].strip()
                if line not in results:
                    results[line] = 0
                results[line] += 1

    print(hl(results, color='green', bold=True))
    assert len(results) == N

    # stop the workers
    for i in range(N):
        result = yield management_session.call('crossbarfabriccenter.remote.node.stop_worker', node_id, worker_id.format(i))
        print(hl(result, bold=True))
    yield sleep(.1)

    yield management_session.leave()


@inlineCallbacks
def test_remote_web_service_multiple_shared(cfx_master, cfx_edge1, cfx_edge2, cfx_edge3, transport_config=None):

    # test configuration
    N = 4
    mrealm = 'mrealm1'
    worker_id = 'worker{}'
    worker_type = 'router'
    transport_id = 'transport1'

    # connect management session
    management_session, _ = yield functest_management_session(realm=mrealm)
    yield sleep(.1)

    # get first node
    node_oids = yield management_session.call('crossbarfabriccenter.mrealm.get_nodes')
    for node_id in node_oids:
        if not transport_config:
            transport_config = {
                "type": "web",
                "endpoint": {
                    "type": "tcp",
                    "port": 8080,
                    "shared": True,
                },
                "paths": {
                    "/": {
                        "type": "nodeinfo"
                    }
                }
            }
        for i in range(N):
            _worker_id = worker_id.format(i)

            # start a worker
            result = yield management_session.call('crossbarfabriccenter.remote.node.start_worker', node_id, _worker_id, worker_type)
            print(hl(result, bold=True))

            # start a web transport
            result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_transport', node_id, _worker_id, transport_id, transport_config)
            print(hl(result, bold=True))

    yield sleep(2)

    # FIXME: get rid of this shit noise (also https://twistedmatrix.com/trac/ticket/9235)
    # Starting factory _HTTP11ClientFactory(<function HTTPConnectionPool._newConnection.<locals>.quiescentCallback at 0x7fbfcb094c80>, <HostnameEndpoint localhost:8080>)
    # Stopping factory _HTTP11ClientFactory(<function HTTPConnectionPool._newConnection.<locals>.quiescentCallback at 0x7fbfcb041ea0>, <HostnameEndpoint localhost:8080>)
    results = {}
    for i in range(N * 16 * len(node_oids)):
        response = yield treq.get('http://localhost:8080/', persistent=False)
        result = yield response.text()
        for line in result.splitlines():
            line = line.strip()
            if 'router worker with PID' in line:
                line = line.split('PID')[-1].strip()
                if line not in results:
                    results[line] = 0
                results[line] += 1

    print(hl(results, color='green', bold=True))
    assert len(results) == N * len(node_oids)

    # stop the workers
    for node_id in node_oids:
        for i in range(N):
            result = yield management_session.call('crossbarfabriccenter.remote.node.stop_worker', node_id, worker_id.format(i))
            print(hl(result, bold=True))
    yield sleep(.1)

    yield management_session.leave()
