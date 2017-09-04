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
import time

from twisted.web import http, server
from twisted.web.http import NOT_FOUND
from twisted.web.resource import Resource, NoResource
from twisted.web.static import File
from twisted.python.filepath import FilePath

from txaio import make_logger

import crossbar
from crossbar._compat import native_string
from crossbar.router import longpoll

try:
    # triggers module level reactor import
    # https://twistedmatrix.com/trac/ticket/6849#comment:5
    from twisted.web.twcgi import CGIScript, CGIProcessProtocol
    _HAS_CGI = True
except (ImportError, SyntaxError):
    # Twisted hasn't ported this to Python 3 yet
    _HAS_CGI = False


def set_cross_origin_headers(request):
    origin = request.getHeader(b'origin')
    if origin is None or origin == b'null':
        origin = b'*'
    request.setHeader(b'access-control-allow-origin', origin)
    request.setHeader(b'access-control-allow-credentials', b'true')

    headers = request.getHeader(b'access-control-request-headers')
    if headers is not None:
        request.setHeader(b'access-control-allow-headers', headers)


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
            set_cross_origin_headers(request)

        # set response headers to disallow caching
        #
        if self._discourage_caching:
            request.setHeader(b'cache-control', b'no-store, no-cache, must-revalidate, max-age=0')

        self._requests_served += 1
        if self._requests_served % 10000 == 0:
            self.log.debug("Served {requests_served} requests", requests_served=self._requests_served)

        return self._data


class Resource404(Resource):
    """
    Custom error page (404).
    """

    def __init__(self, templates, directory):
        Resource.__init__(self)
        self._page = templates.get_template('cb_web_404.html')
        self._directory = native_string(directory)
        self._pid = u'{}'.format(os.getpid())

    def render_GET(self, request):
        request.setResponseCode(NOT_FOUND)

        try:
            peer = request.transport.getPeer()
            peer = u'{}:{}'.format(peer.host, peer.port)
        except:
            peer = u'?:?'

        s = self._page.render(cbVersion=crossbar.__version__,
                              directory=self._directory,
                              workerPid=self._pid,
                              peer=peer)

        return s.encode('utf8')

    def render_HEAD(self, request):
        request.setResponseCode(NOT_FOUND)
        return b''


class NodeInfoResource(Resource):
    """
    Node information page.
    """

    isLeaf = True

    def __init__(self, templates, controller_session):
        Resource.__init__(self)
        self._page = templates.get_template('cb_node_info.html')
        self._pid = u'{}'.format(os.getpid())
        self._controller_session = controller_session

    def _delayedRender(self, node_info, request):
        try:
            peer = request.transport.getPeer()
            peer = u'{}:{}'.format(peer.host, peer.port)
        except:
            peer = u'?:?'

        s = self._page.render(cbVersion=crossbar.__version__,
                              workerPid=self._pid,
                              peer=peer,
                              **node_info)

        request.write(s.encode('utf8'))
        request.finish()

    def render_GET(self, request):
        # http://twistedmatrix.com/documents/current/web/howto/web-in-60/asynchronous-deferred.html
        d = self._controller_session.call(u'crossbar.get_status')
        d.addCallback(self._delayedRender, request)
        return server.NOT_DONE_YET


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
        self._allow_cross_origin = kwargs.pop('allow_cross_origin', True)
        File.__init__(self, *args, **kwargs)

    def render_GET(self, request):
        if self._cache_timeout is not None:
            request.setHeader(b'cache-control', u'max-age={}, public'.format(self._cache_timeout).encode('utf8'))
            request.setHeader(b'expires', http.datetimeToString(time.time() + self._cache_timeout))

        # set response headers for cross-origin requests
        #
        if self._allow_cross_origin:
            set_cross_origin_headers(request)

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
            u'type': 'longpoll',
            u'protocol': transport_details['protocol'],
            u'peer': transport_details['peer'],
            u'http_headers_received': transport_details['http_headers_received'],
            u'http_headers_sent': transport_details['http_headers_sent']
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
            self.log.failure("Error rendering LongPoll notice page template: {log_failure.value}")


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
