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

from collections import namedtuple

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet import reactor

from crossbar.adapter.rest import RESTCallee

from autobahn.wamp.types import ComponentConfig

from autobahn.twisted.util import sleep

from autobahn.wamp import message
from autobahn.wamp import serializer
from autobahn.wamp import role
from autobahn import util
from autobahn.wamp.exception import ApplicationError, NotAuthorized, InvalidUri, ProtocolError
from autobahn.wamp import types

MockResponse = namedtuple("MockResponse", ["code", "headers"])


class MockTransport(object):

    def __init__(self, handler):
        self._log = False
        self._handler = handler
        self._serializer = serializer.JsonSerializer()
        self._registrations = {}
        self._invocations = {}
        #: str -> ID
        self._subscription_topics = {}

        self._handler.onOpen(self)

        self._my_session_id = util.id()

        roles = {u'broker': role.RoleBrokerFeatures(), u'dealer': role.RoleDealerFeatures()}

        msg = message.Welcome(self._my_session_id, roles)
        self._handler.onMessage(msg)

    def send(self, msg):
        if self._log:
            payload, isbinary = self._serializer.serialize(msg)
            print("Send: {0}".format(payload))

        reply = None

        if isinstance(msg, message.Publish):
            if msg.topic.startswith(u'com.myapp'):
                if msg.acknowledge:
                    reply = message.Published(msg.request, util.id())
            elif len(msg.topic) == 0:
                reply = message.Error(message.Publish.MESSAGE_TYPE, msg.request, u'wamp.error.invalid_uri')
            else:
                reply = message.Error(message.Publish.MESSAGE_TYPE, msg.request, u'wamp.error.not_authorized')

        elif isinstance(msg, message.Call):

            if msg.procedure in self._registrations:
                registration = self._registrations[msg.procedure]
                request = util.id()
                self._invocations[request] = msg.request
                reply = message.Invocation(request, registration, args=msg.args, kwargs=msg.kwargs)
            else:
                reply = message.Error(message.Call.MESSAGE_TYPE, msg.request, u'wamp.error.no_such_procedure')

        elif isinstance(msg, message.Yield):
            if msg.request in self._invocations:
                request = self._invocations[msg.request]
                reply = message.Result(request, args=msg.args, kwargs=msg.kwargs)

        elif isinstance(msg, message.Subscribe):
            topic = msg.topic
            if topic in self._subscription_topics:
                reply_id = self._subscription_topics[topic]
            else:
                reply_id = util.id()
                self._subscription_topics[topic] = reply_id
            reply = message.Subscribed(msg.request, reply_id)

        elif isinstance(msg, message.Unsubscribe):
            reply = message.Unsubscribed(msg.request)

        elif isinstance(msg, message.Register):
            registration = util.id()
            self._registrations[msg.procedure] = registration
            reply = message.Registered(msg.request, registration)

        elif isinstance(msg, message.Unregister):
            reply = message.Unregistered(msg.request)

        if reply:
            if self._log:
                payload, isbinary = self._serializer.serialize(reply)
                print("Receive: {0}".format(payload))
            self._handler.onMessage(reply)

    def isOpen(self):
        return True

    def close(self):
        pass

    def abort(self):
        pass


class MockHeaders(object):

    def getAllRawHeaders(self):
        return {"foo": ["bar"]}


class MockWebTransport(object):

    def __init__(self, testCase):
        self.testCase = testCase
        self._code = None
        self._content = None

    def _addResponse(self, code, content):
        self._code = code
        self._content = content

    def request(self, *args, **kwargs):
        self.request = {"args": args, "kwargs": kwargs}
        resp = MockResponse(headers=MockHeaders(),
                            code=self._code)
        d = Deferred()
        reactor.callLater(0.0, d.callback, resp)
        return d

    def text_content(self, res):
        self.testCase.assertEqual(res.code, self._code)
        d = Deferred()
        reactor.callLater(0.0, d.callback, self._content)
        return d


class CalleeTestCase(TestCase):

    @inlineCallbacks
    def test_basic_web(self):

        config = ComponentConfig(realm="realm1",
                                 extra={"baseurl": "https://foo.com/",
                                        "procedure": "io.crossbar.testrest"})

        m = MockWebTransport(self)
        m._addResponse(200, "whee")

        c = RESTCallee(config=config, webTransport=m)
        MockTransport(c)

        res = yield c.call(u"io.crossbar.testrest", method="GET", url="baz.html")

        self.assertEqual(res,
                         {"content": "whee",
                          "code": 200,
                          "headers": {"foo": ["bar"]}})
