###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

# This test is for "plain crossbar" to demonstrate multiple router
# processes with multiple frontend proxy processes. It confirms that a
# single logical "router" can span 2 (or more) processes, that proxy
# workers will round-robin between multiple routes (when available)
# and that WAMP calls work regardless of which proxy or router they
# hit.

from __future__ import print_function
from __future__ import absolute_import

import os
import re
from os.path import join

from functools import partial

from autobahn.wamp import types, exception
from autobahn.twisted.util import sleep
from autobahn.twisted.component import Component
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks, DeferredList, returnValue
from twisted.logger import globalLogPublisher

import treq
import pytest

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import _cleanup_crossbar, start_crossbar, functest_session, _create_temp


class WaitForStarted(object):

    def __init__(self, done, success_string):
        self.data = ''
        self.done = done
        self.success_string = success_string

    def write(self, data):
        print(data, end='')
        if self.done.called:
            return

        # in case it's not line-buffered for some crazy reason
        self.data = self.data + data
        if self.success_string in self.data:
            self.done.callback(None)
        if "Address already in use" in self.data:
            self.done.errback(RuntimeError("Address already in use"))


@inlineCallbacks
def start_node(request, reactor, virtualenv, config, node_dir):
    listening = Deferred()

    success = 'NODE_BOOT_COMPLETE'
    for worker in config.get("workers"):
        for realm in worker.get("realms", []):
            if "rlinks" in realm:
                success = "Ok, router-to-router rlink{:03d} started".format(len(realm["rlinks"]) - 1)
    print("SUCCESSS will be '{}'".format(success))

    protocol = yield start_crossbar(
            reactor, virtualenv,
            node_dir, config,
            stdout=WaitForStarted(listening, success),
            stderr=WaitForStarted(listening, success),
            log_level='debug' if request.config.getoption('logdebug', False) else False,
    )
    request.addfinalizer(partial(_cleanup_crossbar, protocol))
    yield listening
    returnValue(protocol)


