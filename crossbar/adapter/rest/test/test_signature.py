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

from crossbar.adapter.rest import PusherResource
from crossbar.adapter.rest.test import MockPusherSession, testResource, makeSignedArguments

resourceOptions = {
    "secret": "foobar",
    "key": "bazapp"
}

pushBody = '{"topic": "com.test.messages", "args": [1]}'


class SignatureTestCase(TestCase):
    """
    Unit tests for the signature authentication part of L{_CommonResource}.
    """
    @inlineCallbacks
    def test_good_signature(self):
        """
        A valid, correct signature will mean the request is processed.
        """
        session = MockPusherSession(self)
        resource = PusherResource(resourceOptions, session)

        request = yield testResource(
            resource, "/", method="POST",
            headers={"Content-Type": ["application/json"]},
            body=pushBody,
            sign=True, signKey="bazapp", signSecret="foobar")

        self.assertEqual(request.code, 202)
        self.assertEqual(json.loads(request.getWrittenData()),
                         {"id": session._published_messages[0]["id"]})

    @inlineCallbacks
    def test_incorrect_secret(self):
        """
        An incorrect secret (but an otherwise well-formed signature) will mean
        the request is rejected.
        """
        session = MockPusherSession(self)
        resource = PusherResource(resourceOptions, session)

        request = yield testResource(
            resource, "/",
            method="POST",
            headers={"Content-Type": ["application/json"]},
            body=pushBody,
            sign=True, signKey="bazapp", signSecret="foobar2")

        self.assertEqual(request.code, 401)
        self.assertIn("invalid request signature",
                      request.getWrittenData())

    @inlineCallbacks
    def test_unknown_key(self):
        """
        An unknown key in a request should mean the request is rejected.
        """
        session = MockPusherSession(self)
        resource = PusherResource(resourceOptions, session)

        request = yield testResource(
            resource, "/", method="POST",
            headers={"Content-Type": ["application/json"]},
            body=pushBody,
            sign=True, signKey="spamapp", signSecret="foobar")

        self.assertEqual(request.code, 400)
        self.assertIn("unknown key 'spamapp' in signed request",
                      request.getWrittenData())

    @inlineCallbacks
    def test_no_timestamp(self):
        """
        No timestamp in a request should mean the request is rejected.
        """
        session = MockPusherSession(self)
        resource = PusherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", pushBody)
        del signedParams['timestamp']

        request = yield testResource(
            resource, "/", method="POST",
            headers={"Content-Type": ["application/json"]},
            body=pushBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn("signed request required, but mandatory 'timestamp' field missing",
                      request.getWrittenData())

    @inlineCallbacks
    def test_wrong_timestamp(self):
        """
        An invalid timestamp in a request should mean the request is rejected.
        """
        session = MockPusherSession(self)
        resource = PusherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", pushBody)
        signedParams['timestamp'] = ["notatimestamp"]

        request = yield testResource(
            resource, "/", method="POST",
            headers={"Content-Type": ["application/json"]},
            body=pushBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn("invalid timestamp 'notatimestamp' (must be UTC/ISO-8601,"
                      " e.g. '2011-10-14T16:59:51.123Z')",
                      request.getWrittenData())

    @inlineCallbacks
    def test_outdated_delta(self):
        """
        If the delta between now and the timestamp in the request is larger than
        C{timestamp_delta_limit}, the request is rejected.
        """
        custOpts = {"timestamp_delta_limit": 1}
        custOpts.update(resourceOptions)
        session = MockPusherSession(self)
        resource = PusherResource(custOpts, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", pushBody)
        signedParams['timestamp'] = ["2011-10-14T16:59:51.123Z"]

        request = yield testResource(
            resource, "/", method="POST",
            headers={"Content-Type": ["application/json"]},
            body=pushBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn("request expired (delta",
                      request.getWrittenData())
