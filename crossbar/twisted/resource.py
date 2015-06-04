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

from twisted.python import log, compat
from twisted.web import http
from twisted.web.http import NOT_FOUND
from twisted.web.resource import Resource, NoResource
from twisted.web import server

from autobahn.twisted import longpoll
from autobahn.wamp.types import PublishOptions

import crossbar

try:
    # triggers module level reactor import
    # https://twistedmatrix.com/trac/ticket/6849#comment:4
    from twisted.web.static import File
    _HAS_STATIC = True
except ImportError:
    # Twisted hasn't ported this to Python 3 yet
    _HAS_STATIC = False


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

    def __init__(self, value):
        Resource.__init__(self)
        self._data = json.dumps(value, sort_keys=True, indent=3)

    def render_GET(self, request):
        request.setHeader(b'content-type', b'application/json; charset=UTF-8')
        return self._data


class FileUploadResource(Resource):

    """
    Twisted Web resource that handles file uploads over `HTTP/POST` requests.
    """

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
        self._dir = upload_directory
        self._tempDir = temp_directory
        self._form_fields = form_fields
        self._fileupload_session = upload_session
        self._options = options or {}
        self._debug = self._options.get('debug', False)
        self._max_file_size = self._options.get('max_file_size', 10 * 1024 * 1024)
        self._fileTypes = self._options.get('file_types', None)
        self._file_permissions = self._options.get('file_permissions', None)

        # track uploaded files / chunks
        self._uploads = {}

    def render_POST(self, request):
        headers = request.getAllHeaders()

        # FIXME: this is a hack
        origin = headers['host'].replace(".", "_").replace(":", "-").replace("/", "_")

        content = cgi.FieldStorage(
            fp=request.content,
            headers=headers,
            environ={'REQUEST_METHOD': 'POST',
                     'CONTENT_TYPE': headers['content-type']})

        f = self._form_fields
        fileId = content[f['file_id']].value
        filename = content[f['file_name']].value
        totalSize = int(content[f['total_size']].value)
        totalChunks = int(content[f['total_chunks']].value)
        chunkSize = int(content[f['chunk_size']].value)
        chunkNumber = int(content[f['chunk_number']].value)
        fileContent = content[f['content']].value

        if self._debug:
            log.msg('file upload resource - started upload of file: file_id={}, file_name={}, total_size={}, total_chunks={}, chunk_size={}, chunk_number={}'.format(fileId, filename, totalSize, totalChunks, chunkSize, chunkNumber))

        if 'on_progress' in f and f['on_progress'] in content and self._fileupload_session != {}:
            topic = content[f['on_progress']].value

            if 'session' in f and f['session'] in content:
                session = int(content[f['session']].value)
                publish_options = PublishOptions(eligible=[session])
            else:
                publish_options = None

            def fileupload_publish(payload):
                self._fileupload_session.publish(topic, payload, options=publish_options)
        else:
            def fileupload_publish(payload):
                pass

        # check file size
        #
        if totalSize > self._max_file_size:
            msg = "file upload resource - size {} of file to be uploaded exceeds maximum {}".format(totalSize, self._max_file_size)
            if self._debug:
                log.msg(msg)
            # 413 Request Entity Too Large
            request.setResponseCode(413, msg)
            return msg

        # check file extensions
        #
        extension = os.path.splitext(filename)[1]
        if self._fileTypes and extension not in self._fileTypes:
            msg = "file upload resource - type '{}' of file to be uploaded is in allowed types {}".format(extension, self._fileTypes)
            if self._debug:
                log.msg(msg)
            # 415 Unsupported Media Type
            request.setResponseCode(415, msg)
            return msg

        # FIXME: this is a hack
        # check if another session is uploading this file already
        #
        for e in os.listdir(self._tempDir):
            common_id = e[0:e.find("#")]
            existing_origin = e[e.find("#") + 1:]
            if common_id == fileId + '_orig' and existing_origin != origin:
                msg = "file upload resource - file being uploaded is already uploaded in a different session"
                if self._debug:
                    log.msg(msg)
                # 409 Conflict
                request.setResponseCode(409, msg)
                return msg

        # TODO: check mime type

        fileTempDir = os.path.join(self._tempDir, fileId + '_orig#' + origin)
        chunkName = os.path.join(fileTempDir, 'chunk_' + str(chunkNumber))

        if not (os.path.exists(os.path.join(self._dir, fileId)) or os.path.exists(fileTempDir)):
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
                               "progress": 0.
                               })

            if totalChunks == 1:
                # only one chunk overall -> write file directly
                finalFileName = os.path.join(self._dir, fileId)
                with open(finalFileName, 'wb') as finalFile:
                    finalFile.write(fileContent)

                if self._file_permissions:
                    perm = int(self._file_permissions, 8)
                    try:
                        os.chmod(finalFileName, perm)
                    except Exception as e:
                        os.remove(finalFileName)
                        msg = "file upload resource - could not change file permissions of uploaded file"
                        if self._debug:
                            log.msg(msg)
                            log.msg(e)
                        request.setResponseCode(500, msg)
                        return msg

                # publish file upload progress to file_progress_URI
                fileupload_publish({
                                   "id": fileId,
                                   "chunk": chunkNumber,
                                   "name": filename,
                                   "total": totalSize,
                                   "remaining": 0,
                                   "status": "finished",
                                   "progress": 1.
                                   })
            else:
                # first of more chunks
                os.makedirs(fileTempDir)
                with open(chunkName, 'wb') as chunk:
                    chunk.write(fileContent)

                # publish file upload progress
                #
                fileupload_publish({
                                   "id": fileId,
                                   "chunk": chunkNumber,
                                   "name": filename,
                                   "total": totalSize,
                                   "remaining": totalSize - chunkSize,
                                   "status": "progress",
                                   "progress": round(float(chunkSize) / float(totalSize), 3)
                                   })

        else:
            # intermediate chunk
            with open(chunkName, 'wb') as chunk:
                chunk.write(fileContent)

            received = sum(os.path.getsize(os.path.join(fileTempDir, f)) for f in os.listdir(fileTempDir))

            fileupload_publish({
                               "id": fileId,
                               "chunk": chunkNumber,
                               "name": filename,
                               "total": totalSize,
                               "remaining": totalSize - received,
                               "status": "progress",
                               "progress": round(float(received) / float(totalSize), 3)
                               })

            if chunkNumber == totalChunks:
                # last chunk
                with open(chunkName, 'wb') as chunk:
                    chunk.write(fileContent)

                # Now merge all files into one file and remove the temp files
                with open(os.path.join(self._dir, fileId), 'wb') as finalFile:
                    for tfileName in os.listdir(fileTempDir):
                        with open(os.path.join(fileTempDir, tfileName), 'r') as tfile:
                            finalFile.write(tfile.read())

                if self._file_permissions:
                    perm = int(self._file_permissions, 8)
                    try:
                        os.chmod(finalFileName, perm)
                    except Exception as e:
                        self._remove_temp_dir(fileTempDir)
                        msg = "file upload resource - could not change file permissions of uploaded file"
                        if self._debug:
                            log.msg(msg)
                            log.msg(e)
                        request.setResponseCode(500, msg)
                        return msg

                # publish file upload progress to file_progress_URI

                fileupload_publish({
                                   "id": fileId,
                                   "chunk": chunkNumber,
                                   "name": filename,
                                   "total": totalSize,
                                   "remaining": 0,
                                   "status": "finished",
                                   "progress": 1.
                                   })

                # remove the file temp folder
                self._remove_temp_dir(fileTempDir)

        request.setResponseCode(200)
        return ''

    def _remove_temp_dir(self, fileTempDir):
        return
        for tfileName in os.listdir(fileTempDir):
            os.remove(os.path.join(fileTempDir, tfileName))

        os.rmdir(fileTempDir)

    def render_GET(self, request):
        """
        This method can be used to check wether a chunk has been uploaded already.
        It returns with HTTP status code `200` if yes and `404` if not.
        The request needs to contain the file identifier and the chunk number to check for.
        """
        for param in ['file_id', 'chunk_number']:
            if not self._form_fields[param] in request.args:
                msg = "file upload resource - missing request query parameter '{}', configured from '{}'".format(self._form_fields[param], param)
                if self._debug:
                    log.msg(msg)
                # 400 Bad Request
                request.setResponseCode(400, msg)
                return msg

        file_id = request.args[self._form_fields['file_id']][0]
        chunk_number = request.args[self._form_fields['chunk_number']][0]
        origin = request.getHeader('host')[0]
        origin = origin.replace(".", "_").replace(":", "-").replace("/", "_")

        fileTempDir = os.path.join(self._tempDir, file_id + '_orig#' + origin)
        chunkName = os.path.join(fileTempDir, 'chunk_' + str(chunk_number))

        if (os.path.exists(chunkName) or os.path.exists(os.path.join(self._dir, file_id))):
            msg = "chunk of file already uploaded"
            request.setResponseCode(200, msg)
            return msg
        else:
            msg = "chunk of file not yet uploaded"
            request.setResponseCode(404, msg)
            return msg