@inlineCallbacks
def test_roundrobin_proxy(request, reactor, virtualenv):
    """
    Confirm that a proxy with two connections does connections to both
    backends.

    Two nodes each with a router-worker for 'realm1'
    Each node rlink-connects to the other.
    One node has a proxy
    """

    tempdir = _create_temp(request)

    # burn in hard-coded keys so we can refer to the public parts in
    # configs more easily.
    node_keys = [
        (node0_pubkey, node0_privkey),
        (node1_pubkey, node1_privkey),
        (node2_pubkey, node2_privkey),
        (node3_pubkey, node3_privkey),
    ]
    for node_num in range(4):
        node_dir = join(tempdir, "node{}".format(node_num))
        os.mkdir(node_dir)

        pub, priv = node_keys[node_num]
        with open(join(node_dir, "key.pub"), "w") as f:
            f.write(pub)
        with open(join(node_dir, "key.priv"), "w") as f:
            f.write(priv)

    # we start the nodes in parallel because we don't know which one
    # will "win" and connect first
    node_setup = [
        (node0_config, join(tempdir, "node0")),
        (node1_config, join(tempdir, "node1")),
        (node2_config, join(tempdir, "node2")),
        (node3_config, join(tempdir, "node3")),
    ]
    node_starts = []
    for node_config, node_dir in node_setup:
        node_d = start_node(request, reactor, virtualenv, node_config, node_dir)
        node_starts.append(node_d)
    print("-" * 80)
    print(node_starts)
    results = yield DeferredList(node_starts)
    print("-" * 80)
    print(results)
    print("-" * 80)
    nodes = []
    for ok, res in results:
        if not ok:
            raise res
        nodes.append(res)
    protocol0, protocol1, protocol2, protocol3 = nodes

    print("Started rlink'd nodes:")

    print("  0: {}".format(protocol0))
    print("  1: {}".format(protocol1))
    print("  2: {}".format(protocol2))
    print("  3: {}".format(protocol3))

    print("-" * 80)

    # we could wait to see text of each node successfully connecting
    # to the other .. or we just wait a bit.
    yield sleep(5)

    subscribed_d = Deferred()
    rpc_call_d = Deferred()
    print("start alice")
    # run alice first

    alice = Component(
        transports=[
            {"url": "ws://localhost:7070/ws", "type": "websocket"},  # proxy0
        ],
        realm="realm1",
    )

    @alice.on_join
    @inlineCallbacks
    def alice_join(session, details):
        print("\n\nalice joined\n")

        def a_thing(*args, **kw):
            print("received: a_thing: args={} kw={}".format(args, kw))
            reactor.callLater(3, session.leave)
        yield session.subscribe(a_thing, "test.a_thing")

        def rpc(*args, **kw):
            print("call: rpc: args={} kw={}".format(args, kw))
            reactor.callLater(1, rpc_call_d.callback, None)
            return "rpc return"
        yield session.register(rpc, "test.rpc")
        # XXX we don't know when the rlink registration goes all the way through...
        reactor.callLater(2.0, subscribed_d.callback, None)

    alice_done = alice.start(reactor)

    # wait until Alice actually subscribes (and thus is also registered) before starting bob
    yield subscribed_d
    print("alice is subscribed + registered")

    print("start bob")

    bob = Component(
        transports=[{
            "url": "ws://localhost:7070/ws",  # node0 XXX should be node1
            "type": "websocket",
        }],
        realm="realm1",
    )

    @bob.on_join
    @inlineCallbacks
    def bob_join(session, details):
        print("bob joined: PID={x_cb_pid}".format(**details.authextra))
        print("publishing 'test.a_thing'")
        p = yield session.publish("test.a_thing", 3, 2, 1, options=types.PublishOptions(acknowledge=True))
        print("published {}".format(p))
        res = yield session.call("test.rpc", 1, 2, 3)
        print("test.rpc returned: {}".format(res))
        reactor.callLater(2, session.leave)

    bob_done = bob.start(reactor)
    print("bob is starting", bob_done, alice_done)
    yield rpc_call_d
    yield bob_done
    yield alice_done

    # do a bunch of pubs in different sessions to prove we're hitting
    # different proxies and different router processes.

    received = []
    connects = []

    carol = Component(
        transports=[{
            "url": "ws://localhost:7070/ws",  # node0 XXX should be node1
            "type": "websocket",
        }],
        realm="realm1",
    )

    @carol.subscribe("multiverse", types.SubscribeOptions(details=True))
    def _(*args, **kwargs):
        print("SUB: {}".format(kwargs.get('details', None)))
        received.append((args, kwargs))

    carol_ready = Deferred()
    carol.on('ready', carol_ready.callback)
    carol.start()
    yield carol_ready

    GROUPS = 10
    CONNECTS = 5

    for g in range(GROUPS):
        group = []
        for m in range(CONNECTS):
            client = Component(
                transports=[{
                    "url": "ws://localhost:7070/ws",  # proxy0
                    "type": "websocket",
                }],
                realm="realm1",
            )

            @client.on_join
            @inlineCallbacks
            def _(session, details):
                connects.append(details)
                yield session.publish(
                    u"multiverse", group=g, member=m,
                    options=types.PublishOptions(acknowledge=True)
                )
                yield session.leave()

            group.append(client.start())
        res = yield DeferredList(group)
        for ok, value in res:
            if not ok:
                raise value
    print("-" * 80)
    print("Received {} events".format(len(received)))
    for r in received:
        print(r[1]['details'])

    # some client should get each publish() that we sent
    assert len(received) == GROUPS * CONNECTS
    print("-" * 80)

    # figure out which nodes and proxies we've contacted
    workers = set()
    proxies = set()
    for c in connects:
        workers.add(c.authextra['x_cb_worker'])
        proxies.add(c.authextra['x_cb_proxy_worker'])
        print(c.authextra['x_cb_worker'])
    print("workers: {}".format(workers))
    print("proxies: {}".format(proxies))
    print("-" * 80)
    assert workers == set([
        "node0_worker0",
        "node1_worker0",
        "node2_worker0",
        "node3_worker0",
    ])
    assert proxies == set(["node0_proxy0"])



