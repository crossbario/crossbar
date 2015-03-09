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

import json

from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, inlineCallbacks

from twisted.internet import reactor

from .requestMock import testResource

from crossbar.adapter.rest import CallerResource


class MockSession(object):

    def __init__(self, testCase):

        self._procedureName = None
        self._args = None
        self._kwargs = None
        self._response = None
        self._testCase = testCase

    def _addProcedureCall(self, procedureName, args, kwargs, response):

        self._procedureName = procedureName
        self._args = args
        self._kwargs = kwargs
        self._response = response

        def call(procedureName, *args, **kwargs):

            self._testCase.assertEqual(procedureName, self._procedureName)
            self._testCase.assertEqual(args, self._args)
            self._testCase.assertEqual(kwargs, self._kwargs)

            d = Deferred()
            reactor.callLater(0, d.callback, self._response)
            return d

        setattr(self, "call", call)


class CallerTestCase(TestCase):

    @inlineCallbacks
    def test_add2(self):
        """
        Test a very basic call where you add two numbers together.
        """
        mockSession = MockSession(self)
        mockSession._addProcedureCall("com.test.add2",
                                      args=(1, 2),
                                      kwargs={},
                                      response=3)

        resource = CallerResource({}, mockSession)

        request = yield testResource(
            resource, "/",
            method="POST",
            headers={"Content-Type": ["application/json"]},
            body='{"procedure": "com.test.add2", "args": [1,2]}')

        self.assertEqual(json.loads(request.getWrittenData()),
                         {"response": 3})
