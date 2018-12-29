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
        request.responseHeaders.setRawHeaders("Strict-Transport-Security",
                                              ["max-age={}".format(hstsMaxAge)])
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
            self._abortingCall = self.callLater(
                self.abortTimeout, self.forceAbortClient
            )
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
