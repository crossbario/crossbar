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
from twisted.python import log

import pytest

from ..helpers import *


@inlineCallbacks
def test_session_leave(crossbar, reactor):
    """
    make sure we really forget about a session after leave()
    """

    # setup
    left = Deferred()
    class TestSession(HelperSession):
        def onJoin(self, details):
            HelperSession.onJoin(self, details)
            reactor.callLater(1, self.leave)
            #reactor.callLater(1, self._transport.sendClose)

        def onLeave(self, details):
            left.callback(details)

    # make sure we close the session within 5 seconds
    session = yield functest_session(session_factory=TestSession, debug=True)
    timeout = sleep(5)
    res = yield DeferredList([timeout, left], fireOnOneCallback=True, fireOnOneErrback=True)

    # ensure we didn't timeout, and got a "wamp.close.normal" onLeave callback
    assert left.called
    assert not timeout.called
    assert left.result.reason == 'wamp.close.normal'


@inlineCallbacks
def test_dangling_session(crossbar, reactor, session_temp):
    """
    make sure we really forget about a session after leave()
    """

    session0 = yield functest_session(debug=True, log_level='debug')
    session1 = yield functest_session(debug=True, log_level='debug')

    sessions0 = yield session0.call(u'wamp.session.list')
    assert session0._session_id in sessions0
    assert session1._session_id in sessions0

    # nuke session0, and give crossbar a few seconds "just in case".
    session0._transport.abort()
    yield sleep(5)

    # confirm that session0 doesn't show up anymore
    sessions1 = yield session1.call(u'wamp.session.list')
    assert session0._session_id not in sessions1
    assert session1._session_id in sessions1
