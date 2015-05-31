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
import cgi
import os, os.path

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

    def __init__(self, fileupload_directory='', temp_dir='..', max_file_size=1024 * 1024 * 100, mime_types='', file_types='', file_progress_URI=''):
        Resource.__init__(self)
        self.max_file_size = max_file_size
        self.dir = fileupload_directory
        self.tempDir = temp_dir
        self.mimeTypes = mime_types
        self.fileTypes = file_types
        self.fileProgressURI = file_progress_URI

    def render_POST(self, request):
        # request.setHeader(b'content-type', b'text/text; charset=UTF-8')
        log.msg( 'file uploads --------POST--------')
        headers = request.getAllHeaders()
        log.msg(json.dumps(headers))

        content = cgi.FieldStorage(
        fp = request.content,
        headers = headers,
        environ = {'REQUEST_METHOD':'POST',
                 'CONTENT_TYPE': headers['content-type'],
                 }
        )

        fileId = content['resumableIdentifier'].value
        chunkNumber = int(content['resumableChunkNumber'].value)
        chunkSize = int(content['resumableChunkSize'].value)
        cchunkSize = int(content['resumableCurrentChunkSize'].value)
        totalSize = int(content['resumableTotalSize'].value)
        fileType = content['resumableType'].value
        filename = content['resumableFilename'].value
        relPath = content['resumableRelativePath'].value
        totalChunks = int(content['resumableTotalChunks'].value)
        fileContent = content['file'].value

        print fileId,chunkNumber, chunkSize, cchunkSize, totalSize, fileType, filename, relPath, totalChunks

        # check request header for file upload
        # check file size
        print 'max file size', self.max_file_size, 'total', totalChunks

        if int(totalSize) > self.max_file_size: 
            print 'what??'
            request.setResponseCode(500)
            return 'max filesize exceeded'


        # check mime type
        # check file name suffix (file type)

        # if first of many chunks: create temp file in temp_dir for uncomplete uploads.
        fileTempDir = os.path.join(self.tempDir,fileId)
        chunkName = os.path.join(fileTempDir, 'chunk_' + str(chunkNumber))
        print fileTempDir
        if not (os.path.exists(os.path.join(self.tempDir, fileId)) or os.path.exists(fileTempDir)):
            # first chunk of file
            # publish file upload start to file_progress_URI     
            if totalChunks == 1: 
                print 'doing first and only chunk'
                # only on chunk overall
                # write file directly
                chunk = open(os.path.join(self.dir, fileId), 'wb') 
                chunk.write(fileContent)
                chunk.close
            else:
                print 'doing first of more chunks'
                # first of more chunks
                os.makedirs(fileTempDir)
                chunk = open(chunkName, 'wb') 
                chunk.write(fileContent)
                chunk.close
            # publish file upload progress to file_progress_URI
        
        else:
            numExistingChunks = len(os.listdir(fileTempDir))
            # intermediate chunk
            print 'intermediate chunk' + str(chunkNumber) + ' of existing ' + str(numExistingChunks)
            chunk = open(chunkName, 'wb') 
            chunk.write(fileContent)
            chunk.close 

            if numExistingChunks == totalChunks - 1:
                # last chunk
                print 'last chunk' + str(chunkNumber)
                chunk = open(chunkName, 'wb') 
                chunk.write(fileContent)
                chunk.close  

                # Now merge all files into one file and remove the temp files
                finalFile = open(os.path.join(self.dir, fileId), 'wb')
                for tfileName in os.listdir(fileTempDir):
                    print 'the temp file list name' + tfileName
                    tfile = open(os.path.join(fileTempDir, tfileName),'r')
                    finalFile.write( tfile.read())
                finalFile.close()                
                # publish file upload progress to file_progress_URI                        
                # remove the file temp folder
                for tfileName in os.listdir(fileTempDir):
                    os.remove(os.path.join(fileTempDir, tfileName))
                os.rmdir(fileTempDir)

        # if middle chunk:
        # publish file upload progress to file_progress_URI

        # if last or single chunk: create file_name for finished file
        # move uploaded file to fileupload_directory
        # publish file complete to file_progress_URI

        # compile request return (for POST not required !?)

        #     print img["upl_file"].name, img["upl_file"].filename,
        #     print img["upl_file"].type, img["upl_file"].type
        #     out = open(img["upl_file"].filename, 'wb')
        #     out.write(img["upl_file"].value)
        #     out.close()
        #     request.redirect('/tests')
        request.setResponseCode(200)


    def render_GET(self, request):
        """
        This method is used by resumable.js to check wether a chunk has been uploaded already.
        It returns Status 200 if yes and something else if not.
        """
        request.setHeader(b'content-type', b'text/text; charset=UTF-8')
        request.setResponseCode(400)
       
        # log.msg(request.path)
        log.msg( 'file uploads --------GET--------')
        log.msg(json.dumps(request.args))
        # request.write('this is a test')
        # for key, records in request.files.iteritems():
        #     print key
        #     for record in records:
        #         name, mime, stream = record
        #         data = stream.read()
        #         print '   %s %s %s %r' % (name, mime, stream, data)

        return json.dumps(request.args)


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
