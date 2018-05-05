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

from __future__ import absolute_import

from twisted.internet.defer import inlineCallbacks

from crossbar.test import TestCase
from crossbar._logging import LogCapturer
from crossbar.bridge.rest import WebhookResource
from crossbar.bridge.rest.test import MockPublisherSession, renderResource


class WebhookTestCase(TestCase):
    """
    Unit tests for L{WebhookResource}.
    """
    @inlineCallbacks
    def test_basic(self):
        """
        A message, when a request has gone through to it, publishes a WAMP
        message on the configured topic.
        """
        session = MockPublisherSession(self)
        resource = WebhookResource({u"topic": u"com.test.webhook"}, session)

        with LogCapturer() as l:
            request = yield renderResource(
                resource, b"/",
                method=b"POST",
                headers={b"Content-Type": []},
                body=b'{"foo": "has happened"}')

        self.assertEqual(len(session._published_messages), 1)
        self.assertEqual(
            {
                u"body": u'{"foo": "has happened"}',
                u"headers": {
                    u"Content-Type": [],
                    u'Date': [u'Sun, 1 Jan 2013 15:21:01 GMT'],
                    u'Host': [u'localhost:8000']
                }
            },
            session._published_messages[0]["args"][0])

        self.assertEqual(request.code, 202)
        self.assertEqual(request.get_written_data(), b"OK")

        logs = l.get_category("AR201")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["code"], 202)
