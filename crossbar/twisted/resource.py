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

import os

import json
import time
import cgi  # for POST Request Header decoding

from twisted.web import http, server
from twisted.web.http import NOT_FOUND
from twisted.web.resource import Resource, NoResource
from twisted.web.static import File
from twisted.python.filepath import FilePath

from autobahn.wamp.types import PublishOptions

import crossbar
from crossbar._compat import native_string
from crossbar._logging import make_logger
from crossbar.router import longpoll

try:
    # triggers module level reactor import
    # https://twistedmatrix.com/trac/ticket/6849#comment:5
    from twisted.web.twcgi import CGIScript, CGIProcessProtocol
    _HAS_CGI = True
except (ImportError, SyntaxError):
    # Twisted hasn't ported this to Python 3 yet
    _HAS_CGI = False


class JsonResource(Resource):
    """
    Static Twisted Web resource that renders to a JSON document.
    """
    log = make_logger()

    def __init__(self, value, options=None):
        Resource.__init__(self)
        options = options or {}

        if options.get('prettify', False):
            self._data = json.dumps(value, sort_keys=True, indent=3, ensure_ascii=False)
        else:
            self._data = json.dumps(value, separators=(',', ':'), ensure_ascii=False)

        # Twisted Web render_METHOD methods are expected to return a byte string
        self._data = self._data.encode('utf8')

        self._allow_cross_origin = options.get('allow_cross_origin', True)
        self._discourage_caching = options.get('discourage_caching', False)

        # number of HTTP/GET requests we served from this resource
        #
        self._requests_served = 0

    def render_GET(self, request):
        # we produce JSON: set correct response content type
        #
        # note: both args to request.setHeader are supposed to be byte strings
        # https://twistedmatrix.com/documents/current/api/twisted.web.http.Request.html#setHeader
        #
        request.setHeader(b'content-type', b'application/json; charset=utf8-8')

        # set response headers for cross-origin requests
        #
        if self._allow_cross_origin:
            origin = request.getHeader(b'origin')
            if origin is None or origin == b'null':
                origin = b'*'
            request.setHeader(b'access-control-allow-origin', origin)
            request.setHeader(b'access-control-allow-credentials', b'true')

            headers = request.getHeader(b'access-control-request-headers')
            if headers is not None:
                request.setHeader(b'access-control-allow-headers', headers)

        # set response headers to disallow caching
        #
        if self._discourage_caching:
            request.setHeader(b'cache-control', b'no-store, no-cache, must-revalidate, max-age=0')

        self._requests_served += 1
        if self._requests_served % 10000 == 0:
            self.log.debug("Served {requests_served} requests", requests_served=self._requests_served)

        return self._data


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
        self._uploadRoot = FilePath(upload_directory)
        self._tempDirRoot = FilePath(temp_directory)
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
        for fileTempDir in self._tempDirRoot.children():
            fileTempName = fileTempDir.basename()
            if fileTempDir.isdir():
                self._uploads[fileTempName] = {'chunk_list': [], 'origin': 'startup'}
                for chunk in fileTempDir.listdir():
                    if chunk[:6] == 'chunk_':
                        self._uploads[fileTempName]['chunk_list'].append(int(chunk[6:]))
                    else:
                        fileTempDir.child(chunk).remove()
                # if no chunks detected then remove remains completely
                if len(self._uploads[fileTempName]['chunk_list']) == 0:
                    fileTempDir.remove()
                    self._uploads.pop(fileTempName, None)
            else:  # fileTempDir is a file remaining from a single chunk upload
                fileTempDir.remove()

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
        #         if self._debug:
        #             log.msg(msg)
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
            self.log.debug('Will try to resume upload of file: file_name={file_name}, total_size={total_size}, total_chunks={total_chunks}, chunk_size={chunk_size}, chunk_number={chunk_number}',
                           file_name=fileId, total_size=totalSize, total_chunks=totalChunks, chunk_size=chunkSize, chunk_number=chunkNumber)
            # If the chunks are read at startup of crossbar any client may claim and resume the pending upload !
            #
            upl = self._uploads[fileId]
            if upl['origin'] == 'startup':
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
                        # 409 Conflict
                        request.setResponseCode(409, msg.encode('utf8'))
                        return msg.encode('utf8')

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
        fileTempDir = self._tempDirRoot.child(fileId)
        chunkName = fileTempDir.child('chunk_' + str(chunkNumber))
        _chunkName = fileTempDir.child('#kfhf3kz412uru578e38viokbjhfvz4w__' + 'chunk_' + str(chunkNumber))

        if chunk_is_first:
            # first chunk of file

            # publish file upload start
            #
            fileupload_publish({
                               "id": fileId,
                               "chunk": chunkNumber,
                               "name": filename,
                               "total": totalSize,
                               "remaining": totalSize,
                               "status": "started",
                               "progress": 0.,
                               "chunk_extra": chunk_extra
                               })

            if totalChunks == 1:
                # only one chunk overall -> write file directly
                finalFileName = self._uploadRoot.child(fileId)
                _finalFileName = self._tempDirRoot.child('#kfhf3kz412uru578e38viokbjhfvz4w__' + fileId)

                with open(_finalFileName.path, 'wb') as _finalFile:
                    _finalFile.write(fileContent)

                self._uploads[fileId]['chunk_list'].append(chunkNumber)

                if self._file_permissions:
                    perm = int(self._file_permissions, 8)
                    try:
                        _finalFileName.chmod(perm)
                    except Exception as e:
                        # finalFileName.remove()
                        msg = "Could not change file permissions of uploaded file"
                        self.log.debug(msg)
                        self.log.debug(e)
                        request.setResponseCode(500, msg.encode('utf8'))
                        return msg.encode('utf8')
                    else:
                        self.log.debug("Changed permissions on {file_name} to {permissions}", file_name=finalFileName, permissions=self._file_permissions)

                _finalFileName.moveTo(finalFileName)

                # publish file upload progress to file_progress_URI
                fileupload_publish({
                                   "id": fileId,
                                   "chunk": chunkNumber,
                                   "name": filename,
                                   "total": totalSize,
                                   "remaining": 0,
                                   "status": "finished",
                                   "progress": 1.,
                                   "finish_extra": finish_extra,
                                   "chunk_extra": chunk_extra
                                   })

                self._uploads.pop(fileId, None)

            else:
                # first of more chunks
                # fileTempDir.remove()  # any potential conflict should have been resolved above. This should not be necessary!
                if not os.path.isdir(fileTempDir.path):
                    fileTempDir.makedirs()

                with open(_chunkName.path, 'wb') as chunk:
                    chunk.write(fileContent)
                _chunkName.moveTo(chunkName)  # atomic file system operation

                self._uploads[fileId]['chunk_list'].append(chunkNumber)

                # publish file upload progress
                #
                fileupload_publish({
                                   "id": fileId,
                                   "chunk": chunkNumber,
                                   "name": filename,
                                   "total": totalSize,
                                   "remaining": totalSize - chunkSize,
                                   "status": "progress",
                                   "progress": round(float(chunkSize) / float(totalSize), 3),
                                   "chunk_extra": chunk_extra
                                   })

            # clean the temp dir once per file upload
            self._remove_stale_uploads()

        else:
            # intermediate chunk
            if not os.path.isdir(fileTempDir.path):
                fileTempDir.makedirs()

            with open(_chunkName.path, 'wb') as chunk:
                chunk.write(fileContent)
            _chunkName.moveTo(chunkName)

            self._uploads[fileId]['chunk_list'].append(chunkNumber)

            received = sum(fileTempDir.child(f).getsize() for f in fileTempDir.listdir())

            fileupload_publish({
                               "id": fileId,
                               "chunk": chunkNumber,
                               "name": filename,
                               "total": totalSize,
                               "remaining": totalSize - received,
                               "status": "progress",
                               "progress": round(float(received) / float(totalSize), 3),
                               "chunk_extra": chunk_extra
                               })

            # every chunk has to check if it is the last chunk written, except in a single chunk scenario
            if totalChunks > 1 and len(self._uploads[fileId]['chunk_list']) == totalChunks:
                # last chunk
                self.log.debug('Finished file upload after chunk {chunk_number}', chunk_number=chunkNumber)

                # Merge all files into one file and remove the temp files
                # TODO: How to avoid the extra file IO ?
                finalFileName = self._uploadRoot.child(fileId)
                _finalFileName = fileTempDir.child('#kfhf3kz412uru578e38viokbjhfvz4w__' + fileId)
                with open(_finalFileName.path, 'wb') as _finalFile:
                    for cn in range(1, totalChunks + 1):
                        with open(fileTempDir.child('chunk_' + str(cn)).path, 'rb') as ff:
                            _finalFile.write(ff.read())

                _finalFileName.moveTo(finalFileName)

                if self._file_permissions:
                    perm = int(self._file_permissions, 8)
                    try:
                        finalFileName.chmod(perm)
                    except Exception as e:
                        msg = "file upload resource - could not change file permissions of uploaded file"
                        self.log.debug(msg)
                        self.log.debug(e)
                        self._uploads.pop(fileId, None)
                        request.setResponseCode(500, msg.encode('utf8'))
                        return msg.encode('utf8')
                    else:
                        self.log.debug("Changed permissions on {file_name} to {permissions}", file_name=finalFileName, permissions=self._file_permissions)

                # publish file upload progress to file_progress_URI
                fileupload_publish({
                                   "id": fileId,
                                   "chunk": chunkNumber,
                                   "name": filename,
                                   "total": totalSize,
                                   "remaining": 0,
                                   "status": "finished",
                                   "progress": 1.,
                                   "finish_extra": finish_extra,
                                   "chunk_extra": chunk_extra
                                   })

                # remove the file temp folder
                fileTempDir.remove()

                self._uploads.pop(fileId, None)

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
        for fileTempDir in self._tempDirRoot.children():
            if fileTempDir.isdir() and fileTempDir.basename() not in self._uploads:
                fileTempDir.remove()

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


