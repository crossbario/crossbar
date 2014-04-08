###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

from __future__ import absolute_import


def createHSTSRequestFactory(requestFactory, hstsMaxAge = 31536000):
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
