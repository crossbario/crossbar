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
    Twisted Web resource that handles file uploads over HTTP post requests.
    """

    def __init__(self,
                 file_permissions,
                 fileupload_session,
                 form_fields,
                 fileupload_directory='',
                 temp_dir='..',
                 max_file_size=1024 * 1024 * 100,
                 file_types=[]):

        Resource.__init__(self)
        self._max_file_size = max_file_size
        self._dir = fileupload_directory
        self._tempDir = temp_dir
        self._fileTypes = file_types
        self._form_fields = form_fields
        self._file_permissions = file_permissions
        self._fileupload_session = fileupload_session

    def render_POST(self, request):
        headers = request.getAllHeaders()

        origin = headers['host'].replace(".", "_").replace(":", "-").replace("/", "_")
        content = cgi.FieldStorage(
            fp=request.content,
            headers=headers,
            environ={'REQUEST_METHOD': 'POST',
                     'CONTENT_TYPE': headers['content-type']})

        f = self._form_fields
        fileId = content[f['file_id']].value
        chunkNumber = int(content[f['chunk_number']].value)
        chunkSize = int(content[f['chunk_size']].value)
        totalSize = int(content[f['total_size']].value)
        filename = content[f['file_name']].value
        totalChunks = int(content[f['total_chunks']].value)
        fileContent = content[f['content']].value

        if 'progress_uri' in f and f['progress_uri'] in content and self._fileupload_session != {}:
            topic = content[f['progress_uri']].value
            def fileupload_publish(payload):
                    self._fileupload_session.publish(topic, *[payload], **{})
        else:
            def fileupload_publish(payload):
                return ''

        log.msg('--------Try POST File--------' + filename)

        # check file size

        if int(totalSize) > self._max_file_size:
            request.setResponseCode(500, "max filesize of " + self._max_file_size + " bytes exceeded.")
            return 'max filesize exceeded'

        # check file extensions

        extension = os.path.splitext(filename)[1]

        if extension not in self._fileTypes and len(self._fileTypes) > 0:
            request.setResponseCode(500, "File extension not accepted.")
            return 'file extension not accepted'

        # check if directories exist
        if not os.path.exists(self._dir) or not os.path.exists(self._tempDir):
                request.setResponseCode(500, "File upload directories are not accessible.")
                return "File upload directories are not accessible."

        # check if another session is uploading this file already

        for e in os.listdir(self._tempDir):
            common_id = e[0:e.find("#")]
            existing_origin = e[e.find("#") + 1:]
            if common_id == fileId + '_orig' and existing_origin != origin:
                request.setResponseCode(500, "Upload in progress in other session.")
                # Error has to be captured in the calling session. No need to publish.
                # self._fileupload_publish( {
                #     "fileId": fileId,
                #     "fileName": filename,
                #     "totalSize": totalSize,
                #     "status": "ERROR",
                #     "error_msg": "Upload in Progress in other session.",
                #     "progress": 0
                #     })
                return ''

        # TODO: check mime type

        fileTempDir = os.path.join(self._tempDir, fileId + '_orig#' + origin)
        chunkName = os.path.join(fileTempDir, 'chunk_' + str(chunkNumber))

        if not (os.path.exists(os.path.join(self._dir, fileId)) or os.path.exists(fileTempDir)):
            # first chunk of file

            # publish file upload start to file_progress_URI
            fileupload_publish({
                               "fileId": fileId,
                               "fileName": filename,
                               "totalSize": totalSize,
                               "status": "START",
                               "progress": 0
                               })

            if totalChunks == 1:
                # only one chunk overall -> write file directly
                finalFileName = os.path.join(self._dir, fileId)
                finalFile = open(finalFileName, 'wb')
                finalFile.write(fileContent)
                finalFile.close

                try:
                    perm = int(self._file_permissions, 8)
                    os.chmod(finalFileName, perm)

                except Exception as e:
                    request.setResponseCode(500, "File permissions could not be changed")
                    os.remove(finalFileName)
                    return ''

                # publish file upload progress to file_progress_URI
                fileupload_publish({
                                   "fileId": fileId,
                                   "fileName": filename,
                                   "totalSize": totalSize,
                                   "status": "FINISH",
                                   "progress": 1
                                   })
            else:
                # first of more chunks
                os.makedirs(fileTempDir)
                chunk = open(chunkName, 'wb')
                chunk.write(fileContent)
                chunk.close

                # publish file upload progress to file_progress_URI
                fileupload_publish({
                                   "fileId": fileId,
                                   "fileName": filename,
                                   "totalSize": totalSize,
                                   "status": "PROGRESS",
                                   "progress": chunkSize / float(totalSize)
                                   })

        else:
            # intermediate chunk
            chunk = open(chunkName, 'wb')
            chunk.write(fileContent)
            chunk.close

            prog = float(sum(os.path.getsize(os.path.join(fileTempDir, f)) for f in os.listdir(fileTempDir))) / totalSize

            fileupload_publish({
                               "fileId": fileId,
                               "fileName": filename,
                               "totalSize": totalSize,
                               "status": "PROGRESS",
                               "progress": prog
                               })

            if chunkNumber == totalChunks:
                # last chunk
                chunk = open(chunkName, 'wb')
                chunk.write(fileContent)
                chunk.close

                # Now merge all files into one file and remove the temp files
                finalFile = open(os.path.join(self._dir, fileId), 'wb')

                for tfileName in os.listdir(fileTempDir):
                    tfile = open(os.path.join(fileTempDir, tfileName), 'r')
                    finalFile.write(tfile.read())

                finalFile.close()

                try:
                    perm = int(self._file_permissions, 8)
                    os.chmod(finalFileName, perm)

                except Exception as e:
                    request.setResponseCode(500, "File permissions could not be changed")
                    self.removeTempDir(fileTempDir)
                    return ''

                # publish file upload progress to file_progress_URI

                fileupload_publish({
                                   "fileId": fileId,
                                   "fileName": filename,
                                   "totalSize": totalSize,
                                   "status": "FINISH",
                                   "progress": 1
                                   })

                # remove the file temp folder
                self.removeTempDir(fileTempDir)

        request.setResponseCode(200)
        return ''

    def removeTempDir(fileTempDir):
        for tfileName in os.listdir(fileTempDir):
            os.remove(os.path.join(fileTempDir, tfileName))

        os.rmdir(fileTempDir)

    def render_GET(self, request):
        """
        This method can be used to check wether a chunk has been uploaded already.
        It returns Status 200 if yes and something else if not.
        The request needs to contain the file identifier and the chunk number to check for.
        """
        # log.msg( 'file uploads --------GET--------')

        arg = request.args

        headers = request.getAllHeaders()
        origin = headers['host'].replace(".", "_").replace(":", "-").replace("/", "_")

        fileId = arg['resumableIdentifier'][0]
        chunkNumber = int(arg['resumableChunkNumber'][0])

        fileTempDir = os.path.join(self._tempDir, fileId + '_orig#' + origin)
        chunkName = os.path.join(fileTempDir, 'chunk_' + str(chunkNumber))

        if (os.path.exists(chunkName) or os.path.exists(os.path.join(self._dir, fileId))):
            request.setResponseCode(200, "Chunk of File already uploaded.")
            return 'chunk already uploaded'

        request.setResponseCode(404, "Chunk of file not yet uploaded.")

        return 'Chunk of file not yet uploaded.'


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

    def __init__(self, *args, **kwargs):
        longpoll.WampLongPollResourceSession.__init__(self, *args, **kwargs)
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
