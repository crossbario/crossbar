###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

# https://asciinema.org/a/cBUGKheFHbI6T4qRijjREYjUK

import json

from twisted.internet import reactor
from autobahn.twisted.util import sleep
from autobahn.twisted.component import Component

import uuid
import pytest_twisted
from copy import deepcopy
from pprint import pformat

import txaio
txaio.use_twisted()

from autobahn.wamp.types import SubscribeOptions, PublishOptions
from crossbar.common.key import _read_node_key
from twisted.internet.defer import DeferredList, ensureDeferred

# do not directly import fixtures, or session-scoped ones will get run twice.
from ..helpers import *

node1_pubkey = _read_node_key('./test/cf1/.crossbar/', private=False)['hex']
node2_pubkey = _read_node_key('./test/cf2/.crossbar/', private=False)['hex']
node3_pubkey = _read_node_key('./test/cf3/.crossbar/', private=False)['hex']


node_rlink_ports = {
    "node1": 8090,
    "node2": 8091,
    "node3": 8092,
}
node_websocket_ports = {
    "node1": 9080,
    "node2": 9081,
    "node3": 9082,
}


def client_node_transport(node):
    return {
        "type": "websocket",
        "url": "ws://localhost:{}/".format(node_websocket_ports[node]),
    }


def rlink_config(realm, from_node, to_node):
    return {
        "id": "{}_to_{}".format(from_node, to_node),
        "realm": realm,  # e.g. "realm1"
        "forward_local_invocations": True,
        "forward_remote_invocations": False,
        "forward_local_events": True,
        "forward_remote_events": False,
        "transport": {
            "type": "rawsocket",
            "serializer": "cbor",
            "endpoint": {
                "type": "tcp",
                "host": "localhost",
                "port": node_rlink_ports[to_node],
            },
            "url": "rs://localhost:{}".format(node_rlink_ports[to_node]),
        }
    }


def role_config(role):
    return {
        "name": role,
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
            }
        ]
    }


def realm_config(realm):
    # rlinks, roles have to be created with API calls
    return {
        "name": realm,
    }


def rlink_transport_config(node):
    return {
        "type": "rawsocket",
        "endpoint": {
            "type": "tcp",
            "port": node_rlink_ports[node],
            "backlog": 1024
        },
        "options": {
            "max_message_size": 1048576
        },
        "serializers": ["cbor", "msgpack", "json"],
        "auth": {
            "cryptosign": {
                "type": "static",
                "principals": {
                    "rlink": {
                        "realm": "realm1",
                        "role": "rlink",
                        "authorized_keys": [
                            node1_pubkey,
                            node2_pubkey,
                            node3_pubkey,
                        ]
                    }
                }
            }
        }
    }



def web_transport_config(node):
    return {
        "type": "websocket",
        "endpoint": {
            "type": "tcp",
            "port": node_websocket_ports[node],
        }
    }

import attr

@attr.s
class Management(object):
    session = attr.ib()

    async def get_nodes(self):
        node_oids = await self.session.call(
            u'crossbarfabriccenter.mrealm.get_nodes',
            u'online',
        )
        node_datas = []
        for nid in node_oids:
            data = await self.session.call(
                u"crossbarfabriccenter.mrealm.get_node",
                nid,
            )
            node_datas.append(data)
            print("DATA", data)

        return [
            ManagedNode(node_oid, node_data, self)
            for node_oid, node_data in zip(node_oids, node_datas)
        ]


@attr.s
class ManagedNode(object):
    node_oid = attr.ib()
    data = attr.ib()
    management = attr.ib()

    async def realm_worker(self, request, name, kind):
        res = await self.management.session.call(
            u"crossbarfabriccenter.remote.node.start_worker",
            self.node_oid,
            name,
            kind,
        )

        def cleanup():
            try:
                pytest_twisted.blockon(
                    self.management.session.call(
                        u"crossbarfabriccenter.remote.node.stop_worker",
                        self.node_oid,
                        name,
                    )
                )
            except Exception:
                # this can fail if e.g. ALL the tests are stopping and
                # other pytest shutdown code runs before this does --
                # probably only CancelledError needs to be caught
                # here.
                pass
        request.addfinalizer(cleanup)
        return RealmWorker(self, name, self.management)


