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

from .multipart import Multipart

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

        mp = Multipart()
        mp.add_part(b"resumableChunkNumber", b"1")
        mp.add_part(b"resumableChunkSize", b"1048576")
        mp.add_part(b"resumableCurrentChunkSize", b"16")
        mp.add_part(b"resumableTotalSize", b"16")
        mp.add_part(b"resumableType", b"text/plain")
        mp.add_part(b"resumableIdentifier", b"16-examplefiletxt")
        mp.add_part(b"resumableFilename", b"examplefile.txt")
        mp.add_part(b"resumableRelativePath", b"examplefile.txt")
        mp.add_part(b"resumableTotalChunks", b"1")
        mp.add_part(b"on_progress", b"com.example.upload.on_progress")
        mp.add_part(b"session", b"6891276359801283")
        mp.add_part(b"file", b"hello Crossbar!\n",
                    content_type=b"application/octet-stream",
                    filename=b"blob")
        body, headers = mp.render()

        d = renderResource(
            resource, b"/", method="POST",
            headers=headers,
            body=body
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

        mp = Multipart()
        mp.add_part(b"resumableChunkNumber", b"1")
        mp.add_part(b"resumableChunkSize", b"10")
        mp.add_part(b"resumableCurrentChunkSize", b"10")
        mp.add_part(b"resumableTotalSize", b"16")
        mp.add_part(b"resumableType", b"text/plain")
        mp.add_part(b"resumableIdentifier", b"16-examplefiletxt")
        mp.add_part(b"resumableFilename", b"examplefile.txt")
        mp.add_part(b"resumableRelativePath", b"examplefile.txt")
        mp.add_part(b"resumableTotalChunks", b"2")
        mp.add_part(b"on_progress", b"com.example.upload.on_progress")
        mp.add_part(b"session", b"6891276359801283")
        mp.add_part(b"file", b"hello Cros",
                    content_type=b"application/octet-stream",
                    filename=b"blob")
        body, headers = mp.render()

        d = renderResource(
            resource, b"/", method="POST",
            headers=headers,
            body=body
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

        mp = Multipart()
        mp.add_part(b"resumableChunkNumber", b"2")
        mp.add_part(b"resumableChunkSize", b"10")
        mp.add_part(b"resumableCurrentChunkSize", b"6")
        mp.add_part(b"resumableTotalSize", b"16")
        mp.add_part(b"resumableType", b"text/plain")
        mp.add_part(b"resumableIdentifier", b"16-examplefiletxt")
        mp.add_part(b"resumableFilename", b"examplefile.txt")
        mp.add_part(b"resumableRelativePath", b"examplefile.txt")
        mp.add_part(b"resumableTotalChunks", b"2")
        mp.add_part(b"on_progress", b"com.example.upload.on_progress")
        mp.add_part(b"session", b"6891276359801283")
        mp.add_part(b"file", b"sbar!\n",
                    content_type=b"application/octet-stream",
                    filename=b"blob")
        body, headers = mp.render()

        d = renderResource(
            resource, b"/", method="POST",
            headers=headers,
            body=body
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


    def test_resumed_upload(self):
        """
        Uploading part of a file, simulating a Crossbar restart, and continuing
        to upload works.
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

        # Make some stuff in the temp dir that wasn't there when it started but
        # is put there before a file upload
        temp_dir.child("otherjunk").makedirs()

        #
        # Chunk 1

        mp = Multipart()
        mp.add_part(b"resumableChunkNumber", b"1")
        mp.add_part(b"resumableChunkSize", b"10")
        mp.add_part(b"resumableCurrentChunkSize", b"10")
        mp.add_part(b"resumableTotalSize", b"16")
        mp.add_part(b"resumableType", b"text/plain")
        mp.add_part(b"resumableIdentifier", b"16-examplefiletxt")
        mp.add_part(b"resumableFilename", b"examplefile.txt")
        mp.add_part(b"resumableRelativePath", b"examplefile.txt")
        mp.add_part(b"resumableTotalChunks", b"2")
        mp.add_part(b"on_progress", b"com.example.upload.on_progress")
        mp.add_part(b"session", b"6891276359801283")
        mp.add_part(b"file", b"hello Cros",
                    content_type=b"application/octet-stream",
                    filename=b"blob")
        body, headers = mp.render()

        d = renderResource(
            resource, b"/", method="POST",
            headers=headers,
            body=body
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

        del resource

        # Add some random junk in there that Crossbar isn't expecting
        temp_dir.child("junk").setContent(b"just some junk")
        temp_dir.child("examplefile.txt").child("hi").setContent(b"what")

        # Simulate restarting Crossbar by reinitialising the FileUploadResource
        resource = FileUploadResource(upload_dir.path, temp_dir.path, fields, mock_session)

        #
        # Chunk 2

        mp = Multipart()
        mp.add_part(b"resumableChunkNumber", b"2")
        mp.add_part(b"resumableChunkSize", b"10")
        mp.add_part(b"resumableCurrentChunkSize", b"6")
        mp.add_part(b"resumableTotalSize", b"16")
        mp.add_part(b"resumableType", b"text/plain")
        mp.add_part(b"resumableIdentifier", b"16-examplefiletxt")
        mp.add_part(b"resumableFilename", b"examplefile.txt")
        mp.add_part(b"resumableRelativePath", b"examplefile.txt")
        mp.add_part(b"resumableTotalChunks", b"2")
        mp.add_part(b"on_progress", b"com.example.upload.on_progress")
        mp.add_part(b"session", b"6891276359801283")
        mp.add_part(b"file", b"sbar!\n",
                    content_type=b"application/octet-stream",
                    filename=b"blob")
        body, headers = mp.render()

        d = renderResource(
            resource, b"/", method="POST",
            headers=headers,
            body=body
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

        # One item in the temp dir which we made earlier, one item in the
        # upload dir
        self.assertEqual(len(temp_dir.listdir()), 1)
        self.assertEqual(len(upload_dir.listdir()), 1)
        with upload_dir.child("examplefile.txt").open("rb") as f:
            self.assertEqual(f.read(), b"hello Crossbar!\n")
