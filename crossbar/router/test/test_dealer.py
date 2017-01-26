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

import mock

from autobahn.wamp import message
from autobahn.wamp import role

from crossbar.worker.router import RouterRealm
from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.session import RouterApplicationSession
from crossbar.router.role import RouterRoleStaticAuth

from twisted.internet import defer


class TestDealer(unittest.TestCase):
    """
    """

    def setUp(self):
        """
        Setup router and router session factories.
        """

        # create a router factory
        self.router_factory = RouterFactory()

        # start a realm
        self.realm = RouterRealm(u'realm-001', {u'name': u'realm1'})
        self.router_factory.start_realm(self.realm)

        # allow everything
        self.router = self.router_factory.get(u'realm1')
        self.router.add_role(
            RouterRoleStaticAuth(
                self.router,
                u'test_role',
                default_permissions={
                    u'uri': u'com.example.',
                    u'match': u'prefix',
                    u'allow': {
                        u'call': True,
                        u'register': True,
                        u'publish': True,
                        u'subscribe': True,
                    }
                }
            )
        )

        # create a router session factory
        self.session_factory = RouterSessionFactory(self.router_factory)

    def tearDown(self):
        pass

    @defer.inlineCallbacks
    def test_outstanding_invoke(self):
        """
        When a call is pending and the callee goes away, it cancels the
        in-flight call
        """

        session = mock.Mock()
        session._realm = u'realm1'
        self.router.authorize = mock.Mock(
            return_value=defer.succeed({u'allow': True, u'disclose': True})
        )
        rap = RouterApplicationSession(session, self.router_factory)

        rap.send(message.Hello(u"realm1", {u'caller': role.RoleCallerFeatures()}))
        rap.send(message.Register(1, u'foo'))

        # we can retrieve the Registration via
        # session.mock_calls[-1][1][0] if req'd

        # re-set the authorize, as the Deferred from above is already
        # used-up and it gets called again to authorize the Call
        self.router.authorize = mock.Mock(
            return_value=defer.succeed({u'allow': True, u'disclose': True})
        )
        rap.send(message.Call(42, u'foo'))

        orig = rap.send
        d = defer.Deferred()

        rap.send(message.Goodbye())

        def wrapper(*args, **kw):
            d.callback(args[0])
            return orig(*args, **kw)
        rap.send = wrapper

        # we can do this *after* the call to send() the Goodbye
        # (above) because it takes a reactor-turn to actually
        # process the cancel/errors etc -- hence the Deferred and
        # yield in this test...

        msg = yield d

        self.assertEqual(42, msg.request)
        self.assertEqual(u'wamp.error.canceled', msg.error)
