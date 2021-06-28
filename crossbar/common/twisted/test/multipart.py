#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
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

        self._parts.append(_Part(name, content, content_type=content_type, filename=filename))

    def render(self):
        """
        Render this Multipart into content and the requisite headers.
        """
        boundary = _boundary_segment + self._boundary

        end_content = []
        end_content.append(b"--" + boundary + b"\r\n")
        end_content.append((b"--" + boundary + b"\r\n").join([part.render() for part in self._parts]))
        end_content.append(b"--" + boundary)
        end_content.append(b"--\r\n")
        content = b"".join(end_content)

        headers = {
            b"content-type": [b"multipart/form-data; boundary=" + boundary],
            b"content-length": [str(len(content)).encode('ascii')]
        }

        return (content, headers)
