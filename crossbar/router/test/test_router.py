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
        self.router_factory = RouterFactory(None, None)

        # start a realm
        self.router_factory.start_realm(RouterRealm(None, {u'name': u'realm1'}))

        # allow everything
        default_permissions = {
            u'uri': u'',
            u'match': u'prefix',
            u'allow': {
                u'call': True,
                u'register': True,
                u'publish': True,
                u'subscribe': True
            }
        }
        self.router = self.router_factory.get(u'realm1')
        self.router.add_role(RouterRoleStaticAuth(self.router, u'test_role', default_permissions=default_permissions))
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
        self.router._roles[u'test_role'].authorize = boom

        class TestSession(ApplicationSession):
            def __init__(self, *args, **kw):
                super(TestSession, self).__init__(*args, **kw)
                self._authrole = u'test_role'
                self._transport = mock.MagicMock()
        session0 = TestSession()
        self.router._dealer._registration_map.add_observer(session0, u'test.proc')

        # okay, we have an authorizer that will always explode and a
        # single procedure registered; when we call it, then
        # on_authorize_error (in dealer.py) should get called and our
        # error logged.

        call = message.Call(
            request=1234,
            procedure=u'test.proc',
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
        self.router._roles[u'test_role'].authorize = boom

        class TestSession(ApplicationSession):
            def __init__(self, *args, **kw):
                super(TestSession, self).__init__(*args, **kw)
                self._authrole = u'test_role'
                self._transport = mock.MagicMock()
        session0 = TestSession()

        call = message.Register(
            request=1234,
            procedure=u'test.proc_reg',
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

        session = TestSession(types.ComponentConfig(u'realm1'))

        self.session_factory.add(session)

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
        session = TestSession(types.ComponentConfig(u'realm1'))

        # in this test, we are just looking for onUserError to get
        # called so we don't need to patch the logger. this should
        # call onJoin, triggering our error
        self.session_factory.add(session)

        # check we got the right log.failure() call
        self.assertTrue(len(errors) > 0, "expected onUserError call")
        fail = errors[0][0][0]
        self.assertTrue(fail.value == the_exception)

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

                d2 = self.subscribe(on_event, u'com.example.topic1')

                def ok(_):
                    txaio.resolve(d, None)

                def error(err):
                    txaio.reject(d, err)

                txaio.add_callbacks(d2, ok, error)

        session = TestSession(types.ComponentConfig(u'realm1'))

        self.session_factory.add(session)

        return d
