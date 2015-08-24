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
from crossbar.adapter.rest.test import MockPublisherSession, renderResource, makeSignedArguments

resourceOptions = {
    "secret": "foobar",
    "key": "bazapp"
}

publishBody = b'{"topic": "com.test.messages", "args": [1]}'


class SignatureTestCase(TestCase):
    """
    Unit tests for the signature authentication part of L{_CommonResource}.
    """
    @inlineCallbacks
    def test_good_signature(self):
        """
        A valid, correct signature will mean the request is processed.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody,
            sign=True, signKey="bazapp", signSecret="foobar")

        self.assertEqual(request.code, 202)
        self.assertEqual(json.loads(native_string(request.getWrittenData())),
                         {"id": session._published_messages[0]["id"]})

    @inlineCallbacks
    def test_incorrect_secret(self):
        """
        An incorrect secret (but an otherwise well-formed signature) will mean
        the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        request = yield renderResource(
            resource, b"/",
            method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody,
            sign=True, signKey="bazapp", signSecret="foobar2")

        self.assertEqual(request.code, 401)
        self.assertIn(b"invalid request signature",
                      request.getWrittenData())

    @inlineCallbacks
    def test_unknown_key(self):
        """
        An unknown key in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody,
            sign=True, signKey="spamapp", signSecret="foobar")

        self.assertEqual(request.code, 400)
        self.assertIn(b"unknown key 'spamapp' in signed request",
                      request.getWrittenData())

    @inlineCallbacks
    def test_no_timestamp(self):
        """
        No timestamp in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'timestamp']

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"signed request required, but mandatory 'timestamp' field missing",
                      request.getWrittenData())

    @inlineCallbacks
    def test_wrong_timestamp(self):
        """
        An invalid timestamp in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        signedParams[b'timestamp'] = [b"notatimestamp"]

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"invalid timestamp 'notatimestamp' (must be UTC/ISO-8601,"
                      b" e.g. '2011-10-14T16:59:51.123Z')",
                      request.getWrittenData())

    @inlineCallbacks
    def test_outdated_delta(self):
        """
        If the delta between now and the timestamp in the request is larger than
        C{timestamp_delta_limit}, the request is rejected.
        """
        custOpts = {"timestamp_delta_limit": 1}
        custOpts.update(resourceOptions)
        session = MockPublisherSession(self)
        resource = PublisherResource(custOpts, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        signedParams[b'timestamp'] = [b"2011-10-14T16:59:51.123Z"]

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"request expired (delta",
                      request.getWrittenData())

    @inlineCallbacks
    def test_invalid_nonce(self):
        """
        An invalid nonce in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        signedParams[b'nonce'] = [b"notanonce"]

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"invalid nonce 'notanonce' (must be an integer)",
                      request.getWrittenData())

    @inlineCallbacks
    def test_no_nonce(self):
        """
        A missing nonce in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'nonce']

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"signed request required, but mandatory 'nonce' field missing",
                      request.getWrittenData())

    @inlineCallbacks
    def test_no_signature(self):
        """
        A missing signature in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'signature']

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"signed request required, but mandatory 'signature' field missing",
                      request.getWrittenData())

    @inlineCallbacks
    def test_no_key(self):
        """
        A missing key in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'key']

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"signed request required, but mandatory 'key' field missing",
                      request.getWrittenData())

    @inlineCallbacks
    def test_no_seq(self):
        """
        A missing sequence in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'seq']

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"signed request required, but mandatory 'seq' field missing",
                      request.getWrittenData())

    @inlineCallbacks
    def test_wrong_seq(self):
        """
        A missing sequence in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        signedParams[b'seq'] = [b"notaseq"]

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)
        self.assertIn(b"invalid sequence number 'notaseq' (must be an integer)",
                      request.getWrittenData())