class Resource404(Resource):

    """
    Custom error page (404).
    """

    def __init__(self, templates, directory):
        Resource.__init__(self)
        self._page = templates.get_template('cb_web_404.html')
        self._directory = native_string(directory)

    def render_GET(self, request):
        request.setResponseCode(NOT_FOUND)

        s = self._page.render(cbVersion=crossbar.__version__,
                              directory=self._directory)
        return s.encode('utf8')

    def render_HEAD(self, request):
        request.setResponseCode(NOT_FOUND)
        return b''


class RedirectResource(Resource):

    isLeaf = True

    def __init__(self, redirect_url):
        Resource.__init__(self)
        self._redirect_url = redirect_url

    def render_GET(self, request):
        request.redirect(self._redirect_url)
        request.finish()
        return server.NOT_DONE_YET


class StaticResource(File):
    """
    Resource for static assets from file system.
    """

    def __init__(self, *args, **kwargs):
        self._cache_timeout = kwargs.pop('cache_timeout', None)
        File.__init__(self, *args, **kwargs)

    def render_GET(self, request):
        if self._cache_timeout is not None:
            request.setHeader(b'cache-control', u'max-age={}, public'.format(self._cache_timeout).encode('utf8'))
            request.setHeader(b'expires', http.datetimeToString(time.time() + self._cache_timeout))

        return File.render_GET(self, request)

    def createSimilarFile(self, *args, **kwargs):
        #
        # File.getChild uses File.createSimilarFile to make a new resource of the same class to serve actual files under
        # a directory. We need to override that to also set the cache timeout on the child.
        #

        similar_file = File.createSimilarFile(self, *args, **kwargs)

        # need to manually set this - above explicitly enumerates constructor args
        similar_file._cache_timeout = self._cache_timeout

        return similar_file


