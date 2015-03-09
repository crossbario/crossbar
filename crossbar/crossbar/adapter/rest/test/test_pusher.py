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

from random import randint

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, maybeDeferred

from crossbar.adapter.rest import PusherResource
from crossbar.adapter.rest.test import MockPusherSession, testResource


class PublisherTestCase(TestCase):
    """
    Unit tests for L{PusherResource}. These tests publish no real WAMP messages,
    but test the interation of the HTTP request and the resource.
    """
    @inlineCallbacks
    def test_basic_publish(self):
        """
        Test a very basic publish to a topic.
        """
        session = MockPusherSession(self)
        resource = PusherResource({}, session)

        request = yield testResource(
            resource, "/",
            method="POST",
            headers={"Content-Type": ["application/json"]},
            body='{"topic": "com.test.messages", "args": [1]}')

        self.assertEqual(len(session._published_messages), 1)
        self.assertEqual(session._published_messages[0]["args"], (1,))

        self.assertEqual(request.code, 202)
        self.assertEqual(json.loads(request.getWrittenData()),
                         {"id": session._published_messages[0]["id"]})

    @inlineCallbacks
    def test_publish_needs_topic(self):
        """
        Test that attempted publishes without a topic will be rejected.
        """
        session = MockPusherSession(self)
        resource = PusherResource({}, session)

        request = yield testResource(
            resource, "/",
            method="POST",
            headers={"Content-Type": ["application/json"]},
            body='{}')

        self.assertEqual(len(session._published_messages), 0)

        self.assertEqual(request.code, 400)
        self.assertIn(
            "invalid request event - missing 'topic' in HTTP/POST body",
            request.getWrittenData())
