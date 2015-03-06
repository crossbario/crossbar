import json
import six

from twisted.python import log
from twisted.web import server

from .common import _CommonResource


class CallerResource(_CommonResource):

    """
    A HTTP/POST to WAMP procedure bridge.

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
                "call": {
                   "type": "caller",
                   "realm": "realm1",
                   "role": "anonymous",
                   "options": {
                      "post_body_limit": 8192,
                      "timestamp_delta_limit": 10,
                      "require_ip": ["192.168.1.1/255.255.255.0", "127.0.0.1"],
                      "require_tls": false
                   }
                }
             }
          }
       ]

    Test calling a procedure named `com.example.add2`:

       curl -H "Content-Type: application/json" -d '{"procedure": "com.example.add2", "args": [1,2]}' http://127.0.0.1:8080/call
    """

    def _process(self, request, event):

        if 'procedure' not in event:
            return self._deny_request(request, 400, "invalid request event - missing 'procedure' in HTTP/POST body")

        procedure = event.pop('procedure')

        args = event.pop('args', [])
        kwargs = event.pop('kwargs', {})

        d = self._session.call(procedure, *args, **kwargs)

        def on_call_ok(res):
            res = {'response': res}
            if self._debug:
                log.msg("CallerResource - request succeeded with result {0}".format(res))
            body = json.dumps(res, separators=(',', ':'))
            if six.PY3:
                body = body.encode('utf8')

            request.setHeader('content-type', 'application/json; charset=UTF-8')
            request.setHeader('cache-control', 'no-store, no-cache, must-revalidate, max-age=0')
            request.setResponseCode(200)
            request.write(body)
            request.finish()

        def on_call_error(err):
            emsg = "CallerResource - request failed with error {0}\n".format(err.value)
            if self._debug:
                log.msg(emsg)
            request.setResponseCode(400)
            request.write(emsg)
            request.finish()

        d.addCallbacks(on_call_ok, on_call_error)

        return server.NOT_DONE_YET
