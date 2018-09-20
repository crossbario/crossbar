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

import os
import datetime
import json
import hmac
import hashlib
import base64
import binascii

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp import types
from txaio import make_logger

from crossbar._util import dump_json
from crossbar._compat import native_string
from crossbar._log_categories import log_categories
from crossbar.router.auth import PendingAuthTicket
from ipaddress import ip_address, ip_network

from twisted.web import server
from twisted.web.resource import Resource
from twisted.internet.defer import maybeDeferred

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import hmac as hazmat_hmac

from autobahn.websocket.utf8validator import Utf8Validator
_validator = Utf8Validator()


_ALLOWED_CONTENT_TYPES = set([b'application/json'])


class _InvalidUnicode(BaseException):
    """
    Invalid Unicode was found.
    """


# used for constant-time compares
_nonce = os.urandom(32)


def _hmac_sha256(key, data):
    """
    :returns: the HMAC-SHA256 of 'data' using 'key'
    """
    h = hazmat_hmac.HMAC(key, hashes.SHA256(), default_backend())
    h.update(data)
    return h.finalize()


def _constant_compare(a, b):
    """
    Compare the two byte-strings 'a' and 'b' using a constant-time
    algorithm. The byte-strings should be the same length.
    """
    return _hmac_sha256(_nonce, a.encode('ascii')) == _hmac_sha256(_nonce, b.encode('ascii'))


def _confirm_github_signature(request, secret_token, raw_body):
    """
    confirm that signature headers from GitHub are present and valid
    """
    # stuff just "won't work" unless we gives bytes objects to the
    # underlying crypto primitives
    if not isinstance(secret_token, bytes):
        secret_token = secret_token.encode('ascii')
    assert isinstance(raw_body, bytes)
    # must have the header to continue
    if not request.requestHeaders.getRawHeaders(u'X-Hub-Signature'):
        return False
    purported_signature = str(request.requestHeaders.getRawHeaders(u'X-Hub-Signature')[0]).lower()
    # NOTE: never use SHA1 for new code ... but GitHub signatures are
    # SHA1, so we have to here :(
    h = hazmat_hmac.HMAC(secret_token, hashes.SHA1(), default_backend())  # nosec
    h.update(raw_body)
    our_signature = u"sha1={}".format(binascii.b2a_hex(h.finalize()).decode('ascii'))
    return _constant_compare(our_signature, purported_signature)


