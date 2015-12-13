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

from __future__ import absolute_import, division

from io import BytesIO

from twisted.web import server
from twisted.web.http_headers import Headers
from twisted.web.test._util import _render
from twisted.web.test.test_web import DummyChannel

def request(path, method=b"GET", args=[], isSecure=False, headers={}, body=b''):

    channel = DummyChannel()

    req = server.Request(channel=DummyChannel(), queued=False)

    req.requestHeaders = Headers(headers)
    req.requestHeaders.setRawHeaders(b"Date", [b"Sun, 1 Jan 2013 15:21:01 GMT"])

    req.content = BytesIO(body)


    _written_data = BytesIO()

    def _write(data):
        print(data)
        assert not req.finished
        req.startedWriting = True
        _written_data.write(data)

    req.write = _write

    def _get_written_data():
        return _written_data.getvalue()

    req.get_written_data = _get_written_data

    return req
