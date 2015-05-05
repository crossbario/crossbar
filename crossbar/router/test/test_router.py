#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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

from mock import Mock

import txaio

import six

from autobahn.wamp import types
from autobahn.twisted.wamp import ApplicationSession

from crossbar.router.router import RouterFactory, CrossbarRouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.session import CrossbarRouterSession


class TestCrossbarSessions(unittest.TestCase):
    def test_onjoin_metaevent(self):
        # we're just short-circuiting straight to calling onJoin()
        # ourselves rather than drive the protocol to that point.
        factory = CrossbarRouterFactory()
        session = CrossbarRouterSession(factory)
        # ...but we therefore have to set up enough internals so the
        # onJoin() can emit the session-details it wants.
        session._router = Mock()
        session._router._realm = Mock()
        session._router._realm.session = Mock()
        session._transport = Mock()
        session._transport._transport_info = 'nothing to see here'
        details = types.SessionDetails(u'test_realm', 1234)

        session.onJoin(details)

        calls = session._router._realm.session.method_calls
        print(calls, calls[0][1])
        self.assertEqual(1, len(calls))
        for (k, v) in six.iteritems(calls[0][1][1]):
            self.assertTrue(type(k) == six.text_type)


class TestEmbeddedSessions(unittest.TestCase):

    """
    Test cases for application session running embedded in router.
    """

    def setUp(self):
        """
        Setup router and router session factories.
        """
        self.router_factory = RouterFactory()
        self.session_factory = RouterSessionFactory(self.router_factory)

    def tearDown(self):
        pass

    def test_add(self):
        """
        Create an application session and add it to a router to
        run embedded.
        """
        d = txaio.create_future()

        class TestSession(ApplicationSession):

            def onJoin(self, details):
                txaio.resolve(d, None)

        session = TestSession(types.ComponentConfig(u'realm1'))

        self.session_factory.add(session)

        return d

    def test_add_and_subscribe(self):
        """
        Create an application session that subscribes to some
        topic and add it to a router to run embedded.
        """
        d = txaio.create_future()

        class TestSession(ApplicationSession):

            def onJoin(self, details):
                # noinspection PyUnusedLocal
                def on_event(*arg, **kwargs):
                    pass

                d2 = self.subscribe(on_event, u'com.example.topic1')

                def ok(_):
                    txaio.resolve(d, None)

                def error(err):
                    txaio.reject(d, err)

                txaio.add_callbacks(d2, ok, error)

        session = TestSession(types.ComponentConfig(u'realm1'))

        self.session_factory.add(session)

        return d