node0_pubkey = """
creator: integration-test
created-at: 2020-05-14T00:00:00.000Z
machine-id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
public-key-ed25519: 97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f
"""

node0_privkey = """
creator: integration-test
created-at: 2020-05-14T00:00:00.00Z
machine-id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
public-key-ed25519: 97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f
private-key-ed25519: a13a0850e231e9e350aac1ad22a691becbfd3afd74b913a33f6a840322d75677
"""

node1_pubkey = """
creator: integration-test
created-at: 2020-05-14T00:00:00.00Z
machine-id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
public-key-ed25519: 2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355
"""

node1_privkey = """
creator: integration-test
created-at: 2020-05-14T00:00:00.00Z
machine-id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
public-key-ed25519: 2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355
private-key-ed25519: 54f3758b91a2bd55a026f36a0a3f76b6507797c71595c088ac5d1418ddaded48
"""

node2_pubkey = """
creator: integration-test
created-at: 2020-05-14T00:00:00.00Z
machine-id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
public-key-ed25519: 298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987
"""

node2_privkey = """
creator: integration-test
created-at: 2020-05-14T00:00:00.00Z
machine-id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
public-key-ed25519: 298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987
private-key-ed25519: c30233a6f289cba27d903cabaf06e4ae8d2b9be9f582c604dc43d6fc260d50dd
"""

node3_pubkey = """
creator: integration-test
created-at: 2020-05-14T00:00:00.00Z
machine-id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
public-key-ed25519: 11a4107b9bfb96fe192efa5f2747a248d9e70853249a6bb61698ecb107582465
"""

node3_privkey = """
creator: integration-test
created-at: 2020-05-14T00:00:00.00Z
machine-id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
public-key-ed25519: 11a4107b9bfb96fe192efa5f2747a248d9e70853249a6bb61698ecb107582465
private-key-ed25519: aba9c04669c1359bf4fd6049503130cd7e54897261f4a7aa0dadbdfbb5bc0ed5
"""

