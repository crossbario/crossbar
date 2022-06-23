#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from txaio import make_logger

from twisted.web import server
from twisted.web.http import HTTPChannel


def createHSTSRequestFactory(requestFactory, hstsMaxAge=31536000):
    """
    Builds a request factory that sets HSTS (HTTP Strict Transport
    Security) headers, by wrapping another request factory.
    """
    def makeRequest(*a, **kw):
        request = requestFactory(*a, **kw)
        request.responseHeaders.setRawHeaders("Strict-Transport-Security", ["max-age={}".format(hstsMaxAge)])
        return request

    return makeRequest


class _LessNoisyHTTPChannel(HTTPChannel):
    """
    Internal helper.

    This is basically exactly what Twisted does, except without using
    "log.msg" so we can put it at debug log-level instead
    """
    log = make_logger()

    def timeoutConnection(self):
        self.log.debug(
            "Timing out client: {peer}",
            peer=self.transport.getPeer(),
        )
        if self.abortTimeout is not None:
            self._abortingCall = self.callLater(self.abortTimeout, self.forceAbortClient)
        self.loseConnection()


class Site(server.Site):
    def __init__(self,
                 resource,
                 client_timeout=None,
                 access_log=None,
                 display_tracebacks=None,
                 hsts=None,
                 hsts_max_age=None):

        server.Site.__init__(self, resource, timeout=client_timeout)

        # Web access logging
        if not access_log:
            self.noisy = False
            self.log = lambda _: None

        # Traceback rendering
        self.displayTracebacks = True if display_tracebacks else False

        # HSTS
        if hsts:
            hsts_max_age = hsts_max_age or 31536000
            self.requestFactory = createHSTSRequestFactory(self.requestFactory, hsts_max_age)
