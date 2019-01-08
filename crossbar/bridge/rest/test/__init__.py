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

from __future__ import absolute_import, print_function

import hmac
import hashlib
import random
import base64

from collections import namedtuple

from ._request import request

from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred, Deferred
from twisted.web.test._util import _render

from autobahn.wamp import message
from autobahn.wamp import serializer
from autobahn.wamp import role
from autobahn import util

publishedMessage = namedtuple("pub", ["id"])


class MockPublisherSession(object):
    """
    A mock WAMP session.
    """
    def __init__(self, testCase):
        self._published_messages = []

        def publish(topic, *args, **kwargs):
            messageID = random.randint(0, 100000)

            self._published_messages.append({
                "id": messageID,
                "topic": topic,
                "args": args,
                "kwargs": kwargs
            })

            return publishedMessage(id=messageID)

        def _publish(topic, *args, **kwargs):
            return maybeDeferred(publish, topic, *args, **kwargs)

        setattr(self, "publish", _publish)


def makeSignedArguments(params, signKey, signSecret, body):

    params[b'timestamp'] = [util.utcnow().encode()]
    params[b'seq'] = [b"1"]
    params[b'key'] = [signKey.encode()]
    params[b'nonce'] = [str(random.randint(0, 9007199254740992)).encode()]

    # HMAC[SHA256]_{secret} (key | timestamp | seq | nonce | body) => signature

    hm = hmac.new(signSecret.encode('utf8'), None, hashlib.sha256)
    hm.update(params[b'key'][0])
    hm.update(params[b'timestamp'][0])
    hm.update(params[b'seq'][0])
    hm.update(params[b'nonce'][0])
    hm.update(body)
    signature = base64.urlsafe_b64encode(hm.digest())
    params[b'signature'] = [signature]

    return params


def renderResource(resource, path, params=None, method=b"GET", body=b"", isSecure=False,
                   headers=None, sign=False, signKey=None, signSecret=None):

    params = {} if params is None else params
    headers = {} if params is None else headers

    def _cb(result, request):
        return request

    if sign:
        params = makeSignedArguments(params, signKey, signSecret, body)

    req = request(path, args=params, method=method, isSecure=isSecure,
                  headers=headers, body=body)

    d = _render(resource, req)
    d.addCallback(_cb, req)
    return d


MockResponse = namedtuple("MockResponse", ["code", "headers"])


class MockHeaders(object):

    def getAllRawHeaders(self):
        return {b"foo": [b"bar"]}


class MockWebTransport(object):

    def __init__(self, testCase):
        self.testCase = testCase
        self._code = None
        self._content = None
        self.maderequest = None

    def _addResponse(self, code, content):
        self._code = code
        self._content = content

    def request(self, *args, **kwargs):
        self.maderequest = {"args": args, "kwargs": kwargs}
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


class MockTransport(object):

    def __init__(self, handler):
        self._log = False
        self._handler = handler
        self._serializer = serializer.JsonSerializer()
        self._registrations = {}
        self._invocations = {}
        self._subscription_topics = {}
        self._my_session_id = util.id()

        self._handler.onOpen(self)

        roles = {u'broker': role.RoleBrokerFeatures(), u'dealer': role.RoleDealerFeatures()}

        msg = message.Welcome(self._my_session_id, roles)
        self._handler.onMessage(msg)

    def _s(self, msg):
        if msg:
            self._handler.onMessage(msg)

    def send(self, msg):

        if self._log:
            print("req")
            print(msg)

        reply = None

        if isinstance(msg, message.Publish):
            if msg.topic in self._subscription_topics.keys():

                pubID = util.id()

                def published():
                    self._s(message.Published(msg.request, pubID))

                reg = self._subscription_topics[msg.topic]
                reply = message.Event(reg, pubID, args=msg.args, kwargs=msg.kwargs)

                if msg.acknowledge:
                    reactor.callLater(0, published)

            elif len(msg.topic) == 0:
                reply = message.Error(message.Publish.MESSAGE_TYPE, msg.request, u'wamp.error.invalid_uri')
            else:
                reply = message.Error(message.Publish.MESSAGE_TYPE, msg.request, u'wamp.error.not_authorized')

        elif isinstance(msg, message.Error):
            # Convert an invocation error into a call error
            if msg.request_type == 68:
                msg.request_type = 48

            reply = msg

        elif isinstance(msg, message.Call):
            if msg.procedure in self._registrations:
                request = util.id()
                registration = self._registrations[msg.procedure]
                self._invocations[msg.request] = msg.request

                def invoke():
                    self._s(message.Invocation(msg.request, registration, args=msg.args, kwargs=msg.kwargs))

                reactor.callLater(0, invoke)

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
            self._s(reply)

    def isOpen(self):
        return True

    def close(self):
        pass

    def abort(self):
        pass
