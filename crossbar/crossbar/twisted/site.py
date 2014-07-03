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

import six


def patchFileContentTypes(root):
   """
   For reasons beyond my understanding, on Python 2.7.7, the MIME type map in
   `twisted.web.static.File.contentTypes` ends up having values (not all) that
   are of type unicode. This breaks stuff further down the line, since twisted
   will bail out "data must not be unicode" when the HTTP header with the
   respective content type is written.

   We work around by patching the map.

   See also: https://twistedmatrix.com/trac/ticket/7461

   Update: the origin is http://bugs.python.org/issue21652

   It is specific to CPython 2.7.7 on Windows. It is fixed in 2.7.8.
   """
   if six.PY2:
      c = 0
      for k, v in root.contentTypes.items():
         if type(v) == unicode:
            root.contentTypes[k] = root.contentTypes[k].encode('ascii')
            c += 1
      if c:
         print("Monkey-patched MIME table ({} of {} entries)".format(c, len(root.contentTypes)))



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
