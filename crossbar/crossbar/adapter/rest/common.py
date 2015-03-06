import datetime
import json
import hmac
import hashlib
import base64

from netaddr.ip import IPAddress, IPNetwork

from twisted.python import log
from twisted.web.resource import Resource


class _CommonResource(Resource):

    """
    A HTTP/POST to WAMP PubSub bridge.

    Config:

       "transports": [
          {
             "type": "web",
             "endpoint": {
                "type": "tcp",
                "port": 8080
             },
             "paths": {
                "/": {
                   "type": "static",
                   "directory": ".."
                },
                "ws": {
                   "type": "websocket"
                },
                "push": {
                   "type": "pusher",
                   "realm": "realm1",
                   "role": "anonymous",
                   "options": {
                      "key": "foobar",
                      "secret": "secret",
                      "post_body_limit": 8192,
                      "timestamp_delta_limit": 10,
                      "require_ip": ["192.168.1.1/255.255.255.0", "127.0.0.1"],
                      "require_tls": false
                   }
                }
             }
          }
       ]

    Test:

       curl -H "Content-Type: application/json" -d '{"topic": "com.myapp.topic1", "args": ["Hello, world"]}' http://127.0.0.1:8080/push
    """

    isLeaf = True

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

        self._debug = options.get('debug', False)

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

    def _deny_request(self, request, code, reason):
        """
        Called when client request is denied.
        """
        if self._debug:
            log.msg("PusherResource [request denied] - {0} / {1}".format(code, reason))
        request.setResponseCode(code)
        return "{}\n".format(reason)

    def render(self, request):
        if self._debug:
            log.msg("PusherResource [render]", request.method, request.path, request.args)

        if request.method != "POST":
            return self._deny_request(request, 405, "HTTP/{0} not allowed".format(request.method))
        else:
            return self.render_POST(request)

    def render_POST(self, request):
        """
        Receives an HTTP/POST request to forward a WAMP event.
        """
        try:
            # path = request.path
            args = request.args
            headers = request.getAllHeaders()

            # check content type
            #
            if headers.get("content-type", None) != 'application/json':
                return self._deny_request(request, 400, "bad or missing content type ('{0}')".format(headers.get("content-type", None)))

            # enforce "post_body_limit"
            #
            content_length = int(headers.get("content-length", 0))
            if self._post_body_limit and content_length > self._post_body_limit:
                return self._deny_request(request, 400, "HTTP/POST body length ({0}) exceeds maximum ({1})".format(content_length, self._post_body_limit))

            #
            # parse/check HTTP/POST query parameters
            #

            # key
            #
            if 'key' in args:
                key_str = args["key"][0]
            else:
                if self._secret:
                    return self._deny_request(request, 400, "signed request required, but mandatory 'key' field missing")

            # timestamp
            #
            if 'timestamp' in args:
                timestamp_str = args["timestamp"][0]
                try:
                    ts = datetime.datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                    delta = abs((ts - datetime.datetime.utcnow()).total_seconds())
                    if self._timestamp_delta_limit and delta > self._timestamp_delta_limit:
                        return self._deny_request(request, 400, "request expired (delta {0} seconds)".format(delta))
                except:
                    return self._deny_request(request, 400, "invalid timestamp '{0}' (must be UTC/ISO-8601, e.g. '2011-10-14T16:59:51.123Z')".format(timestamp_str))
            else:
                if self._secret:
                    return self._deny_request(request, 400, "signed request required, but mandatory 'timestamp' field missing")

            # seq
            #
            if 'seq' in args:
                seq_str = args["seq"][0]
                try:
                    # FIXME: check sequence
                    seq = int(seq_str)  # noqa
                except:
                    return self._deny_request(request, 400, "invalid sequence number '{0}' (must be an integer)".format(seq_str))
            else:
                if self._secret:
                    return self._deny_request(request, 400, "signed request required, but mandatory 'seq' field missing")

            # nonce
            #
            if 'nonce' in args:
                nonce_str = args["nonce"][0]
                try:
                    # FIXME: check nonce
                    nonce = int(nonce_str)  # noqa
                except:
                    return self._deny_request(request, 400, "invalid nonce '{0}' (must be an integer)".format(nonce_str))
            else:
                if self._secret:
                    return self._deny_request(request, 400, "signed request required, but mandatory 'nonce' field missing")

            # signature
            #
            if 'signature' in args:
                signature_str = args["signature"][0]
            else:
                if self._secret:
                    return self._deny_request(request, 400, "signed request required, but mandatory 'signature' field missing")

            # read HTTP/POST body
            #
            body = request.content.read()

            # do more checks if signed requests are required
            #
            if self._secret:

                if key_str != self._key:
                    return self._deny_request(request, 400, "unknown key '{0}' in signed request".format(key_str))

                # Compute signature: HMAC[SHA256]_{secret} (key | timestamp | seq | nonce | body) => signature
                hm = hmac.new(self._secret, None, hashlib.sha256)
                hm.update(key_str)
                hm.update(timestamp_str)
                hm.update(seq_str)
                hm.update(nonce_str)
                hm.update(body)
                signature_recomputed = base64.urlsafe_b64encode(hm.digest())

                if signature_str != signature_recomputed:
                    return self._deny_request(request, 401, "invalid request signature")
                else:
                    if self._debug:
                        log.msg("PusherResource - ok, request signature valid.")

            # user_agent = headers.get("user-agent", "unknown")
            client_ip = request.getClientIP()
            is_secure = request.isSecure()

            # enforce client IP address
            #
            if self._require_ip:
                ip = IPAddress(client_ip)
                allowed = False
                for net in self._require_ip:
                    if ip in net:
                        allowed = True
                        break
                if not allowed:
                    return self._deny_request(request, 400, "request denied based on IP address")

            # enforce TLS
            #
            if self._require_tls:
                if not is_secure:
                    return self._deny_request(request, 400, "request denied because not using TLS")

            # FIXME: authorize request
            authorized = True

            if authorized:

                try:
                    event = json.loads(body)
                except Exception as e:
                    return self._deny_request(request, 400, "invalid request event - HTTP/POST body must be valid JSON: {0}".format(e))

                if not isinstance(event, dict):
                    return self._deny_request(request, 400, "invalid request event - HTTP/POST body must be JSON dict")

                return self._process(request, event)

            else:
                return self._deny_request(request, 401, "not authorized")

        except Exception as e:
            # catch all .. should not happen (usually)
            return self._deny_request(request, 500, "internal server error ('{0}')".format(e))
