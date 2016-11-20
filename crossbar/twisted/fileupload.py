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

import os
import json
import cgi  # for POST Request Header decoding
import shutil

from twisted.web.resource import Resource

from autobahn.wamp.types import PublishOptions

from txaio import make_logger


class FileUploadResource(Resource):

    """
    Twisted Web resource that handles file uploads over `HTTP/POST` requests.
    """

    log = make_logger()

    def __init__(self,
                 upload_directory,
                 temp_directory,
                 form_fields,
                 upload_session,
                 options=None):
        """

        :param upload_directory: The target directory where uploaded files will be stored.
        :type upload_directory: str
        :param temp_directory: A temporary directory where chunks of a file being uploaded are stored.
        :type temp_directory: str
        :param form_fields: Names of HTML form fields used for uploading.
        :type form_fields: dict
        :param upload_session: An instance of `ApplicationSession` used for publishing progress events.
        :type upload_session: obj
        :param options: Options for file upload.
        :type options: dict or None
        """

        Resource.__init__(self)
        self._uploadRoot = upload_directory
        self._tempDirRoot = temp_directory
        self._form_fields = form_fields
        self._fileupload_session = upload_session
        self._options = options or {}
        self._max_file_size = self._options.get('max_file_size', 10 * 1024 * 1024)
        self._fileTypes = self._options.get('file_types', None)
        self._file_permissions = self._options.get('file_permissions', None)

        # track uploaded files / chunks
        self._uploads = {}

        self.log.info('Upload Resource started.')

        # scan the temp dir for uploaded chunks and fill the _uploads dict with it
        # so existing uploads can be resumed
        # all other remains will be purged
        for _fileTempDir in os.listdir(self._tempDirRoot):
            fileTempDir = os.path.join(self._tempDirRoot, _fileTempDir)
            fileTempName = os.path.basename(fileTempDir)
            if os.path.isdir(fileTempDir):
                self._uploads[fileTempName] = {'chunk_list': [], 'origin': 'startup'}
                for chunk in os.listdir(fileTempDir):
                    if chunk[:6] == 'chunk_':
                        self._uploads[fileTempName]['chunk_list'].append(int(chunk[6:]))
                    else:
                        os.remove(os.path.join(fileTempDir, chunk))
                # if no chunks detected then remove remains completely
                if len(self._uploads[fileTempName]['chunk_list']) == 0:
                    shutil.rmtree(fileTempDir)
                    self._uploads.pop(fileTempName, None)
            else:  # fileTempDir is a file remaining from a single chunk upload
                os.remove(fileTempDir)

        self.log.debug("Scanned pending uploads: {uploads}", uploads=self._uploads)

    def render_POST(self, request):
        headers = {x.decode('iso-8859-1'): y.decode('iso-8859-1')
                   for x, y in request.getAllHeaders().items()}

        origin = headers['host']

        postFields = cgi.FieldStorage(
            fp=request.content,
            headers=headers,
            environ={"REQUEST_METHOD": "POST"})

        f = self._form_fields

        filename = postFields[f['file_name']].value
        totalSize = int(postFields[f['total_size']].value)
        totalChunks = int(postFields[f['total_chunks']].value)
        chunkSize = int(postFields[f['chunk_size']].value)
        chunkNumber = int(postFields[f['chunk_number']].value)
        fileContent = postFields[f['content']].value

        if 'chunk_extra' in f and f['chunk_extra'] in postFields:
            chunk_extra = json.loads(postFields[f['chunk_extra']].value)
        else:
            chunk_extra = {}

        if 'finish_extra' in f and f['finish_extra'] in postFields:
            finish_extra = json.loads(postFields[f['finish_extra']].value)
        else:
            finish_extra = {}

        fileId = filename

        # # prepare user specific upload areas
        # # NOT YET IMPLEMENTED
        # #
        # if 'auth_id' in f and f['auth_id'] in postFields:
        #     auth_id = postFields[f['auth_id']].value
        #     mydir = os.path.join(self._uploadRoot, auth_id)
        #     my_temp_dir = os.path.join(self._tempDirRoot, auth_id)
        #
        #     # check if auth_id is a valid directory_name
        #     #
        #     if auth_id != auth_id.encode('ascii', 'ignore'):
        #         msg = "The requestor auth_id must be an ascii string."
        #         # 415 Unsupported Media Type
        #         request.setResponseCode(415, msg)
        #         return msg
        # else:
        #     auth_id = 'anonymous'

        # create user specific folder

        # mydir = self._uploadRoot
        # my_temp_dir = self._tempDirRoot

        # if not os.path.exists(mydir):
        #     os.makedirs(mydir)
        # if not os.path.exists(my_temp_dir):
        #     os.makedirs(my_temp_dir)

        # prepare the on_progress publisher
        if 'on_progress' in f and f['on_progress'] in postFields and self._fileupload_session != {}:
            topic = postFields[f['on_progress']].value

            if 'session' in f and f['session'] in postFields:
                session = int(postFields[f['session']].value)
                publish_options = PublishOptions(eligible=[session])
            else:
                publish_options = None

            def fileupload_publish(payload):
                self._fileupload_session.publish(topic, payload, options=publish_options)
        else:
            def fileupload_publish(payload):
                pass

        # Register upload right at the start to avoid overlapping upload conflicts
        #
        if fileId not in self._uploads:
            self._uploads[fileId] = {'chunk_list': [], 'origin': origin}
            chunk_is_first = True
            self.log.debug('Started upload of file: file_name={file_name}, total_size={total_size}, total_chunks={total_chunks}, chunk_size={chunk_size}, chunk_number={chunk_number}',
                           file_name=fileId, total_size=totalSize, total_chunks=totalChunks, chunk_size=chunkSize, chunk_number=chunkNumber)
        else:
            chunk_is_first = False
            # If the chunks are read at startup of crossbar any client may claim and resume the pending upload !
            #
            upl = self._uploads[fileId]
            if upl['origin'] == 'startup':
                self.log.debug('Will try to resume upload of file: file_name={file_name}, total_size={total_size}, total_chunks={total_chunks}, chunk_size={chunk_size}, chunk_number={chunk_number}',
                               file_name=fileId, total_size=totalSize, total_chunks=totalChunks, chunk_size=chunkSize, chunk_number=chunkNumber)
                upl['origin'] = origin
            else:
                # check if another session is uploading this file already
                #
                if upl['origin'] != origin:
                    msg = "File being uploaded is already uploaded in a different session."
                    self.log.debug(msg)
                    # 409 Conflict
                    request.setResponseCode(409, msg.encode('utf8'))
                    return msg.encode('utf8')
                else:
                    # check if the chunk is being uploaded in this very session already
                    # this should never happen !
                    if chunkNumber in upl['chunk_list']:
                        msg = "Chunk beeing uploaded is already uploading."
                        self.log.debug(msg)
                        # Don't throw a conflict. This may be a wanted behaviour.
                        # Even if an upload would be resumable, you don't have to resume.
                        # 409 Conflict
                        # request.setResponseCode(409, msg.encode('utf8'))
                        # return msg.encode('utf8')

        # check file size
        #
        if totalSize > self._max_file_size:
            msg = "Size {} of file to be uploaded exceeds maximum {}".format(totalSize, self._max_file_size)
            self.log.debug(msg)
            # 413 Request Entity Too Large
            request.setResponseCode(413, msg.encode('utf8'))
            return msg.encode('utf8')

        # check file extensions
        #
        extension = os.path.splitext(filename)[1]
        if self._fileTypes and extension not in self._fileTypes:
            msg = "Type '{}' of file to be uploaded is in allowed types {}".format(extension, self._fileTypes)
            self.log.debug(msg)
            # 415 Unsupported Media Type
            request.setResponseCode(415, msg.encode('utf8'))
            return msg.encode('utf8')

        # TODO: check mime type
        #
        fileTempDir = os.path.join(self._tempDirRoot, fileId)
        chunkName = os.path.join(fileTempDir, 'chunk_' + str(chunkNumber))
        _chunkName = os.path.join(fileTempDir, '#kfhf3kz412uru578e38viokbjhfvz4w__' + 'chunk_' + str(chunkNumber))

        def mergeFile():
            # every chunk has to check if it is the last chunk written, except in a single chunk scenario
            if totalChunks > 1 and len(self._uploads[fileId]['chunk_list']) >= totalChunks:
                # last chunk
                self.log.debug('Finished file upload after chunk {chunk_number} with chunk_list {chunk_list}', chunk_number=chunkNumber, chunk_list=self._uploads)

                # Merge all files into one file and remove the temp files
                # TODO: How to avoid the extra file IO ?
                finalFileName = os.path.join(self._uploadRoot, fileId)
                _finalFileName = os.path.join(fileTempDir, '#kfhf3kz412uru578e38viokbjhfvz4w__' + fileId)
                with open(_finalFileName, 'wb') as _finalFile:
                    for cn in range(1, totalChunks + 1):
                        with open(os.path.join(fileTempDir, 'chunk_' + str(cn)), 'rb') as ff:
                            _finalFile.write(ff.read())

                os.rename(_finalFileName, finalFileName)

                if self._file_permissions:
                    perm = int(self._file_permissions, 8)
                    try:
                        os.chmod(finalFileName, perm)
                    except Exception as e:
                        msg = "file upload resource - could not change file permissions of uploaded file"
                        self.log.debug(msg)
                        self.log.debug(e)
                        self._uploads.pop(fileId, None)
                        request.setResponseCode(500, msg.encode('utf8'))
                        return msg.encode('utf8')
                    else:
                        self.log.debug("Changed permissions on {file_name} to {permissions}", file_name=finalFileName, permissions=self._file_permissions)

                # remove the file temp folder
                shutil.rmtree(fileTempDir)

                self._uploads.pop(fileId, None)

                # publish file upload progress to file_progress_URI
                fileupload_publish(
                    {
                        u"id": fileId,
                        u"chunk": chunkNumber,
                        u"name": filename,
                        u"total": totalSize,
                        u"remaining": 0,
                        u"status": "finished",
                        u"progress": 1.,
                        u"finish_extra": finish_extra,
                        u"chunk_extra": chunk_extra,
                    }
                )

        if chunk_is_first:
            # first chunk of file

            # publish file upload start
            #
            fileupload_publish(
                {
                    u"id": fileId,
                    u"chunk": chunkNumber,
                    u"name": filename,
                    u"total": totalSize,
                    u"remaining": totalSize,
                    u"status": "started",
                    u"progress": 0.,
                    u"chunk_extra": chunk_extra,
                }
            )

            if totalChunks == 1:
                # only one chunk overall -> write file directly
                finalFileName = os.path.join(self._uploadRoot, fileId)
                _finalFileName = os.path.join(self._tempDirRoot, '#kfhf3kz412uru578e38viokbjhfvz4w__' + fileId)

                with open(_finalFileName, 'wb') as _finalFile:
                    _finalFile.write(fileContent)

                if self._file_permissions:
                    perm = int(self._file_permissions, 8)
                    try:
                        os.chmod(_finalFileName, perm)
                    except Exception as e:
                        # finalFileName.remove()
                        msg = "Could not change file permissions of uploaded file"
                        self.log.debug(msg)
                        self.log.debug(e)
                        request.setResponseCode(500, msg.encode('utf8'))
                        return msg.encode('utf8')
                    else:
                        self.log.debug("Changed permissions on {file_name} to {permissions}", file_name=finalFileName, permissions=self._file_permissions)

                os.rename(_finalFileName, finalFileName)
                if chunkNumber not in self._uploads[fileId]['chunk_list']:
                    self._uploads[fileId]['chunk_list'].append(chunkNumber)

                self._uploads.pop(fileId, None)

                # publish file upload progress to file_progress_URI
                fileupload_publish(
                    {
                        u"id": fileId,
                        u"chunk": chunkNumber,
                        u"name": filename,
                        u"total": totalSize,
                        u"remaining": 0,
                        u"status": "finished",
                        u"progress": 1.,
                        u"finish_extra": finish_extra,
                        u"chunk_extra": chunk_extra,
                    }
                )

            else:
                # first of more chunks
                # fileTempDir.remove()  # any potential conflict should have been resolved above. This should not be necessary!
                if not os.path.isdir(fileTempDir):
                    os.makedirs(fileTempDir)

                with open(_chunkName, 'wb') as chunk:
                    chunk.write(fileContent)
                os.rename(_chunkName, chunkName)  # atomic file system operation
                self.log.debug('chunk_' + str(chunkNumber) + ' written and moved to ' + chunkName)
                # publish file upload progress
                #
                fileupload_publish(
                    {
                        u"id": fileId,
                        u"chunk": chunkNumber,
                        u"name": filename,
                        u"total": totalSize,
                        u"remaining": totalSize - chunkSize,
                        u"status": "progress",
                        u"progress": round(float(chunkSize) / float(totalSize), 3),
                        u"chunk_extra": chunk_extra,
                    }
                )
                if chunkNumber not in self._uploads[fileId]['chunk_list']:
                    self._uploads[fileId]['chunk_list'].append(chunkNumber)
                mergeFile()
            # clean the temp dir once per file upload
            self._remove_stale_uploads()

        else:
            # intermediate chunk
            if not os.path.isdir(fileTempDir):
                os.makedirs(fileTempDir)

            with open(_chunkName, 'wb') as chunk:
                chunk.write(fileContent)
            os.rename(_chunkName, chunkName)
            self.log.debug('chunk_' + str(chunkNumber) + ' written and moved to ' + chunkName)

            if chunkNumber not in self._uploads[fileId]['chunk_list']:
                self._uploads[fileId]['chunk_list'].append(chunkNumber)

            received = sum(os.path.getsize(os.path.join(fileTempDir, f)) for f in os.listdir(fileTempDir))

            fileupload_publish(
                {
                    u"id": fileId,
                    u"chunk": chunkNumber,
                    u"name": filename,
                    u"total": totalSize,
                    u"remaining": totalSize - received,
                    u"status": "progress",
                    u"progress": round(float(received) / float(totalSize), 3),
                    u"chunk_extra": chunk_extra,
                }
            )
            mergeFile()
        # no errors encountered -> respond success
        request.setResponseCode(200)
        return b''

    def _remove_stale_uploads(self):
        """
        This only works if there is a temp folder exclusive for crossbar file uploads
        if the system temp folder is used then crossbar creates a "crossbar-uploads" there and
        uses that as the temp folder for uploads
        If you don't clean up regularly an attacker could fill up the OS file system
        """
        for _fileTempDir in os.listdir(self._tempDirRoot):
            fileTempDir = os.path.join(self._tempDirRoot, _fileTempDir)
            self.log.debug('REMOVE STALE UPLOADS ' + str(os.path.basename(fileTempDir)))
            if os.path.isdir(fileTempDir) and os.path.basename(fileTempDir) not in self._uploads:
                shutil.rmtree(fileTempDir)

    def render_GET(self, request):
        """
        This method can be used to check whether a chunk has been uploaded already.
        It returns with HTTP status code `200` if yes and `404` if not.
        The request needs to contain the file identifier and the chunk number to check for.
        """
        for param in ['file_name', 'chunk_number']:
            if not self._form_fields[param].encode('iso-8859-1') in request.args:
                msg = "file upload resource - missing request query parameter '{}', configured from '{}'".format(self._form_fields[param], param)
                self.log.debug(msg)
                # 400 Bad Request
                request.setResponseCode(400, msg.encode('utf8'))
                return msg.encode('utf8')

        file_name = request.args[self._form_fields['file_name'].encode('iso-8859-1')][0].decode('utf8')
        chunk_number = int(request.args[self._form_fields['chunk_number'].encode('iso-8859-1')][0].decode('utf8'))

        # a complete upload will be repeated an incomplete upload will be resumed
        if file_name in self._uploads and chunk_number in self._uploads[file_name]['chunk_list']:
            self.log.debug("Skipping chunk upload {file_name} of chunk {chunk_number}", file_name=file_name, chunk_number=chunk_number)
            msg = b"chunk of file already uploaded"
            request.setResponseCode(200, msg)
            return msg
        else:
            msg = b"chunk of file not yet uploaded"
            request.setResponseCode(404, msg)
            return msg
