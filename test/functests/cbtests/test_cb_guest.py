###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

import sys
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


@inlineCallbacks
def test_guest_logging(reactor, request, virtualenv, virtualenv3, temp_dir):
    """
    Test logging of stdout/stderr from Guest worker.
    """

    client_port = server_port = 7778
    client_realm = server_realm = u'realm_7778'

    guestcode = join(temp_dir, 'loggingguest.py')
    with open(guestcode, 'w') as f:
        f.write('''
from __future__ import print_function
from sys import stderr, stdout
#from autobahn.twisted.wamp import ApplicationSession
from autobahn.asyncio.wamp import ApplicationSession

class Component(ApplicationSession):
    def onJoin(self, details):
        print("testcase: onJoin stdout", file=stdout)
        print("testcase: onJoin stderr", file=stderr)

    def onClose(self, wasClean):
        print("testcase: onClose stdout", file=stdout)
        print("testcase: onClose stderr", file=stderr)

if __name__ == '__main__':
    #from autobahn.twisted.wamp import ApplicationRunner
    from autobahn.asyncio.wamp import ApplicationRunner
    runner = ApplicationRunner(u"ws://127.0.0.1:%(client_port)s/ws", u"%(client_realm)s")
    runner.run(Component)
    print("testcase: post-run() stdout", file=stdout)
    print("testcase: post-run() stderr", file=stderr)
''' % dict(client_port=client_port, client_realm=client_realm))

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
                "id": "logging_guest",
                "type": "guest",
                "executable": join(virtualenv3, 'bin', 'python3'),
                "arguments": ['-u', guestcode],
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
    logs = cb.logs.getvalue()
    assert 'testcase: onJoin stdout' in logs, logs
    assert 'testcase: onJoin stderr' in logs, logs

    # now shut it down
    cb.transport.signalProcess('KILL')

    if False:
        # something screwy with shutdown still (might just need to
        # handle SIGTERM properly in children :/) should see ALL the
        # messages now
        logs = cb.logs.getvalue()
        assert 'testcase: onJoin stdout' in logs, logs
        assert 'testcase: onJoin stderr' in logs, logs
        assert 'testcase: onClose stdout' in logs, logs
        assert 'testcase: onClose stderr' in logs, logs
        assert 'testcase: post-run() stdout' in logs, logs
        assert 'testcase: post-run() stderr' in logs, logs
