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
from twisted.internet import reactor
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks, DeferredList, returnValue
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
from ..helpers import _start_session
from ..helpers import HelperSession


@pytest_twisted.inlineCallbacks
def test_shutdown_failed_component(reactor, request, virtualenv, session_temp):
    """
    ticket 1576: a component that registers (or subscribes) to
    something but disconnects before the dynamic authenticator is done
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
                        "name": "root",
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
                            },
                            {
                                "name": "authorized",
                                "authorizer": "test.authorize"
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
                            "port": 7373
                        },
                        "paths": {
                            "ws": {
                                "type": "websocket",
                                "auth": {
                                    "anonymous": {
                                        "type": "static",
                                        "role": "anonymous",
                                    },
                                    "ticket": {
                                        "type": "dynamic",
                                        "authenticator": "test.authenticate",
                                    }
                                }
                            }
                        }
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
            if "ws_test_0 has started" in self.data:
                print("Detected transport starting up")
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    tempdir = _create_temp(request, prefix="cts_auth")
    print("starting in {}".format(tempdir))
    got_transport = Deferred()
    protocol_d = start_crossbar(
        reactor, virtualenv, tempdir, crossbar_config,
        stdout=WaitForTransport(got_transport),
        stderr=WaitForTransport(got_transport),
        log_level='debug' if request.config.getoption('logdebug', False) else 'info',
    )

    print("waiting for magic")
    yield got_transport
    print(protocol_d)
    protocol = yield protocol_d

    def cleanup():
        try:
            protocol.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass
    request.addfinalizer(cleanup)

    # the session that handles authorize/authenticate

    @inlineCallbacks
    def slow_authenticate(*args, **kw):
        yield sleep(10)
        returnValue({
            "role": "authorized",
            "authid": "foo",
        })

    @inlineCallbacks
    def slow_authorize(*args):
        yield sleep(5)
        returnValue({
            "allow": True
        })

    session = yield _start_session(False, "ws://localhost:7373/ws", "root", HelperSession)
    yield session.register(slow_authenticate, u"test.authenticate")
    yield session.register(slow_authorize, u"test.authorize")

    # the "error" session, which disconnects immediately after trying
    # to register and subscribe
    class DisconnectBeforeAuthorize(HelperSession):
        def onConnect(self):
            self.join("root", ["ticket"])

        def onChallenge(self, ch):
            return "sekrit"

        def onJoin(self, details):
            self.register(lambda: "foo", "foo.2")
            self.subscribe(lambda x: "asdf", "bar")
            self.publish("ding", "something")
            reactor.callLater(0.1, self.disconnect)
            HelperSession.onJoin(self, details)

    client1 = yield _start_session(False, "ws://localhost:7373/ws", "root", DisconnectBeforeAuthorize)

    yield sleep(20)