class Resource404(Resource):

    """
    Custom error page (404).
    """

    def __init__(self, templates, directory):
        Resource.__init__(self)
        self._page = templates.get_template('cb_web_404.html')
        self._directory = compat.nativeString(directory)

    def render_GET(self, request):
        request.setResponseCode(NOT_FOUND)

        s = self._page.render(cbVersion=crossbar.__version__,
                              directory=self._directory)
        return s.encode('utf8')


class RedirectResource(Resource):

    isLeaf = True

    def __init__(self, redirect_url):
        Resource.__init__(self)
        self._redirect_url = redirect_url

    def render_GET(self, request):
        request.redirect(self._redirect_url)
        request.finish()
        return server.NOT_DONE_YET


if _HAS_STATIC:

    class StaticResource(File):

        """
        Resource for static assets from file system.
        """

        def __init__(self, *args, **kwargs):
            self._cache_timeout = kwargs.pop('cache_timeout', None)

            File.__init__(self, *args, **kwargs)

        def render_GET(self, request):
            if self._cache_timeout is not None:
                request.setHeader(b'cache-control', 'max-age={}, public'.format(self._cache_timeout))
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

    from twisted.python.filepath import FilePath

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
        except Exception as e:
            log.msg("Error rendering LongPoll notice page template: {}".format(e))


class SchemaDocResource(Resource):

    """
    """

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