class _CommonResource(Resource):
    """
    Shared components between PublisherResource and CallerResource.
    """
    isLeaf = True
    decode_as_json = True

    def __init__(self, options, session, auth_config=None):
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
            self._require_ip = [ip_network(net) for net in options['require_ip']]

        self._require_tls = options.get('require_tls', None)

        self._auth_config = auth_config or {}
        self._pending_auth = None

    def _deny_request(self, request, code, **kwargs):
        """
        Called when client request is denied.
        """
        if "log_category" not in kwargs.keys():
            kwargs["log_category"] = "AR" + str(code)

        self.log.debug(code=code, **kwargs)

        error_str = log_categories[kwargs['log_category']].format(**kwargs)
        body = dump_json({"error": error_str,
                          "args": [], "kwargs": {}}, True).encode('utf8')
        request.setResponseCode(code)
        return body

    def _fail_request(self, request, **kwargs):
        """
        Called when client request fails.
        """
        res = {}
        err = kwargs["failure"]
        if isinstance(err.value, ApplicationError):
            res['error'] = err.value.error
            if err.value.args:
                res['args'] = err.value.args
            else:
                res['args'] = []
            if err.value.kwargs:
                res['kwargs'] = err.value.kwargs
            else:
                res['kwargs'] = {}

            # This is a user-level error, not a CB error, so return 200
            code = 200
        else:
            # This is a "CB" error, so return 500 and a generic error
            res['error'] = u'wamp.error.runtime_error'
            res['args'] = ["Sorry, Crossbar.io has encountered a problem."]
            res['kwargs'] = {}

            # CB-level error, return 500
            code = 500

            self.log.failure(None, failure=err, log_category="AR500")

        body = json.dumps(res).encode('utf8')

        if "log_category" not in kwargs.keys():
            kwargs["log_category"] = "AR" + str(code)

        self.log.debug(code=code, **kwargs)

        request.setResponseCode(code)
        request.write(body)
        request.finish()

    def _complete_request(self, request, code, body, **kwargs):
        """
        Called when client request is complete.
        """
        if "log_category" not in kwargs.keys():
            kwargs["log_category"] = "AR" + str(code)

        self.log.debug(code=code, **kwargs)
        request.setResponseCode(code)
        request.write(body)

    def _set_common_headers(self, request):
        """
        Set common HTTP response headers.
        """
        origin = request.getHeader(b'origin')
        if origin is None or origin == b'null':
            origin = b'*'

        request.setHeader(b'access-control-allow-origin', origin)
        request.setHeader(b'access-control-allow-credentials', b'true')
        request.setHeader(b'cache-control', b'no-store,no-cache,must-revalidate,max-age=0')
        request.setHeader(b'content-type', b'application/json; charset=UTF-8')

        headers = request.getHeader(b'access-control-request-headers')
        if headers is not None:
            request.setHeader(b'access-control-allow-headers', headers)

    def render(self, request):
        """
        Handle the request. All requests start here.
        """
        self.log.debug(log_category="AR100", method=request.method, path=request.path)
        self._set_common_headers(request)

        try:
            if request.method not in (b"POST", b"PUT", b"OPTIONS"):
                return self._deny_request(request, 405, method=request.method,
                                          allowed="POST, PUT")
            else:

                if request.method == b"OPTIONS":
                    # http://greenbytes.de/tech/webdav/rfc2616.html#rfc.section.14.7
                    request.setHeader(b'allow', b'POST,PUT,OPTIONS')

                    # https://www.w3.org/TR/cors/#access-control-allow-methods-response-header
                    request.setHeader(b'access-control-allow-methods', b'POST,PUT,OPTIONS')

                    request.setResponseCode(200)
                    return b''
                else:
                    return self._render_request(request)
        except Exception as e:
            self.log.failure(log_category="CB501", exc=e)
            return self._deny_request(request, 500, log_category="CB500")

    def _render_request(self, request):
        """
        Receives an HTTP/POST|PUT request, and then calls the Publisher/Caller
        processor.
        """
        # read HTTP/POST|PUT body
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
            # if the client sent a content type, it MUST be one of _ALLOWED_CONTENT_TYPES
            # (but we allow missing content type .. will catch later during JSON
            # parsing anyway)
            if len(content_type_elements) > 0 and \
               content_type_elements[0] not in _ALLOWED_CONTENT_TYPES:
                return self._deny_request(
                    request, 400,
                    accepted=list(_ALLOWED_CONTENT_TYPES),
                    given=content_type_elements[0],
                    log_category="AR452"
                )

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
                return self._deny_request(request, 400, log_category="AR450")

        charset_encoding = encoding_parts.get("charset", "utf-8")

        if charset_encoding not in ["utf-8", 'utf8']:
            return self._deny_request(
                request, 400,
                log_category="AR450")

        # enforce "post_body_limit"
        #
        body_length = len(body)
        content_length_header = headers.getRawHeaders(b"content-length", [])

        if len(content_length_header) == 1:
            content_length = int(content_length_header[0])
        elif len(content_length_header) > 1:
            return self._deny_request(
                request, 400,
                log_category="AR463")
        else:
            content_length = body_length

        if body_length != content_length:
            # Prevent the body length from being different to the given
            # Content-Length. This is so that clients can't lie and bypass
            # length restrictions by giving an incorrect header with a large
            # body.
            return self._deny_request(request, 400, bodylen=body_length,
                                      conlen=content_length,
                                      log_category="AR465")

        if self._post_body_limit and content_length > self._post_body_limit:
            return self._deny_request(
                request, 413,
                length=content_length,
                accepted=self._post_body_limit
            )

        #
        # if we were given a GitHub token, check for a valid signature
        # header
        #

        github_secret = self._options.get("github_secret", "")
        if github_secret:
            if not _confirm_github_signature(request, github_secret, body):
                return self._deny_request(
                    request, 400,
                    log_cagegory="AR467",
                )

        #
        # parse/check HTTP/POST|PUT query parameters
        #

        # key
        #
        if 'key' in args:
            key_str = args["key"]
        else:
            if self._secret:
                return self._deny_request(
                    request, 400,
                    reason=u"'key' field missing",
                    log_category="AR461")

        # timestamp
        #
        if 'timestamp' in args:
            timestamp_str = args["timestamp"]
            try:
                ts = datetime.datetime.strptime(native_string(timestamp_str), "%Y-%m-%dT%H:%M:%S.%fZ")
                delta = abs((ts - datetime.datetime.utcnow()).total_seconds())
                if self._timestamp_delta_limit and delta > self._timestamp_delta_limit:
                    return self._deny_request(
                        request, 400,
                        log_category="AR464")
            except ValueError:
                return self._deny_request(
                    request, 400,
                    reason=u"invalid timestamp '{0}' (must be UTC/ISO-8601, e.g. '2011-10-14T16:59:51.123Z')".format(native_string(timestamp_str)),
                    log_category="AR462")
        else:
            if self._secret:
                return self._deny_request(
                    request, 400, reason=u"signed request required, but mandatory 'timestamp' field missing",
                    log_category="AR461")

        # seq
        #
        if 'seq' in args:
            seq_str = args["seq"]
            try:
                # FIXME: check sequence
                seq = int(seq_str)  # noqa
            except:
                return self._deny_request(
                    request, 400,
                    reason=u"invalid sequence number '{0}' (must be an integer)".format(native_string(seq_str)),
                    log_category="AR462")
        else:
            if self._secret:
                return self._deny_request(
                    request, 400,
                    reason=u"'seq' field missing",
                    log_category="AR461")

        # nonce
        #
        if 'nonce' in args:
            nonce_str = args["nonce"]
            try:
                # FIXME: check nonce
                nonce = int(nonce_str)  # noqa
            except:
                return self._deny_request(
                    request, 400,
                    reason=u"invalid nonce '{0}' (must be an integer)".format(native_string(nonce_str)),
                    log_category="AR462")
        else:
            if self._secret:
                return self._deny_request(
                    request, 400,
                    reason=u"'nonce' field missing",
                    log_category="AR461")

        # signature
        #
        if 'signature' in args:
            signature_str = args["signature"]
        else:
            if self._secret:
                return self._deny_request(
                    request, 400,
                    reason=u"'signature' field missing",
                    log_category="AR461")

        # do more checks if signed requests are required
        #
        if self._secret:

            if key_str != self._key:
                return self._deny_request(
                    request, 401,
                    reason=u"unknown key '{0}' in signed request".format(native_string(key_str)),
                    log_category="AR460")

            # Compute signature: HMAC[SHA256]_{secret} (key | timestamp | seq | nonce | body) => signature
            hm = hmac.new(self._secret, None, hashlib.sha256)
            hm.update(key_str)
            hm.update(timestamp_str)
            hm.update(seq_str)
            hm.update(nonce_str)
            hm.update(body)
            signature_recomputed = base64.urlsafe_b64encode(hm.digest())

            if signature_str != signature_recomputed:
                return self._deny_request(request, 401,
                                          log_category="AR459")
            else:
                self.log.debug("REST request signature valid.",
                               log_category="AR203")

        # user_agent = headers.get("user-agent", "unknown")
        client_ip = request.getClientIP()
        is_secure = request.isSecure()

        # enforce client IP address
        #
        if self._require_ip:
            ip = ip_address(client_ip)
            allowed = False
            for net in self._require_ip:
                if ip in net:
                    allowed = True
                    break
            if not allowed:
                return self._deny_request(request, 400, log_category="AR466")

        # enforce TLS
        #
        if self._require_tls:
            if not is_secure:
                return self._deny_request(request, 400,
                                          reason=u"request denied because not using TLS")

        # authenticate request
        #

        # TODO: also support HTTP Basic AUTH for ticket

        def on_auth_ok(value):
            if value is True:
                # treat like original behavior and just accept the request_id
                pass
            elif isinstance(value, types.Accept):
                self._session._authid = value.authid
                self._session._authrole = value.authrole
                # realm?
            else:
                # FIXME: not returning deny request... probably not ideal
                request.write(self._deny_request(request, 401, reason=u"not authorized", log_category="AR401"))
                request.finish()
                return

            _validator.reset()
            validation_result = _validator.validate(body)

            # validate() returns a 4-tuple, of which item 0 is whether it
            # is valid
            if not validation_result[0]:
                request.write(self._deny_request(
                    request, 400,
                    log_category="AR451"))
                request.finish()
                return

            event = body.decode('utf8')

            if self.decode_as_json:
                try:
                    event = json.loads(event)
                except Exception as e:
                    request.write(self._deny_request(
                        request, 400,
                        exc=e, log_category="AR453"))
                    request.finish()
                    return

                if not isinstance(event, dict):
                    request.write(self._deny_request(
                        request, 400,
                        log_category="AR454"))
                    request.finish()
                    return

            d = maybeDeferred(self._process, request, event)

            def finish(value):
                if isinstance(value, bytes):
                    request.write(value)
                request.finish()

            d.addCallback(finish)

        def on_auth_error(err):
            # XXX: is it ideal to write to the request?
            request.write(self._deny_request(request, 401, reason=u"not authorized", log_category="AR401"))

            request.finish()
            return

        authmethod = None
        authid = None
        signature = None

        authorization_header = headers.getRawHeaders(b"authorization", [])
        if len(authorization_header) == 1:
            # HTTP Basic Authorization will be processed as ticket authentication
            authorization = authorization_header[0]
            auth_scheme, auth_details = authorization.split(b" ", 1)

            if auth_scheme.lower() == b"basic":
                try:
                    credentials = binascii.a2b_base64(auth_details + b'===')
                    credentials = credentials.split(b":", 1)
                    if len(credentials) == 2:
                        authmethod = "ticket"
                        authid = credentials[0].decode("utf-8")
                        signature = credentials[1].decode("utf-8")
                    else:
                        return self._deny_request(request, 401, reason=u"not authorized", log_category="AR401")
                except binascii.Error:
                    # authentication failed
                    return self._deny_request(request, 401, reason=u"not authorized", log_category="AR401")
        elif 'authmethod' in args and args['authmethod'].decode("utf-8") == 'ticket':
            if "ticket" not in args or "authid" not in args:
                # AR401 - fail if the ticket or authid are not in the args
                on_auth_ok(False)
            else:
                authmethod = "ticket"
                authid = args['authid'].decode("utf-8")
                signature = args['ticket'].decode("utf-8")

        if authmethod and authid and signature:

            hdetails = types.HelloDetails(
                authid=authid,
                authmethods=[authmethod]
            )

            # wire up some variables for the authenticators to work, this is hackish

            # a custom header based authentication scheme can be implemented
            # without adding alternate authenticators by forwarding all headers.
            self._session._transport._transport_info = {
                "http_headers_received": {
                    native_string(x).lower(): native_string(y[0]) for x, y in request.requestHeaders.getAllRawHeaders()
                }
            }

            self._session._pending_session_id = None
            self._session._router_factory = self._session._transport._routerFactory

            if authmethod == "ticket":
                self._pending_auth = PendingAuthTicket(self._session, self._auth_config['ticket'])
                self._pending_auth.hello(self._session._realm, hdetails)

            auth_d = maybeDeferred(self._pending_auth.authenticate, signature)
            auth_d.addCallbacks(on_auth_ok, on_auth_error)

        else:
            # don't return the value or it will be written to the request
            on_auth_ok(True)

        return server.NOT_DONE_YET

    def _process(self, request, event):
        raise NotImplementedError()
