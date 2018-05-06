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

from crossbar.test import TestCase
from crossbar._logging import LogCapturer
from crossbar.bridge.rest import PublisherResource
from crossbar.bridge.rest.test import MockPublisherSession, renderResource

publishBody = b'{"topic": "com.test.messages", "args": [1]}'


class IPWhitelistingTestCase(TestCase):
    """
    Unit tests for the IP address checking parts of L{_CommonResource}.
    """
    def test_allowed_IP(self):
        """
        The client having an allowed IP address allows the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_ip": ["127.0.0.1"]}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody))

        self.assertEqual(request.code, 200)

    def test_allowed_IP_range(self):
        """
        The client having an IP in an allowed address range allows the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_ip": ["127.0.0.0/8"]}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody))

        self.assertEqual(request.code, 200)

    def test_disallowed_IP_range(self):
        """
        The client having an IP not in allowed address range denies the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_ip": ["192.168.0.0/16", "10.0.0.0/8"]}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody))

        self.assertEqual(request.code, 400)
        self.assertIn(b"Request denied based on IP address",
                      request.get_written_data())


class SecureTransportTestCase(TestCase):
    """
    Unit tests for the transport security testing parts of L{_CommonResource}.
    """
    def test_required_tls_with_tls(self):
        """
        Required TLS, plus a request over TLS, will allow the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_tls": True}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, isSecure=True))

        self.assertEqual(request.code, 200)

    def test_not_required_tls_with_tls(self):
        """
        A request over TLS even when not required, will allow the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, isSecure=True))

        self.assertEqual(request.code, 200)

    def test_required_tls_without_tls(self):
        """
        Required TLS, plus a request NOT over TLS, will deny the request.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"require_tls": True}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=publishBody, isSecure=False))

        self.assertEqual(request.code, 400)


class RequestBodyTestCase(TestCase):
    """
    Unit tests for the body validation parts of L{_CommonResource}.
    """
    def test_allow_charset_in_content_type(self):
        """
        A charset in the content-type will be allowed.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json; charset=utf-8"]},
            body=publishBody))

        self.assertEqual(request.code, 200)
        self.assertIn(b'{"id":',
                      request.get_written_data())

    def test_allow_caps_in_content_type(self):
        """
        Differently-capitalised content-type headers will be allowed.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"CONTENT-TYPE": [b"APPLICATION/JSON"]},
            body=publishBody))

        self.assertEqual(request.code, 200)
        self.assertIn(b'{"id":',
                      request.get_written_data())

    def test_bad_content_type(self):
        """
        An incorrect content type will mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/text"]},
                body=publishBody))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR452")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    def test_bad_method(self):
        """
        An incorrect method will mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"BLBLBLB",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody))

        self.assertEqual(request.code, 405)
        errors = l.get_category("AR405")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 405)

    def test_too_large_body(self):
        """
        A too large body will mean the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"post_body_limit": 1}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=publishBody))

        self.assertEqual(request.code, 413)

        errors = l.get_category("AR413")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 413)

    def test_multiple_content_length(self):
        """
        Requests with multiple Content-Length headers will be rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"],
                         b"Content-Length": ["1", "10"]},
                body=publishBody))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR463")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    def test_not_matching_bodylength(self):
        """
        A body length that is different than the Content-Length header will mean
        the request is rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({"post_body_limit": 1}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"],
                         b"Content-Length": [1]},
                body=publishBody))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR465")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    def test_invalid_JSON_body(self):
        """
        A body that is not valid JSON will be rejected by the server.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=b"sometext"))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR453")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    def test_JSON_list_body(self):
        """
        A body that is not a JSON dict will be rejected by the server.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json"]},
                body=b"[{},{}]"))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR454")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    def test_UTF8_assumption(self):
        """
        A body, when the Content-Type has no charset, is assumed to be UTF-8.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json"]},
            body=b'{"topic": "com.test.messages", "args": ["\xe2\x98\x83"]}'))

        self.assertEqual(request.code, 200)
        self.assertIn(b'{"id":',
                      request.get_written_data())

    def test_ASCII_denied(self):
        """
        A body with an ASCII charset is denied, it must be UTF-8.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json; charset=ascii"]},
                body=b''))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR450")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    def test_decodes_UTF8(self):
        """
        A body, when the Content-Type has been set to be charset=utf-8, will
        decode it as UTF8.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        request = self.successResultOf(renderResource(
            resource, b"/", method=b"POST",
            headers={b"Content-Type": [b"application/json;charset=utf-8"]},
            body=b'{"topic": "com.test.messages", "args": ["\xe2\x98\x83"]}'))

        self.assertEqual(request.code, 200)
        self.assertIn(b'{"id":',
                      request.get_written_data())

    def test_undecodable_UTF8(self):
        """
        Undecodable UTF-8 will return an error.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json;charset=utf-8"]},
                body=b'{"topic": "com.test.messages", "args": ["\x61\x62\x63\xe9"]}'))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR451")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    def test_unknown_encoding(self):
        """
        A body, when the Content-Type has been set to something other than
        charset=utf-8, will error out.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json;charset=blarg"]},
                body=b'{"args": ["\x61\x62\x63\xe9"]}'))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR450")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

    def test_broken_contenttype(self):
        """
        Crossbar rejects broken content-types.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"application/json;charset=blarg;charset=boo"]},
                body=b'{"foo": "\xe2\x98\x83"}'))

        errors = l.get_category("AR450")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

        del l

        with LogCapturer("debug") as l:
            request = self.successResultOf(renderResource(
                resource, b"/", method=b"POST",
                headers={b"Content-Type": [b"charset=blarg;application/json"]},
                body=b'{"foo": "\xe2\x98\x83"}'))

        self.assertEqual(request.code, 400)

        errors = l.get_category("AR452")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)
