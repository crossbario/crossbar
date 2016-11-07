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

"""
Tools for generating multipart requests.
"""

from uuid import uuid4

_boundary_segment = b"---------------------------"


class _Part(object):
    """
    A multipart "part".
    """
    def __init__(self, name, content, filename=None, content_type=None):

        self._content = content
        self._name = name
        self._content_type = content_type
        self._filename = filename

    def render(self):

        end_content = []
        end_content.append(b'Content-Disposition: form-data; name="')
        end_content.append(self._name)
        end_content.append(b'"')

        if self._filename:
            end_content.append(b'; filename="')
            end_content.append(self._filename)
            end_content.append(b'"')

        end_content.append(b'\r\n')

        if self._content_type:
            end_content.append(b"Content-Type: ")
            end_content.append(self._content_type)
            end_content.append(b"\r\n")

        end_content.append(b"\r\n")
        end_content.append(self._content)
        end_content.append(b"\r\n")

        return b"".join(end_content)


class Multipart(object):
    """
    A multipart request.
    """
    def __init__(self):
        self._parts = []
        self._boundary = uuid4().hex.encode('ascii')

    def add_part(self, name, content, filename=None, content_type=None):

        self._parts.append(_Part(name, content, content_type=content_type,
                                 filename=filename))

    def render(self):
        """
        Render this Multipart into content and the requisite headers.
        """
        boundary = _boundary_segment + self._boundary

        end_content = []
        end_content.append(b"--" + boundary + b"\r\n")
        end_content.append((b"--" + boundary + b"\r\n").join(
            [part.render() for part in self._parts]))
        end_content.append(b"--" + boundary)
        end_content.append(b"--\r\n")
        content = b"".join(end_content)

        headers = {
            b"content-type": [b"multipart/form-data; boundary=" + boundary],
            b"content-length": [str(len(content)).encode('ascii')]
        }

        return (content, headers)
