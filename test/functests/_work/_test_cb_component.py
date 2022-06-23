###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from autobahn.wamp import types
from autobahn.twisted.component import Component, run
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.python import log
from os.path import join

import pytest

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import *
from ..helpers import _create_temp, _cleanup_crossbar


@pytest.fixture(scope="session")
def component_crossbar(reactor, request, virtualenv, session_temp):

    crossbar_config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee",
                "type": "router",
                "realms": [
                    {
                        "name": "auth_realm",
                        "roles": [
                            {
                                "name": "authenticated",
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
                            },
                            {
                                "name": "anonymous",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "subscribe": True,
                                            "call": True,
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            },
                            {
                                "name": "role0",
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
                            },
                            {
                                "name": "role1",
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
                        "id": "auth_ws_99",
                        "endpoint": {
                            "type": "tcp",
                            "port": 7171
                        },
                        "paths": {
                            "/": {
                                "type": "static",
                                "directory": "../web"
                            },
                            "auth_ws": {
                                "type": "websocket",
                                "auth": {
                                    "cryptosign": {
                                        "type": "static",
                                        "principals": {
                                            "someone@example.com": {
                                                "realm": "auth_realm",
                                                "role": "authenticated",
                                                "authorized_keys": [
                                                    "545efb0a2192db8d43f118e9bf9aee081466e1ef36c708b96ee6f62dddad9122"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ],
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
            if "started Transport auth_ws_99" in self.data:
                print("Detected transport starting up")
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    tempdir = _create_temp(request, prefix="cts_auth")
    listening = Deferred()
    from cts.functional_tests.helpers import start_crossbar
    protocol = pytest.blockon(
        start_crossbar(
            reactor, virtualenv, tempdir, crossbar_config,
            stdout=WaitForTransport(listening),
            stderr=WaitForTransport(listening),
            log_level='debug' if request.config.getoption('logdebug', False) else False,
        )
    )
    request.addfinalizer(partial(_cleanup_crossbar, protocol))

    timeout = sleep(10)
    pytest.blockon(DeferredList([timeout, listening], fireOnOneErrback=True, fireOnOneCallback=True))
    if timeout.called:
        raise RuntimeError("Timeout waiting for crossbar to start")
    return protocol


@pytest.inlineCallbacks
def test_component_wrong_auth(reactor, component_crossbar):
    """
    a component connects which can't authenticate; should get errors
    """

    def main(reactor, session):
        assert False, "should not have joined the session"

    component = Component(
        transports=[
            {
                u"url": u"ws://localhost:7171/auth_ws",
                u"endpoint": {
                    u"type": u"tcp",
                    u"host": u"localhost",
                    u"port": 7171,
                },
                u"max_retries": 1,
            },
        ],
        authentication={
            u"anonymous": {},
        },
        realm=u"auth_realm",
        main=main,
    )

    try:
        yield component.start(reactor)
        assert False, "should fail"
    except Exception as e:
        assert "Exhausted all transport connect attempts" in str(e)


@pytest.inlineCallbacks
def test_component_start_twice(reactor, component_crossbar):
    """
    a component which start()s twice
    """

    sessions = []

    def main(reactor, session):
        sessions.append(session)
        return session.leave()

    component = Component(
        transports=[
            {
                u"url": u"ws://localhost:7171/auth_ws",
                u"endpoint": {
                    u"type": u"tcp",
                    u"host": u"localhost",
                    u"port": 7171,
                },
                u"max_retries": 1,
            },
        ],
        authentication={
            u"cryptosign": {
                u"privkey": u"dc1371c6171411d24d149aaf9bf6c83c12818690f04421467fe318b9a14f8db7",
                u"authid": u"someone@example.com",
                u"authrole": u"authenticated",
            }
        },
        realm=u"auth_realm",
        main=main,
    )

    d0 = component.start(reactor)
    yield d0
    d1 = component.start(reactor)
    yield d1
    assert len(sessions) == 2


@pytest.inlineCallbacks
def test_component_cryptosign_auth(reactor, component_crossbar):

    joined = Deferred()
    def main(reactor, session):
        joined.callback(session)
        return session.leave()

    component = Component(
        transports=[
            {
                u"url": u"ws://localhost:7171/auth_ws",
                u"endpoint": {
                    u"type": u"tcp",
                    u"host": u"localhost",
                    u"port": 7171,
                },
                u"max_retries": 1,
            },
        ],
        authentication={
            u"cryptosign": {
                u"privkey": u"dc1371c6171411d24d149aaf9bf6c83c12818690f04421467fe318b9a14f8db7",
                u"authid": u"someone@example.com",
                u"authrole": u"authenticated",
            }
        },
        realm=u"auth_realm",
        main=main,
    )

    yield component.start(reactor)
    yield joined
