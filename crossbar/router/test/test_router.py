#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.trial import unittest

import txaio
import mock

from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp import role
from autobahn.wamp.types import TransportDetails
from autobahn.twisted.wamp import ApplicationSession

from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.worker.types import RouterRealm
from crossbar.router.role import RouterRoleStaticAuth


class TestEmbeddedSessions(unittest.TestCase):
    """
    Test cases for application session running embedded in router.
    """
    def setUp(self):
        """
        Setup router and router session factories.
        """

        # create a router factory
        self.router_factory = RouterFactory('node1', 'router1', None)

        # start a realm
        self.router_factory.start_realm(RouterRealm(None, None, {'name': 'realm1'}))

        # allow everything
        default_permissions = {
            'uri': '',
            'match': 'prefix',
            'allow': {
                'call': True,
                'register': True,
                'publish': True,
                'subscribe': True
            }
        }
        self.router = self.router_factory.get('realm1')
        self.router.add_role(RouterRoleStaticAuth(self.router, 'test_role', default_permissions=default_permissions))
        self.router.add_role(RouterRoleStaticAuth(self.router, None, default_permissions=default_permissions))

        # create a router session factory
        self.session_factory = RouterSessionFactory(self.router_factory)

    def tearDown(self):
        pass

    def test_authorize_exception_call(self):
        """
        When a dynamic authorizor throws an exception (during processCall)
        we log it.
        """
        raise unittest.SkipTest('FIXME: the mock may be wrong here ..')

        the_exception = RuntimeError("authorizer bug")

        def boom(*args, **kw):
            raise the_exception

        self.router._roles['test_role'].authorize = boom

        class TestSession(ApplicationSession):
            def __init__(self, *args, **kw):
                super(TestSession, self).__init__(*args, **kw)
                self._authrole = 'test_role'
                self._transport = mock.MagicMock()

        session0 = TestSession()
        self.router._dealer._registration_map.add_observer(session0, 'test.proc')

        # okay, we have an authorizer that will always explode and a
        # single procedure registered; when we call it, then
        # on_authorize_error (in dealer.py) should get called and our
        # error logged.

        call = message.Call(
            request=1234,
            procedure='test.proc',
            args=tuple(),
            kwargs=dict(),
        )
        # this should produce an error -- however processCall doesn't
        # itself return the Deferred, so we look for the side-effect
        # -- the router should have tried to send a message.Error (and
        # we should also have logged the error).
        self.router._dealer.processCall(session0, call)

        self.assertEqual(1, len(session0._transport.mock_calls))
        call = session0._transport.mock_calls[0]
        self.assertEqual('send', call[0])
        # ensure we logged our error (flushLoggedErrors also causes
        # trial to *not* fail the unit-test despite an error logged)
        errors = self.flushLoggedErrors()
        self.assertTrue(the_exception in [fail.value for fail in errors])

    def test_authorize_exception_register(self):
        """
        When a dynamic authorizor throws an exception (during processRegister)
        we log it.
        """
        raise unittest.SkipTest('FIXME: the mock may be wrong here ..')

        the_exception = RuntimeError("authorizer bug")

        def boom(*args, **kw):
            raise the_exception

        self.router._roles['test_role'].authorize = boom

        class TestSession(ApplicationSession):
            def __init__(self, *args, **kw):
                super(TestSession, self).__init__(*args, **kw)
                self._authrole = 'test_role'
                self._transport = mock.MagicMock()

        session0 = TestSession()

        call = message.Register(
            request=1234,
            procedure='test.proc_reg',
        )
        # this should produce an error -- however processCall doesn't
        # itself return the Deferred, so we look for the side-effect
        # -- the router should have tried to send a message.Error (and
        # we should also have logged the error).
        self.router._dealer.processRegister(session0, call)

        self.assertEqual(1, len(session0._transport.mock_calls))
        call = session0._transport.mock_calls[0]
        self.assertEqual('send', call[0])
        # ensure we logged our error (flushLoggedErrors also causes
        # trial to *not* fail the unit-test despite an error logged)
        errors = self.flushLoggedErrors()
        self.assertTrue(the_exception in [fail.value for fail in errors])

    def test_add(self):
        """
        Create an application session and add it to a router to
        run embedded.
        """
        d = txaio.create_future()

        class TestSession(ApplicationSession):
            def onJoin(self, details):
                txaio.resolve(d, None)

        session = TestSession(types.ComponentConfig('realm1'))

        self.session_factory.add(session, self.router)

        return d

    def test_application_session_internal_error(self):
        """
        simulate an internal error triggering the 'onJoin' error-case from
        _RouterApplicationSession's send() method (from the Hello msg)
        """
        # setup
        the_exception = RuntimeError("sadness")
        errors = []

        class TestSession(ApplicationSession):
            def onJoin(self, *args, **kw):
                raise the_exception

            def onUserError(self, *args, **kw):
                errors.append((args, kw))

        session = TestSession(types.ComponentConfig('realm1'))

        # in this test, we are just looking for onUserError to get
        # called so we don't need to patch the logger. this should
        # call onJoin, triggering our error
        self.session_factory.add(session, self.router)

        # check we got the right log.failure() call
        self.assertTrue(len(errors) > 0, "expected onUserError call")
        fail = errors[0][0][0]
        self.assertTrue(fail.value == the_exception)

    def test_router_session_internal_error_onHello(self):
        """
        similar to above, but during _RouterSession's onMessage handling,
        where it calls self.onHello
        """
        raise unittest.SkipTest('FIXME: Adjust unit test mocks #1567')

        # setup
        transport = mock.MagicMock()
        transport.transport_details = TransportDetails(channel_id={'tls-unique': b'deadbeef'})
        the_exception = RuntimeError("kerblam")

        def boom(*args, **kw):
            raise the_exception

        session = self.session_factory()  # __call__ on the _RouterSessionFactory
        session.onHello = boom
        session.onOpen(transport)
        msg = message.Hello('realm1', dict(caller=role.RoleCallerFeatures()))

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
        raise unittest.SkipTest('FIXME: Adjust unit test mocks #1567')

        # setup
        transport = mock.MagicMock()
        transport.transport_details = TransportDetails(channel_id={'tls-unique': b'deadbeef'})
        the_exception = RuntimeError("kerblam")

        def boom(*args, **kw):
            raise the_exception

        session = self.session_factory()  # __call__ on the _RouterSessionFactory
        session.onAuthenticate = boom
        session.onOpen(transport)
        msg = message.Authenticate('bogus signature')

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

                d2 = self.subscribe(on_event, 'com.example.topic1')

                def ok(_):
                    txaio.resolve(d, None)

                def error(err):
                    txaio.reject(d, err)

                txaio.add_callbacks(d2, ok, error)

        session = TestSession(types.ComponentConfig('realm1'))

        self.session_factory.add(session, self.router)

        return d