node0_config = {
    "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
    "version": 2,
    "controller": {
    },
    "workers": [
        {
            "type": "router",
            "id": "node0_worker0",
            "realms": [
                {
                    "name": "realm1",
                    "rlinks": [
                        {
#                            "id": "node0_to_node1",
                            "realm": "realm1",
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
                                    "port": 7001
                                },
                                "url": "rs://localhost:7001"
                            }
                        },
                        {
#                            "id": "node0_to_node2",
                            "realm": "realm1",
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
                                    "port": 7002
                                },
                                "url": "rs://localhost:7002"
                            }
                        }
                    ],
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
                                }
                            ]
                        },
                        {
                            "name": "rlink",
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
                    ]
                }
            ],
            "transports": [
                {
                    "type": "rawsocket",
                    "endpoint": {
                        "type": "tcp",
                        "port": 7000,
                        "backlog": 1024
                    },
                    "options": {
                        "max_message_size": 1048576
                    },
                    "serializers": ["cbor"],
                    "auth": {
                        "cryptosign": {
                            "type": "static",
                            "principals": {
                                "rlink": {
                                    "realm": "realm1",
                                    "role": "rlink",
                                    "authorized_keys": [
                                        "97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f",
                                        "2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355",
                                        "298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987",
                                        "11a4107b9bfb96fe192efa5f2747a248d9e70853249a6bb61698ecb107582465"
                                    ]
                                }
                            }
                        },
                        "anonymous-proxy": {
                            "type": "static"
                        }
                    }
                }
            ]
        },
        {
            "type": "proxy",
            "id": "node0_proxy0",
            "routes": {
                "realm1": {
                    "anonymous": ["backend_zero", "backend_one", "backend_two", "backend_three"]
                }
            },
            "connections": {
                "backend_zero": {
                    "realm": "realm1",
                    "transport": {
                        "type": "rawsocket",
                        "endpoint": {
                            "type": "tcp",
                            "host": "localhost",
                            "port": 7000
                        },
                        "serializer": "cbor",
                        "url": "rs://localhost:7000"
                    }
                },
                "backend_one": {
                    "realm": "realm1",
                    "transport": {
                        "type": "rawsocket",
                        "endpoint": {
                            "type": "tcp",
                            "host": "localhost",
                            "port": 7001
                        },
                        "serializer": "cbor",
                        "url": "rs://localhost:7001"
                    }
                },
                "backend_two": {
                    "realm": "realm1",
                    "transport": {
                        "type": "rawsocket",
                        "endpoint": {
                            "type": "tcp",
                            "host": "localhost",
                            "port": 7002
                        },
                        "serializer": "cbor",
                        "url": "rs://localhost:7002"
                    }
                },
                "backend_three": {
                    "realm": "realm1",
                    "transport": {
                        "type": "rawsocket",
                        "endpoint": {
                            "type": "tcp",
                            "host": "localhost",
                            "port": 7003
                        },
                        "serializer": "cbor",
                        "url": "rs://localhost:7003"
                    }
                }
            },
            "transports": [
                {
                    "type": "web",
                    "endpoint": {
                        "type": "tcp",
                        "port": 7070,
                        "shared": True,
                    },
                    "paths": {
                        "autobahn": {
                            "type": "archive",
                            "archive": "autobahn.zip",
                            "origin": "https://github.com/crossbario/autobahn-js-browser/archive/master.zip",
                            "download": True,
                            "cache": True,
                            "mime_types": {
                                ".min.js": "text/javascript",
                                ".jgz": "text/javascript"
                            }
                        },
                        "ws": {
                            "type": "websocket",
                            "serializers": [
                                "cbor", "msgpack", "json"
                            ],
                            "options": {
                                "allowed_origins": ["*"],
                                "allow_null_origin": True,
                                "enable_webstatus": True,
                                "max_frame_size": 1048576,
                                "max_message_size": 1048576,
                                "auto_fragment_size": 65536,
                                "fail_by_drop": True,
                                "open_handshake_timeout": 2500,
                                "close_handshake_timeout": 1000,
                                "auto_ping_interval": 10000,
                                "auto_ping_timeout": 5000,
                                "auto_ping_size": 12,
                                "auto_ping_restart_on_any_traffic": True,
                                "compression": {
                                    "deflate": {
                                        "request_no_context_takeover": False,
                                        "request_max_window_bits": 13,
                                        "no_context_takeover": False,
                                        "max_window_bits": 13,
                                        "memory_level": 5
                                    }
                                }
                            }
                        },
                        "info": {
                            "type": "nodeinfo"
                        },
                        "/": {
                            "type": "static",
                            "directory": join("..", "web"),
                            "options": {
                                "enable_directory_listing": False
                            }
                        },
                    }
                }
            ]
        }
    ]
}

node1_config = {
    "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
    "version": 2,
    "controller": {
    },
    "workers": [
        {
            "type": "router",
            "id": "node1_worker0",
            "realms": [
                {
                    "name": "realm1",
                    "rlinks": [
                        {
#                            "id": "node1_to_node0",
                            "realm": "realm1",
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
                                    "port": 7000
                                },
                                "url": "rs://localhost:7000"
                            }
                        },
                        {
#                            "id": "node1_to_node2",
                            "realm": "realm1",
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
                                    "port": 7002
                                },
                                "url": "rs://localhost:7002"
                            }
                        },
                        {
#                            "id": "node1_to_node3",
                            "realm": "realm1",
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
                                    "port": 7003
                                },
                                "url": "rs://localhost:7003"
                            }
                        }
                    ],
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
                                }
                            ]
                        },
                        {
                            "name": "rlink",
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
                    ]
                }
            ],
            "transports": [
                {
                    "type": "rawsocket",
                    "endpoint": {
                        "type": "tcp",
                        "port": 7001,
                        "backlog": 1024
                    },
                    "options": {
                        "max_message_size": 1048576
                    },
                    "serializers": ["cbor"],
                    "auth": {
                        "cryptosign": {
                            "type": "static",
                            "principals": {
                                "rlink": {
                                    "realm": "realm1",
                                    "role": "rlink",
                                    "authorized_keys": [
                                        "97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f",
                                        "2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355",
                                        "298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987",
                                        "11a4107b9bfb96fe192efa5f2747a248d9e70853249a6bb61698ecb107582465"
                                    ]
                                }
                            }
                        },
                        "anonymous-proxy": {
                            "type": "static"
                        }
                    }
                }
            ]
        }
    ]
}

