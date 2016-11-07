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

from __future__ import absolute_import, division

from mock import Mock

from io import BytesIO

from twisted.internet.address import IPv4Address
from twisted.web import server
from twisted.web.http_headers import Headers
from twisted.web.test.test_web import DummyChannel


def request(path, method=b"GET", args=[], isSecure=False, headers={}, body=b'',
            host=b"localhost", port=8000, reactor=None):
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
    req.requestHeaders.setRawHeaders(b"Date",
                                     [b"Sun, 1 Jan 2013 15:21:01 GMT"])

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
