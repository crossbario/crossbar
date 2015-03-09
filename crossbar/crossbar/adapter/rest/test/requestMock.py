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

import hmac
import hashlib
import random
import base64

from datetime import datetime

from StringIO import StringIO

from twisted.web import server
from twisted.web.http_headers import Headers
from twisted.web.test.test_web import DummyChannel
from twisted.internet.defer import succeed
from twisted.internet.address import IPv4Address

from mock import Mock

# The following two functions contain code from the Klein and Saratoga projects.

# Copyright (c) 2011-2015, Klein Contributors, (c) 2014-2015 HawkOwl
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

def _render(resource, request):
    result = resource.render(request)
    if isinstance(result, str):
        request.write(result)
        request.finish()
        return succeed(None)
    elif result is server.NOT_DONE_YET:
        if request.finished:
            return succeed(None)
        else:
            return request.notifyFinish()
    else:
        raise ValueError("Unexpected return value: %r" % (result,))


def _requestMock(path, method="GET", host="localhost", port=8080, isSecure=False,
                 body=None, headers=None, args=None, reactor=None):

    if not headers:
        headers = {}

    headers["Date"] = ["Tue, 01 Jan 2014 01:01:01 GMT"]

    if not body:
        body = ''

    if not reactor:
        from twisted.internet import reactor

    request = server.Request(DummyChannel(), False)
    request.site = Mock(server.Site)
    request.gotLength(len(body))
    request.client = IPv4Address("TCP", "127.0.0.1", 80)
    request.content = StringIO()
    request.content.write(body)
    request.content.seek(0)
    request.args = args
    request.requestHeaders = Headers(headers)
    request.setHost(host, port, isSecure)
    request.uri = path
    request.path = path
    request.prepath = []
    request.postpath = path.split('/')[1:]
    request.method = method
    request.clientproto = 'HTTP/1.1'

    request.setHeader = Mock(wraps=request.setHeader)
    request.setResponseCode = Mock(wraps=request.setResponseCode)

    request._written = StringIO()
    request.finishCount = 0
    request.writeCount = 0

    def produce():
        while request.producer:
            request.producer.resumeProducing()

    def registerProducer(producer, streaming):
        request.producer = producer
        if streaming:
            request.producer.resumeProducing()
        else:
            reactor.callLater(0.0, produce)

    def unregisterProducer():
        request.producer = None

    def finish():
        request.finishCount += 1

        if not request.startedWriting:
            request.write('')

        if not request.finished:
            request.finished = True
            request._cleanup()

    def write(data):
        request.writeCount += 1
        request.startedWriting = True

        if not request.finished:
            request._written.write(data)
        else:
            raise RuntimeError('Request.write called on a request after '
                               'Request.finish was called.')

    def getWrittenData():
        return request._written.getvalue()

    request.finish = finish
    request.write = write
    request.getWrittenData = getWrittenData

    request.registerProducer = registerProducer
    request.unregisterProducer = unregisterProducer

    request.processingFailed = Mock(wraps=request.processingFailed)

    return request


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
