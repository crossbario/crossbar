#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.web.http_headers import Headers
from twisted.internet.defer import inlineCallbacks

from autobahn.wamp.types import ComponentConfig, PublishOptions

from crossbar.test import TestCase
from crossbar.bridge.rest.test import MockTransport, MockWebTransport
from crossbar.bridge.rest import MessageForwarder


class MessageForwarderTestCase(TestCase):
    @inlineCallbacks
    def test_basic_web(self):
        """
        Plain request, no params.
        """
        extra = {"subscriptions": [{"url": "https://foo.com/msg", "topic": "io.crossbar.forward1"}]}
        config = ComponentConfig(realm="realm1", extra=extra)

        m = MockWebTransport(self)
        m._addResponse(200, "whee")

        c = MessageForwarder(config=config, webTransport=m)
        MockTransport(c)

        res = yield c.publish("io.crossbar.forward1", "hi", options=PublishOptions(acknowledge=True))

        self.assertNotEqual(res.id, None)
        self.assertEqual(m.maderequest["args"], ("POST", b"https://foo.com/msg"))
        self.assertEqual(m.maderequest["kwargs"], {
            "data": b'{"args":["hi"],"kwargs":{}}',
            "headers": Headers({b"Content-Type": [b"application/json"]})
        })
