# The following file contains code from the Klein and Saratoga projects, and are
# licensed under the MIT license.

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

from io import BytesIO as StringIO

from twisted.web import server
from twisted.web.http_headers import Headers
from twisted.web.test.test_web import DummyChannel
from twisted.internet.defer import succeed
from twisted.internet.address import IPv4Address

from mock import Mock


def _render(resource, request):
    result = resource.render(request)
    if isinstance(result, type(b'')):
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


def _requestMock(path, method=b"GET", host=b"localhost", port=8080, isSecure=False,
                 body=None, headers=None, args=None, reactor=None):

    if not headers:
        headers = {}

    headers[b"Date"] = ["Tue, 01 Jan 2014 01:01:01 GMT"]

    if not body:
        body = b''

    if not reactor:
        from twisted.internet import reactor

    request = server.Request(DummyChannel(), False)
    request.site = Mock(server.Site)
    request.gotLength(len(body))
    request.client = IPv4Address("TCP", b"127.0.0.1", 80)
    request.content = StringIO()
    request.content.write(body)
    request.content.seek(0)
    request.args = args
    request.requestHeaders = Headers(headers)
    request.setHost(host, port, isSecure)
    request.uri = path
    request.path = path
    request.prepath = []
    request.postpath = path.split(b'/')[1:]
    request.method = method
    request.clientproto = b'HTTP/1.1'

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
            request.write(b'')

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