class StaticResourceNoListing(StaticResource):
    """
    A file hierarchy resource with directory listing disabled.
    """

    def directoryListing(self):
        return self.childNotFound


if _HAS_CGI:

    class CgiScript(CGIScript):

        def __init__(self, filename, filter):
            CGIScript.__init__(self, filename)
            self.filter = filter

        def runProcess(self, env, request, qargs=[]):
            p = CGIProcessProtocol(request)
            from twisted.internet import reactor
            reactor.spawnProcess(p, self.filter, [self.filter, self.filename], env, os.path.dirname(self.filename))

    class CgiDirectory(Resource, FilePath):

        cgiscript = CgiScript

        def __init__(self, pathname, filter, childNotFound=None):
            Resource.__init__(self)
            FilePath.__init__(self, pathname)
            self.filter = filter
            if childNotFound:
                self.childNotFound = childNotFound
            else:
                self.childNotFound = NoResource("CGI directories do not support directory listing.")

        def getChild(self, path, request):
            fnp = self.child(path)
            if not fnp.exists():
                return File.childNotFound
            elif fnp.isdir():
                return CgiDirectory(fnp.path, self.filter, self.childNotFound)
            else:
                return self.cgiscript(fnp.path, self.filter)
            return NoResource()

        def render(self, request):
            return self.childNotFound.render(request)


class WampLongPollResourceSession(longpoll.WampLongPollResourceSession):

    def __init__(self, parent, transport_details):
        longpoll.WampLongPollResourceSession.__init__(self, parent, transport_details)
        self._transport_info = {
            'type': 'longpoll',
            'protocol': transport_details['protocol'],
            'peer': transport_details['peer'],
            'http_headers_received': transport_details['http_headers_received'],
            'http_headers_sent': transport_details['http_headers_sent']
        }
        self._cbtid = None


class WampLongPollResource(longpoll.WampLongPollResource):

    protocol = WampLongPollResourceSession
    log = make_logger()

    def getNotice(self, peer, redirectUrl=None, redirectAfter=0):
        try:
            page = self._templates.get_template('cb_lp_notice.html')
            content = page.render(redirectUrl=redirectUrl,
                                  redirectAfter=redirectAfter,
                                  cbVersion=crossbar.__version__,
                                  peer=peer,
                                  workerPid=os.getpid())
            content = content.encode('utf8')
            return content
        except Exception:
            self.log.failure("Error rendering LongPoll notice page template: {failure}")


class SchemaDocResource(Resource):

    isLeaf = True

    def __init__(self, templates, realm, schemas=None):
        Resource.__init__(self)
        self._templates = templates
        self._realm = realm
        self._schemas = schemas or {}

    def render_GET(self, request):
        request.setHeader(b'content-type', b'text/html; charset=UTF-8')
        page = self._templates.get_template('cb_schema_overview.html')
        content = page.render(realm=self._realm, schemas=self._schemas)
        return content.encode('utf8')
