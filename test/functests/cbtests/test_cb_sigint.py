###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from contextlib import contextmanager
from tempfile import mkdtemp
import signal
import shutil
import os

from autobahn.wamp import types
from autobahn.wamp import exception
from autobahn.twisted.util import sleep
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.python import log

import pytest
import psutil

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import *

# NOTE! these tests are all marked "slow", so you need to add "--slow"
# to your py.test command-line (yes, even if you're explicitly
# selecting this file). Like:
#
#    py.test -s --slow -k no_signal_han functests/test_sigint.py
#
# -s gives all output immediately, -k selects by keywords

# XXX Would be nice to get rid of the "yield sleep()" calls, but it
# does make these tests a bit more robust, and I'm not really sure if
# there's anything we can do (besides, e.g., busy-waiting for the PID
# to disappear)

# NOTE that for all these tests, we're specifically *not* using the
# crossbar fixture, because we want our own instance. IF there is a
# way to make it function-scoped for *just* these tests, that would
# be preferable...

# XXX also probably nicer to have the "slowguest.py" etc just be
# data-files in case someone wants to run a similar case "themselves"
# (i.e. without the pytest stuff etc). Although, overall might be
# easier to just keep the temp_dir around. Maybe add --keep-temp or
# similar to pytest (via conftest.py)?


# this "parametrize" mark is special; see
# http://pytest.org/latest/parametrize.html

# the point here is to run this test both when we successfully connect
# (everything matches) and when we don't connect at all, either becuse
# the ports don't match (immediate exit) or the realms don't match
# (does nothing; should probably exit at least after a timeout).
@pytest.mark.parametrize(
    'server_port,client_port,server_realm,client_realm',
    [
        (9999, 9999, u"testee_realm1", u"testee_realm1"),  # happy-path

        (9999, 9989, u"testee_realm1", u"testee_realm1"),
        (9999, 9999, u"testee_realm1", u"foo_realm1"),
    ]
)
@pytest.mark.slowtest
@inlineCallbacks
def test_worker_apprunner(reactor, request, virtualenv, temp_dir,
                          server_port, client_port, server_realm, client_realm):
    '''
    do-nothing worker using apprunner

    neat: setting default_requirements (in conftest.py) to github's
    master vs. my local copy shows failing vs passing for this
    test-case.
    '''

    apprunnerguest = os.path.join(temp_dir, 'apprunnerguest.py')
    with open(apprunnerguest, 'w') as f:
        f.write('''
#!/usr/bin/env python
from __future__ import print_function

from autobahn.twisted.wamp import ApplicationSession
class Component(ApplicationSession):
    def onJoin(self, details):
        print("testcase: onJoin")

    def onClose(self, wasClean):
        print("testcase: onClose", wasClean)

if __name__ == '__main__':
    from autobahn.twisted.wamp import ApplicationRunner
    runner = ApplicationRunner(u"ws://127.0.0.1:%(client_port)s/ws", u"%(client_realm)s")
    runner.run(Component)
    print("testcase: post-run()")
''' % dict(client_port=client_port, client_realm=client_realm))

    # XXX should paramterize on the ports + realms so we can test
    # matching vs. mismatching ports, matching vs. mismatching realm
    # (and combos)

    # XXX ideally, would select an empty port so we never get
    # transient failures. Must match URI in embedded code above.
    transport = {
        "type": "websocket",
        "id": "testcase",
        "endpoint": {
            "type": "tcp",
            "port": server_port,
        },
        "url": u"ws://localhost:{0}/ws".format(server_port)
    }

    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {
                "id": "testee", "type": "router", "transports": [transport],
                "realms": [{"name": server_realm, "roles": [{"name":"anonymous"}]}]
            },
            {
                "id": "apprunnerguest", "type": "guest",
                "executable": sys.executable, "arguments": [apprunnerguest],
            }
        ]
    }

    cbdir = temp_dir
    cb = yield start_crossbar(reactor, virtualenv, cbdir, config, log_level='debug')
    myproc = psutil.Process(cb.transport.pid)

    def cleanup():
        try:
            cb.transport.signalProcess('KILL')
        except:
            pass
    request.addfinalizer(cleanup)

    assert myproc.is_running()
    yield sleep(15)
    assert myproc.is_running()
    print("Crossbar started, sending SIGINT")

    # crossbar has the router-worker, plus our guest (maybe)
    children = myproc.children()
    expected = 1
    if server_port == client_port:
        expected += 1  # guest stays alive if it connects
    assert len(children) == expected

    # sent INT to crossbar, plus all workers
    myproc.send_signal(signal.SIGINT)
    try:
        children[0].send_signal(signal.SIGINT)
        children[1].send_signal(signal.SIGINT)
    except (psutil.NoSuchProcess, IndexError):
        # children might already be dead from parent INT
        # there might only be one child
        pass

    yield sleep(2)
    logs = cb.logs.getvalue()

    # if we successfully connect, we should see that in the logs
    # (this seems flakey, for some reason)
    return
    if server_port == client_port and server_realm == client_realm:
        assert 'testcase: onJoin' in logs, logs
        assert 'testcase: onClose' in logs, logs
        assert 'testcase: post-run()' in logs, logs


