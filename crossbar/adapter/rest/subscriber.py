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

import treq
import json

from functools import partial

from twisted.python import log
from twisted.internet.defer import inlineCallbacks
from twisted.web.http_headers import Headers

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import SubscribeOptions


class MessageForwarder(ApplicationSession):

    def __init__(self, *args, **kwargs):
        self._webtransport = kwargs.pop("webTransport", treq)
        super(MessageForwarder, self).__init__(*args, **kwargs)

    @inlineCallbacks
    def onJoin(self, details):

        subscriptions = self.config.extra["subscriptions"]

        debug = self.config.extra.get("debug", False)
        method = self.config.extra.get("method", u"POST").encode("utf8")
        expectedCode = self.config.extra.get("expectedcode")

        @inlineCallbacks
        def on_event(url, *args, **kwargs):

            headers = Headers({
                "Content-Type": ["application/json"]
            })

            body = json.dumps({"args": args, "kwargs": kwargs},
                              sort_keys=True, separators=(',', ':'))
            res = yield self._webtransport.request(
                method, url.encode("utf8"),
                data=body,
                headers=headers
            )

            if expectedCode:
                if not res.code == expectedCode:
                    raise ApplicationError(
                        "Request returned {}, not the expected {}".format(res.code, expectedCode))

            if debug:
                content = yield self._webtransport.text_content(res)
                log.msg(content)

        for s in subscriptions:
            # Assert that there's "topic" and "url" entries
            assert "topic" in s
            assert "url" in s

            yield self.subscribe(
                partial(on_event, s["url"]),
                s["topic"],
                options=SubscribeOptions(match=s.get("match", u"exact"))
            )

            if debug:
                log.msg("MessageForwarder subscribed to {}".format(s["topic"]))
