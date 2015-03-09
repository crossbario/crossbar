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

import hmac
import hashlib
import random
import base64

from datetime import datetime

from collections import namedtuple

from twisted.internet.defer import maybeDeferred

from crossbar.adapter.rest.test.requestMock import _requestMock, _render

publishedMessage = namedtuple("pub", ["id"])


class MockPusherSession(object):
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



def _utcnow():
    now = datetime.utcnow()
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def makeSignedArguments(params, signKey, signSecret, body):

    params['timestamp'] = [_utcnow()]
    params['seq'] = ["1"]
    params['key'] = [signKey]
    params['nonce'] = [str(random.randint(0, 9007199254740992))]

    # HMAC[SHA256]_{secret} (key | timestamp | seq | nonce | body) => signature

    hm = hmac.new(signSecret.encode('utf8'), None, hashlib.sha256)
    hm.update(params['key'][0].encode('utf8'))
    hm.update(params['timestamp'][0].encode('utf8'))
    hm.update(u"{0}".format(params['seq'][0]).encode('utf8'))
    hm.update(u"{0}".format(params['nonce'][0]).encode('utf8'))
    hm.update(body)
    signature = base64.urlsafe_b64encode(hm.digest())
    params['signature'] = [signature]

    return params


def testResource(resource, path, params=None, method="GET", body="",
                 headers=None, sign=False, signKey=None, signSecret=None):

    params = {} if params == None else params
    headers = {} if params == None else headers

    def _cb(result, request):
        return request

    if sign:
        params = makeSignedArguments(params, signKey, signSecret, body)

    req = _requestMock(path, args=params, method=method,
                       headers=headers, body=body)

    d = _render(resource, req)
    d.addCallback(_cb, req)
    return d
