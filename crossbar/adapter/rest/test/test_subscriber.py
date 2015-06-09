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

from six import PY3

from twisted.trial.unittest import TestCase
from twisted.web.http_headers import Headers
from twisted.internet.defer import inlineCallbacks

from autobahn.wamp.types import ComponentConfig, PublishOptions

from crossbar.adapter.rest.test import MockTransport, MockWebTransport
if not PY3:
    from crossbar.adapter.rest import MessageForwarder


class MessageForwarderTestCase(TestCase):

    if PY3:
        skip = "Not ported to Py3"

    @inlineCallbacks
    def test_basic_web(self):
        """
        Plain request, no params.
        """
        config = ComponentConfig(realm="realm1",
                                 extra={"subscriptions": [
                                     {"url": "https://foo.com/msg",
                                      "topic": "io.crossbar.forward1"}
                                 ]})

        m = MockWebTransport(self)
        m._addResponse(200, "whee")

        c = MessageForwarder(config=config, webTransport=m)
        MockTransport(c)

        res = yield c.publish(u"io.crossbar.forward1", "hi",
                              options=PublishOptions(acknowledge=True))

        self.assertNotEqual(res.id, None)
        self.assertEqual(m.maderequest["args"], ("POST", "https://foo.com/msg"))
        self.assertEqual(m.maderequest["kwargs"], {
            "data": '{"args":["hi"],"kwargs":{}}',
            "headers": Headers({"Content-Type": ["application/json"]})
        })
