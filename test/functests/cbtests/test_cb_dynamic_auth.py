###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from functools import partial

from autobahn.wamp import types, exception
from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.wamp import Session
from autobahn.wamp.auth import create_authenticator
from autobahn.twisted.util import sleep
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks, DeferredList
from twisted.logger import globalLogPublisher

import pytest

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import _create_temp
from ..helpers import _cleanup_crossbar
from ..helpers import start_crossbar
from ..helpers import functest_session


@pytest.fixture(scope="module")
def dynamic_authorize_crossbar(reactor, request, virtualenv, session_temp):
    """
    Provides a 'slow' dynamic authorizer that takes 2 seconds to
    authorize a call
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
                        "name": "realm-auth",
                        "roles": [
                            {
                                "name": "role",
                                "permissions": [
                                    {
                                        "uri": "test.authenticate",
                                        "allow": {
                                            "register": True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "name": "slow_authentication",
                        "roles": [
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
                            "port": 7979
                        },
                        "paths": {
                            "/": {
                                "type": "static",
                                "directory": "../web"
                            },
                            "test_dyn_cryptosign": {
                                "type": "websocket",
                                "auth": {
                                    "cryptosign": {
                                        "type": "dynamic",
                                        "authenticator": "test.authenticate",
                                        "authenticator-realm": "realm-auth"
                                    }
                                }
                            }
                        }
                    }
                ],
                "components": [
                    {
                        "type": "function",
                        "realm": "realm-auth",
                        "role": "role",
                        "callbacks": {
                            "join": "crossbar.functest_helpers.auth.setup_auth"
                        },
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
    listening = Deferred()
    protocol = pytest.blockon(
        start_crossbar(
            reactor, virtualenv, tempdir, crossbar_config,
            stdout=WaitForTransport(listening),
            stderr=WaitForTransport(listening),
            log_level='debug' if request.config.getoption('logdebug', False) else False,
        )
    )
    request.addfinalizer(partial(_cleanup_crossbar, protocol))

    timeout = sleep(40)
    pytest.blockon(DeferredList([timeout, listening], fireOnOneErrback=True, fireOnOneCallback=True))
    if timeout.called:
        raise RuntimeError("Timeout waiting for crossbar to start")
    return protocol


def create_session(config):
    session = Session(config)
    session.add_authenticator(
        create_authenticator(
            "cryptosign",
            authid="foo",
            authrole="role0",
            privkey="a"*64,
        )
    )

    def joined(session, details):
        print("joined: {} {}".format(session, details))
        session.config.extra['running'].callback(session)
    session.on('join', joined)

    def left(session, details):
        if "no_such_procedure" in str(details.reason):
            session.config.extra['running'].errback(Exception(details.reason))
    session.on('leave', left)

    def disconnected(*args, **kw):
        print("disconnect: {} {}".format(args, kw))
    session.on('disconnect', disconnected)

    return session


@inlineCallbacks
def test_dynamic_auth(dynamic_authorize_crossbar):

    session = yield functest_session(
        url=u"ws://localhost:7979/test_dyn_cryptosign",
        realm="slow_authentication",
        session_factory=create_session,
    )
    print("session: {}".format(session))
    yield session.leave()
