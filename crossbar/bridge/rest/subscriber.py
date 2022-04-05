#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import json

from functools import partial

from twisted.internet.defer import inlineCallbacks
from twisted.web.http_headers import Headers

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import SubscribeOptions

from txaio import make_logger


class MessageForwarder(ApplicationSession):

    log = make_logger()

    def __init__(self, *args, **kwargs):
        self._webtransport = kwargs.pop("webTransport", None)

        if not self._webtransport:
            import treq
            self._webtransport = treq

        super(MessageForwarder, self).__init__(*args, **kwargs)

    @inlineCallbacks
    def onJoin(self, details):

        subscriptions = self.config.extra["subscriptions"]

        debug = self.config.extra.get("debug", False)
        method = self.config.extra.get("method", "POST")
        expectedCode = self.config.extra.get("expectedcode")

        @inlineCallbacks
        def on_event(url, *args, **kwargs):

            headers = Headers({b"Content-Type": [b"application/json"]})

            body = json.dumps({
                "args": args,
                "kwargs": kwargs
            },
                              sort_keys=False,
                              separators=(',', ':'),
                              ensure_ascii=False)

            # http://treq.readthedocs.org/en/latest/api.html#treq.request
            res = yield self._webtransport.request(method,
                                                   url.encode('utf8'),
                                                   data=body.encode('utf8'),
                                                   headers=headers)

            if expectedCode:
                if not res.code == expectedCode:
                    raise ApplicationError("Request returned {}, not the expected {}".format(res.code, expectedCode))

            if debug:
                content = yield self._webtransport.text_content(res)
                self.log.debug(content)

        for s in subscriptions:
            # Assert that there's "topic" and "url" entries
            assert "topic" in s
            assert "url" in s

            yield self.subscribe(partial(on_event, s["url"]),
                                 s["topic"],
                                 options=SubscribeOptions(match=s.get("match", "exact")))

            self.log.debug("MessageForwarder subscribed to {topic}", topic=s["topic"])
