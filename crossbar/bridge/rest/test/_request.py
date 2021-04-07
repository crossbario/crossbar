#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from mock import Mock

from io import BytesIO

from twisted.internet.address import IPv4Address
from twisted.web import server
from twisted.web.http_headers import Headers
from twisted.web.test.test_web import DummyChannel


def request(path,
            method=b"GET",
            args=[],
            isSecure=False,
            headers={},
            body=b'',
            host=b"localhost",
            port=8000,
            reactor=None):
    """
    A fake `server.Request` which implements just enough for our tests.
    """

    if reactor is None:
        from twisted.internet import reactor

    channel = DummyChannel()
    site = Mock(server.Site)

    req = server.Request(channel=channel, queued=False)
    req.site = site

    req.method = method
    req.uri = path
    req.path = path
    req.prepath = []
    req.postpath = path.split(b'/')[1:]
    req.clientProto = b"HTTP/1.1"

    req.args = args

    # Set the headers we've got, as setHost writes to them
    req.requestHeaders = Headers(headers)

    # Put in a bogus date of no real significance, but one that will stay the
    # same
    req.requestHeaders.setRawHeaders(b"Date", [b"Sun, 1 Jan 2013 15:21:01 GMT"])

    # Set the host we are, and the client we're talking to
    req.setHost(host, port, isSecure)
    req.client = IPv4Address("TCP", "127.0.0.1", 8000)

    _written_data = BytesIO()

    # Writing
    def _write(data):
        assert not req.finished
        req.startedWriting = True
        _written_data.write(data)

    req.write = _write

    # Finishing
    def _finish():

        if not req.startedWriting:
            req.write(b"")

        if not req.finished:
            req.finished = True
            req._cleanup()

    req.finish = _finish

    # Getting what was wrote

    def _get_written_data():
        return _written_data.getvalue()

    req.get_written_data = _get_written_data

    # We have content now!
    req.content = BytesIO()
    req.content.write(body)
    req.content.seek(0)

    return req
