###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from autobahn.wamp import types, exception
from autobahn.twisted.component import Component
from autobahn.exception import PayloadExceededError

from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.python import log
from os.path import join

import pytest

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import *


@inlineCallbacks
def test_max_message_size(request, temp_dir, crossbar, reactor, virtualenv):
    """
    """

    cbdir = join(temp_dir, "max_message_size")
    config = {
        "version": 2,
        "controller": {
            "options": {
                "shutdown": ["shutdown_on_worker_exit"],
            }
        },
        "workers": [
            {
                "id": "testee",
                "type": "router",
                "realms": [
                    {
                        "name": "foo",
                        "roles": [
                            {
                                "name": "anonymous",
                                "permissions": [
                                    {
                                        "uri": "",
                                        "match": "prefix",
                                        "allow": {
                                            "register": True,
                                            "call": True,
                                            "subscribe": True,
                                            "publish": True
                                        }
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
                            "port": 7773
                        },
                        "options": {
                            "max_message_size": 1024
                        }
                    }
                ],
            }
        ]
    }

    cb = yield start_crossbar(reactor, virtualenv, cbdir, config)

    def cleanup():
        try:
            cb.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass
    request.addfinalizer(cleanup)

    # can't connect until the transport is waiting
    yield cb.when_log_message_seen("WampRawSocketServerFactory starting on 7773")


    class TestSession(HelperSession):
        pass
    session = yield functest_session(
        session_factory=TestSession,
        url=u"rs://localhost:7773",
        debug=True,
        realm="foo",
    )

    last_err = None
    try:
        yield session.call(u"com.foo", b'\xfe' * 1024)
    except Exception as e:
        last_err = e

    cb.transport.signalProcess('TERM')
    yield cb.when_exited()

    assert isinstance(last_err, PayloadExceededError), 'expected PayloadExceededError to be raised, but was {}'.format(last_err)


@inlineCallbacks
def test_reconnect_on_handshake_timeout(request, temp_dir, crossbar, reactor, virtualenv):
    """
    """

    comp = Component(
        transports=[
            {
                "type": "websocket",
                "url": "ws://localhost:6565/ws",
                "max_retries": 2,
                "options": {
                    "open_handshake_timeout": .1,
                }
            }
        ]
    )

    errors = []

    @comp.on_connectfailure
    def error(component, e):
        errors.append(e)

    @comp.on_join
    def joined(session, details):
        import time; time.sleep(2.0)
        print(f"joined: {session} {details}")

    @comp.on_leave
    def left(session, reason):
        print(f"left: {session} {reason}")

    try:
        yield comp.start()
    except Exception as e:
        # will fail, because can't connect
        print(e)
