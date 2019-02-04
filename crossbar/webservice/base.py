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
import importlib

import txaio

from twisted.web import server
from twisted.web._responses import NOT_FOUND
from twisted.web.resource import Resource
from twisted.web.proxy import ReverseProxyResource
from twisted.web.static import File

from autobahn.wamp.exception import ApplicationError

import crossbar


def set_cross_origin_headers(request):
    origin = request.getHeader(b'origin')
    if origin is None or origin == b'null':
        origin = b'*'
    request.setHeader(b'access-control-allow-origin', origin)
    request.setHeader(b'access-control-allow-credentials', b'true')

    headers = request.getHeader(b'access-control-request-headers')
    if headers is not None:
        request.setHeader(b'access-control-allow-headers', headers)


class ResourceFallback(File):
    """
    Handle requests for non-existent URL's
    """
    def __init__(self, path, config, **kwargs):
        File.__init__(self, path, **kwargs)
        directory = config.get('directory', '')
        file = config.get('options', {}).get('default_file')
        self.path = os.path.join(directory, file)


class Resource404(Resource):
    """
    Custom error page (404) Twisted Web resource.
    """

    def __init__(self, templates, directory):
        Resource.__init__(self)
        self._page = templates.get_template('cb_web_404.html')
        self._directory = directory
        self._pid = u'{}'.format(os.getpid())

    def render_HEAD(self, request):
        request.setResponseCode(NOT_FOUND)
        return b''

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


class RouterWebService(object):
    """
    A Web service configured on a URL path on a Web transport.
    """

    log = txaio.make_logger()

    def __init__(self, transport, path, config=None, resource=None):
        # Web transport this Web service is attached to
        self._transport = transport

        # path on Web transport under which the Web service is attached
        self._path = path

        # configuration of the Web service (itself)
        self._config = config or dict(type='page404')

        # Twisted Web resource on self._path itself
        self._resource = resource or Resource404(self._transport._worker._templates)

        # RouterWebService children on subpaths
        self._paths = {}

    def __contains__(self, path):
        return path in self._paths

    def __getitem__(self, path):
        return self._paths.get(path, None)

    def __delitem__(self, path):
        if path in self._paths:
            deleted = self._paths[path]
            web_path = path.encode('utf8')
            if web_path in self._resource.children:
                del self._resource.children[web_path]
            del self._paths[path]
            return deleted

    def __setitem__(self, path, webservice):
        if path in self._paths:
            del self._paths[path]

        self._paths[path] = webservice
        web_path = path.encode('utf8')
        self._resource.putChild(web_path, webservice._resource)

    @property
    def path(self):
        return self._path

    @property
    def config(self):
        return self.config


class RouterWebServiceReverseWeb(RouterWebService):
    """
    Reverse Web proxy service.
    """

    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['reverseproxy'](personality, config)

        host = config['host']
        port = int(config.get('port', 80))
        base_path = config.get('path', '').encode('utf-8')

        resource = ReverseProxyResource(host, port, base_path)

        return RouterWebServiceReverseWeb(transport, base_path, config, resource)


class RedirectResource(Resource):
    """
    Redirecting Twisted Web resource.
    """

    isLeaf = True

    def __init__(self, redirect_url):
        Resource.__init__(self)
        self._redirect_url = redirect_url

    def render_GET(self, request):
        request.redirect(self._redirect_url)
        request.finish()
        return server.NOT_DONE_YET


class RouterWebServiceRedirect(RouterWebService):
    """
    Redirecting Web service.
    """

    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['redirect'](personality, config)

        redirect_url = config['url'].encode('ascii', 'ignore')
        resource = RedirectResource(redirect_url)

        return RouterWebServiceRedirect(transport, path, config, resource)


class RouterWebServiceTwistedWeb(RouterWebService):
    """
    Generic Twisted Web base service.
    """

    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['resource'](personality, config)

        klassname = config['classname']
        try:
            c = klassname.split('.')
            module_name, klass_name = '.'.join(c[:-1]), c[-1]
            module = importlib.import_module(module_name)
            make = getattr(module, klass_name)
            resource = make(config.get('extra', {}))
        except Exception as e:
            emsg = "Failed to import class '{}' - {}".format(klassname, e)
            raise ApplicationError(u"crossbar.error.class_import_failed", emsg)

        return RouterWebServiceTwistedWeb(transport, path, config, resource)


class RouterWebServiceNestedPath(RouterWebService):
    """
    Nested sub-URL path (pseudo-)service.
    """

    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['path'](personality, config)

        nested_paths = config.get('paths', {})

        if '/' in nested_paths:
            resource = personality.create_web_service(personality, transport.worker._reactor, nested_paths['/'], transport.templates, transport.cbdir)
        else:
            resource = Resource404(transport.templates, b'')

        # nest subpaths under the current entry
        #
        # personality.add_web_services(personality, reactor, nested_resource, nested_paths, templates, log, cbdir, _router_session_factory, node)

        return RouterWebServiceNestedPath(transport, path, config, resource)
