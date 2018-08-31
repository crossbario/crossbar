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
from autobahn.wamp.exception import ProtocolError

from crossbar.worker.types import RouterRealm
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
        self.router_factory = RouterFactory(None, None)

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

    def test_outstanding_invoke_but_caller_gone(self):

        session = mock.Mock()
        outstanding = mock.Mock()
        outstanding.call.request = 1

        dealer = self.router._dealer
        dealer.attach(session)

        dealer._callee_to_invocations[session] = [outstanding]
        # pretend we've disconnected already
        outstanding.caller._transport = None

        dealer.detach(session)

        self.assertEqual([], outstanding.mock_calls)

    def test_call_cancel(self):
        messages = []

        def session_send(msg):
            messages.append(msg)

        session = mock.Mock()
        session._transport.send = session_send
        session._session_roles = {'callee': role.RoleCalleeFeatures(call_canceling=True)}

        dealer = self.router._dealer
        dealer.attach(session)

        def authorize(*args, **kwargs):
            return defer.succeed({u'allow': True, u'disclose': False})

        self.router.authorize = mock.Mock(side_effect=authorize)

        dealer.processRegister(session, message.Register(
            1,
            u'com.example.my.proc',
            u'exact',
            message.Register.INVOKE_SINGLE,
            1
        ))

        registered_msg = messages[-1]
        self.assertIsInstance(registered_msg, message.Registered)

        dealer.processCall(session, message.Call(
            2,
            u'com.example.my.proc',
            []
        ))

        invocation_msg = messages[-1]
        self.assertIsInstance(invocation_msg, message.Invocation)

        dealer.processCancel(session, message.Cancel(
            2
        ))

        # we should receive an INTERRUPT from the dealer now -- note
        # that our session is both the caller and the callee in this
        # test, so we'll get an INTERRUPT *and* an ERROR -- in that
        # order.
        interrupt_msg = messages[-2]
        self.assertIsInstance(interrupt_msg, message.Interrupt)
        self.assertEqual(interrupt_msg.request, invocation_msg.request)

        call_error_msg = messages[-1]
        self.assertIsInstance(call_error_msg, message.Error)
        self.assertEqual(message.Call.MESSAGE_TYPE, call_error_msg.request_type)
        self.assertEqual(u'wamp.error.canceled', call_error_msg.error)

    def test_call_cancel_two_sessions(self):
        """
        this has 2 different session using the same ID (42) for their Call
        requests to confirm we deal with the fact that these IDs are
        only unique per-session properly
        """
        messages = []

        def session_send(msg):
            messages.append(msg)

        session0 = mock.Mock()
        session0._transport.send = session_send
        session0._session_roles = {'callee': role.RoleCalleeFeatures(call_canceling=True)}

        session1 = mock.Mock()
        session1._transport.send = session_send
        session1._session_roles = {'callee': role.RoleCalleeFeatures(call_canceling=True)}

        dealer = self.router._dealer
        dealer.attach(session0)
        dealer.attach(session1)

        def authorize(*args, **kwargs):
            return defer.succeed({u'allow': True, u'disclose': False})

        self.router.authorize = mock.Mock(side_effect=authorize)

        dealer.processRegister(session0, message.Register(
            1,
            u'com.example.my.proc',
            u'exact',
            message.Register.INVOKE_SINGLE,
            2
        ))

        registered_msg = messages[-1]
        self.assertIsInstance(registered_msg, message.Registered)

        # two calls outstanding to the endpoint, both happen to use
        # the same ID (42) which is legal
        dealer.processCall(session0, message.Call(
            42,
            u'com.example.my.proc',
            []
        ))

        invocation_msg0 = messages[-1]
        self.assertIsInstance(invocation_msg0, message.Invocation)
        dealer.processCall(session1, message.Call(
            42,
            u'com.example.my.proc',
            []
        ))

        invocation_msg1 = messages[-1]
        self.assertIsInstance(invocation_msg1, message.Invocation)

        # now, cancel the first session's call
        dealer.processCancel(session0, message.Cancel(
            42,
            "kill",
        ))

        # should receive an INTERRUPT from the dealer now (for the
        # correct session only)
        interrupt_msg0 = messages[-1]
        self.assertIsInstance(interrupt_msg0, message.Interrupt)
        self.assertEqual(interrupt_msg0.request, invocation_msg0.request)

        dealer.processInvocationError(session0, message.Error(
            message.Invocation.MESSAGE_TYPE,
            invocation_msg0.request,
            u'wamp.error.canceled'
        ))

    def test_call_cancel_without_callee_support(self):
        last_message = {'1': []}

        def session_send(msg):
            last_message['1'] = msg

        session = mock.Mock()
        session._transport.send = session_send
        session._session_roles = {'callee': role.RoleCalleeFeatures()}

        dealer = self.router._dealer
        dealer.attach(session)

        def authorize(*args, **kwargs):
            return defer.succeed({u'allow': True, u'disclose': False})

        self.router.authorize = mock.Mock(side_effect=authorize)

        dealer.processRegister(session, message.Register(
            1,
            u'com.example.my.proc',
            u'exact',
            message.Register.INVOKE_SINGLE,
            1
        ))

        registered_msg = last_message['1']
        self.assertIsInstance(registered_msg, message.Registered)

        dealer.processCall(session, message.Call(
            2,
            u'com.example.my.proc',
            []
        ))

        invocation_msg = last_message['1']
        self.assertIsInstance(invocation_msg, message.Invocation)

        dealer.processCancel(session, message.Cancel(
            2
        ))

        # set message to None to make sure that we get nothing back
        last_message['1'] = None

        # should NOT receive an INTERRUPT from the dealer now
        interrupt_msg = last_message['1']
        self.assertIsNone(interrupt_msg)

    def test_force_reregister_kick(self):
        """
        Kick an existing registration with force_reregister=True
        """

        session = mock.Mock()
        session._realm = u'realm1'
        self.router.authorize = mock.Mock(
            return_value=defer.succeed({u'allow': True, u'disclose': True})
        )
        rap = RouterApplicationSession(session, self.router_factory)

        rap.send(message.Hello(u"realm1", {u'caller': role.RoleCallerFeatures()}))
        rap.send(message.Register(1, u'foo'))

        reg_id = session.mock_calls[-1][1][0].registration

        # re-set the authorize, as the Deferred from above is already
        # used-up and it gets called again to authorize the Call
        self.router.authorize = mock.Mock(
            return_value=defer.succeed({u'allow': True, u'disclose': True})
        )

        # re-register the same procedure
        rap.send(message.Register(2, u'foo', force_reregister=True))

        # the first procedure with 'reg_id' as the Registration ID
        # should have gotten kicked out
        unregs = [
            call[1][0] for call in session.mock_calls
            if call[0] == 'onMessage' and isinstance(call[1][0], message.Unregistered)
        ]
        self.assertEqual(1, len(unregs))
        unreg = unregs[0]
        self.assertEqual(0, unreg.request)
        self.assertEqual(reg_id, unreg.registration)

    def test_yield_on_unowned_invocation(self):
        sessionMessages = {'1': None}

        def session1send(msg):
            sessionMessages['1'] = msg

        def authorize(*args, **kwargs):
            return defer.succeed({u'allow': True, u'disclose': False})

        self.router.authorize = mock.Mock(side_effect=authorize)

        session1 = mock.Mock()
        session1._transport.send = session1send
        session2 = mock.Mock()

        dealer = self.router._dealer
        dealer.attach(session1)
        dealer.attach(session2)

        register = message.Register(1, u'com.example.some.call', u'exact', message.Register.INVOKE_SINGLE, 1)
        dealer.processRegister(session1, register)
        registered = sessionMessages['1']
        self.assertIsInstance(registered, message.Registered)

        call = message.Call(2, u'com.example.some.call', [], {})
        dealer.processCall(session1, call)
        invocation = sessionMessages['1']
        self.assertIsInstance(invocation, message.Invocation)

        yieldMsg = message.Yield(invocation.request, [u'hello'], {})

        # this yield is happening on a different session than the one that
        # just received the invocation
        def yield_from_wrong_session():
            dealer.processYield(session2, yieldMsg)

        self.failUnlessRaises(ProtocolError, yield_from_wrong_session)

    def test_caller_detach_interrupt_cancel_supported(self):
        last_message = {'1': []}

        def session_send(msg):
            last_message['1'] = msg

        session = mock.Mock()
        session._transport.send = session_send
        session._session_roles = {'callee': role.RoleCalleeFeatures(call_canceling=True)}

        caller_session = mock.Mock()

        dealer = self.router._dealer
        dealer.attach(session)
        dealer.attach(caller_session)

        def authorize(*args, **kwargs):
            return defer.succeed({u'allow': True, u'disclose': False})

        self.router.authorize = mock.Mock(side_effect=authorize)

        dealer.processRegister(session, message.Register(
            1,
            u'com.example.my.proc',
            u'exact',
            message.Register.INVOKE_SINGLE,
            1
        ))

        registered_msg = last_message['1']
        self.assertIsInstance(registered_msg, message.Registered)

        dealer.processCall(caller_session, message.Call(
            2,
            u'com.example.my.proc',
            []
        ))

        invocation_msg = last_message['1']
        self.assertIsInstance(invocation_msg, message.Invocation)

        dealer.detach(caller_session)

        # should receive an INTERRUPT from the dealer now
        interrupt_msg = last_message['1']
        self.assertIsInstance(interrupt_msg, message.Interrupt)
        self.assertEqual(interrupt_msg.request, invocation_msg.request)

    def test_caller_detach_interrupt_cancel_not_supported(self):
        last_message = {'1': []}

        def session_send(msg):
            last_message['1'] = msg

        session = mock.Mock()
        session._transport.send = session_send
        session._session_roles = {'callee': role.RoleCalleeFeatures()}

        caller_session = mock.Mock()

        dealer = self.router._dealer
        dealer.attach(session)
        dealer.attach(caller_session)

        def authorize(*args, **kwargs):
            return defer.succeed({u'allow': True, u'disclose': False})

        self.router.authorize = mock.Mock(side_effect=authorize)

        dealer.processRegister(session, message.Register(
            1,
            u'com.example.my.proc',
            u'exact',
            message.Register.INVOKE_SINGLE,
            1
        ))

        registered_msg = last_message['1']
        self.assertIsInstance(registered_msg, message.Registered)

        dealer.processCall(caller_session, message.Call(
            2,
            u'com.example.my.proc',
            []
        ))

        invocation_msg = last_message['1']
        self.assertIsInstance(invocation_msg, message.Invocation)

        dealer.detach(caller_session)

        # reset recorded message to make sure we don't receive anything
        last_message['1'] = None

        # should NOT receive an INTERRUPT from the dealer now because we don't support cancellation
        self.assertIsNone(last_message['1'])

    def test_concurrency_with_error(self):
        """
        register a concurrency=2 method, called with errors
        """
        callee_messages = []
        caller_messages = []

        def callee_send(msg):
            callee_messages.append(msg)

        session = mock.Mock()
        session._transport.send = callee_send
        session._session_roles = {'callee': role.RoleCalleeFeatures()}

        def caller_send(msg):
            caller_messages.append(msg)

        caller_session = mock.Mock()
        caller_session._transport.send = caller_send

        dealer = self.router._dealer
        dealer.attach(session)
        dealer.attach(caller_session)

        def authorize(*args, **kwargs):
            return defer.succeed({u'allow': True, u'disclose': False})

        self.router.authorize = mock.Mock(side_effect=authorize)

        # we register out procedure, with concurrency=1

        dealer.processRegister(session, message.Register(
            request=1,
            procedure=u'com.example.my.proc',
            match=u'exact',
            invoke=message.Register.INVOKE_SINGLE,
            concurrency=1
        ))

        registered_msg = callee_messages[-1]
        self.assertIsInstance(registered_msg, message.Registered)

        # we have registered our procedure that has concurrency=1
        # and now we call it

        dealer.processCall(caller_session, message.Call(
            2,
            u'com.example.my.proc',
            []
        ))

        # we pretend that the call caused an error of some sort
        invocation_msg = callee_messages[-1]
        self.assertIsInstance(invocation_msg, message.Invocation)
        dealer.processInvocationError(
            session, message.Error(
                message.Call.MESSAGE_TYPE,
                invocation_msg.request,
                u"wamp.error.foo",
            )
        )

        self.assertEqual(1, len(caller_messages))
        self.assertEqual(
            u"wamp.error.foo",
            caller_messages[-1].error,
        )

        # now we call it again, which should work because the
        # previously-outstanding call was resolved with an error
        # (before bug 1105 being fixed this wouldn't work properly)

        dealer.processCall(caller_session, message.Call(
            3,
            u'com.example.my.proc',
            ['foo']
        ))
        invocation_msg = callee_messages[-1]
        self.assertIsInstance(invocation_msg, message.Invocation)

        self.assertEqual(1, len(caller_messages), "got an extra unexpected message")

        dealer.processYield(
            session, message.Yield(
                invocation_msg.request,
                args=['a result'],
            )
        )

        result_msg = caller_messages[-1]
        self.assertIsInstance(result_msg, message.Result)
        self.assertEqual(result_msg.args, ['a result'])
