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
from twisted.python.compat import nativeString

from crossbar.adapter.rest import PublisherResource
from crossbar.adapter.rest.test import MockPublisherSession, renderResource

publishBody = b'{"topic": "com.test.messages", "args": [1]}'


class IPWhitelistingTestCase(TestCase):
    """
    Unit tests for the IP address checking parts of L{_CommonResource}.
    """
    @inlineCallbacks
    def test_allowed_IP(self):
        """
        The client having an allowed IP address allows the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_ip": ["127.0.0.1"]}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody)

        self.assertEqual(request.code, 202)

    @inlineCallbacks
    def test_allowed_IP_range(self):
        """
        The client having an IP in an allowed address range allows the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_ip": ["127.0.0.0/8"]}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody)

        self.assertEqual(request.code, 202)

    @inlineCallbacks
    def test_disallowed_IP_range(self):
        """
        The client having an IP not in allowed address range denies the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_ip": ["192.168.0.0/16", "10.0.0.0/8"]}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody)

        self.assertEqual(request.code, 400)
        self.assertIn(b"request denied based on IP address",
                      request.getWrittenData())


class SecureTransportTestCase(TestCase):
    """
    Unit tests for the transport security testing parts of L{_CommonResource}.
    """
    @inlineCallbacks
    def test_required_tls_with_tls(self):
        """
        Required TLS, plus a request over TLS, will allow the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_tls": True}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, isSecure=True)

        self.assertEqual(request.code, 202)

    @inlineCallbacks
    def test_not_required_tls_with_tls(self):
        """
        A request over TLS even when not required, will allow the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, isSecure=True)

        self.assertEqual(request.code, 202)

    @inlineCallbacks
    def test_required_tls_without_tls(self):
        """
        Required TLS, plus a request NOT over TLS, will deny the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_tls": True}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, isSecure=False)

        self.assertEqual(request.code, 400)


class RequestBodyTestCase(TestCase):
    """
    Unit tests for the body validation parts of L{_CommonResource}.
    """
    @inlineCallbacks
    def test_bad_content_type(self):
        """
        An incorrect content type will mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/text"]},
            body=publishBody)

        self.assertEqual(request.code, 400)
        self.assertIn(b"bad or missing content type ('application/text')",
                      request.getWrittenData())

    @inlineCallbacks
    def test_bad_method(self):
        """
        An incorrect method will mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = yield renderResource(
            resource, b"/", method=b"PUT",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody)

        self.assertEqual(request.code, 405)
        self.assertIn(b"HTTP/PUT not allowed",
                      request.getWrittenData())

    @inlineCallbacks
    def test_too_large_body(self):
        """
        A too large body will mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"post_body_limit": 1}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody)

        self.assertEqual(request.code, 400)
        self.assertIn("HTTP/POST body length ({}) exceeds maximum ({})".format(len(publishBody), 1),
                      nativeString(request.getWrittenData()))

    @inlineCallbacks
    def test_not_matching_bodylength(self):
        """
        A body length that is different than the Content-Length header will mean
        the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"post_body_limit": 1}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"],
                     b"Content-Length": [1]},
            body=publishBody)

        self.assertEqual(request.code, 400)
        self.assertIn("HTTP/POST body length ({}) is different to Content-Length ({})".format(len(publishBody), 1),
                      nativeString(request.getWrittenData()))

    @inlineCallbacks
    def test_invalid_JSON_body(self):
        """
        A body that is not valid JSON will be rejected by the server.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=b"sometext")

        self.assertEqual(request.code, 400)
        self.assertIn(b"invalid request event - HTTP/POST body must be valid JSON:",
                      request.getWrittenData())

    @inlineCallbacks
    def test_JSON_list_body(self):
        """
        A body that is not a JSON dict will be rejected by the server.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = yield renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=b"[{},{}]")

        self.assertEqual(request.code, 400)
        self.assertIn(b"invalid request event - HTTP/POST body must be JSON dict",
                      request.getWrittenData())
