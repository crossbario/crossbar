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
            if isinstance(v, six.text_type):
                root.contentTypes[k] = root.contentTypes[k].encode('ascii')
                c += 1


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