@attr.s
class RealmWorker(object):
    node = attr.ib()
    worker_id = attr.ib()
    management = attr.ib()

    async def realm(self, request, name, config):
        res = await self.management.session.call(
            u"crossbarfabriccenter.remote.router.start_router_realm",
            self.node.node_oid,
            self.worker_id,
            name,
            config,
        )
        return RouterRealm(
            self.node,
            self.worker_id,
            name,
            self.management,
        )

    async def transport(self, request, name, config):
        res = await self.management.session.call(
            u"crossbarfabriccenter.remote.router.start_router_transport",
            self.node.node_oid,
            self.worker_id,
            name,
            config,
        )
        return res
        #return RouterTransport()


@attr.s
class RouterRealm(object):
    node = attr.ib()
    worker_id = attr.ib()
    realm_id = attr.ib()
    management = attr.ib()

    async def role(self, request, name, config):
        res = await self.management.session.call(
            u"crossbarfabriccenter.remote.router.start_router_realm_role",
            self.node.node_oid,
            self.worker_id,
            self.realm_id,
            name,
            config,
        )
        return None  # could make RouterRole class too...

    async def rlink_to(self, to_node, config):
        res = await self.management.session.call(
            u"crossbarfabriccenter.remote.router.start_router_realm_link",
            self.node.node_oid,
            self.worker_id,
            self.realm_id,
            "{}_to_{}".format(self.node.data["authid"], to_node.data["authid"]),
            config,
        )
        return res  # XXX Rlink object..?


@pytest_twisted.ensureDeferred
async def _test_remote_rlink(request, cfx_master, cfx_edge1, cfx_edge2, cfx_edge3):

    mrealm = 'mrealm1'
    worker_id = 'rlink_worker'
    worker_type = 'router'
    realm_id = 'realm1'
    management_session, management_session_details = await functest_management_session(realm=mrealm)

    def clean():
        reactor.callLater(0, management_session.leave)
    request.addfinalizer(clean)
    print(hl(management_session_details, bold=True))

    mgmt = Management(management_session)
    nodes = await mgmt.get_nodes()
    assert len(nodes) == 3, "Should have exactly 3 nodes"
    rlink_coros = []

    # Set up some roles + rlinks (these will be torn down after this test)
    for node in nodes:
        worker = await node.realm_worker(request, worker_id, worker_type)
        realm = await worker.realm(request, realm_id, realm_config(realm_id))
        for role in ["anonymous", "rlink"]:
            await realm.role(request, role, role_config(role))

        # transport for client-style sessions
        await worker.transport(request, "ws000", web_transport_config(node.data["authid"]))

        # rlink transport
        await worker.transport(request, "rlink", rlink_transport_config(node.data["authid"]))

        # note: some of these will connect to rlink transports that
        # don't yet exist; that's okay because we don't await them
        # until those DO exist, so they will succeed at some
        # point...that's why we wait separately for the rlinks-deferreds

        for to_node in nodes:
            if node == to_node:  # no rlink to ourself
                continue
            rlink_coros.append(
                ensureDeferred(
                    realm.rlink_to(
                        to_node,
                        rlink_config(realm_id, node.data["authid"], to_node.data["authid"]),
                    )
                )
            )

    # now we await all rlink connections (all listening transports on
    # all nodes are set up now)
    rlinks = await DeferredList(rlink_coros)
    assert len(rlinks) == 6, "Expected exactly 6 rlinks"
    for ok, res in rlinks:
        if not ok:
            raise res
        print(json.dumps(res, indent=4))


    # test some client-type connections

    alice_ready = Deferred()
    alice_got_pub = Deferred()

    alice = Component(
        transports=[client_node_transport("node1")],
        realm=realm_id,
    )
    @alice.register("test.foo")
    def foo(*args, **kw):
        return (args, kw)

    @alice.subscribe("test.pub")
    def bar(*args, **kw):
        alice_got_pub.callback(None)
        return (args, kw)

    alice.on_ready(alice_ready.callback)

    bob_got_result = Deferred()
    bob = Component(
        transports=[client_node_transport("node2")],
        realm=realm_id,
    )
    @bob.on_join
    async def joined(session, details):
        session.publish(u"test.pub", 1, "two", three=4)
        result = await session.call(u"test.foo", 1, 2, 3, "four", key="word")
        # note: tuples become lists in WAMP
        assert result == [[1, 2, 3, "four"], {"key": "word"}]
        bob_got_result.callback(None)

    print("register / call test")
    print("starting alice (to node1)")
    alice.start()
    await alice_ready

    print("starting bob (to node2)")
    bob.start()
    await bob_got_result

    print("waiting for alice to get publication")
    await alice_got_pub

    print("successful register + call test")
