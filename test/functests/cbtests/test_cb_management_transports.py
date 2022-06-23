###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

import random
from functools import partial
from os.path import join

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.internet.process import ProcessExitedAlready
from twisted.python import log

import pytest
import psutil

from ..helpers import *

# the configs for these don't *have* to have different ports, but
# makes debugging a little easier
@pytest.mark.parametrize(
    "expected_port,config",
    [
        (
            7878,
            {"type": "websocket", "endpoint": { "type": "tcp", "port": 7878 }}
        ),
        (
            7979,
            {
                u"type": u"rawsocket",
                u"endpoint": {
                    "type": "tcp",
                    "port": 7979,
                },
            }
        ),
        (
            7171,
            {
                u"type": u"flashpolicy",
                u"endpoint": {
                    "type": "tcp",
                    "port": 7171,
                },
            }
        ),
        (
            7272,
            {
                "type": "websocket.testee",
                "endpoint": {
                    "type": "tcp",
                    "port": 7272,
                },
            }
        ),
        (
            8181,
            {
                u"type": u"stream.testee",
                u"endpoint": {
                    "type": "tcp",
                    "port": 8181,
                },
            }
        )
    ]
)
@inlineCallbacks
def test_non_web_transports(crossbar, request, expected_port, config):
    """
    start up all the "simple" transports
    """
    pytest.skip("Needs old-style management API to work")

    manage = yield functest_management_session(debug=False)

    info = yield manage.call("crossbar.node.functestee.get_info")

    workers = yield manage.call("crossbar.node.functestee.get_workers")
    pid = None
    for worker in workers:
        if worker['id'] == 'testee':
            pid = worker['pid']

    assert pid is not None
    p = psutil.Process(pid)

    x = yield manage.call("crossbar.node.functestee.worker.testee.start_router_transport", "foo", config)
    transports = yield manage.call("crossbar.node.functestee.worker.testee.get_router_transports")
    def cleanup():
        # shut the transport down before the assert, for when/if assert fails
        pytest.blockon(manage.call("crossbar.node.functestee.worker.testee.stop_router_transport", "foo"))
    request.addfinalizer(cleanup)

    print("Router claims transports:")
    for transport in transports:
        print("  {}".format(transport))

    found = False
    for conn in p.connections():
        if conn.status == 'LISTEN':
            if conn.laddr[1] == expected_port:
                print("Found connection:", conn)
                found = True

    assert found, "nothing listening on {} -- start_router_transport failed".format(expected_port)


@inlineCallbacks
def test_web_transport_simple(crossbar, request):
    """
    test basic web transport
    """

    pytest.skip("Needs old-style management API to work")
    manage = yield functest_management_session(debug=False)
    config = {
        "type": "web",
        "endpoint": {
            "type": "tcp",
            "port": 8181,
        },
        "paths": {
            "/": {
                "type": "static",
                "directory": ".",
            },
        },
    }

    info = yield manage.call("crossbar.node.functestee.get_info")

    workers = yield manage.call("crossbar.node.functestee.get_workers")
    pid = None
    for worker in workers:
        if worker['id'] == 'testee':
            pid = worker['pid']

    assert pid is not None
    p = psutil.Process(pid)

    x = yield manage.call("crossbar.node.functestee.worker.testee.start_router_transport", "foo", config)
    transports = yield manage.call("crossbar.node.functestee.worker.testee.get_router_transports")
    def cleanup():
        # shut the transport down before the assert, for when/if assert fails
        pytest.blockon(manage.call("crossbar.node.functestee.worker.testee.stop_router_transport", "foo"))
    request.addfinalizer(cleanup)

    found = False
    for conn in p.connections():
        if conn.status == 'LISTEN':
            if conn.laddr[1] == 8181:
                print("Found connection:", conn)
                found = True

    assert found, "nothing listening on 8181 -- start_router_transport failed"