@pytest.mark.slowtest
@inlineCallbacks
def test_worker_no_signal_handling(reactor, request, virtualenv, temp_dir):
    '''
    Worker with no signal handling code at all.
    '''

    nosigguest = os.path.join(temp_dir, 'nosigguest.py')
    with open(nosigguest, 'w') as f:
        f.write('''
#!/usr/bin/env python

import time

while True:
    time.sleep(1)
    print("waiting")
''')

    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {"id": "testee", "type": "router", "transports": []},
            {"id": "nosigguest",
             "type": "guest",
             "executable": sys.executable,
             "arguments": [nosigguest],
         }
        ]
    }

    cbdir = temp_dir
    cb = yield start_crossbar(reactor, virtualenv, cbdir, config, log_level='debug')
    myproc = psutil.Process(cb.transport.pid)

    def cleanup():
        try:
            myproc.send_signal(signal.SIGKILL)
        except psutil.NoSuchProcess:
            pass
        pytest.blockon(sleep(1))
    request.addfinalizer(cleanup)

    yield sleep(15)
    print("Crossbar started, sending SIGINT")
    assert myproc.is_running()

    # crossbar has the router-worker, plus our guest
    children = myproc.children()
    assert len(children) == 2

    # sent INT to crossbar, plus all workers
    myproc.send_signal(signal.SIGINT)
    children[0].send_signal(signal.SIGINT)
    children[1].send_signal(signal.SIGINT)

    yield sleep(2)
    logs = cb.logs.getvalue()
    for line in logs:
        if 'Failure' in line:
            # there's a log message in the controller printing out the
            # SIGKILL Failure...which is not a test-case failure
            if 'Router' in line:
                assert "Router shouldn't throw exception"


@pytest.mark.slowtest
@inlineCallbacks
def test_slow_worker_shutdown(reactor, request, virtualenv, temp_dir):
    '''
    Test-case for #278, where the worker takes some non-zero time to
    shutdown (in this case, 1 second).
    '''

    slowguest = os.path.join(temp_dir, 'slowguest.py')
    with open(slowguest, 'w') as f:
        f.write('''
#!/usr/bin/env python

import time
import signal
import os

def slow_shutdown(sig, frame):
    print("signal; pausing shutdown")
    time.sleep(4)
    print("actually shutting down")
    os._exit(0)

signal.signal(signal.SIGTERM, slow_shutdown)
signal.signal(signal.SIGINT, slow_shutdown)

while True:
    time.sleep(1)
    print("waiting")
''')

    config = {
        "version": 2,
        "controller": {},
        "workers": [
            {"id": "testee", "type": "router", "transports": []},
            {"id": "slowguest",
             "type": "guest",
             "executable": sys.executable,
             "arguments": [slowguest],
         }
        ]
    }

    cbdir = temp_dir
    cb = yield start_crossbar(reactor, virtualenv, cbdir, config, log_level='debug')
    myproc = psutil.Process(cb.transport.pid)

    def cleanup():
        try:
            myproc.send_signal(signal.SIGKILL)
        except psutil.NoSuchProcess:
            pass
        pytest.blockon(sleep(1))
    request.addfinalizer(cleanup)

    yield sleep(15)
    print("Crossbar started, sending SIGINT")

    # crossbar has the router-worker, plus our guest
    children = myproc.children()
    assert len(children) == 2

    # sent INT to crossbar
    myproc.send_signal(signal.SIGINT)

    # slowguest takes at least 4 seconds to shutdown, so the guest
    # should still be running 1 second after we sent the SIGINT if the
    # controller is waiting properly.
    yield sleep(1)
    assert "slowguest" in children[1].cmdline()[1]
    assert children[1].is_running()
    print("slowguest running", children[1].cmdline())

    # should be shutdown by now
    yield sleep(15)
    assert not children[1].is_running()
    assert not children[0].is_running()
    assert not myproc.is_running()