node2_config = {
    "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
    "version": 2,
    "controller": {
    },
    "workers": [
        {
            "type": "router",
            "id": "node2_worker0",
            "realms": [
                {
                    "name": "realm1",
                    "rlinks": [
                        {
#                            "id": "node2_to_node0",
                            "realm": "realm1",
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
                                    "port": 7000
                                },
                                "url": "rs://localhost:7000"
                            }
                        },
                        {
 #                            "id": "node2_to_node1",
                            "realm": "realm1",
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
                                    "port": 7001
                                },
                                "url": "rs://localhost:7001"
                            }
                        },
                        {
 #                            "id": "node2_to_node3",
                            "realm": "realm1",
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
                                    "port": 7003
                                },
                                "url": "rs://localhost:7003"
                            }
                        }
                    ],
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
                                }
                            ]
                        },
                        {
                            "name": "rlink",
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
                    ]
                }
            ],
            "transports": [
                {
                    "type": "rawsocket",
                    "endpoint": {
                        "type": "tcp",
                        "port": 7002,
                        "backlog": 1024
                    },
                    "options": {
                        "max_message_size": 1048576
                    },
                    "serializers": ["cbor"],
                    "auth": {
                        "cryptosign": {
                            "type": "static",
                            "principals": {
                                "rlink": {
                                    "realm": "realm1",
                                    "role": "rlink",
                                    "authorized_keys": [
                                        "97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f",
                                        "2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355",
                                        "298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987",
                                        "11a4107b9bfb96fe192efa5f2747a248d9e70853249a6bb61698ecb107582465"
                                    ]
                                }
                            }
                        },
                        "anonymous-proxy": {
                            "type": "static"
                        }
                    }
                }
            ]
        }
    ]
}

node3_config = {
    "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
    "version": 2,
    "controller": {
    },
    "workers": [
        {
            "type": "router",
            "id": "node3_worker0",
            "realms": [
                {
                    "name": "realm1",
                    "rlinks": [
                        {
#                            "id": "node3_to_node0",
                            "realm": "realm1",
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
                                    "port": 7000
                                },
                                "url": "rs://localhost:7000"
                            }
                        },
                        {
 #                            "id": "node3_to_node1",
                            "realm": "realm1",
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
                                    "port": 7001
                                },
                                "url": "rs://localhost:7001"
                            }
                        },
                        {
 #                            "id": "node3_to_node2",
                            "realm": "realm1",
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
                                    "port": 7002
                                },
                                "url": "rs://localhost:7002"
                            }
                        }
                    ],
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
                                }
                            ]
                        },
                        {
                            "name": "rlink",
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
                    ]
                }
            ],
            "transports": [
                {
                    "type": "rawsocket",
                    "endpoint": {
                        "type": "tcp",
                        "port": 7003,
                        "backlog": 1024
                    },
                    "options": {
                        "max_message_size": 1048576
                    },
                    "serializers": ["cbor"],
                    "auth": {
                        "cryptosign": {
                            "type": "static",
                            "principals": {
                                "rlink": {
                                    "realm": "realm1",
                                    "role": "rlink",
                                    "authorized_keys": [
                                        "97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f",
                                        "2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355",
                                        "298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987",
                                        "11a4107b9bfb96fe192efa5f2747a248d9e70853249a6bb61698ecb107582465"
                                    ]
                                }
                            }
                        },
                        "anonymous-proxy": {
                            "type": "static"
                        }
                    }
                }
            ]
        }
    ]
}

