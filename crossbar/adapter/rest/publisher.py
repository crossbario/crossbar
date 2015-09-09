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

from autobahn.wamp.types import PublishOptions

from crossbar.adapter.rest.common import _CommonResource

__all__ = ('PublisherResource',)


class PublisherResource(_CommonResource):
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
                "publish": {
                   "type": "publisher",
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

    Test publishing to a topic `com.myapp.topic1`:

       curl -H "Content-Type: application/json" -d '{"topic": "com.myapp.topic1", "args": ["Hello, world"]}' http://127.0.0.1:8080/publish
    """

    def _process(self, request, event):

        if 'topic' not in event:
            return self._deny_request(request, 400, "invalid request event - missing 'topic' in HTTP/POST body")

        topic = event.pop('topic')

        args = event.pop('args', [])
        kwargs = event.pop('kwargs', {})
        options = event.pop('options', {})

        publish_options = PublishOptions(acknowledge=True,
                                         exclude=options.get('exclude', None),
                                         eligible=options.get('eligible', None))

        kwargs['options'] = publish_options

        # http://twistedmatrix.com/documents/current/web/howto/web-in-60/asynchronous-deferred.html

        d = self._session.publish(topic, *args, **kwargs)

        def on_publish_ok(pub):
            res = {'id': pub.id}
            self.log.debug("request succeeded with result {res}", res=res)
            body = json.dumps(res, separators=(',', ':'), ensure_ascii=False).encode('utf8')
            request.setHeader(b'content-type', b'application/json; charset=UTF-8')
            request.setHeader(b'cache-control', b'no-store, no-cache, must-revalidate, max-age=0')
            request.setResponseCode(202)
            request.write(body)
            request.finish()

        def on_publish_error(err):
            emsg = "PublisherResource - request failed with error {0}\n".format(err.value)
            self.log.debug(emsg)
            request.setResponseCode(400)
            request.write(emsg)
            request.finish()

        d.addCallbacks(on_publish_ok, on_publish_error)

        return server.NOT_DONE_YET