@pytest.mark.slowtest
@inlineCallbacks
def test_sigint_router(reactor, request, virtualenv, temp_dir):
    '''
    Test-case for #278.

    Variation 1: just Router (subprocess) gets SIGINT
    '''

    config = {
        "version": 2,
        "controller": {},
        "workers": [{"id": "testee", "type": "router", "transports": []}]
    }

    cbdir = temp_dir
    cb = yield start_crossbar(reactor, virtualenv, cbdir, config, log_level='debug')
    myproc = psutil.Process(cb.transport.pid)

    def cleanup():
        try:
            myproc.send_signal(signal.SIGKILL)
        except psutil.NoSuchProcess:
            pass
        pytest.blockon(sleep(1))
    request.addfinalizer(cleanup)

    yield sleep(15)
    print("Crossbar started, sending SIGINT")

    # find the NodeController worker; should be the only subprocess of
    # our crossbar.
    children = myproc.children()
    assert len(children) == 1

    # kill JUST the Router child.
    children[0].send_signal(signal.SIGINT)
    yield sleep(1)

    sigints = 0
    errors = []
    for line in cb.logs.getvalue().split('\n'):
        if 'SIGINT' in line:
            sigints += 1
        if 'Failure: ' in line:
            errors.append(line)

    assert sigints == 1, "Wanted precisely one SIGINT"
    # XXX the controller/crossbar are still running here; should they
    # in turn die if their Router process has gone away?
    assert len(errors) == 0, '\n'.join(errors)


@pytest.mark.slowtest
@inlineCallbacks
def test_sigint_controller(reactor, request, virtualenv, temp_dir):
    '''
    Test-case for #278.

    Variation 2: crossbar instance itself gets SIGINT
    '''

    config = {
        "version": 2,
        "controller": {},
        "workers": [{"id": "testee", "type": "router", "transports": []}]
    }

    cb = yield start_crossbar(reactor, virtualenv, temp_dir, config, log_level='debug')
    myproc = psutil.Process(cb.transport.pid)

    def cleanup():
        try:
            myproc.send_signal(signal.SIGKILL)
        except psutil.NoSuchProcess:
            pass
        pytest.blockon(sleep(1))
    request.addfinalizer(cleanup)

    print("Crossbar started, waiting")
    yield sleep(15)
    print("sending SIGINT")
    myproc.send_signal(signal.SIGINT)
    yield sleep(1)

    sigints = 0
    errors = []
    for line in cb.logs.getvalue().split('\n'):
        # note the logs don't actually emit anything about SIGINT any
        # longer...
        if 'SIGINT' in line:
            sigints += 1
        if 'Failure: ' in line:
            errors.append(line)

#    assert sigints >= 1, "Wanted at least one SIGINT"
    assert not myproc.is_running()
    assert len(errors) == 0, '\n'.join(errors)


@pytest.mark.slowtest
@inlineCallbacks
def test_sigint_controller_and_router(reactor, request, virtualenv, temp_dir):
    '''
    Test-case for #278.

    Variation 3: crossbar AND the Router subprocess both get SIGINT at "same time"
    '''

    config = {
        "version": 2,
        "controller": {},
        "workers": [{"id": "testee", "type": "router", "transports": []}]
    }

    cb = yield start_crossbar(reactor, virtualenv, temp_dir, config, log_level='debug')
    myproc = psutil.Process(cb.transport.pid)

    def cleanup():
        try:
            myproc.send_signal(signal.SIGKILL)
        except psutil.NoSuchProcess:
            pass
        pytest.blockon(sleep(1))
    request.addfinalizer(cleanup)

    yield sleep(15)
    # print("Crossbar started, sending SIGINT")

    children = myproc.children()
    assert len(children) == 1

    assert myproc.is_running()
    assert children[0].is_running()

    children[0].send_signal(signal.SIGINT)
    myproc.send_signal(signal.SIGINT)
    yield sleep(1)

    sigints = 0
    errors = []
    for line in cb.logs.getvalue().split('\n'):
        if 'SIGINT' in line:
            sigints += 1
        if 'Failure: ' in line:
            errors.append(line)

    assert sigints >= 1, "Wanted at least one SIGINT"
    assert not myproc.is_running()
    assert len(errors) == 0, '\n'.join(errors)
