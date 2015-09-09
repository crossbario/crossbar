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

from twisted.web import server

from autobahn.wamp.types import CallResult
from autobahn.wamp.exception import ApplicationError

from crossbar.adapter.rest.common import _CommonResource

__all__ = ('CallerResource',)


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

        args = event['args'] if 'args' in event and event['args'] else []
        kwargs = event['kwargs'] if 'kwargs' in event and event['kwargs'] else {}

        d = self._session.call(procedure, *args, **kwargs)

        def return_call_result(res):
            body = json.dumps(res, separators=(',', ':'), ensure_ascii=False).encode('utf8')
            request.setHeader(b'content-type', b'application/json; charset=UTF-8')
            request.setHeader(b'cache-control', b'no-store, no-cache, must-revalidate, max-age=0')
            request.setResponseCode(200)
            request.write(body)
            request.finish()

        def on_call_ok(value):
            # a WAMP procedure call result may have a single return value, but also
            # multiple, positional return values as well as keyword-based return values
            #
            if isinstance(value, CallResult):
                res = {}
                if value.results:
                    res['args'] = value.results
                if value.kwresults:
                    res['kwargs'] = value.kwresults
            else:
                res = {'args': [value]}

            self.log.debug("WAMP call succeeded with result {res}",
                           res=res)

            return_call_result(res)

        def on_call_error(err):
            # a WAMP procedure call returning with error should be forwarded
            # to the HTTP-requestor still successfully
            #
            res = {}
            if isinstance(err.value, ApplicationError):
                res['error'] = err.value.error
                if err.value.args:
                    res['args'] = err.value.args
                if err.value.kwargs:
                    res['kwargs'] = err.value.kwargs
            else:
                res['error'] = u'wamp.error.runtime_error'
                res['args'] = ["{}".format(err)]

            self.log.debug("WAMP call failed with error {err}", err=res)

            return_call_result(res)

        d.addCallbacks(on_call_ok, on_call_error)

        return server.NOT_DONE_YET
