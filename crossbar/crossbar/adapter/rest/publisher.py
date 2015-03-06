import json
import six

from twisted.python import log
from twisted.web import server

from autobahn.wamp.types import PublishOptions

from .common import _CommonResource


class PusherResource(_CommonResource):

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
            if self._debug:
                log.msg("PusherResource - request succeeded with result {0}".format(res))
            body = json.dumps(res, separators=(',', ':'))
            if six.PY3:
                body = body.encode('utf8')

            request.setHeader('content-type', 'application/json; charset=UTF-8')
            request.setHeader('cache-control', 'no-store, no-cache, must-revalidate, max-age=0')
            request.setResponseCode(202)
            request.write(body)
            request.finish()

        def on_publish_error(err):
            emsg = "PusherResource - request failed with error {0}\n".format(err.value)
            if self._debug:
                log.msg(emsg)
            request.setResponseCode(400)
            request.write(emsg)
            request.finish()

        d.addCallbacks(on_publish_ok, on_publish_error)

        return server.NOT_DONE_YET
