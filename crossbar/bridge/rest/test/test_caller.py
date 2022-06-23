#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

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


@error("com.myapp.error1")
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

        yield self.register(sqrt, 'com.myapp.sqrt')

        # raising WAMP application exceptions
        ##
        def checkname(name):
            if name in ['foo', 'bar']:
                raise ApplicationError("com.myapp.error.reserved")

            if name.lower() != name.upper():
                # forward positional arguments in exceptions
                raise ApplicationError("com.myapp.error.mixed_case", name.lower(), name.upper())

            if len(name) < 3 or len(name) > 10:
                # forward keyword arguments in exceptions
                raise ApplicationError("com.myapp.error.invalid_length", min=3, max=10)

        yield self.register(checkname, 'com.myapp.checkname')

        # defining and automapping WAMP application exceptions
        ##
        self.define(AppError1)

        def compare(a, b):
            if a < b:
                raise AppError1(b - a)

        yield self.register(compare, 'com.myapp.compare')


class CallerTestCase(TestCase):
    """
    Unit tests for L{CallerResource}.
    """
    def setUp(self):

        # create a router factory
        self.router_factory = RouterFactory('node1', 'worker1', None)

        # start a realm
        self.realm = RouterRealm(None, None, {'name': 'realm1'})
        self.router_factory.start_realm(self.realm)

        # allow everything
        self.router = self.router_factory.get('realm1')
        self.router.add_role(
            RouterRoleStaticAuth(self.router,
                                 'test_role',
                                 default_permissions={
                                     'uri': 'com.myapp.',
                                     'match': 'prefix',
                                     'allow': {
                                         'call': True,
                                         'register': True,
                                         'publish': True,
                                         'subscribe': True,
                                     }
                                 }))

        # create a router session factory
        self.session_factory = RouterSessionFactory(self.router_factory)

    @inlineCallbacks
    def test_add2(self):
        """
        Test a very basic call where you square root a number. This has one
        arg, no kwargs, and no authorisation.
        """
        session = TestSession(types.ComponentConfig('realm1'))
        self.session_factory.add(session, self.router, authrole="test_role")

        session2 = ApplicationSession(types.ComponentConfig('realm1'))
        self.session_factory.add(session2, self.router, authrole="test_role")
        resource = CallerResource({}, session2)

        with LogCapturer() as l:
            request = yield renderResource(resource,
                                           b"/",
                                           method=b"POST",
                                           headers={b"Content-Type": [b"application/json"]},
                                           body=b'{"procedure": "com.myapp.sqrt", "args": [2]}')

        self.assertEqual(request.code, 200)
        self.assertEqual(json.loads(native_string(request.get_written_data())), {"args": [1.4142135623730951]})

        logs = l.get_category("AR202")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["code"], 200)

    @inlineCallbacks
    def test_failure(self):
        """
        A failed call returns the error to the client.
        """
        session = TestSession(types.ComponentConfig('realm1'))
        self.session_factory.add(session, self.router, authrole="test_role")

        session2 = ApplicationSession(types.ComponentConfig('realm1'))
        self.session_factory.add(session2, self.router, authrole="test_role")
        resource = CallerResource({}, session2)

        tests = [
            ("com.myapp.sqrt", (0, ), {
                "error": "wamp.error.runtime_error",
                "args": ["don't ask foolish questions ;)"],
                "kwargs": {}
            }),
            ("com.myapp.checkname", ("foo", ), {
                "error": "com.myapp.error.reserved",
                "args": [],
                "kwargs": {}
            }),
            ("com.myapp.checkname", ("*", ), {
                "error": "com.myapp.error.invalid_length",
                "args": [],
                "kwargs": {
                    "min": 3,
                    "max": 10
                }
            }),
            ("com.myapp.checkname", ("hello", ), {
                "error": "com.myapp.error.mixed_case",
                "args": ["hello", "HELLO"],
                "kwargs": {}
            }),
            ("com.myapp.compare", (1, 10), {
                "error": "com.myapp.error1",
                "args": [9],
                "kwargs": {}
            }),
        ]

        for procedure, args, err in tests:
            with LogCapturer() as l:
                request = yield renderResource(resource,
                                               b"/",
                                               method=b"POST",
                                               headers={b"Content-Type": [b"application/json"]},
                                               body=dump_json({
                                                   "procedure": procedure,
                                                   "args": args
                                               }).encode('utf8'))

            self.assertEqual(request.code, 200)
            self.assertEqual(json.loads(native_string(request.get_written_data())), err)

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
            request = yield renderResource(resource,
                                           b"/",
                                           method=b"POST",
                                           headers={b"Content-Type": [b"application/json"]},
                                           body=b'{"procedure": "foo"}')

        self.assertEqual(request.code, 500)
        self.assertEqual(json.loads(native_string(request.get_written_data())), {
            "error": "wamp.error.runtime_error",
            "args": ["Sorry, Crossbar.io has encountered a problem."],
            "kwargs": {}
        })

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
            request = yield renderResource(resource,
                                           b"/",
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
            request = yield renderResource(resource,
                                           b"/",
                                           method=b"POST",
                                           headers={b"Content-Type": [b"application/json"]})

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR453")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)
