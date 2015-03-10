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

from twisted.python import log
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
    # trigers module level reactor import
    # https://twistedmatrix.com/trac/ticket/6849#comment:5
    from twisted.web.twcgi import CGIScript, CGIProcessProtocol
    _HAS_CGI = True
except ImportError:
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
        request.setHeader('content-type', 'application/json; charset=UTF-8')
        return self._data


class Resource404(Resource):

    """
    Custom error page (404).
    """

    def __init__(self, templates, directory):
        Resource.__init__(self)
        self._page = templates.get_template('cb_web_404.html')
        self._directory = directory

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
                request.setHeader('cache-control', 'max-age={}, public'.format(self._cache_timeout))
                request.setHeader('expires', http.datetimeToString(time.time() + self._cache_timeout))

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
        request.setHeader('content-type', 'text/html; charset=UTF-8')
        page = self._templates.get_template('cb_schema_overview.html')
        content = page.render(realm=self._realm, schemas=self._schemas)
        return content.encode('utf8')
