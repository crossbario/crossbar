#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
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

from twisted.web.http_headers import Headers
from twisted.internet.defer import inlineCallbacks

from crossbar.test import TestCase
from crossbar.bridge.rest.test import MockTransport, MockWebTransport
from crossbar.bridge.rest import RESTCallee

from autobahn.wamp.types import ComponentConfig


class CalleeTestCase(TestCase):

    @inlineCallbacks
    def test_basic_web(self):
        """
        Plain request, no params.
        """
        config = ComponentConfig(realm="realm1",
                                 extra={"baseurl": "https://foo.com/",
                                        "procedure": "io.crossbar.testrest"})

        m = MockWebTransport(self)
        m._addResponse(200, "whee")

        c = RESTCallee(config=config, webTransport=m)
        MockTransport(c)

        res = yield c.call("io.crossbar.testrest", method="GET", url="baz.html")

        self.assertEqual(m.maderequest["args"], ("GET", "https://foo.com/baz.html"))
        self.assertEqual(m.maderequest["kwargs"], {
            "data": b"",
            "headers": Headers({}),
            "params": {}
        })
        self.assertEqual(res,
                         {"content": "whee",
                          "code": 200,
                          "headers": {"foo": ["bar"]}})

    @inlineCallbacks
    def test_slightlymorecomplex_web(self):
        """
        Giving headers, params, a body.
        """
        config = ComponentConfig(realm="realm1",
                                 extra={"baseurl": "https://foo.com/",
                                        "procedure": "io.crossbar.testrest"})

        m = MockWebTransport(self)
        m._addResponse(220, "whee!")

        c = RESTCallee(config=config, webTransport=m)
        MockTransport(c)

        res = yield c.call("io.crossbar.testrest", method="POST",
                           url="baz.html", params={"spam": "ham"},
                           body="see params", headers={"X-Something": ["baz"]})

        self.assertEqual(m.maderequest["args"], ("POST", "https://foo.com/baz.html"))
        self.assertEqual(m.maderequest["kwargs"], {
            "data": b"see params",
            "headers": Headers({b"X-Something": [b"baz"]}),
            "params": {b"spam": b"ham"}
        })
        self.assertEqual(res,
                         {"content": "whee!",
                          "code": 220,
                          "headers": {"foo": ["bar"]}})
