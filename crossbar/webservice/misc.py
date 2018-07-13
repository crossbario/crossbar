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

import json
import os

from twisted.python.filepath import FilePath
from twisted.internet import reactor
from twisted.web import server
from twisted.web.resource import Resource, NoResource
from twisted.web.static import File
from twisted.web.twcgi import CGIScript, CGIProcessProtocol

import crossbar
from crossbar.webservice.base import RouterWebService, Resource404, set_cross_origin_headers


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


class RouterWebServiceNodeInfo(RouterWebService):
    """
    Node information page service.
    """

    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['nodeinfo'](personality, config)

        resource = NodeInfoResource(transport.templates, transport.worker)

        return RouterWebServiceNodeInfo(transport, path, config, resource)


class JsonResource(Resource):
    """
    Static Twisted Web resource that renders to a JSON document.
    """

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


class RouterWebServiceJson(RouterWebService):
    """
    JSON static value Web service.
    """

    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['json'](personality, config)

        value = config['value']

        resource = JsonResource(value)

        return RouterWebServiceJson(transport, path, config, resource)


class CgiScript(CGIScript):

    def __init__(self, filename, filter):
        CGIScript.__init__(self, filename)
        self.filter = filter

    def runProcess(self, env, request, qargs=[]):
        p = CGIProcessProtocol(request)
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

    def render(self, request):
        return self.childNotFound.render(request)


class RouterWebServiceCgi(RouterWebService):
    """
    CGI script Web service.
    """

    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['cgi'](personality, config)

        cgi_processor = config['processor']
        cgi_directory = os.path.abspath(os.path.join(transport.cbdir, config['directory']))
        # http://stackoverflow.com/a/20433918/884770
        cgi_directory = cgi_directory.encode('ascii', 'ignore')

        resource = CgiDirectory(cgi_directory, cgi_processor, Resource404(transport.templates, cgi_directory))

        return RouterWebServiceCgi(transport, path, config, resource)
