#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession

from .helpers import make_router_and_realm, connect_application_session
from crossbar._logging import LogCapturer


class TestamentTests(unittest.TestCase):

    # FIXME:
    # [ERROR] Traceback (most recent call last):
    # File "/home/oberstet/scm/crossbario/crossbar/crossbar/router/test/test_testament.py", line 203, in test_one_scope_does_not_affect_other
    # d = session.call(u"wamp.session.add_testament", u"com.test.dc",
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
                self.s = yield self.subscribe(
                    lambda *a, **kw: self.events.append({'args': a, 'kwargs': kw}),
                    u'com.test.destroyed')

        session, pump = connect_application_session(server_factory,
                                                    ApplicationSession)

        ob_session, ob_pump = connect_application_session(server_factory,
                                                          ObservingSession)

        d = session.call(u"wamp.session.add_testament", u"com.test.destroyed",
                         [u'hello'], {})
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
        self.assertEqual(ob_session.events,
                         [{'args': (u"hello",), 'kwargs': {}}])

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
                self.s = yield self.subscribe(
                    lambda *a, **kw: self.events.append({'args': a, 'kwargs': kw}),
                    u'com.test.destroyed')

        session, pump = connect_application_session(server_factory,
                                                    ApplicationSession)

        ob_session, ob_pump = connect_application_session(server_factory,
                                                          ObservingSession)

        d = session.call(u"wamp.session.add_testament", u"com.test.destroyed",
                         [u'hello'], {})
        pump.flush()

        # Make sure it returns an integer (the testament event publication ID)
        self.assertIsInstance(self.successResultOf(d), (int, ))

        # No testament sent yet
        pump.flush()
        ob_pump.flush()
        self.assertEqual(ob_session.events, [])

        # Flush the testament
        d = session.call(u"wamp.session.flush_testaments")
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

        session, pump = connect_application_session(server_factory,
                                                    ApplicationSession)

        d = session.call(u"wamp.session.add_testament", u"com.test.destroyed",
                         [u'hello'], {}, scope=u"bar")
        pump.flush()

        # Make sure it returns a failure
        failure = self.failureResultOf(d)
        self.assertEqual(failure.value.args,
                         (u"scope must be destroyed or detached",))

    def test_flush_testament_needs_valid_scope(self):
        """
        Only 'detached' and 'destroyed' are valid scopes for flush_testament.
        """
        router, server_factory, router_factory = make_router_and_realm()

        session, pump = connect_application_session(server_factory,
                                                    ApplicationSession)

        d = session.call(u"wamp.session.flush_testaments", scope=u"bar")
        pump.flush()

        # Make sure it returns a failure
        failure = self.failureResultOf(d)
        self.assertEqual(failure.value.args,
                         (u"scope must be destroyed or detached",))

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
                self.s = yield self.subscribe(
                    lambda *a, **kw: self.events.append({'args': a, 'kwargs': kw}),
                    u'com.test.dc')

        session, pump = connect_application_session(server_factory,
                                                    ApplicationSession)

        ob_session, ob_pump = connect_application_session(server_factory,
                                                          ObservingSession)

        # Add a destroyed testament
        d = session.call(u"wamp.session.add_testament", u"com.test.dc",
                         [u'destroyed'], {}, scope=u"destroyed")
        pump.flush()
        self.assertIsInstance(self.successResultOf(d), (int, ))

        # Add a detached testament
        d = session.call(u"wamp.session.add_testament", u"com.test.dc",
                         [u'detached'], {}, scope=u"detached")
        pump.flush()
        self.assertIsInstance(self.successResultOf(d), (int, ))

        # No testament sent yet
        pump.flush()
        ob_pump.flush()
        self.assertEqual(ob_session.events, [])

        # Flush the destroyed testament
        d = session.call(u"wamp.session.flush_testaments", scope=u"destroyed")
        pump.flush()

        # Make sure it returns number of flushed testaments
        self.assertEqual(self.successResultOf(d), 1)

        # Then leave...
        session.leave()
        pump.flush()
        ob_pump.flush()

        # Just the detached testament is sent
        self.assertEqual(ob_session.events, [{"args": (u'detached',), "kwargs": {}}])
