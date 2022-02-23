###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. All rights reserved.
#
###############################################################################

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
from ..helpers import _cleanup_crossbar, start_crossbar, functest_session

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
def start_node(request, reactor, virtualenv, session_temp, config, node_dir):
    listening = Deferred()

    success = 'NODE_BOOT_COMPLETE'
    for worker in config.get("workers"):
        for realm in worker.get("realms", []):
            if "rlinks" in realm:
                success = "Ok, router-to-router rlink001 started"

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
def test_r2r_three(request, reactor, virtualenv, session_temp):
    """
    Test of 'full-mesh' r2r links with three nodes.

    - node0, node1, node2 all have realm1
    - node0, node1, node2 all have "rlink" role for rlink
    - node0 makes rlink connection to node1, node2
    - node1 makes rlink connection to node0, node2
    - node2 makes rlink connection to node0, node1
    - (full-mesh)

    - alice connects to node0
    - alice registers "test.echo"
    - alice subscribes to "test.event"

    - bob connects to node1
    - bob calls "test.echo"
    - bob publishes to "test.event"

    - claire connects to node2
    - claire calls "test.echo"
    - claire publishes to "test.event"

    So, we should receive two calls at "test.echo" and receive two
    events to "test.event" for a successful test.
    """

    node0_dir = join(session_temp, "node0")
    if not os.path.exists(node0_dir):
        os.mkdir(node0_dir)
    node1_dir = join(session_temp, "node1")
    if not os.path.exists(node1_dir):
        os.mkdir(node1_dir)
    node2_dir = join(session_temp, "node2")
    if not os.path.exists(node2_dir):
        os.mkdir(node2_dir)

    # burn in keys so they can match in the configs
    node_keys = [
        (join(node0_dir, "key.pub"), node0_pubkey),
        (join(node0_dir, "key.priv"), node0_privkey),
        (join(node1_dir, "key.pub"), node1_pubkey),
        (join(node1_dir, "key.priv"), node1_privkey),
        (join(node2_dir, "key.pub"), node2_pubkey),
        (join(node2_dir, "key.priv"), node2_privkey),
    ]
    for fname, keydata in node_keys:
        with open(fname, "w") as f:
            f.write(keydata)

    # we start the three nodes in parallel because they all have to
    # connect to the other before they're "started" but we don't know
    # which one will "win" and connect first
    node0_d = start_node(request, reactor, virtualenv, session_temp, node0_config, node0_dir)
    node1_d = start_node(request, reactor, virtualenv, session_temp, node1_config, node1_dir)
    node2_d = start_node(request, reactor, virtualenv, session_temp, node2_config, node2_dir)
    results = yield DeferredList([node0_d, node1_d, node2_d])
    nodes = []
    for ok, res in results:
        if not ok:
            raise res
        nodes.append(res)
    protocol0, protocol1, protocol2 = nodes

    print("Started rlink'd nodes:")

    print("  0: {}".format(protocol0))
    print("  1: {}".format(protocol1))
    print("  2: {}".format(protocol2))

    print("-" * 80)

    # we could wait to see text of each node successfully connecting
    # to the other .. or we just wait a bit.
    yield sleep(10)
    # XXX we could rig this up with crossbar master and then use the
    # management API to determine when all nodes + their rlinks are
    # up..

    # track the events and invocations we get
    events = []
    calls = []
    subscribed_d = Deferred()
    rpc_call_d = Deferred()

    print("start alice")  # run alice first

    alice = Component(
        transports=[
            {"url": "ws://localhost:9080/ws", "type": "websocket"},  # node0
        ],
        realm="realm1",
    )

    @alice.on_join
    @inlineCallbacks
    def alice_join(session, details):
        print("\n\nalice joined\n")

        def a_thing(*args, **kw):
            print("received: a_thing: args={} kw={}".format(args, kw))
            events.append((args, kw))
            if len(events) >= 2:
                reactor.callLater(1, session.leave)
        yield session.subscribe(a_thing, "test.a_thing")

        def rpc(*args, **kw):
            print("call: rpc: args={} kw={}".format(args, kw))
            calls.append((args, kw))
            if len(calls) >= 2:
                reactor.callLater(1, rpc_call_d.callback, None)
            return "rpc return"
        yield session.register(rpc, "test.rpc")
        # XXX we don't know when the rlink registration goes all the way through...
        reactor.callLater(2.0, subscribed_d.callback, None)

    alice_done = alice.start(reactor)

    # wait until Alice actually subscribes before starting bob
    yield subscribed_d
    print("alice is subscribed + registered")

    print("start bob")

    bob = Component(
        transports=[{
            "url": "ws://localhost:9081/ws",  # node1
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


    print("start claire")

    claire = Component(
        transports=[{
            "url": "ws://localhost:9081/ws",  # node1
            "type": "websocket",
        }],
        realm="realm1",
    )

    @claire.on_join
    @inlineCallbacks
    def claire_join(session, details):
        print("claire joined: PID={x_cb_pid}".format(**details.authextra))
        print("publishing 'test.a_thing'")
        p = yield session.publish("test.a_thing", 3, 2, 1, options=types.PublishOptions(acknowledge=True))
        print("published {}".format(p))
        res = yield session.call("test.rpc", 1, 2, 3)
        print("test.rpc returned: {}".format(res))
        reactor.callLater(2, session.leave)

    claire_done = claire.start(reactor)
    print("claire is starting", claire_done)

    yield rpc_call_d
    yield bob_done
    yield alice_done
    yield claire_done


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

node0_config = {
    "$schema": "https://raw.githubusercontent.com/crossbario/crossbar/master/crossbar.json",
    "version": 2,
    "controller": {
    },
    "workers": [
        {
            "type": "router",
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
                                    "port": 8091
                                },
                                "url": "rs://localhost:8091"
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
                                    "port": 8092
                                },
                                "url": "rs://localhost:8092"
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
                        "port": 8090,
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
                                        "97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f",
                                        "2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355",
                                        "298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987"
                                    ]
                                }
                            }
                        }
                    }
                },
                {
                    "type": "web",
                    "endpoint": {
                        "type": "tcp",
                        "port": 9080,
                        "backlog": 1024
                    },
                    "paths": {
                        "/": {
                            "type": "static",
                            "directory": "../web",
                            "options": {
                                "enable_directory_listing": True
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
                                "enable_webstatus": False,
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
                        }
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
                                    "port": 8090
                                },
                                "url": "rs://localhost:8090"
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
                                    "port": 8092
                                },
                                "url": "rs://localhost:8092"
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
                        "port": 8091,
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
                                        "97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f",
                                        "2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355",
                                        "298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987"
                                    ]
                                }
                            }
                        }
                    }
                },
                {
                    "type": "web",
                    "endpoint": {
                        "type": "tcp",
                        "port": 9081,
                        "backlog": 1024
                    },
                    "paths": {
                        "/": {
                            "type": "static",
                            "directory": "../web",
                            "options": {
                                "enable_directory_listing": True
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
                                "enable_webstatus": False,
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
                                    "port": 8090
                                },
                                "url": "rs://localhost:8090"
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
                                    "port": 8091
                                },
                                "url": "rs://localhost:8091"
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
                        "port": 8092,
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
                                        "97474dca6e3d1bccf2ab0dea030bde7799c4cbdb6e6f73304b33bfbf0d6a147f",
                                        "2ecd87909589f02938bd0d9e3a57489339c17509b13d8044974a7f47ba99f355",
                                        "298209e5752fa70b722ed40d97b623d2ba07558b4400fd20a2b876ce52b41987"
                                    ]
                                }
                            }
                        }
                    }
                },
                {
                    "type": "web",
                    "endpoint": {
                        "type": "tcp",
                        "port": 9082,
                        "backlog": 1024
                    },
                    "paths": {
                        "/": {
                            "type": "static",
                            "directory": "../web",
                            "options": {
                                "enable_directory_listing": True
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
                                "enable_webstatus": False,
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
                        }
                    }
                }
            ]
        }
    ]
}
