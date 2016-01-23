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

import json

from twisted.internet.defer import inlineCallbacks, maybeDeferred

from crossbar.test import TestCase
from crossbar._compat import native_string
from crossbar._logging import LogCapturer
from crossbar.adapter.rest import CallerResource
from crossbar.adapter.rest.test import renderResource


class MockSession(object):
    """
    A mock WAMP session.
    """
    def __init__(self, testCase):
        self._procedureName = None
        self._args = None
        self._kwargs = None
        self._response = None
        self._testCase = testCase

    def _addProcedureCall(self, procedureName, args=(), kwargs={}, response=None):
        """
        Add an expected procedure call, which expects a certain args, kwargs,
        and returns the response if it's okay.
        """
        self._procedureName = procedureName
        self._args = args
        self._kwargs = kwargs
        self._response = response

        def call(procedureName, *args, **kwargs):
            self._testCase.assertEqual(procedureName, self._procedureName)
            self._testCase.assertEqual(args, self._args)
            self._testCase.assertEqual(kwargs, self._kwargs)
            return self._response

        def _call(procedureName, *args, **kwargs):
            return maybeDeferred(call, procedureName, *args, **kwargs)

        setattr(self, "call", _call)


class CallerTestCase(TestCase):
    """
    Unit tests for L{CallerResource}. These tests make no WAMP calls, but test
    the interaction of the calling HTTP request and the resource.
    """
    @inlineCallbacks
    def test_add2(self):
        """
        Test a very basic call where you add two numbers together. This has two
        args, no kwargs, and no authorisation.
        """
        session = MockSession(self)
        session._addProcedureCall("com.test.add2",
                                  args=(1, 2),
                                  kwargs={},
                                  response=3)

        resource = CallerResource({}, session)

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/",
                method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=b'{"procedure": "com.test.add2", "args": [1,2]}')

        self.assertEqual(request.code, 200)
        self.assertEqual(json.loads(native_string(request.get_written_data())),
                         {"args": [3]})

        logs = l.get_category("AR202")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["code"], 200)

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
