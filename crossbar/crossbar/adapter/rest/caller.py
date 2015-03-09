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
