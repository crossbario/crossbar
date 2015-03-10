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

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from crossbar.adapter.rest import PusherResource
from crossbar.adapter.rest.test import MockPusherSession, testResource

pushBody = '{"topic": "com.test.messages", "args": [1]}'


class RequestBodyTestCase(TestCase):
    """
    Unit tests for the validation parts of L{_CommonResource}.
    """
    @inlineCallbacks
    def test_bad_content_type(self):
        """
        An incorrect content type will mean the request is rejected.
        """
        session = MockPusherSession(self)
        resource = PusherResource({}, session)

        request = yield testResource(
            resource, "/", method="POST",
            headers={"Content-Type": ["application/text"]},
            body=pushBody)

        self.assertEqual(request.code, 400)
        self.assertIn("bad or missing content type ('application/text')",
                      request.getWrittenData())

    @inlineCallbacks
    def test_bad_method(self):
        """
        An incorrect method will mean the request is rejected.
        """
        session = MockPusherSession(self)
        resource = PusherResource({}, session)

        request = yield testResource(
            resource, "/", method="PUT",
            headers={"Content-Type": ["application/jsn"]},
            body=pushBody)

        self.assertEqual(request.code, 405)
        self.assertIn("HTTP/PUT not allowed",
                      request.getWrittenData())

    @inlineCallbacks
    def test_too_large_body(self):
        """
        A too large body will mean the request is rejected.
        """
        session = MockPusherSession(self)
        resource = PusherResource({"post_body_limit": 1}, session)

        request = yield testResource(
            resource, "/", method="POST",
            headers={"Content-Type": ["application/json"]},
            body=pushBody)

        self.assertEqual(request.code, 400)
        self.assertIn("HTTP/POST body length ({}) exceeds maximum ({})".format(len(pushBody), 1),
                      request.getWrittenData())

    @inlineCallbacks
    def test_not_matching_bodylength(self):
        """
        A body length that is different than the Content-Length header will mean
        the request is rejected
        """
        session = MockPusherSession(self)
        resource = PusherResource({"post_body_limit": 1}, session)

        request = yield testResource(
            resource, "/", method="POST",
            headers={"Content-Type": ["application/json"],
                     "Content-Length": [1]},
            body=pushBody)

        self.assertEqual(request.code, 400)
        self.assertIn("HTTP/POST body length ({}) is different to Content-Length ({})".format(len(pushBody), 1),
                      request.getWrittenData())
