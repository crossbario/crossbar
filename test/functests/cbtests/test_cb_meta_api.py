###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from os.path import join
from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.internet.process import ProcessExitedAlready
from twisted.internet.task import deferLater
from twisted.python import log

import pytest

from ..helpers import *


@inlineCallbacks
def test_get_sessions(crossbar, reactor):
    """
    """

    # setup
    class TestSession(HelperSession):
        pass
    session = yield functest_session(session_factory=TestSession, debug=True)
    old_session_id = session._session_id

    # use meta-API to query sessions
    data = yield session.call(u"wamp.session.get", session._session_id)
    print("session data: {}".format(data))
    assert data['session'] == session._session_id

    yield session.leave()

    # meta-API again to query sessions (but it's gone now)
    session = yield functest_session(session_factory=TestSession, debug=True)
    try:
        yield session.call(u"wamp.session.get", old_session_id)
        assert False, "should get exception"
    except ApplicationError as e:
        print("Got an expected error: {}".format(e))
        assert e.error == "wamp.error.no_such_session"


@inlineCallbacks
def test_get_sessions_filter_authrole(crossbar, reactor):
    """
    see also https://github.com/crossbario/crossbar/issues/1581
    """

    # setup
    class TestSession(HelperSession):
        pass
    session = yield functest_session(session_factory=TestSession, debug=True)
    old_session_id = session._session_id

    # use meta-API to query sessions
    data = yield session.call(u"wamp.session.list", filter_authroles=[u"anonymous"])
    print("session data: {}".format(data))

    yield session.leave()


@inlineCallbacks
def _test_leak_registrations(reactor, temp_dir, virtualenv):
    """
    """

    cbdir = join(temp_dir, "boom")
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
                                "name": "approver",
                                "permissions": [
                                    {
                                        "uri": "com.example.authorize",
                                        "allow": {
                                            "register": True
                                        }
                                    }
                                ]
                            },
                            {
                                "name": "user",
                                "authorizer": "com.example.authorize"
                            }
                        ]
                    }
                ],
                "transports": [
                    {
                        "type": "universal",
                        "endpoint": {
                            "type": "tcp",
                            "port": 7772
                        },
                        "rawsocket": {
                            "serializers": [
                                "cbor", "msgpack", "ubjson", "json"
                            ]
                        },
                    }
                ],
            },
            {
                "id": "container_a",
                "type": "container",
                "options": {
                    "shutdown": "shutdown-on-last-component-stopped",
                },
                "components": [
                    {
                        "type": "function",
                        "callbacks": {
                            "join": ".metatest.authorizer_setup",
                        },
                        "realm": "foo",
                        "role": "approver",
                        "transport": {
                            "type": "rawsocket",
                            "serializer": "json",
                            "endpoint": {
                                "type": "tcp",
                                "port": 7772,
                                "host": "127.0.0.1",
                            }
                        },
                        "auth": {}
                    },
                    {
                        "type": "function",
                        "callbacks": {
                            "join": ".metatest.client",
                        },
                        "realm": "foo",
                        "role": "user",
                        "transport": {
                            "type": "rawsocket",
                            "serializer": "json",
                            "endpoint": {
                                "type": "tcp",
                                "port": 7772,
                                "host": "127.0.0.1",
                            },
                        },
                        "auth": {}
                    }
                ]
            }
        ]
    }

    cb = yield start_crossbar(reactor, virtualenv, cbdir, config)

    try:
        yield cb._all_done
    except Exception as e:
        print("exception: {}".format(e))
    log_output = cb.logs.getvalue()
    print(log_output)

    # FIXME
    # assert u"wamp.error.not_authorized" in log_output, "all call()s should be unauthorized"
    # assert u"wamp.error.no_such_procedure" not in log_output, "all call()s should be unauthorized"
