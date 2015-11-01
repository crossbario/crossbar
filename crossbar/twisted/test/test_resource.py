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

from __future__ import absolute_import, division, print_function

from crossbar.adapter.rest.test import renderResource
from crossbar.twisted.resource import FileUploadResource

from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from mock import Mock


class FileUploadTests(TestCase):
    """
    Tests for crossbar.twisted.resource.FileUploadResource.
    """

    def test_basic(self):
        """
        Upload a basic file using the FileUploadResource, in just a single chunk.
        """
        upload_dir = FilePath(self.mktemp())
        upload_dir.makedirs()
        temp_dir = FilePath(self.mktemp())
        temp_dir.makedirs()

        fields = {
            "file_name": "resumableFilename",
            "mime_type": "resumableType",
            "total_size": "resumableTotalSize",
            "chunk_number": "resumableChunkNumber",
            "chunk_size": "resumableChunkSize",
            "total_chunks": "resumableTotalChunks",
            "content": "file",
            "on_progress": "on_progress",
            "session": "session"
        }

        mock_session = Mock()

        resource = FileUploadResource(upload_dir.path, temp_dir.path, fields, mock_session)

        multipart_body = b"""-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableChunkNumber"\r\n\r\n1\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableChunkSize"\r\n\r\n1048576\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableCurrentChunkSize"\r\n\r\n16\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableTotalSize"\r\n\r\n16\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableType"\r\n\r\ntext/plain\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableIdentifier"\r\n\r\n16-examplefiletxt\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableFilename"\r\n\r\nexamplefile.txt\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableRelativePath"\r\n\r\nexamplefile.txt\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="resumableTotalChunks"\r\n\r\n1\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="on_progress"\r\n\r\ncom.example.upload.on_progress\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="session"\r\n\r\n6891276359801283\r\n-----------------------------478904261175205671481632460\r\nContent-Disposition: form-data; name="file"; filename="blob"\r\nContent-Type: application/octet-stream\r\n\r\nhello Crossbar!\n\r\n-----------------------------478904261175205671481632460--\r\n"""

        d = renderResource(
            resource, b"/", method="POST",
            headers={
                b"content-type": [b"multipart/form-data; boundary=---------------------------478904261175205671481632460"],
                b"Content-Length": [b"1678"]
            },
            body=multipart_body
        )

        res = self.successResultOf(d)
        res.setResponseCode.assert_called_once_with(200)

        self.assertEqual(len(mock_session.method_calls), 2)

        # Starting the upload
        self.assertEqual(mock_session.method_calls[0][1][0], u"com.example.upload.on_progress")
        self.assertEqual(mock_session.method_calls[0][1][1]["status"], "started")
        self.assertEqual(mock_session.method_calls[0][1][1]["id"], "examplefile.txt")

        # Upload complete
        self.assertEqual(mock_session.method_calls[1][1][0], u"com.example.upload.on_progress")
        self.assertEqual(mock_session.method_calls[1][1][1]["status"], "finished")
        self.assertEqual(mock_session.method_calls[1][1][1]["id"], "examplefile.txt")

        # Nothing in the temp dir, one file in the upload
        self.assertEqual(len(temp_dir.listdir()), 0)
        self.assertEqual(len(upload_dir.listdir()), 1)
        with upload_dir.child("examplefile.txt").open("rb") as f:
            self.assertEqual(f.read(), b"hello Crossbar!\n")

    def test_multichunk(self):
        """
        Uploading files that are in multiple chunks works.
        """
        upload_dir = FilePath(self.mktemp())
        upload_dir.makedirs()
        temp_dir = FilePath(self.mktemp())
        temp_dir.makedirs()

        fields = {
            "file_name": "resumableFilename",
            "mime_type": "resumableType",
            "total_size": "resumableTotalSize",
            "chunk_number": "resumableChunkNumber",
            "chunk_size": "resumableChunkSize",
            "total_chunks": "resumableTotalChunks",
            "content": "file",
            "on_progress": "on_progress",
            "session": "session"
        }

        mock_session = Mock()

        resource = FileUploadResource(upload_dir.path, temp_dir.path, fields, mock_session)

        #
        # Chunk 1

        multipart_body = b"""-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableChunkNumber"\r\n\r\n1\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableChunkSize"\r\n\r\n10\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableCurrentChunkSize"\r\n\r\n10\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableTotalSize"\r\n\r\n16\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableType"\r\n\r\ntext/plain\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableIdentifier"\r\n\r\n16-examplefiletxt\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableFilename"\r\n\r\nexamplefile.txt\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableRelativePath"\r\n\r\nexamplefile.txt\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="resumableTotalChunks"\r\n\r\n2\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="on_progress"\r\n\r\ncom.example.upload.on_progress\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="session"\r\n\r\n8887465641628580\r\n-----------------------------1311987731215707521443909311\r\nContent-Disposition: form-data; name="file"; filename="blob"\r\nContent-Type: application/octet-stream\r\n\r\nhello Cros\r\n-----------------------------1311987731215707521443909311--\r\n"""

        d = renderResource(
            resource, b"/", method="POST",
            headers={
                b"content-type": [b"multipart/form-data; boundary=---------------------------1311987731215707521443909311"],
                b"Content-Length": [b"1680"]
            },
            body=multipart_body
        )

        res = self.successResultOf(d)
        res.setResponseCode.assert_called_once_with(200)

        # One directory in the temp dir, nothing in the upload dir, temp dir
        # contains one chunk
        self.assertEqual(len(temp_dir.listdir()), 1)
        self.assertEqual(len(temp_dir.child("examplefile.txt").listdir()), 1)
        with temp_dir.child("examplefile.txt").child("chunk_1").open("rb") as f:
            self.assertEqual(f.read(), b"hello Cros")
        self.assertEqual(len(upload_dir.listdir()), 0)

        #
        # Chunk 2

        multipart_body = b"""-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableChunkNumber"\r\n\r\n2\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableChunkSize"\r\n\r\n10\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableCurrentChunkSize"\r\n\r\n6\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableTotalSize"\r\n\r\n16\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableType"\r\n\r\ntext/plain\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableIdentifier"\r\n\r\n16-examplefiletxt\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableFilename"\r\n\r\nexamplefile.txt\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableRelativePath"\r\n\r\nexamplefile.txt\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="resumableTotalChunks"\r\n\r\n2\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="on_progress"\r\n\r\ncom.example.upload.on_progress\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="session"\r\n\r\n8887465641628580\r\n-----------------------------42560029919436807832069165364\r\nContent-Disposition: form-data; name="file"; filename="blob"\r\nContent-Type: application/octet-stream\r\n\r\nsbar!\n\r\n-----------------------------42560029919436807832069165364--\r\n"""

        d = renderResource(
            resource, b"/", method="POST",
            headers={
                b"content-type": [b"multipart/form-data; boundary=---------------------------42560029919436807832069165364"],
                b"Content-Length": [b"1688"]
            },
            body=multipart_body
        )

        res = self.successResultOf(d)
        res.setResponseCode.assert_called_once_with(200)

        self.assertEqual(len(mock_session.method_calls), 4)

        # Starting the upload
        self.assertEqual(mock_session.method_calls[0][1][0], u"com.example.upload.on_progress")
        self.assertEqual(mock_session.method_calls[0][1][1]["status"], "started")
        self.assertEqual(mock_session.method_calls[0][1][1]["id"], "examplefile.txt")
        self.assertEqual(mock_session.method_calls[0][1][1]["chunk"], 1)

        # Progress, first chunk done
        self.assertEqual(mock_session.method_calls[1][1][0], u"com.example.upload.on_progress")
        self.assertEqual(mock_session.method_calls[1][1][1]["status"], "progress")
        self.assertEqual(mock_session.method_calls[1][1][1]["id"], "examplefile.txt")
        self.assertEqual(mock_session.method_calls[1][1][1]["chunk"], 1)

        # Progress, second chunk done
        self.assertEqual(mock_session.method_calls[2][1][0], u"com.example.upload.on_progress")
        self.assertEqual(mock_session.method_calls[2][1][1]["status"], "progress")
        self.assertEqual(mock_session.method_calls[2][1][1]["id"], "examplefile.txt")
        self.assertEqual(mock_session.method_calls[2][1][1]["chunk"], 2)

        # Upload complete
        self.assertEqual(mock_session.method_calls[3][1][0], u"com.example.upload.on_progress")
        self.assertEqual(mock_session.method_calls[3][1][1]["status"], "finished")
        self.assertEqual(mock_session.method_calls[3][1][1]["id"], "examplefile.txt")
        self.assertEqual(mock_session.method_calls[3][1][1]["chunk"], 2)

        # Nothing in the temp dir, one file in the upload
        self.assertEqual(len(temp_dir.listdir()), 0)
        self.assertEqual(len(upload_dir.listdir()), 1)
        with upload_dir.child("examplefile.txt").open("rb") as f:
            self.assertEqual(f.read(), b"hello Crossbar!\n")
