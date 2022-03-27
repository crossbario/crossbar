###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from os.path import join
from autobahn.wamp import types
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.internet.process import ProcessExitedAlready
from twisted.internet.error import ProcessTerminated
from twisted.python import log

import pytest

from ..helpers import *


@inlineCallbacks
def test_guest_startup_error(reactor, request, virtualenv, temp_dir):
    """
    worker raises in ctor
    """
    apprunnerguest = join(temp_dir, 'raisingsession.py')
    with open(apprunnerguest, 'w') as f:
        f.write('''
#!/usr/bin/env python
from __future__ import print_function

from autobahn.twisted.wamp import ApplicationSession
class Component(ApplicationSession):
    def __init__(self, *args, **kw):
        print("testcase: __init__")
        raise RuntimeError("A RuntimeError from __init__")


if __name__ == '__main__':
    from autobahn.twisted.wamp import ApplicationRunner
    runner = ApplicationRunner(u"ws://127.0.0.1:7676/ws", u"testee_realm1")
    try:
        runner.run(Component)
    finally:
        print("testcase: post-run()")
''')

    transport = {
        "type": "websocket",
        "id": "testcase",
        "endpoint": {
            "type": "tcp",
            "port": 7676,
        },
        "url": u"ws://localhost:7676/ws"
    }

    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee", "type": "router", "transports": [transport],
                "realms": [{"name": "testee_realm1", "roles": [{"name":"anonymous"}]}]
            },
            {
                "id": "apprunnerguest",
                "type": "guest",
                "executable": sys.executable, "arguments": ['-u', apprunnerguest],
            }
        ]
    }

    cbdir = temp_dir
    cb = yield start_crossbar(reactor, virtualenv, cbdir, config)

    def cleanup():
        try:
            cb.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass
    request.addfinalizer(cleanup)

    try:
        x = yield DeferredList([sleep(5), cb._all_done], fireOnOneErrback=True, fireOnOneCallback=True)
        if x[1] == 0:
            print("We timed-out; crossbar *should* ideally exit with error, though")
    except RuntimeError as e:
        print("We do actually really want an error here")
        print("Got error", e)

    # ...as it is, we can at least make sure the exceptions end up in
    # the log.
    assert 'A RuntimeError from __init__' in cb.logs.getvalue()
    assert 'testcase: __init__' in cb.logs.getvalue()
    assert 'testcase: post-run()' in cb.logs.getvalue()


@inlineCallbacks
def test_guest_error(reactor, virtualenv, temp_dir, request):
    """
    ensure we log an error from a guest worker
    """

    guest = join(temp_dir, 'guest.py')
    with open(guest, 'w') as f:
        f.write('''
#!/usr/bin/env python
import time

raise RuntimeError("some kind of error")
''')
    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee", "type": "router", "transports": [],
                "realms": [{"name": "some_realm", "roles": [{"name":"anonymous"}]}]
            },
            {
                "id": "apprunnerguest", "type": "guest",
                "executable": sys.executable, "arguments": [guest],
            }
        ]
    }

    found_error = Deferred()
    class Logger(object):
        def write(self, line):
            # print("XXX", line)
            if not found_error.called and 'some kind of error' in line:
                found_error.callback(None)
    log_data = Logger()

    cb = yield start_crossbar(reactor, virtualenv, temp_dir, config,
                              stdout=log_data, stderr=log_data)

    def cleanup():
        try:
            cb.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass
    request.addfinalizer(cleanup)

    # give crossbar a chance to start up
    yield DeferredList([sleep(15), found_error], fireOnOneCallback=True, fireOnOneErrback=True)

    assert found_error.called, "Expected to find error from guest in the logs"
    # seems like we'd probably want Crossbar to have exited at this
    # point too. But it doesn't do that currently.


@inlineCallbacks
def test_component_class_startup_error(reactor, request, virtualenv, temp_dir):
    """
    type="class" component that dies in startup
    """
    apprunnerguest = join(temp_dir, 'guest.py')
    with open(apprunnerguest, 'w') as f:
        f.write('''
from __future__ import print_function

from autobahn.twisted.wamp import ApplicationSession
class Component(ApplicationSession):
    def __init__(self, *args, **kw):
        print("testcase: __init__")
        raise RuntimeError("A RuntimeError from __init__")
''')

    transport = {
        "type": "websocket",
        "id": "testcase",
        "endpoint": {
            "type": "tcp",
            "port": 7778,
        },
        "url": u"ws://localhost:7778/ws"
    }
    transport_client = transport.copy()
    transport_client["endpoint"] = transport["endpoint"].copy()
    transport_client["endpoint"]["host"] = "127.0.0.1"

    # could also put code at websocket.py:63 or so to print out
    # exceptions always, not just on debug_wamp...
    # transport_client["debug_wamp"] = True

    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee", "type": "router", "transports": [transport],
                "realms": [{"name": "testee_realm1", "roles": [{"name":"anonymous"}]}]
            },
            {
                "id": "guest_class",
                "type": "container",
                "options": {
                    "pythonpath": [temp_dir]
                },
                "components": [
                    {
                        "type": "class",
                        "classname": "guest.Component",
                        "realm": "testee_realm1",
                        "transport": transport_client,
                    }
                ]
            }
        ]
    }

    class Monitor(object):
        done = Deferred()
        logs = ''
        def write(self, data):
            self.logs = self.logs + data
            print(data, end='')
            if 'A RuntimeError from __init__' in data and not self.done.called:
                self.done.callback(None)
    monitor = Monitor()
    cbdir = temp_dir
    cb = yield start_crossbar(reactor, virtualenv, cbdir, config,
                              stdout=monitor, stderr=monitor)

    def cleanup():
        try:
            cb.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass
    request.addfinalizer(cleanup)

    yield DeferredList([sleep(5), monitor.done, cb._all_done], fireOnOneCallback=True, fireOnOneErrback=True)
    assert not cb._all_done.called, "looks like crossbar exited early"
    assert monitor.done.called, "didn't see our exception"
    assert 'A RuntimeError from __init__' in monitor.logs


