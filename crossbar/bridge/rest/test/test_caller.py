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

import math
import json

from twisted.internet.defer import inlineCallbacks

from autobahn.wamp import types, error
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationSession

from crossbar.worker.types import RouterRealm
from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.role import RouterRoleStaticAuth

from crossbar.test import TestCase
from crossbar._util import dump_json
from crossbar._compat import native_string
from crossbar._logging import LogCapturer
from crossbar.bridge.rest import CallerResource
from crossbar.bridge.rest.test import renderResource


@error(u"com.myapp.error1")
class AppError1(Exception):
    """
    An application specific exception that is decorated with a WAMP URI,
    and hence can be automapped by Autobahn.
    """


class TestSession(ApplicationSession):
    """
    Example WAMP application backend that raises exceptions.

    See: https://github.com/crossbario/autobahn-python/blob/master/examples/twisted/wamp/rpc/errors/backend.py
    """
    @inlineCallbacks
    def onJoin(self, details):
        # raising standard exceptions
        ##
        def sqrt(x):
            if x == 0:
                raise Exception("don't ask foolish questions ;)")
            else:
                # this also will raise, if x < 0
                return math.sqrt(x)

        yield self.register(sqrt, u'com.myapp.sqrt')

        # raising WAMP application exceptions
        ##
        def checkname(name):
            if name in ['foo', 'bar']:
                raise ApplicationError(u"com.myapp.error.reserved")

            if name.lower() != name.upper():
                # forward positional arguments in exceptions
                raise ApplicationError(u"com.myapp.error.mixed_case", name.lower(), name.upper())

            if len(name) < 3 or len(name) > 10:
                # forward keyword arguments in exceptions
                raise ApplicationError(u"com.myapp.error.invalid_length", min=3, max=10)

        yield self.register(checkname, u'com.myapp.checkname')

        # defining and automapping WAMP application exceptions
        ##
        self.define(AppError1)

        def compare(a, b):
            if a < b:
                raise AppError1(b - a)

        yield self.register(compare, u'com.myapp.compare')


class CallerTestCase(TestCase):
    """
    Unit tests for L{CallerResource}.
    """
    def setUp(self):

        # create a router factory
        self.router_factory = RouterFactory(None, None)

        # start a realm
        self.realm = RouterRealm(None, {u'name': u'realm1'})
        self.router_factory.start_realm(self.realm)

        # allow everything
        self.router = self.router_factory.get(u'realm1')
        self.router.add_role(
            RouterRoleStaticAuth(
                self.router,
                u'test_role',
                default_permissions={
                    u'uri': u'com.myapp.',
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

    @inlineCallbacks
    def test_add2(self):
        """
        Test a very basic call where you square root a number. This has one
        arg, no kwargs, and no authorisation.
        """
        session = TestSession(types.ComponentConfig(u'realm1'))
        self.session_factory.add(session, authrole=u"test_role")

        session2 = ApplicationSession(types.ComponentConfig(u'realm1'))
        self.session_factory.add(session2, authrole=u"test_role")
        resource = CallerResource({}, session2)

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/",
                method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=b'{"procedure": "com.myapp.sqrt", "args": [2]}')

        self.assertEqual(request.code, 200)
        self.assertEqual(json.loads(native_string(request.get_written_data())),
                         {"args": [1.4142135623730951]})

        logs = l.get_category("AR202")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["code"], 200)

    @inlineCallbacks
    def test_failure(self):
        """
        A failed call returns the error to the client.
        """
        session = TestSession(types.ComponentConfig(u'realm1'))
        self.session_factory.add(session, authrole=u"test_role")

        session2 = ApplicationSession(types.ComponentConfig(u'realm1'))
        self.session_factory.add(session2, authrole=u"test_role")
        resource = CallerResource({}, session2)

        tests = [
            (u"com.myapp.sqrt", (0,),
             {u"error": u"wamp.error.runtime_error", u"args": [u"don't ask foolish questions ;)"], u"kwargs": {}}),
            (u"com.myapp.checkname", ("foo",),
             {u"error": u"com.myapp.error.reserved", u"args": [], u"kwargs": {}}),
            (u"com.myapp.checkname", ("*",),
             {u"error": u"com.myapp.error.invalid_length", u"args": [], u"kwargs": {"min": 3, "max": 10}}),
            (u"com.myapp.checkname", ("hello",),
             {u"error": u"com.myapp.error.mixed_case", u"args": ["hello", "HELLO"], u"kwargs": {}}),
            (u"com.myapp.compare", (1, 10),
             {u"error": u"com.myapp.error1", u"args": [9], u"kwargs": {}}),
        ]

        for procedure, args, err in tests:
            with LogCapturer() as l:
                request = yield renderResource(
                    resource, b"/",
                    method=b"POST",
                    headers={b"Content-Type": [b"application/json"]},
                    body=dump_json({"procedure": procedure, "args": args}).encode('utf8'))

            self.assertEqual(request.code, 200)
            self.assertEqual(json.loads(native_string(request.get_written_data())),
                             err)

            logs = l.get_category("AR458")
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["code"], 200)

        # We manually logged the errors; we can flush them from the log
        self.flushLoggedErrors()

    @inlineCallbacks
    def test_cb_failure(self):
        """
        Test that calls with no procedure in the request body are rejected.
        """
        resource = CallerResource({}, None)

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/",
                method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=b'{"procedure": "foo"}')

        self.assertEqual(request.code, 500)
        self.assertEqual(json.loads(native_string(request.get_written_data())),
                         {"error": "wamp.error.runtime_error", "args": ["Sorry, Crossbar.io has encountered a problem."], "kwargs": {}})

        errors = l.get_category("AR500")
        self.assertEqual(len(errors), 1)

        # We manually logged the errors; we can flush them from the log
        self.flushLoggedErrors()

    @inlineCallbacks
    def test_no_procedure(self):
        """
        Test that calls with no procedure in the request body are rejected.
        """
        resource = CallerResource({}, None)

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/",
                method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=b"{}")

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR455")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    @inlineCallbacks
    def test_no_body(self):
        """
        Test that calls with no body are rejected.
        """
        resource = CallerResource({}, None)

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/",
                method=b"POST",
                headers={b"Content-Type": [b"application/json"]})

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR453")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)
