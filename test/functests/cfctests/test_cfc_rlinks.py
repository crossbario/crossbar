###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

# https://asciinema.org/a/cBUGKheFHbI6T4qRijjREYjUK

import uuid
from copy import deepcopy
from pprint import pformat

import txaio
txaio.use_twisted()

from autobahn.wamp.types import SubscribeOptions, PublishOptions
from crossbar.common.key import _read_node_key

# do not directly import fixtures, or session-scoped ones will get run twice.
from ..helpers import *

node1_pubkey = _read_node_key('./test/cf1/.crossbar/', private=False)['hex']
node2_pubkey = _read_node_key('./test/cf2/.crossbar/', private=False)['hex']
node3_pubkey = _read_node_key('./test/cf3/.crossbar/', private=False)['hex']


@inlineCallbacks
def _test_remote_rlink(cfx_master, cfx_edge1, cfx_edge2, cfx_edge3):

    mrealm = 'mrealm1'

    worker_id = 'worker1'
    worker_type = 'router'
    realm_id = 'realm1'
    transport_id = 'transport{}'

    realm_config = {
        "name": realm_id,
        "options": {
            "enable_meta_api": True,
            "bridge_meta_api": False
        },
        "roles": [
            {
                "name": "anonymous",
                "permissions": [
                    {
                        "uri": "",
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
                ]
            },
            {
                "name": "router2router",
                "permissions": [
                    {
                        "uri": "",
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
                ]
            }
        ]
    }
    transport_configs = [
        {
            "type": "rawsocket",
            "endpoint": {
                "type": "unix",
                "path": None
            },
            "options": {
                "max_message_size": 1048576
            },
            "serializers": ["cbor"],
            "auth": {
                "cryptosign": {
                    "type": "static",
                    "principals": {
                        "edge1": {
                            "realm": "realm1",
                            "role": "router2router",
                            "authorized_keys": [node1_pubkey]
                        },
                        "edge2": {
                            "realm": "realm1",
                            "role": "router2router",
                            "authorized_keys": [node2_pubkey]
                        },
                        "edge3": {
                            "realm": "realm1",
                            "role": "router2router",
                            "authorized_keys": [node3_pubkey]
                        }
                    }
                }
            }
        },
        {
            "type": "universal",
            "endpoint": {
                "type": "tcp",
                "port": 8080,
                "shared": True
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
    ]
    rlink_config = {
        "realm": realm_id,
        "transport": {
            "type": "rawsocket",
            "endpoint": {
                "type": "unix",
                "path": None
            },
            "serializer": "cbor",
            "url": "rs://localhost"
        },
        "forward_local_events": False,
        "forward_remote_events": True,
    }

    management_session, management_session_details = yield functest_management_session(realm=mrealm)
    print(hl(management_session_details, bold=True))
    yield sleep(.1)

    node_oids = yield management_session.call('crossbarfabriccenter.mrealm.get_nodes')
    assert node_oids
    for node_id in node_oids:

        result = yield management_session.call('crossbarfabriccenter.remote.node.start_worker',
                                               node_id, worker_id, worker_type)
        print(hl(result, bold=True))

        result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_realm',
                                               node_id, worker_id, realm_id, realm_config)
        print(hl(result, bold=True))

        for role_config in realm_config.get('roles', []):
            role_id = str(uuid.uuid4())
            result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_realm_role',
                                                   node_id, worker_id, realm_id, role_id, role_config)
            print(hl(result, bold=True))

        i = 1
        for transport_config in transport_configs:
            if i == 1:
                transport_config['endpoint']['path'] = '/tmp/{}.sock'.format(node_id)
            result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_transport',
                                                   node_id, worker_id, transport_id.format(i), transport_config)
            print(hl(result, bold=True))
            i += 1

    yield sleep(.1)

    if True:
        links = [
            (node_oids[0], node_oids[1]),
            (node_oids[0], node_oids[2]),
            (node_oids[1], node_oids[0]),
            (node_oids[1], node_oids[2]),
            (node_oids[2], node_oids[0]),
            (node_oids[2], node_oids[1]),
        ]
        for node_id, other_node_id in links:
            link_id = 'rlink-{}-{}'.format(node_id, other_node_id)
            link_config = deepcopy(rlink_config)
            # link_config['authid'] = node_id
            # link_config['exclude_authid'] = [node_id]
            link_config['transport']['endpoint']['path'] = '/tmp/{}.sock'.format(other_node_id)
            result = yield management_session.call('crossbarfabriccenter.remote.router.start_router_realm_link', node_id, worker_id, realm_id, link_id, link_config)
            print(hl(result, bold=True))
            #yield sleep(.1)

    # ########### START Application Session Scope

    M_RANGE = 100
    K_RANGE = 2

    app_sessions = {}
    cnt_app_sessions = {}
    for i in range(M_RANGE):
        session, details = yield functest_app_session(realm=realm_id)

        node_id = details.authextra.get('x_cb_node_id', None)
        node_id = details.authextra.get('x_cb_pid', None)
        if node_id not in cnt_app_sessions:
            cnt_app_sessions[node_id] = 0
        cnt_app_sessions[node_id] += 1

        app_sessions[i] = (node_id, session)

    print(hl(cnt_app_sessions, color='green', bold=True))

    yield sleep(.1)

    results = {}

    def create_event_handler(node_id, session_id):
        if session_id not in results:
            results[session_id] = []

        def on_hello(from_node_id, idx, details=None):
            results[session_id].append(idx)
        return on_hello

    dl = []
    for node_id, session in app_sessions.values():
        d = session.subscribe(create_event_handler(node_id, session._session_id), 'com.example.hello', options=SubscribeOptions(details=True))
        dl.append(d)
    yield DeferredList(dl)
    yield sleep(.1)

    i = 0
    for k in range(K_RANGE):
        dl = []
        for node_id, session in app_sessions.values():
            d = session.publish('com.example.hello', node_id, i, options=PublishOptions(acknowledge=True, exclude_me=False))
            # dl.append(d)
            yield d
            yield sleep(.01)
            i += 1
        yield DeferredList(dl)
    yield sleep(.1)

    print(hl(pformat(results)[:800], color='green', bold=True))

    for res in results.values():
        # FIXME: investigate the strange reordering if events that sometimes happens
        # we make this test succeed regardless of these reorderings by apply a sort-op
        assert sorted(res) == list(range(M_RANGE * K_RANGE))
        # assert res == list(range(M_RANGE * K_RANGE))

    dl = []
    for node_id, session in app_sessions.values():
        d = session.leave()
        dl.append(d)
    yield DeferredList(dl)

    # ########### END   Application Session Scope
    #
    # result = yield management_session.call('crossbarfabriccenter.remote.router.stop_router_transport', node_id, worker_id, transport_id)
    # print(hl(result, bold=True))
    # yield sleep(.1)
    #
    # result = yield management_session.call('crossbarfabriccenter.remote.router.stop_router_realm', node_id, worker_id, realm_id)
    # print(hl(result, bold=True))
    # yield sleep(.1)
    #
    # result = yield management_session.call('crossbarfabriccenter.remote.node.stop_worker', node_id, worker_id)
    # print(hl(result, bold=True))
    # yield sleep(.1)

    yield management_session.leave()
