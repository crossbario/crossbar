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

import datetime
import json
import hmac
import hashlib
import base64

from crossbar._logging import make_logger
from crossbar._compat import native_string

from netaddr.ip import IPAddress, IPNetwork

from twisted.web.resource import Resource

from autobahn.websocket.utf8validator import Utf8Validator
_validator = Utf8Validator()


class _InvalidUnicode(BaseException):
    """
    Invalid Unicode was found.
    """


class _CommonResource(Resource):
    """
    Shared components between PublisherResource and CallerResource.
    """
    isLeaf = True
    decode_as_json = True

    def __init__(self, options, session):
        """
        Ctor.

        :param options: Options for path service from configuration.
        :type options: dict
        :param session: Instance of `ApplicationSession` to be used for forwarding events.
        :type session: obj
        """
        Resource.__init__(self)
        self._options = options
        self._session = session
        self.log = make_logger()

        self._key = None
        if 'key' in options:
            self._key = options['key'].encode('utf8')

        self._secret = None
        if 'secret' in options:
            self._secret = options['secret'].encode('utf8')

        self._post_body_limit = int(options.get('post_body_limit', 0))
        self._timestamp_delta_limit = int(options.get('timestamp_delta_limit', 300))

        self._require_ip = None
        if 'require_ip' in options:
            self._require_ip = [IPNetwork(net) for net in options['require_ip']]

        self._require_tls = options.get('require_tls', None)

    def _deny_request(self, request, code, reason, **kwargs):
        """
        Called when client request is denied.
        """
        self.log.debug("[request denied] - {code} / " + reason,
                       code=code, **kwargs)
        request.setResponseCode(code)
        return reason.format(**kwargs).encode('utf8') + b"\n"

    def render(self, request):
        self.log.debug("[render] method={request.method} path={request.path} args={request.args}",
                       request=request)

        if request.method != b"POST":
            return self._deny_request(request, 405, u"HTTP/{0} not allowed".format(native_string(request.method)))
        else:
            return self.render_POST(request)

    def render_POST(self, request):
        """
        Receives an HTTP/POST request, and then calls the Publisher/Caller
        processor.
        """
        # read HTTP/POST body
        body = request.content.read()

        args = {native_string(x): y[0] for x, y in request.args.items()}
        headers = request.requestHeaders

        # check content type + charset encoding
        #
        content_type_header = headers.getRawHeaders(b"content-type", [])

        if len(content_type_header) > 0:
            content_type_elements = [
                x.strip().lower()
                for x in content_type_header[0].split(b";")
            ]
        else:
            content_type_elements = []

        if self.decode_as_json:
            if len(content_type_elements) == 0 or \
               b'application/json' != content_type_elements[0]:
                return self._deny_request(
                    request, 400,
                    u"bad or missing content type, should be 'application/json'")

        encoding_parts = {}

        if len(content_type_elements) > 1:
            try:
                for item in content_type_elements:
                    if b"=" not in item:
                        # Don't bother looking at things "like application/json"
                        continue

                    # Parsing things like:
                    # charset=utf-8
                    _ = native_string(item).split("=")
                    assert len(_) == 2

                    # We don't want duplicates
                    key = _[0].strip().lower()
                    assert key not in encoding_parts
                    encoding_parts[key] = _[1].strip().lower()
            except:
                return self._deny_request(request, 400,
                                          u"mangled Content-Type header")

        charset_encoding = encoding_parts.get("charset", "utf-8")

        if charset_encoding not in ["utf-8", 'utf8']:
            return self._deny_request(
                request, 400,
                (u"'{charset_encoding}' is not an accepted charset encoding, "
                 u"must be utf-8"),
                charset_encoding=charset_encoding)

        # enforce "post_body_limit"
        #
        body_length = len(body)
        content_length_header = headers.getRawHeaders(b"content-length", [])

        if len(content_length_header) == 1:
            content_length = int(content_length_header[0])
        elif len(content_length_header) > 1:
            return self._deny_request(
                request, 400,
                u"Multiple Content-Length headers are not allowed")
        else:
            content_length = body_length

        if body_length != content_length:
            # Prevent the body length from being different to the given
            # Content-Length. This is so that clients can't lie and bypass
            # length restrictions by giving an incorrect header with a large
            # body.
            return self._deny_request(request, 400, u"HTTP/POST body length ({0}) is different to Content-Length ({1})".format(body_length, content_length))

        if self._post_body_limit and content_length > self._post_body_limit:
            return self._deny_request(request, 400, u"HTTP/POST body length ({0}) exceeds maximum ({1})".format(content_length, self._post_body_limit))

        #
        # parse/check HTTP/POST query parameters
        #

        # key
        #
        if 'key' in args:
            key_str = args["key"]
        else:
            if self._secret:
                return self._deny_request(request, 400, u"signed request required, but mandatory 'key' field missing")

        # timestamp
        #
        if 'timestamp' in args:
            timestamp_str = args["timestamp"]
            try:
                ts = datetime.datetime.strptime(native_string(timestamp_str), "%Y-%m-%dT%H:%M:%S.%fZ")
                delta = abs((ts - datetime.datetime.utcnow()).total_seconds())
                if self._timestamp_delta_limit and delta > self._timestamp_delta_limit:
                    return self._deny_request(request, 400, u"request expired (delta {0} seconds)".format(delta))
            except ValueError as e:
                return self._deny_request(request, 400, u"invalid timestamp '{0}' (must be UTC/ISO-8601, e.g. '2011-10-14T16:59:51.123Z')".format(native_string(timestamp_str)))
        else:
            if self._secret:
                return self._deny_request(request, 400, u"signed request required, but mandatory 'timestamp' field missing")

        # seq
        #
        if 'seq' in args:
            seq_str = args["seq"]
            try:
                # FIXME: check sequence
                seq = int(seq_str)  # noqa
            except:
                return self._deny_request(request, 400, u"invalid sequence number '{0}' (must be an integer)".format(native_string(seq_str)))
        else:
            if self._secret:
                return self._deny_request(request, 400, u"signed request required, but mandatory 'seq' field missing")

        # nonce
        #
        if 'nonce' in args:
            nonce_str = args["nonce"]
            try:
                # FIXME: check nonce
                nonce = int(nonce_str)  # noqa
            except:
                return self._deny_request(request, 400, u"invalid nonce '{0}' (must be an integer)".format(native_string(nonce_str)))
        else:
            if self._secret:
                return self._deny_request(request, 400, u"signed request required, but mandatory 'nonce' field missing")

        # signature
        #
        if 'signature' in args:
            signature_str = args["signature"]
        else:
            if self._secret:
                return self._deny_request(request, 400, u"signed request required, but mandatory 'signature' field missing")

        # do more checks if signed requests are required
        #
        if self._secret:

            if key_str != self._key:
                return self._deny_request(request, 400, u"unknown key '{0}' in signed request".format(native_string(key_str)))

            # Compute signature: HMAC[SHA256]_{secret} (key | timestamp | seq | nonce | body) => signature
            hm = hmac.new(self._secret, None, hashlib.sha256)
            hm.update(key_str)
            hm.update(timestamp_str)
            hm.update(seq_str)
            hm.update(nonce_str)
            hm.update(body)
            signature_recomputed = base64.urlsafe_b64encode(hm.digest())

            if signature_str != signature_recomputed:
                return self._deny_request(request, 401, u"invalid request signature")
            else:
                self.log.debug("ok, request signature valid.")

        # user_agent = headers.get("user-agent", "unknown")
        client_ip = request.getClientIP()
        is_secure = request.isSecure()

        # enforce client IP address
        #
        if self._require_ip:
            ip = IPAddress(native_string(client_ip))
            allowed = False
            for net in self._require_ip:
                if ip in net:
                    allowed = True
                    break
            if not allowed:
                return self._deny_request(request, 400, u"request denied based on IP address")

        # enforce TLS
        #
        if self._require_tls:
            if not is_secure:
                return self._deny_request(request, 400, u"request denied because not using TLS")

        # FIXME: authorize request
        authorized = True

        if not authorized:
            return self._deny_request(request, 401, u"not authorized")

        _validator.reset()
        validation_result = _validator.validate(body)

        # validate() returns a 4-tuple, of which item 0 is whether it
        # is valid
        if not validation_result[0]:
            return self._deny_request(
                request, 400,
                u"invalid request event - HTTP/POST body was invalid UTF-8")

        event = body.decode('utf8')

        if self.decode_as_json:
            try:
                event = json.loads(event)
            except Exception as e:
                return self._deny_request(
                    request, 400,
                    (u"invalid request event - HTTP/POST body must be "
                     u"valid JSON: {exc}"), exc=e)

            if not isinstance(event, dict):
                return self._deny_request(
                    request, 400,
                    (u"invalid request event - HTTP/POST body must be "
                     u"a JSON dict"))

        return self._process(request, event)

    def _process(self, request, event):
        raise NotImplementedError()
