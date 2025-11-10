#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.wamp.types import ComponentConfig, PublishOptions
from twisted.internet.defer import inlineCallbacks
from twisted.web.http_headers import Headers

from crossbar.bridge.rest import MessageForwarder
from crossbar.bridge.rest.test import MockTransport, MockWebTransport
from crossbar.test import TestCase


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
        self.assertEqual(
            m.maderequest["kwargs"],
            {"data": b'{"args":["hi"],"kwargs":{}}', "headers": Headers({b"Content-Type": [b"application/json"]})},
        )
