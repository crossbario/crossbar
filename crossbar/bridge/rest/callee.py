#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from urllib.parse import urljoin

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
        def on_call(method=None, url=None, body="", headers={}, params={}):

            newURL = urljoin(baseURL, url)

            params = {x.encode('utf8'): y.encode('utf8') for x, y in params.items()}

            res = yield self._webtransport.request(method,
                                                   newURL,
                                                   data=body.encode('utf8'),
                                                   headers=Headers(headers),
                                                   params=params)
            content = yield self._webtransport.text_content(res)

            headers = {
                x.decode('utf8'): [z.decode('utf8') for z in y]
                for x, y in dict(res.headers.getAllRawHeaders()).items()
            }

            resp = {"code": res.code, "content": content, "headers": headers}

            returnValue(resp)

        yield self.register(on_call, procedure)
