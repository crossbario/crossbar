###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

import json
import random
from functools import partial
from os.path import join

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.util import sleep
from twisted.internet.defer import Deferred, FirstError, DeferredList, inlineCallbacks
from twisted.internet.process import ProcessExitedAlready
from twisted.python import log

import pytest
import treq

from ..helpers import _create_temp, _cleanup_crossbar, functest_session

# XXX cleanup: should get rid of transports after each test? and/or
# make a "rest_transport" fixture for this module might be a better way...

@pytest.fixture(scope="session")
def rest_crossbar(reactor, request, virtualenv, session_temp):

    crossbar_config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee",
                "type": "router",
                "realms": [
                    {
                        "name": "some_realm",
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
                            },
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
                        "id": "web_trans",
                        "endpoint": {
                            "type": "tcp",
                            "port": 8585,
                        },
                        "paths": {
                            "/": {
                                "type": "caller",
                                "realm": "some_realm",
                                "role": "role0"
                            }
                        }
                    },
                    {
                        "type": "websocket",
                        "endpoint": {
                            "type": "tcp",
                            "port": 8686
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
            if "started Transport web_trans" in self.data:
                print("Detected transport starting up")
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    tempdir = _create_temp(request, prefix="cts_auth")
    listening = Deferred()
    from ..helpers import start_crossbar
    protocol = pytest.blockon(
        start_crossbar(
            reactor, virtualenv, tempdir, crossbar_config,
            stdout=WaitForTransport(listening),
            stderr=WaitForTransport(listening),
            log_level='debug' if request.config.getoption('logdebug', False) else False,
        )
    )
    request.addfinalizer(partial(_cleanup_crossbar, protocol))

    timeout = sleep(15)
    pytest.blockon(DeferredList([timeout, listening], fireOnOneErrback=True, fireOnOneCallback=True))
    if timeout.called:
        raise RuntimeError("Timeout waiting for crossbar to start")
    return protocol


@inlineCallbacks
def test_rest_caller_error(rest_crossbar, request):

    body = {
        u"procedure": u"some.method",
        u"args": [1],
        u"kwargs": {u"key": 2},
    }
    timeout = sleep(5)
    r = treq.post(
        "http://localhost:8585/",
        json.dumps(body).encode('utf8'),
        headers={b'Content-Type': [b'application/json']},
    )
    results = yield DeferredList([timeout, r], fireOnOneCallback=True, fireOnOneErrback=True)
    r = results[0]

    assert r.code >= 200 and r.code < 300
    data = yield r.content()
    data = json.loads(data)

    assert 'args' in data
    # one arg, of a 3-tuple (all sequences become lists)


@inlineCallbacks
def test_rest_call(crossbar, request, rest_crossbar):
    """
    call an rpc via HTTP call from client
    """

    session = yield functest_session(
        url=u"ws://localhost:8686",
        realm=u'some_realm',
        role="role0",
    )

    def some_method(*args, **kw):
        return types.CallResult("greetings", "fellow", "human", dict())
    reg = yield session.register(some_method, u'some.method')
    request.addfinalizer(reg.unregister)

    body = {
        u"procedure": u"some.method",
        u"args": [1],
        u"kwargs": {u"key": 2},
    }
    timeout = sleep(5)
    r = treq.post(
        "http://localhost:8585/",
        json.dumps(body).encode('utf8'),
        headers={b'Content-Type': [b'application/json']},
    )
    results = yield DeferredList([timeout, r], fireOnOneCallback=True, fireOnOneErrback=True)
    r = results[0]

    assert r.code >= 200 and r.code < 300
    data = yield r.content()
    data = json.loads(data)

    assert 'args' in data
    # one arg, of a 3-tuple (all sequences become lists)
#    assert data['args'] == [['greetings', 'fellow', 'human']]


@inlineCallbacks
def test_rest_error(crossbar, request, rest_crossbar):
    """
    an RPC call that raises an error
    """

    session = yield functest_session(
        url=u"ws://localhost:8686",
        realm=u'some_realm',
        role="role0",
    )

    def sad_method(*args, **kw):
        raise RuntimeError("sadness")
    reg = yield session.register(sad_method, u'sad.method')
    request.addfinalizer(lambda: reg.unregister())

    body = {
        u"procedure": u"sad.method",
    }
    r = treq.post(
        "http://localhost:8585/",
        json.dumps(body).encode('utf8'),
        headers={'Content-Type': ['application/json']},
    )
    timeout = sleep(5)

    results = yield DeferredList([r, timeout], fireOnOneCallback=True, fireOnOneErrback=True)
    r = results[0]

    # the HTTP "call" succeeds...
    assert r.code >= 200 and r.code < 300
    data = yield r.content()
    data = json.loads(data)

    # ...but there's an error key
    assert 'error' in data
    assert 'args' in data

    assert data['error'] == 'wamp.error.runtime_error'
    assert data['args'] == ['sadness']


@inlineCallbacks
def test_rest_no_procedure(crossbar, request, rest_crossbar):
    """
    try to make a call with no "procedure" arg
    """

    session = yield functest_session()

    r = yield treq.post(
        "http://localhost:8585/",
        json.dumps({}).encode('utf8'),
        headers={'Content-Type': ['application/json']},
    )

    # should get an HTTP error of some kind
    assert r.code >= 400 and r.code < 500
