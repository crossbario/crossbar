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

import txaio
import mock

from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp import role
from autobahn.twisted.wamp import ApplicationSession

from crossbar.worker.types import RouterRealm
from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory, RouterSession
from crossbar.router.broker import Broker
from crossbar.router.role import RouterRoleStaticAuth

from twisted.internet import defer, reactor
from twisted.test.proto_helpers import Clock

from txaio.testutil import replace_loop


class TestBrokerPublish(unittest.TestCase):
    """
    Tests for crossbar.router.broker.Broker
    """

    def setUp(self):
        """
        Setup router and router session factories.
        """

        # create a router factory
        self.router_factory = RouterFactory(None, None)

        # start a realm
        self.realm = RouterRealm(None, None, {u'name': u'realm1'})
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

        self.session_factory.add(session, self.router)

        return d

    def test_application_session_internal_error(self):
        """
        simulate an internal error triggering the 'onJoin' error-case from
        RouterApplicationSession's send() method (from the Hello msg)
        """
        # setup
        the_exception = RuntimeError("sadness")
        errors = []

        class TestSession(ApplicationSession):
            def onJoin(self, *args, **kw):
                raise the_exception

            def onUserError(self, fail, msg):
                errors.append((fail, msg))

        session = TestSession(types.ComponentConfig(u'realm1'))
        from crossbar.router.session import RouterApplicationSession

        # Note to self: original code was logging directly in
        # RouterApplicationSession -- which *may* actually be better?
        # or not...
        with mock.patch.object(RouterApplicationSession, 'log') as logger:
            # this should call onJoin, triggering our error
            self.session_factory.add(session, self.router)

            if True:
                self.assertEqual(1, len(errors), "Didn't see our error")
                self.assertEqual(the_exception, errors[0][0].value)

            else:
                # check we got the right log.failure() call
                self.assertTrue(len(logger.method_calls) > 0)
                call = logger.method_calls[0]
                # for a MagicMock call-object, 0th thing is the method-name, 1st
                # thing is the arg-tuple, 2nd thing is the kwargs.
                self.assertEqual(call[0], 'failure')
                self.assertEqual(call[1][0].value, the_exception)

    def test_router_session_internal_error_onHello(self):
        """
        similar to above, but during _RouterSession's onMessage handling,
        where it calls self.onHello
        """
        # setup
        transport = mock.MagicMock()
        transport.get_channel_id = mock.MagicMock(return_value=b'deadbeef')
        the_exception = RuntimeError("kerblam")

        def boom(*args, **kw):
            raise the_exception
        session = self.session_factory()  # __call__ on the _RouterSessionFactory
        session.onHello = boom
        session.onOpen(transport)
        msg = message.Hello(u'realm1', dict(caller=role.RoleCallerFeatures()))

        # XXX think: why isn't this using _RouterSession.log?
        from crossbar.router.session import RouterSession
        with mock.patch.object(RouterSession, 'log') as logger:
            # do the test; should call onHello which is now "boom", above
            session.onMessage(msg)

            # check we got the right log.failure() call
            self.assertTrue(len(logger.method_calls) > 0)
            call = logger.method_calls[0]
            # for a MagicMock call-object, 0th thing is the method-name, 1st
            # thing is the arg-tuple, 2nd thing is the kwargs.
            self.assertEqual(call[0], 'failure')
            self.assertTrue('failure' in call[2])
            self.assertEqual(call[2]['failure'].value, the_exception)

    def test_router_session_internal_error_onAuthenticate(self):
        """
        similar to above, but during _RouterSession's onMessage handling,
        where it calls self.onAuthenticate)
        """
        # setup
        transport = mock.MagicMock()
        transport.get_channel_id = mock.MagicMock(return_value=b'deadbeef')
        the_exception = RuntimeError("kerblam")

        def boom(*args, **kw):
            raise the_exception
        session = self.session_factory()  # __call__ on the _RouterSessionFactory
        session.onAuthenticate = boom
        session.onOpen(transport)
        msg = message.Authenticate(u'bogus signature')

        # do the test; should call onHello which is now "boom", above
        session.onMessage(msg)

        errors = self.flushLoggedErrors()
        self.assertEqual(1, len(errors), "Expected just one error: {}".format(errors))
        self.assertTrue(the_exception in [fail.value for fail in errors])

    def test_router_session_goodbye_custom_message(self):
        """
        Reason should be propagated properly from Goodbye message
        """
        raise unittest.SkipTest('FIXME: Adjust unit test mocks #1567')

        from crossbar.router.session import RouterApplicationSession
        session = mock.Mock()
        session._realm = u'realm'
        router_factory = mock.Mock()
        rap = RouterApplicationSession(session, router_factory)

        rap.send(message.Hello(u'realm', {u'caller': role.RoleCallerFeatures()}))
        session.reset_mock()
        rap.send(message.Goodbye(u'wamp.reason.logout', u'some custom message'))

        leaves = [call for call in session.mock_calls if call[0] == 'onLeave']
        self.assertEqual(1, len(leaves))
        details = leaves[0][1][0]
        self.assertEqual(u'wamp.reason.logout', details.reason)
        self.assertEqual(u'some custom message', details.message)

    def test_router_session_goodbye_onLeave_error(self):
        """
        Reason should be propagated properly from Goodbye message
        """
        raise unittest.SkipTest('FIXME: Adjust unit test mocks #1567')

        from crossbar.router.session import RouterApplicationSession
        session = mock.Mock()
        the_exception = RuntimeError("onLeave fails")

        def boom(*args, **kw):
            raise the_exception
        session.onLeave = mock.Mock(side_effect=boom)
        session._realm = u'realm'
        router_factory = mock.Mock()
        rap = RouterApplicationSession(session, router_factory)

        rap.send(message.Hello(u'realm', {u'caller': role.RoleCallerFeatures()}))
        session.reset_mock()
        rap.send(message.Goodbye(u'wamp.reason.logout', u'some custom message'))

        errors = self.flushLoggedErrors()
        self.assertEqual(1, len(errors))
        self.assertEqual(the_exception, errors[0].value)

    def test_router_session_goodbye_fire_disconnect_error(self):
        """
        Reason should be propagated properly from Goodbye message
        """
        raise unittest.SkipTest('FIXME: Adjust unit test mocks #1567')

        from crossbar.router.session import RouterApplicationSession
        session = mock.Mock()
        the_exception = RuntimeError("sad times at ridgemont high")

        def boom(*args, **kw):
            if args[0] == 'disconnect':
                return defer.fail(the_exception)
            return defer.succeed(None)
        session.fire = mock.Mock(side_effect=boom)
        session._realm = u'realm'
        router_factory = mock.Mock()
        rap = RouterApplicationSession(session, router_factory)

        rap.send(message.Hello(u'realm', {u'caller': role.RoleCallerFeatures()}))
        session.reset_mock()
        rap.send(message.Goodbye(u'wamp.reason.logout', u'some custom message'))

        errors = self.flushLoggedErrors()
        self.assertEqual(1, len(errors))
        self.assertEqual(the_exception, errors[0].value)

    def test_router_session_lifecycle(self):
        """
        We see all 'lifecycle' notifications.
        """
        raise unittest.SkipTest('FIXME: Adjust unit test mocks #1567')

        from crossbar.router.session import RouterApplicationSession

        def mock_fire(name, *args, **kw):
            fired.append(name)
            return defer.succeed(None)

        fired = []
        session = mock.Mock()
        session._realm = u'realm'
        session.fire = mock.Mock(side_effect=mock_fire)
        router_factory = mock.Mock()
        rap = RouterApplicationSession(session, router_factory)

        # we never fake out the 'Welcome' message, so there will be no
        # 'ready' notification...
        rap.send(message.Hello(u'realm', {u'caller': role.RoleCallerFeatures()}))
        rap.send(message.Goodbye(u'wamp.reason.logout', u'some custom message'))

        self.assertTrue('connect' in fired)
        self.assertTrue('join' in fired)
        self.assertTrue('ready' in fired)
        self.assertTrue('leave' in fired)
        self.assertTrue('disconnect' in fired)

    def test_add_and_subscribe(self):
        """
        Create an application session that subscribes to some
        topic and add it to a router to run embedded.
        """
        d = txaio.create_future()

        class TestSession(ApplicationSession):

            def onJoin(self, details):
                d2 = self.subscribe(lambda: None, u'com.example.topic1')

                def ok(_):
                    txaio.resolve(d, None)

                def error(err):
                    txaio.reject(d, err)

                txaio.add_callbacks(d2, ok, error)

        session = TestSession(types.ComponentConfig(u'realm1'))

        self.session_factory.add(session, self.router, authrole=u'test_role')

        return d

    def test_publish_closed_session(self):
        """
        ensure a session doesn't get Events if it's closed
        (see also issue #431)
        """
        # we want to trigger a deeply-nested condition in
        # processPublish in class Broker -- lets try w/o refactoring
        # anything first...

        class TestSession(ApplicationSession):
            pass
        session0 = TestSession()
        session1 = TestSession()
        router = mock.MagicMock()
        router.new_correlation_id = lambda: u'fake correlation id'
        broker = Broker(router, reactor)

        # let's just "cheat" our way a little to the right state by
        # injecting our subscription "directly" (e.g. instead of
        # faking out an entire Subscribe etc. flow
        # ...so we need _subscriptions_map to have at least one
        # subscription (our test one) for the topic we'll publish to
        broker._subscription_map.add_observer(session0, u'test.topic')

        # simulate the session state we want, which is that a
        # transport is connected (._transport != None) but there
        # _session_id *is* None (not joined yet, or left already)
        self.assertIs(None, session0._session_id)
        session0._transport = mock.MagicMock()
        session0._transport.get_channel_id = mock.MagicMock(return_value=b'deadbeef')
        session1._session_id = 1234  # "from" session should look connected + joined
        session1._transport = mock.MagicMock()
        session1._transport.channel_id = b'aaaabeef'

        # here's the main "cheat"; we're faking out the
        # router.authorize because we need it to callback immediately
        router.authorize = mock.MagicMock(return_value=txaio.create_future_success(dict(allow=True, cache=False, disclose=True)))

        # now we scan call "processPublish" such that we get to the
        # condition we're interested in (this "comes from" session1
        # beacuse by default publishes don't go to the same session)
        pubmsg = message.Publish(123, u'test.topic')
        broker.processPublish(session1, pubmsg)

        # neither session should have sent anything on its transport
        self.assertEquals(session0._transport.method_calls, [])
        self.assertEquals(session1._transport.method_calls, [])

    def test_publish_traced_events(self):
        """
        with two subscribers and message tracing the last event should
        have a magic flag
        """
        # we want to trigger a deeply-nested condition in
        # processPublish in class Broker -- lets try w/o refactoring
        # anything first...

        class TestSession(ApplicationSession):
            pass
        session0 = TestSession()
        session1 = TestSession()
        session2 = TestSession()
        router = mock.MagicMock()
        router.send = mock.Mock()
        router.new_correlation_id = lambda: u'fake correlation id'
        router.is_traced = True
        broker = Broker(router, reactor)

        # let's just "cheat" our way a little to the right state by
        # injecting our subscription "directly" (e.g. instead of
        # faking out an entire Subscribe etc. flow
        # ...so we need _subscriptions_map to have at least one
        # subscription (our test one) for the topic we'll publish to
        broker._subscription_map.add_observer(session0, u'test.topic')
        broker._subscription_map.add_observer(session1, u'test.topic')

        session0._session_id = 1000
        session0._transport = mock.MagicMock()
        session0._transport.get_channel_id = mock.MagicMock(return_value=b'deadbeef')

        session1._session_id = 1001
        session1._transport = mock.MagicMock()
        session1._transport.get_channel_id = mock.MagicMock(return_value=b'deadbeef')

        session2._session_id = 1002
        session2._transport = mock.MagicMock()
        session2._transport.get_channel_id = mock.MagicMock(return_value=b'deadbeef')

        # here's the main "cheat"; we're faking out the
        # router.authorize because we need it to callback immediately
        router.authorize = mock.MagicMock(return_value=txaio.create_future_success(dict(allow=True, cache=False, disclose=True)))

        # now we scan call "processPublish" such that we get to the
        # condition we're interested in (this "comes from" session1
        # beacuse by default publishes don't go to the same session)
        pubmsg = message.Publish(123, u'test.topic')
        broker.processPublish(session2, pubmsg)

        # extract all the event calls
        events = [
            call[1][1]
            for call in router.send.mock_calls
            if call[1][0] in [session0, session1, session2]
        ]

        self.assertEqual(2, len(events))
        self.assertFalse(events[0].correlation_is_last)
        self.assertTrue(events[1].correlation_is_last)

    def test_publish_traced_events_batched(self):
        """
        with two subscribers and message tracing the last event should
        have a magic flag
        """
        # we want to trigger a deeply-nested condition in
        # processPublish in class Broker -- lets try w/o refactoring
        # anything first...

        class TestSession(ApplicationSession):
            pass
        session0 = TestSession()
        session1 = TestSession()
        session2 = TestSession()
        session3 = TestSession()
        session4 = TestSession()
        # NOTE! We ensure that "session0" (the publishing session) is
        # *last* in the observation-list to trigger a (now fixed)
        # edge-case)
        sessions = [session1, session2, session3, session4, session0]
        router = mock.MagicMock()
        router.send = mock.Mock()
        router.new_correlation_id = lambda: u'fake correlation id'
        router.is_traced = True
        clock = Clock()
        with replace_loop(clock):
            broker = Broker(router, clock)
            broker._options.event_dispatching_chunk_size = 2

            # to ensure we get "session0" last, we turn on ordering in
            # the observations
            broker._subscription_map._ordered = 1

            # let's just "cheat" our way a little to the right state by
            # injecting our subscription "directly" (e.g. instead of
            # faking out an entire Subscribe etc. flow
            # ...so we need _subscriptions_map to have at least one
            # subscription (our test one) for the topic we'll publish to
            for session in sessions:
                broker._subscription_map.add_observer(session, u'test.topic')

            for i, sess in enumerate(sessions):
                sess._session_id = 1000 + i
                sess._transport = mock.MagicMock()
                sess._transport.get_channel_id = mock.MagicMock(return_value=b'deadbeef')

            # here's the main "cheat"; we're faking out the
            # router.authorize because we need it to callback immediately
            router.authorize = mock.MagicMock(return_value=txaio.create_future_success(dict(allow=True, cache=False, disclose=True)))

            # now we scan call "processPublish" such that we get to the
            # condition we're interested in; should go to all sessions
            # except session0
            pubmsg = message.Publish(123, u'test.topic')
            broker.processPublish(session0, pubmsg)
            clock.advance(1)
            clock.advance(1)

            # extract all the event calls
            events = [
                call[1][1]
                for call in router.send.mock_calls
                if call[1][0] in [session0, session1, session2, session3, session4]
            ]

            # all except session0 should have gotten an event, and
            # session4's should have the "last" flag set
            self.assertEqual(4, len(events))
            self.assertFalse(events[0].correlation_is_last)
            self.assertFalse(events[1].correlation_is_last)
            self.assertFalse(events[2].correlation_is_last)
            self.assertTrue(events[3].correlation_is_last)

    def test_subscribe_unsubscribe(self):
        """
        Make sure the wamp.* event sequence delivered as part of a subscribe/unsubscribe sequence
        is correct and contains the correct session id and subscription id values.
        """
        router = self.router
        test = self

        class Session(mock.MagicMock):

            _private = []
            _events = []
            _authrole = 'trusted'
            _session_id = 0

            def send(self, *args, **argv):
                self._private.append(args[0])

            def publish(self, *args, **argv):
                self._events.append([args, argv])

        class TestSession(ApplicationSession):

            def __init__(self, *args, **kw):
                super().__init__(*args, **kw)
                self._service_session = Session()
                self._router = router

            def onJoin(self, details):
                self._service_session._session_id = details.session
                router.attach(self._service_session)

                router._broker._router._realm.session = self._service_session
                subscription = message.Subscribe(self._service_session._session_id, u'com.example.test1')
                router._broker.processSubscribe(self._service_session, subscription)
                subscription = message.Subscribe(self._service_session._session_id, u'com.example.test2')
                router._broker.processSubscribe(self._service_session, subscription)
                subscription = message.Subscribe(self._service_session._session_id, u'com.example.test3')
                router._broker.processSubscribe(self._service_session, subscription)

                subscriptions = []
                for obj in list(self._service_session._private):
                    subscription = message.Unsubscribe(self._service_session._session_id, subscription=obj.subscription)
                    router._broker.processUnsubscribe(self._service_session, subscription)
                    subscriptions.append(obj.subscription)

                def all_done():

                    created = list(subscriptions)
                    subscribes = list(subscriptions)
                    unsubscribes = list(subscriptions)
                    deletes = list(subscriptions)

                    for args, argv in self._service_session._events:
                        if args[0] == 'wamp.subscription.on_create':
                            test.assertEqual(args[1], self._service_session._session_id, 'on_create: session id is incorrect!')
                            test.assertTrue(args[2]['id'] in created, 'on_create: subscription id is incorrect!')
                            created.remove(args[2]['id'])

                        if args[0] == 'wamp.subscription.on_subscribe':
                            test.assertEqual(args[1], self._service_session._session_id, 'on_subscribe: session id is incorrect!')
                            test.assertTrue(args[2] in subscribes, 'on_subscribe: subscription id is incorrect!')
                            subscribes.remove(args[2])

                        if args[0] == 'wamp.subscription.on_unsubscribe':
                            test.assertEqual(args[1], self._service_session._session_id, 'on_unsubscribe: session id is incorrect!')
                            test.assertTrue(args[2] in unsubscribes, 'on_unsubscribe: subscription id is incorrect!')
                            unsubscribes.remove(args[2])

                        if args[0] == 'wamp.subscription.on_delete':
                            test.assertEqual(args[1], self._service_session._session_id, 'on_delete: session id is incorrect!')
                            test.assertTrue(args[2] in deletes, 'on_delete: subscription id is incorrect!')
                            deletes.remove(args[2])

                    test.assertEqual(len(created), 0, 'incorrect response sequence for on_create')
                    test.assertEqual(len(subscribes), 0, 'incorrect response sequence for on_subscribe')
                    test.assertEqual(len(unsubscribes), 0, 'incorrect response sequence for on_unsubscribe')
                    test.assertEqual(len(deletes), 0, 'incorrect response sequence for on_delete')

                reactor.callLater(0, all_done)

        session = TestSession(types.ComponentConfig(u'realm1'))
        self.session_factory.add(session, self.router, authrole=u'trusted')

    def test_subscribe_detach(self):
        """
        Make sure the wamp.* event sequence delivered as part of a subscribe/detach sequence
        is correct and contains the correct session id and subscription id values.
        """
        router = self.router
        test = self

        class Session(mock.MagicMock):
            """
            Mock the session object, this is key to capturing all the replies and publications.
            We get all replies in _private and publications in events, so we can issue the
            request we need to test, then check at the end _events contains the list of
            pub's we are expecting.
            """
            _private = []
            _events = []
            _authrole = 'trusted'
            _session_id = 0

            def send(self, *args, **argv):
                self._private.append(args[0])

            def publish(self, *args, **argv):
                self._events.append([args, argv])

        class TestSession(ApplicationSession):

            def __init__(self, *args, **kw):
                super().__init__(*args, **kw)
                self._service_session = Session()
                self._router = router

            def onJoin(self, details):
                self._service_session._session_id = details.session
                router.attach(self._service_session)

                router._broker._router._realm.session = self._service_session
                subscription = message.Subscribe(self._service_session._session_id, u'com.example.test1')
                router._broker.processSubscribe(self._service_session, subscription)
                subscription = message.Subscribe(self._service_session._session_id, u'com.example.test2')
                router._broker.processSubscribe(self._service_session, subscription)
                subscription = message.Subscribe(self._service_session._session_id, u'com.example.test3')
                router._broker.processSubscribe(self._service_session, subscription)

                subscriptions = []
                for obj in list(self._service_session._private):
                    subscriptions.append(obj.subscription)

                router.detach(self._service_session)

                def all_done():

                    #
                    #   These lists are initialised with the subscription id's we've generated
                    #   with out subscribe sequence, the following routines should decrement each
                    #   list to exactly zero.
                    #
                    created = list(subscriptions)
                    subscribes = list(subscriptions)
                    unsubscribes = list(subscriptions)
                    deletes = list(subscriptions)

                    for args, argv in self._service_session._events:

                        if args[0] == 'wamp.subscription.on_create':
                            test.assertEqual(args[1], self._service_session._session_id, 'on_create: session id is incorrect!')
                            test.assertTrue(args[2]['id'] in created, 'on_create: subscription id is incorrect!')
                            created.remove(args[2]['id'])

                        if args[0] == 'wamp.subscription.on_subscribe':
                            test.assertEqual(args[1], self._service_session._session_id, 'on_subscribe: session id is incorrect!')
                            test.assertTrue(args[2] in subscribes, 'on_subscribe: subscription id is incorrect!')
                            subscribes.remove(args[2])

                        if args[0] == 'wamp.subscription.on_unsubscribe':
                            test.assertEqual(args[1], self._service_session._session_id, 'on_unsubscribe: session id is incorrect!')
                            test.assertTrue(args[2] in unsubscribes, 'on_unsubscribe: subscription id is incorrect!')
                            unsubscribes.remove(args[2])

                        if args[0] == 'wamp.subscription.on_delete':
                            test.assertEqual(args[1], self._service_session._session_id, 'on_delete: session id is incorrect!')
                            test.assertTrue(args[2] in deletes, 'on_delete: subscription id is incorrect!')
                            deletes.remove(args[2])

                    test.assertEqual(len(created), 0, 'incorrect response sequence for on_create')
                    test.assertEqual(len(subscribes), 0, 'incorrect response sequence for on_subscribe')
                    test.assertEqual(len(unsubscribes), 0, 'incorrect response sequence for on_unsubscribe')
                    test.assertEqual(len(deletes), 0, 'incorrect response sequence for on_delete')

                reactor.callLater(0, all_done)

        session = TestSession(types.ComponentConfig(u'realm1'))
        self.session_factory.add(session, self.router, authrole=u'trusted')


