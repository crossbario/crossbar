###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

import re
from functools import partial

from autobahn.wamp import types, exception
from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.wamp import Session
from autobahn.wamp.auth import create_authenticator
from autobahn.twisted.util import sleep
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks, DeferredList
from twisted.internet.error import ProcessTerminated
from twisted.logger import globalLogPublisher

import pytest
import pytest_twisted

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import _create_temp
from ..helpers import _cleanup_crossbar
from ..helpers import start_crossbar
from ..helpers import functest_session


@pytest_twisted.inlineCallbacks
def test_shutdown_failed_component(reactor, request, virtualenv, session_temp):
    """
    crossbar shuts down a container on any component failure
    """

    crossbar_config = {
        "version": 2,
        "controller": {},
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
                                        "uri": "*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                            "call": True,
                                            "register": True
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "transports": [
                    {
                        "type": "web",
                        "id": "ws_test_0",
                        "endpoint": {
                            "type": "tcp",
                            "port": 7272
                        },
                        "paths": {
                            "/": {
                                "type": "static",
                                "directory": "../web"
                            },
                            "ws": {
                                "type": "websocket"
                            }
                        }
                    }
                ]
            },
            {
                "type": "container",
                "options": {
                    "shutdown": "shutdown-on-any-component-stopped",
                },
                "components": [
                    {
                        "type": "function",
                        "callbacks": {
                            "join": "crossbar.functest_helpers.shutdown_test.good_join",
                        },
                        "realm": "foo",
                        "transport": {
                            "type": "websocket",
                            "url": "ws://127.0.0.1:7272/ws",
                            "endpoint": {
                                "type": "tcp",
                                "port": 7272,
                                "host": "127.0.0.1",
                            }
                        },
                        "auth": {}
                    },
                    {
                        "type": "function",
                        "callbacks": {
                            "join": "crossbar.functest_helpers.shutdown_test.failed_join",
                        },
                        "realm": "foo",
                        "transport": {
                            "type": "websocket",
                            "url": "ws://127.0.0.1:7272/ws",
                            "endpoint": {
                                "type": "tcp",
                                "port": 7272,
                                "host": "127.0.0.1",
                            }
                        },
                        "auth": {}
                    },
                ]
            }
        ]
    }

    class WaitForTransport(object):
        """
        Super hacky, but ... other suggestions? Could busy-wait for ports
        to become connect()-able? Better text to search for?
        """
        def __init__(self, done):
            self.data = ''
            self.done = done

        def write(self, data):
            print(data, end='')
            if self.done.called:
                return

            # in case it's not line-buffered for some crazy reason
            self.data = self.data + data
            if "started Transport ws_test_0" in self.data:
                print("Detected transport starting up")
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    tempdir = _create_temp(request, prefix="cts_auth")
    protocol = yield start_crossbar(
        reactor, virtualenv, tempdir, crossbar_config,
        log_level='debug' if request.config.getoption('logdebug', False) else 'info',
    )

    # XXX we probably want a timeout on here too...
    try:
        yield protocol._all_done
        assert False, "should get an error"
    except ProcessTerminated as e:
        print("Got error as expected: {}".format(e))
        assert e.exitCode == 1


@pytest_twisted.inlineCallbacks
def test_restart_failed_component(reactor, request, virtualenv, session_temp):
    """
    crossbar restarts a component on failure
    """

    crossbar_config = {
        "version": 2,
        "controller": {},
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
                                        "uri": "*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                            "call": True,
                                            "register": True
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "transports": [
                    {
                        "type": "web",
                        "id": "ws_test_0",
                        "endpoint": {
                            "type": "tcp",
                            "port": 7272
                        },
                        "paths": {
                            "/": {
                                "type": "static",
                                "directory": "../web"
                            },
                            "ws": {
                                "type": "websocket"
                            }
                        }
                    }
                ]
            },
            {
                "type": "container",
                "options": {
                    "shutdown": "shutdown-manual",
                    "restart": "restart-always",
                },
                "components": [
                    {
                        "type": "function",
                        "callbacks": {
                            "join": "crossbar.functest_helpers.shutdown_test.join_then_close",
                        },
                        "realm": "foo",
                        "transport": {
                            "type": "websocket",
                            "url": "ws://127.0.0.1:7272/ws",
                            "endpoint": {
                                "type": "tcp",
                                "port": 7272,
                                "host": "127.0.0.1",
                            }
                        },
                        "auth": {}
                    }
                ]
            }
        ]
    }

    class WaitForTransport(object):
        """
        Super hacky, but ... other suggestions? Could busy-wait for ports
        to become connect()-able? Better text to search for?
        """
        def __init__(self, done):
            self.data = ''
            self.done = done

        def write(self, data):
            print(data, end='')
            if self.done.called:
                return

            # in case it's not line-buffered for some crazy reason
            self.data = self.data + data
            if "started Transport ws_test_0" in self.data:
                print("Detected transport starting up")
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    tempdir = _create_temp(request, prefix="cts_auth")
    protocol = yield start_crossbar(
        reactor, virtualenv, tempdir, crossbar_config,
        log_level='debug' if request.config.getoption('logdebug', False) else 'info',
    )

    def cleanup():
        return _cleanup_crossbar(protocol)
    request.addfinalizer(cleanup)

    timeout = sleep(15)
    yield DeferredList([timeout, protocol._all_done], fireOnOneCallback=True, fireOnOneErrback=True)

    # in the "happy path", timeout gets called .. and we want to make
    # sure there's at least two "restart" messages in the logs
    restarts = re.findall("restarting", protocol.logs.getvalue().lower())
    assert len(restarts) >= 2, "Expected at least two restarts"
