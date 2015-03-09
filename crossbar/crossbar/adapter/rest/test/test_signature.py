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
from twisted.internet.defer import inlineCallbacks, maybeDeferred

from crossbar.adapter.rest.common import _CommonResource
from crossbar.adapter.rest import PusherResource
from crossbar.adapter.rest.test import MockPusherSession
from crossbar.adapter.rest.test.requestMock import testResource


class SignatureTestCase(TestCase):
    """
    Unit tests for the signature authentication part of L{_CommonResource}.
    """
    @inlineCallbacks
    def test_good_signature(self):

        options = {
            "secret": "foobar",
            "key": "bazapp"
        }

        session = MockPusherSession(self)
        resource = PusherResource(options, session)

        request = yield testResource(
            resource, "/",
            method="POST",
            headers={"Content-Type": ["application/json"]},
            body='{"topic": "com.test.messages", "args": [1]}',
            sign=True, signKey="bazapp", signSecret="foobar")

        self.assertEqual(request.code, 202)
        self.assertEqual(json.loads(request.getWrittenData()),
                         {"id": session._published_messages[0]["id"]})


    @inlineCallbacks
    def test_incorrect_secret(self):

        options = {
            "secret": "foobar2",
            "key": "bazapp"
        }

        session = MockPusherSession(self)
        resource = PusherResource(options, session)

        request = yield testResource(
            resource, "/",
            method="POST",
            headers={"Content-Type": ["application/json"]},
            body='{"topic": "com.test.messages", "args": [1]}',
            sign=True, signKey="bazapp", signSecret="foobar")

        self.assertEqual(request.code, 401)
        self.assertIn("invalid request signature",
                      request.getWrittenData())

    @inlineCallbacks
    def test_unknown_key(self):

        options = {
            "secret": "foobar2",
            "key": "bazapp"
        }

        session = MockPusherSession(self)
        resource = PusherResource(options, session)

        request = yield testResource(
            resource, "/",
            method="POST",
            headers={"Content-Type": ["application/json"]},
            body='{"topic": "com.test.messages", "args": [1]}',
            sign=True, signKey="spamapp", signSecret="foobar")

        self.assertEqual(request.code, 400)
        self.assertIn("unknown key 'spamapp' in signed request",
                      request.getWrittenData())
