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

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from crossbar._compat import native_string
from crossbar.adapter.rest import PublisherResource
from crossbar.adapter.rest.test import MockPublisherSession, renderResource


class PublisherTestCase(TestCase):
    """
    Unit tests for L{PublisherResource}. These tests publish no real WAMP messages,
    but test the interation of the HTTP request and the resource.
    """
    @inlineCallbacks
    def test_basic_publish(self):
        """
        Test a very basic publish to a topic.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = yield renderResource(
            resource, b"/",
            method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=b'{"topic": "com.test.messages", "args": [1]}')

        self.assertEqual(len(session._published_messages), 1)
        self.assertEqual(session._published_messages[0]["args"], (1,))

        self.assertEqual(request.code, 202)
        self.assertEqual(json.loads(native_string(request.getWrittenData())),
                         {"id": session._published_messages[0]["id"]})

    @inlineCallbacks
    def test_publish_needs_topic(self):
        """
        Test that attempted publishes without a topic will be rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = yield renderResource(
            resource, b"/",
            method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=b'{}')

        self.assertEqual(len(session._published_messages), 0)

        self.assertEqual(request.code, 400)
        self.assertIn(
            b"invalid request event - missing 'topic' in HTTP/POST body",
            request.getWrittenData())
