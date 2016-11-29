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

from .helpers import make_router, connect_application_session
from crossbar._logging import LogCapturer


class TestamentTests(unittest.TestCase):

    def setUp(self):

        self.logs = LogCapturer()
        self.logs.__enter__()
        self.addCleanup(lambda: self.logs.__exit__(None, None, None))

    def test_destroy_testament_sent_on_destroy(self):
        """
        If one session calls wamp.session.add_testament and then the session is destroyed, the message it filed as a testament will be sent to subscribers of the chosen topic.
        """
        router, server_factory = make_router()

        class ObservingSession(ApplicationSession):

            @inlineCallbacks
            def onJoin(self, details):
                self.events = []
                self.s = yield self.subscribe(
                    lambda *a, **kw: self.events.append({'args': a, 'kwargs': kw}),
                    u'com.test.destroyed')
                print('SUB', self.s)

        session, pump = connect_application_session(server_factory,
                                                    ApplicationSession)

        ob_session, ob_pump = connect_application_session(server_factory,
                                                          ObservingSession)
        ob_pump.flush()

        d = session.call(u"wamp.session.add_testament", u"com.test.destroyed",
                         [u'hello'], {})
        pump.flush()

        # Make sure it returns None
        add_testament_result = self.successResultOf(d)
        self.assertEqual(add_testament_result, None)

        # No testament sent yet
        pump.flush()
        ob_pump.flush()
        self.assertEqual(ob_session.events, [])

        # Then leave...
        session.leave()
        pump.flush()
        ob_pump.flush()

        # Testament is sent
        self.assertEqual(ob_session.events, [{'args': (u"hello",), 'kwargs': {}}])
