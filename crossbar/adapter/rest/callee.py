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

from six.moves.urllib.parse import urljoin

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.http_headers import Headers

from autobahn.twisted.wamp import ApplicationSession


class RESTCallee(ApplicationSession):

    def __init__(self, *args, **kwargs):
        self._webtransport = kwargs.pop("webTransport", None)

        if not self._webtransport:
            import treq
            self._webtransport = treq

        super(RESTCallee, self).__init__(*args, **kwargs)

    @inlineCallbacks
    def onJoin(self, details):
        assert "baseurl" in self.config.extra
        assert "procedure" in self.config.extra

        baseURL = self.config.extra["baseurl"]
        procedure = self.config.extra["procedure"]

        @inlineCallbacks
        def on_call(method=None, url=None, body=u"", headers={}, params={}):

            newURL = urljoin(baseURL, url)

            params = {x.encode('utf8'): y.encode('utf8') for x, y in params.items()}

            res = yield self._webtransport.request(
                method,
                newURL,
                data=body.encode('utf8'),
                headers=Headers(headers),
                params=params
            )
            content = yield self._webtransport.text_content(res)

            headers = {x.decode('utf8'): [z.decode('utf8') for z in y]
                       for x, y in dict(res.headers.getAllRawHeaders()).items()}

            resp = {
                u"code": res.code,
                u"content": content,
                u"headers": headers
            }

            returnValue(resp)

        yield self.register(on_call, procedure)
