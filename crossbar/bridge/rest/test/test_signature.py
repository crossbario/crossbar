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

import json

from twisted.internet.defer import inlineCallbacks

from crossbar.test import TestCase
from crossbar._compat import native_string
from crossbar._logging import LogCapturer
from crossbar.bridge.rest import PublisherResource
from crossbar.bridge.rest.test import MockPublisherSession, renderResource, makeSignedArguments

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

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody,
                sign=True, signKey="bazapp", signSecret="foobar")

        self.assertEqual(request.code, 200)
        self.assertEqual(json.loads(native_string(request.get_written_data())),
                         {"id": session._published_messages[0]["id"]})

        logs = l.get_category("AR203")
        self.assertEqual(len(logs), 1)

    @inlineCallbacks
    def test_incorrect_secret(self):
        """
        An incorrect secret (but an otherwise well-formed signature) will mean
        the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/",
                method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody,
                sign=True, signKey="bazapp", signSecret="foobar2")

        self.assertEqual(request.code, 401)

        errors = l.get_category("AR459")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 401)

    @inlineCallbacks
    def test_unknown_key(self):
        """
        An unknown key in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody,
                sign=True, signKey="spamapp", signSecret="foobar")

        self.assertEqual(request.code, 401)

        errors = l.get_category("AR460")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 401)

    @inlineCallbacks
    def test_no_timestamp(self):
        """
        No timestamp in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'timestamp']

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR461")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    @inlineCallbacks
    def test_wrong_timestamp(self):
        """
        An invalid timestamp in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        signedParams[b'timestamp'] = [b"notatimestamp"]

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR462")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

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

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR464")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    @inlineCallbacks
    def test_invalid_nonce(self):
        """
        An invalid nonce in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        signedParams[b'nonce'] = [b"notanonce"]

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR462")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    @inlineCallbacks
    def test_no_nonce(self):
        """
        A missing nonce in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'nonce']

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR461")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    @inlineCallbacks
    def test_no_signature(self):
        """
        A missing signature in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'signature']

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR461")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    @inlineCallbacks
    def test_no_key(self):
        """
        A missing key in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'key']

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR461")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    @inlineCallbacks
    def test_no_seq(self):
        """
        A missing sequence in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        del signedParams[b'seq']

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR461")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    @inlineCallbacks
    def test_wrong_seq(self):
        """
        A missing sequence in a request should mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource(resourceOptions, session)

        signedParams = makeSignedArguments({}, "bazapp", "foobar", publishBody)
        signedParams[b'seq'] = [b"notaseq"]

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody, params=signedParams)

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR462")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)
