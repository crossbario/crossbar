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

from autobahn.wamp import types
from autobahn.twisted.wamp import FutureMixin, \
    ApplicationSession

from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory


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
        d = FutureMixin._create_future()

        class TestSession(ApplicationSession):

            def onJoin(self, details):
                FutureMixin._resolve_future(d, None)

        session = TestSession(types.ComponentConfig(u'realm1'))

        self.session_factory.add(session)

        return d

    def test_add_and_subscribe(self):
        """
        Create an application session that subscribes to some
        topic and add it to a router to run embedded.
        """
        d = FutureMixin._create_future()

        class TestSession(ApplicationSession):

            def onJoin(self, details):
                # noinspection PyUnusedLocal
                def on_event(*arg, **kwargs):
                    pass

                d2 = self.subscribe(on_event, u'com.example.topic1')

                def ok(_):
                    FutureMixin._resolve_future(d, None)

                def error(err):
                    FutureMixin._reject_future(d, err)

                FutureMixin._add_future_callbacks(d2, ok, error)

        session = TestSession(types.ComponentConfig(u'realm1'))

        self.session_factory.add(session)

        return d
