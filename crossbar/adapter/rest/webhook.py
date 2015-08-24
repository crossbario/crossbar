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

from twisted.web.server import NOT_DONE_YET

from autobahn.wamp.types import PublishOptions

from crossbar._compat import native_string
from crossbar.adapter.rest.common import _CommonResource

__all__ = ('WebhookResource',)


class WebhookResource(_CommonResource):
    """
    A HTTP -> WAMP pubsub bridge.

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
                "webhook": {
                   "type": "webhook",
                   "realm": "realm1",
                   "role": "anonymous",
                   "options": {
                      "topic": "com.example.webhook"
                   }
                }
             }
          }
       ]

    """
    decode_as_json = False

    def _process(self, request, event):

        # The topic we're going to send to
        topic = self._options["topic"]

        message = {}
        message["headers"] = {
            native_string(x): [native_string(z) for z in y]
            for x, y in request.requestHeaders.getAllRawHeaders()}
        message["body"] = event

        publish_options = PublishOptions(acknowledge=True)

        def _succ(result):
            self.log.info("Successfully sent webhook from {ip} to {topic}",
                          topic=topic, ip=request.getClientIP())
            request.setResponseCode(202)
            request.write(b"OK")
            request.finish()

        def _err(result):
            self.log.error("Unable to send webhook from {ip} to {topic}",
                           topic=topic, ip=request.getClientIP(),
                           log_failure=result)
            request.setResponseCode(500)
            request.write(b"NOT OK")

        d = self._session.publish(topic,
                                  json.loads(json.dumps(message)),
                                  options=publish_options)
        d.addCallback(_succ)
        d.addErrback(_err)

        return NOT_DONE_YET
