#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.wamp.types import ComponentConfig
from twisted.internet.defer import inlineCallbacks
from twisted.web.http_headers import Headers

from crossbar.bridge.rest import RESTCallee
from crossbar.bridge.rest.test import MockTransport, MockWebTransport
from crossbar.test import TestCase


class CalleeTestCase(TestCase):
    @inlineCallbacks
    def test_basic_web(self):
        """
        Plain request, no params.
        """
        config = ComponentConfig(
            realm="realm1", extra={"baseurl": "https://foo.com/", "procedure": "io.crossbar.testrest"}
        )

        m = MockWebTransport(self)
        m._addResponse(200, "whee")

        c = RESTCallee(config=config, webTransport=m)
        MockTransport(c)

        res = yield c.call("io.crossbar.testrest", method="GET", url="baz.html")

        self.assertEqual(m.maderequest["args"], ("GET", "https://foo.com/baz.html"))
        self.assertEqual(m.maderequest["kwargs"], {"data": b"", "headers": Headers({}), "params": {}})
        self.assertEqual(res, {"content": "whee", "code": 200, "headers": {"foo": ["bar"]}})

    @inlineCallbacks
    def test_slightlymorecomplex_web(self):
        """
        Giving headers, params, a body.
        """
        config = ComponentConfig(
            realm="realm1", extra={"baseurl": "https://foo.com/", "procedure": "io.crossbar.testrest"}
        )

        m = MockWebTransport(self)
        m._addResponse(220, "whee!")

        c = RESTCallee(config=config, webTransport=m)
        MockTransport(c)

        res = yield c.call(
            "io.crossbar.testrest",
            method="POST",
            url="baz.html",
            params={"spam": "ham"},
            body="see params",
            headers={"X-Something": ["baz"]},
        )

        self.assertEqual(m.maderequest["args"], ("POST", "https://foo.com/baz.html"))
        self.assertEqual(
            m.maderequest["kwargs"],
            {"data": b"see params", "headers": Headers({b"X-Something": [b"baz"]}), "params": {b"spam": b"ham"}},
        )
        self.assertEqual(res, {"content": "whee!", "code": 220, "headers": {"foo": ["bar"]}})
