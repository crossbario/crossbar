#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import importlib

import txaio

from twisted.internet.defer import inlineCallbacks, maybeDeferred
from twisted.web import server
from twisted.web._responses import NOT_FOUND
from twisted.web.resource import Resource
from twisted.web.proxy import ReverseProxyResource
from twisted.web.server import NOT_DONE_YET
from twisted.python.compat import urllib_parse, urlquote

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


class Resource404(Resource):
    """
    Custom error page (404) Twisted Web resource.
    """
    def __init__(self, templates, directory):
        Resource.__init__(self)
        self._page = templates.get_template('cb_web_404.html')
        self._directory = directory
        self._pid = '{}'.format(os.getpid())

    def render_HEAD(self, request):
        request.setResponseCode(NOT_FOUND)
        return b''

    def render_GET(self, request):
        request.setResponseCode(NOT_FOUND)

        try:
            peer = request.transport.getPeer()
            peer = '{}:{}'.format(peer.host, peer.port)
        except:
            peer = '?:?'

        s = self._page.render(cbVersion=crossbar.__version__,
                              directory=self._directory.decode('utf8'),
                              workerPid=self._pid,
                              peer=peer)

        return s.encode('utf8')


class RootResource(Resource):
    """
    Root resource when you want one specific resource be the default serving
    resource for a Twisted Web site, but have sub-paths served by different
    resources.
    """
    def __init__(self, rootResource, children):
        """

        :param rootResource: The resource to serve as root resource.
        :type rootResource: `twisted.web.resource.Resource <http://twistedmatrix.com/documents/current/api/twisted.web.resource.Resource.html>`_

        :param children: A dictionary with string keys constituting URL sub-paths, and Twisted Web resources as values.
        :type children: dict
        """
        Resource.__init__(self)
        self._rootResource = rootResource
        self.children = children

    def getChild(self, path, request):
        request.prepath.pop()
        request.postpath.insert(0, path)
        return self._rootResource


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
        return self._config

    @property
    def resource(self):
        return self._resource


class ExtReverseProxyResource(ReverseProxyResource):

    log = txaio.make_logger()

    def __init__(self, host, port, path, forwarded_port=None, forwarded_proto=None):
        # host:port/path => target server
        self._forwarded_port = forwarded_port
        self._forwarded_proto = forwarded_proto
        ReverseProxyResource.__init__(self, host, port, path)

    def render(self, request):
        """
        Render a request by forwarding it to the proxied server.
        """
        self.log.info('{klass}.render(): forwarding incoming HTTP request ..', klass=self.__class__.__name__)

        # host request by client in incoming HTTP request
        requested_host = request.requestHeaders.getRawHeaders('Host')[0]

        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-Host
        request.requestHeaders.setRawHeaders(b'X-Forwarded-Host', [requested_host.encode('ascii')])
        # request.requestHeaders.setRawHeaders(b'X-Forwarded-Server', [requested_host.encode('ascii')])

        # crossbar web transport listening IP/port
        server_port = request.getHost().port
        server_port = '{}'.format(server_port).encode('ascii')

        # RFC 2616 tells us that we can omit the port if it's the default port,
        # but we have to provide it otherwise
        if self.port == 80:
            host = self.host
        else:
            host = '%s:%d' % (self.host, self.port)
        request.requestHeaders.setRawHeaders(b'Host', [host.encode('utf8')])

        # forward originating IP of incoming HTTP request
        client_ip = request.getClientAddress().host
        if client_ip:
            client_ip = client_ip.encode('ascii')
            request.requestHeaders.setRawHeaders(b'X-Forwarded-For', [client_ip])
            request.requestHeaders.setRawHeaders(b'X-Real-IP', [client_ip])

        # forward information of outside listening port and protocol (http vs https)
        if self._forwarded_port:
            request.requestHeaders.setRawHeaders(b'X-Forwarded-Port',
                                                 ['{}'.format(self._forwarded_port).encode('ascii')])
        else:
            request.requestHeaders.setRawHeaders(b'X-Forwarded-Port', [server_port])

        if self._forwarded_proto:
            request.requestHeaders.setRawHeaders(b'X-Forwarded-Proto', [self._forwarded_proto])
        else:
            request.requestHeaders.setRawHeaders(b'X-Forwarded-Proto',
                                                 [('https' if server_port == 443 else 'http').encode('ascii')])

        # rewind cursor to begin of request data
        request.content.seek(0, 0)

        # reapply query strings to forwarding HTTP request
        qs = urllib_parse.urlparse(request.uri)[4]
        if qs:
            rest = self.path + b'?' + qs
        else:
            rest = self.path

        self.log.info('forwarding HTTP request to "{rest}" with HTTP request headers {headers}',
                      rest=rest,
                      headers=request.getAllHeaders())

        # now issue the forwarded request to the HTTP server that is being reverse-proxied
        clientFactory = self.proxyClientFactoryClass(request.method, rest, request.clientproto,
                                                     request.getAllHeaders(), request.content.read(), request)
        self.reactor.connectTCP(self.host, self.port, clientFactory)

        # the proxy client request created ^ is taking care of actually finishing the request ..
        return NOT_DONE_YET

    def getChild(self, path, request):
        return ExtReverseProxyResource(self.host,
                                       self.port,
                                       self.path + b'/' + urlquote(path, safe=b"").encode('utf-8'),
                                       forwarded_port=self._forwarded_port,
                                       forwarded_proto=self._forwarded_proto)


class RouterWebServiceReverseWeb(RouterWebService):
    """
    Reverse Web proxy service.
    """
    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['reverseproxy'](personality, config)

        # target HTTP server to forward incoming HTTP requests to
        host = config['host']
        port = int(config.get('port', 80))
        base_path = config.get('path', '').encode('utf-8')

        # public listening port and protocol (http vs https) the crossbar
        # web transport is listening on. this might be used by the HTTP server
        # the request is proxied to to construct correct HTTP links (which need
        # to point to the _public_ listening web transport of crossbar)
        forwarded_port = int(config.get('forwarded_port', 80))
        forwarded_proto = config.get('forwarded_proto', 'http').encode('ascii')

        resource = ExtReverseProxyResource(host,
                                           port,
                                           base_path,
                                           forwarded_port=forwarded_port,
                                           forwarded_proto=forwarded_proto)
        if path == '/':
            resource = RootResource(resource, {})

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
            raise ApplicationError("crossbar.error.class_import_failed", emsg)

        return RouterWebServiceTwistedWeb(transport, path, config, resource)


class RouterWebServiceNestedPath(RouterWebService):
    """
    Nested sub-URL path (pseudo-)service.
    """
    @staticmethod
    @inlineCallbacks
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['path'](personality, config)

        nested_paths = config.get('paths', {})

        if '/' in nested_paths:
            root_config = nested_paths['/']
            root_factory = personality.WEB_SERVICE_FACTORIES[root_config['type']]
            root_service = yield maybeDeferred(root_factory.create, transport, '/', root_config)
            root_resource = root_service.resource
        else:
            root_resource = Resource404(transport.templates, b'')

        for nested_path in sorted(nested_paths):
            if nested_path != '/':
                nested_config = nested_paths[nested_path]
                nested_factory = personality.WEB_SERVICE_FACTORIES[nested_config['type']]
                nested_service = yield maybeDeferred(nested_factory.create, transport, nested_path, nested_config)
                nested_resource = nested_service.resource
                root_resource.putChild(nested_path.encode('utf8'), nested_resource)

        return RouterWebServiceNestedPath(transport, path, config, root_resource)