@inlineCallbacks
def test_spurious_session_not_established(reactor, request, virtualenv, temp_dir):
    """
    from issue #459 AutobahnPython. if you subscribe to
    wamp.session.on_leave it tries to publish to this after
    disconnecting.
    """
    apprunnerguest = join(temp_dir, 'guest.py')
    with open(apprunnerguest, 'w') as f:
        f.write('''
from __future__ import print_function
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor

from autobahn.twisted.wamp import ApplicationSession
class Component(ApplicationSession):
    @inlineCallbacks
    def onJoin(self, details):
        print("onJoin", details)
        yield self.subscribe(self._on_leave, u'wamp.session.on_leave')
        reactor.callLater(2, self.leave)

    def onLeave(self, reason):
        print("onLeave called", reason)
        self.disconnect()

    def _on_leave(self, session_id):
        print("wamp.session.on_leave", session_id)
''')

    transport = {
        "type": "websocket",
        "id": "testcase",
        "endpoint": {
            "type": "tcp",
            "port": 7778,
        },
        "url": u"ws://localhost:7778/ws"
    }
    transport_client = transport.copy()
    transport_client["endpoint"] = transport["endpoint"].copy()
    transport_client["endpoint"]["host"] = "127.0.0.1"

    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee", "type": "router", "transports": [transport],
                "realms": [{"name": "testee_realm1",
                            "roles": [{
                                "name": "anonymous",
                                "permissions": [
                                    {
                                        "uri": "wamp.*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            }]}]
            },
            {
                "id": "guest_class",
                "type": "container",
                "options": {
                    "pythonpath": [temp_dir],
                    "shutdown": "shutdown-on-last-component-stopped"
                },
                "components": [
                    {
                        "type": "class",
                        "classname": "guest.Component",
                        "realm": "testee_realm1",
                        "transport": transport_client,
                    }
                ]
            }
        ]
    }

    class Monitor(object):
        logs = ''
        def write(self, data):
            self.logs = self.logs + data
            print(data, end='')
    monitor = Monitor()
    cbdir = temp_dir
    cb = yield start_crossbar(reactor, virtualenv, cbdir, config,
                              stdout=monitor, stderr=monitor,
                              )#log_level='debug')

    def cleanup():
        try:
            cb.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass
    request.addfinalizer(cleanup)

    try:
        yield DeferredList([sleep(15), cb._all_done], fireOnOneCallback=True, fireOnOneErrback=True)
    except FirstError as e:
        # we wanted crossbar to fail
        assert isinstance(e.subFailure.value, ProcessTerminated)
        assert e.subFailure.value.exitCode == 1
    assert "Received <class 'autobahn.wamp.message.Event'> message, and session is not yet established" not in monitor.logs
    assert "connection was closed uncleanly" not in monitor.logs
    assert "onLeave called" in monitor.logs
    assert cb._all_done.called, "Expected crossbar to exit"


@inlineCallbacks
def test_on_close_rawsocket(reactor, request, virtualenv, temp_dir):
    """
    make sure a raw_socket that gets shutdown does so properly
    """
    apprunnerguest = join(temp_dir, 'guest.py')
    with open(apprunnerguest, 'w') as f:
        f.write('''
from __future__ import print_function
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor

from autobahn.twisted.wamp import ApplicationSession
class Component(ApplicationSession):
    @inlineCallbacks
    def onJoin(self, details):
        print("onJoin {}".format(details))
        yield self.subscribe(self._on_leave, u'wamp.session.on_leave')
        reactor.callLater(2, self.leave)

    def onLeave(self, *args, **kw):
        print("onLeave called {} {}".format(args, kw))
        self.disconnect()

    def _on_leave(self, session_id):
        print("wamp.session.on_leave {}".format(session_id))
''')

    transport = {
        "type": "rawsocket",
        "id": "testcase",
        "endpoint": {
            "type": "tcp",
            "port": 7776,
        },
    }
    transport_client = transport.copy()
    transport_client["endpoint"] = transport["endpoint"].copy()
    transport_client["endpoint"]["host"] = "127.0.0.1"
    transport_client["serializer"] = "cbor"

    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee", "type": "router", "transports": [transport],
                "realms": [{"name": "testee_realm1",
                            "roles": [{
                                "name": "anonymous",
                                "permissions": [
                                    {
                                        "uri": "wamp.*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                        },
                                        "cache": True,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            }]}]
            },
            {
                "id": "guest_class",
                "type": "container",
                "options": {
                    "pythonpath": [temp_dir],
                    "shutdown": "shutdown-on-last-component-stopped"
                },
                "components": [
                    {
                        "type": "class",
                        "classname": "guest.Component",
                        "realm": "testee_realm1",
                        "transport": transport_client,
                    }
                ]
            }
        ]
    }

    class Monitor(object):
        logs = ''
        def write(self, data):
            self.logs = self.logs + data
            print(data, end='')
    monitor = Monitor()
    cbdir = temp_dir
    cb = yield start_crossbar(
        reactor, virtualenv, cbdir, config,
        stdout=monitor,
        stderr=monitor,
        # log_level='debug',
    )

    def cleanup():
        try:
            cb.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass
    request.addfinalizer(cleanup)

    try:
        yield DeferredList([sleep(15), cb._all_done], fireOnOneCallback=True, fireOnOneErrback=True)
    except FirstError as e:
        # we wanted crossbar to fail
        assert isinstance(e.subFailure.value, ProcessTerminated)
        assert e.subFailure.value.exitCode == 1
    assert "Received <class 'autobahn.wamp.message.Event'> message, and session is not yet established" not in monitor.logs
    assert "connection was closed uncleanly" not in monitor.logs
    assert "onLeave called" in monitor.logs
    assert cb._all_done.called, "Expected crossbar to exit"


@inlineCallbacks
def test_log_error_from_subscribe(reactor, request, virtualenv, temp_dir):
    """
    from issue #526 AutobahnPython.
    """
    apprunnerguest = join(temp_dir, 'guest.py')
    with open(apprunnerguest, 'w') as f:
        f.write('''
from __future__ import print_function
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.types import PublishOptions
import sys

class Component(ApplicationSession):
    @inlineCallbacks
    def onJoin(self, details):
        print("onJoin", details)
        sys.stderr.write("this is to stderr\\n")
        s = yield self.subscribe(self.error_pub, u'com.example.foo')
        print("subscribed:", s)
        p = yield self.publish(u"com.example.foo", 1, 2, 3, options=PublishOptions(acknowledge=True, exclude_me=False))
        print("published:", p)
        reactor.callLater(2, self.leave)

    def onLeave(self, reason):
        print("onLeave called", reason)
        self.disconnect()

    def error_pub(self, *args, **kw):
        print("publication:", args, kw)
        sys.stderr.write("about to throw\\n")
        raise RuntimeError("foo")
''')

    transport = {
        "type": "websocket",
        "id": "testcase",
        "endpoint": {
            "type": "tcp",
            "port": 7778,
        },
        "url": u"ws://localhost:7778/ws"
    }
    transport_client = transport.copy()
    transport_client["endpoint"] = transport["endpoint"].copy()
    transport_client["endpoint"]["host"] = "127.0.0.1"

    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee", "type": "router", "transports": [transport],
                "realms": [{"name": "testee_realm1",
                            "roles": [{
                                "name": "anonymous",
                                "permissions": [
                                    {
                                        "uri": "*",
                                        "allow": {
                                            "publish": True,
                                            "subscribe": True,
                                        },
                                        "cache": False,
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True,
                                        }
                                    }
                                ]
                            }]
                        }]
            },
            {
                "id": "guest_class",
                "type": "container",
                "options": {
                    "pythonpath": [temp_dir],
                    "shutdown": "shutdown-on-last-component-stopped"
                },
                "components": [
                    {
                        "type": "class",
                        "classname": "guest.Component",
                        "realm": "testee_realm1",
                        "transport": transport_client,
                    }
                ]
            }
        ]
    }

    class Monitor(object):
        logs = ''
        def write(self, data):
            self.logs = self.logs + data
            print(data, end='')
    monitor = Monitor()
    cbdir = temp_dir
    cb = yield start_crossbar(reactor, virtualenv, cbdir, config,
                              stdout=monitor, stderr=monitor,
                              )#log_level='debug')

    def cleanup():
        try:
            cb.transport.signalProcess('TERM')
        except ProcessExitedAlready:
            pass
    request.addfinalizer(cleanup)

    try:
        yield DeferredList([sleep(20), cb._all_done], fireOnOneCallback=True, fireOnOneErrback=True)
    except FirstError as e:
        # we wanted crossbar to fail
        assert isinstance(e.subFailure.value, ProcessTerminated)
        assert e.subFailure.value.exitCode == 1
    assert "RuntimeError" in monitor.logs
    assert cb._all_done.called, "Expected crossbar to exit"
    print(monitor.logs)
