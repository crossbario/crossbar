#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession

from .helpers import make_router_and_realm, connect_application_session
from crossbar._logging import LogCapturer


class TestamentTests(unittest.TestCase):

    # FIXME:
    # [ERROR] Traceback (most recent call last):
    # File "/home/oberstet/scm/crossbario/crossbar/crossbar/router/test/test_testament.py", line 203, in test_one_scope_does_not_affect_other
    # d = session.call("wamp.session.add_testament", "com.test.dc",
    # builtins.AttributeError: 'NoneType' object has no attribute 'call'
    skip = True

    def setUp(self):

        self.logs = LogCapturer()
        self.logs.__enter__()
        self.addCleanup(lambda: self.logs.__exit__(None, None, None))

    def test_destroy_testament_sent_on_destroy(self):
        """
        If one session calls wamp.session.add_testament and then the session is
        destroyed, the message it filed as a testament will be sent to
        subscribers of the chosen topic.
        """
        router, server_factory, router_factory = make_router_and_realm()

        class ObservingSession(ApplicationSession):
            @inlineCallbacks
            def onJoin(self, details):
                self.events = []
                self.s = yield self.subscribe(lambda *a, **kw: self.events.append({
                    'args': a,
                    'kwargs': kw
                }), 'com.test.destroyed')

        session, pump = connect_application_session(server_factory, ApplicationSession)

        ob_session, ob_pump = connect_application_session(server_factory, ObservingSession)

        d = session.call("wamp.session.add_testament", "com.test.destroyed", ['hello'], {})
        pump.flush()

        # Make sure it returns a publication ID
        self.assertIsInstance(self.successResultOf(d), (int, ))

        # No testament sent yet
        pump.flush()
        ob_pump.flush()
        self.assertEqual(ob_session.events, [])

        # Then leave...
        session.leave()
        pump.flush()
        ob_pump.flush()

        # Testament is sent
        self.assertEqual(ob_session.events, [{'args': ("hello", ), 'kwargs': {}}])

    def test_destroy_testament_not_sent_when_cleared(self):
        """
        If one session calls wamp.session.add_testament, then the same session
        calls wamp.session.flush_testaments, and then the session is destroyed,
        the message it filed as a testament will not be sent, as it was
        deleted.
        """
        router, server_factory, router_factory = make_router_and_realm()

        class ObservingSession(ApplicationSession):
            @inlineCallbacks
            def onJoin(self, details):
                self.events = []
                self.s = yield self.subscribe(lambda *a, **kw: self.events.append({
                    'args': a,
                    'kwargs': kw
                }), 'com.test.destroyed')

        session, pump = connect_application_session(server_factory, ApplicationSession)

        ob_session, ob_pump = connect_application_session(server_factory, ObservingSession)

        d = session.call("wamp.session.add_testament", "com.test.destroyed", ['hello'], {})
        pump.flush()

        # Make sure it returns an integer (the testament event publication ID)
        self.assertIsInstance(self.successResultOf(d), (int, ))

        # No testament sent yet
        pump.flush()
        ob_pump.flush()
        self.assertEqual(ob_session.events, [])

        # Flush the testament
        d = session.call("wamp.session.flush_testaments")
        pump.flush()

        # Make sure it returns flushed count 1
        self.assertEqual(self.successResultOf(d), 1)

        # Then leave...
        session.leave()
        pump.flush()
        ob_pump.flush()

        # No testaments were sent
        self.assertEqual(ob_session.events, [])

    def test_add_testament_needs_valid_scope(self):
        """
        Only 'detached' and 'destroyed' are valid scopes for add_testament.
        """
        router, server_factory, router_factory = make_router_and_realm()

        session, pump = connect_application_session(server_factory, ApplicationSession)

        d = session.call("wamp.session.add_testament", "com.test.destroyed", ['hello'], {}, scope="bar")
        pump.flush()

        # Make sure it returns a failure
        failure = self.failureResultOf(d)
        self.assertEqual(failure.value.args, ("scope must be destroyed or detached", ))

    def test_flush_testament_needs_valid_scope(self):
        """
        Only 'detached' and 'destroyed' are valid scopes for flush_testament.
        """
        router, server_factory, router_factory = make_router_and_realm()

        session, pump = connect_application_session(server_factory, ApplicationSession)

        d = session.call("wamp.session.flush_testaments", scope="bar")
        pump.flush()

        # Make sure it returns a failure
        failure = self.failureResultOf(d)
        self.assertEqual(failure.value.args, ("scope must be destroyed or detached", ))

    def test_one_scope_does_not_affect_other(self):
        """
        Adding a testament to one scope and flushing the other maintains the
        added testament.
        """
        router, server_factory, router_factory = make_router_and_realm()

        class ObservingSession(ApplicationSession):
            @inlineCallbacks
            def onJoin(self, details):
                self.events = []
                self.s = yield self.subscribe(lambda *a, **kw: self.events.append({
                    'args': a,
                    'kwargs': kw
                }), 'com.test.dc')

        session, pump = connect_application_session(server_factory, ApplicationSession)

        ob_session, ob_pump = connect_application_session(server_factory, ObservingSession)

        # Add a destroyed testament
        d = session.call("wamp.session.add_testament", "com.test.dc", ['destroyed'], {}, scope="destroyed")
        pump.flush()
        self.assertIsInstance(self.successResultOf(d), (int, ))

        # Add a detached testament
        d = session.call("wamp.session.add_testament", "com.test.dc", ['detached'], {}, scope="detached")
        pump.flush()
        self.assertIsInstance(self.successResultOf(d), (int, ))

        # No testament sent yet
        pump.flush()
        ob_pump.flush()
        self.assertEqual(ob_session.events, [])

        # Flush the destroyed testament
        d = session.call("wamp.session.flush_testaments", scope="destroyed")
        pump.flush()

        # Make sure it returns number of flushed testaments
        self.assertEqual(self.successResultOf(d), 1)

        # Then leave...
        session.leave()
        pump.flush()
        ob_pump.flush()

        # Just the detached testament is sent
        self.assertEqual(ob_session.events, [{"args": ('detached', ), "kwargs": {}}])