class TestRouterSession(unittest.TestCase):
    """
    Tests for crossbar.router.session.RouterSession
    """

    def test_wamp_session_on_leave(self):
        """
        wamp.session.on_leave receives valid session_id
        """

        router = mock.MagicMock()
        router.new_correlation_id = lambda: u'fake correlation id'

        class TestSession(RouterSession):
            def __init__(self, *args, **kw):
                super(TestSession, self).__init__(*args, **kw)
                # for this test, pretend we're connected (without
                # going through sending a Hello etc.)
                self._transport = mock.MagicMock()
                self._transport.get_channel_id = mock.MagicMock(return_value=b'deadbeef')
                self._session_id = 1234
                self._router = router  # normally done in Hello processing
                self._service_session = mock.MagicMock()

        router_factory = mock.MagicMock()
        session = TestSession(router_factory)
        goodbye = message.Goodbye(u'wamp.close.normal', u'hi there')

        self.assertFalse(session._goodbye_sent)

        # do the test; we should publish wamp.session.on_leave via the
        # service-session
        session.onMessage(goodbye)
        publishes = [call for call in session._service_session.mock_calls if call[0] == 'publish']
        self.assertEqual(1, len(publishes))
        call = publishes[0]
        self.assertEqual(call[0], "publish")
        self.assertEqual(call[1], (u"wamp.session.on_leave", 1234))

    def test_onleave_publish(self):
        """
        Receiving a Goodbye should put the session in a "detached" state
        *before* the onLeave method is triggered
        """

        router = mock.MagicMock()
        router.new_correlation_id = lambda: u'fake correlation id'
        utest = self

        class TestSession(RouterSession):
            def __init__(self, *args, **kw):
                super(TestSession, self).__init__(*args, **kw)
                # for this test, pretend we're connected (without
                # going through sending a Hello etc.)
                self._service_session = mock.MagicMock()
                self._transport = mock.MagicMock()
                self._session_id = 1234
                self._router = router  # normally done in Hello processing
                self.on_leave_called = False  # so the test ensures onLeave called

            def onLeave(self, reason):
                utest.assertFalse(self.on_leave_called)
                # we check that when this method is called, we look
                # like we're un-joined
                utest.assertIs(None, self._session_id)
                utest.assertTrue(self._goodbye_sent)
                # on the router, .detach() should have been called
                utest.assertEqual(1, len(router.method_calls))
                utest.assertEqual('detach', router.method_calls[0][0])
                self.on_leave_called = True

        router_factory = mock.MagicMock()
        session = TestSession(router_factory)
        goodbye = message.Goodbye(u'wamp.close.normal', u'hi there')

        self.assertFalse(session._goodbye_sent)

        # do the test; we check results in onLeave
        self.assertFalse(session.on_leave_called)
        session.onMessage(goodbye)
        self.assertTrue(session.on_leave_called)
