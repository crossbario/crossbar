#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
from pprint import pformat

from typing import Dict, Any, Union

import werkzeug
from werkzeug.routing import Rule, MapAdapter
from werkzeug.exceptions import NotFound, MethodNotAllowed

try:
    # removed in werkzeug 2.1.0
    from werkzeug.utils import escape
except ImportError:
    from markupsafe import escape

from jinja2 import Environment

from txaio import make_logger, time_ns

from twisted.web import resource

from autobahn.wamp.serializer import JsonObjectSerializer
from autobahn.xbr import FbsRepository

from crossbar.webservice.base import RootResource, RouterWebService
from crossbar.common.checkconfig import InvalidConfigException, check_dict_args

from crossbar.worker.proxy import ProxyController
from crossbar.worker.router import RouterController

__all__ = ('RouterWebServiceCatalog', )


class CatalogResource(resource.Resource):
    """
    Twisted Web resource for API FbsRepository Web service.

    This resource uses templates loaded into a Jinja2 environment to render HTML pages
    with data retrieved from an API FbsRepository archive file or on-chain address.
    """

    log = make_logger()

    ser = JsonObjectSerializer()

    isLeaf = True

    def __init__(self, jinja_env: Environment, worker: Union[RouterController, ProxyController],
                 config: Dict[str, Any], path: str):
        """

        :param worker: The router worker controller within this Web service is started.
        :param config: The Web service configuration item.
        """
        resource.Resource.__init__(self)

        # remember all ctor args
        self._jinja_env: Environment = jinja_env
        self._worker = worker
        self._config = config
        self._path = path

        # setup Werkzeug URL map adapter
        # https://werkzeug.palletsprojects.com/en/2.1.x/routing/#werkzeug.routing.Map
        adapter_map = werkzeug.routing.Map()
        routes = {
            '/': 'wamp_catalog_home.html',
            'table': 'wamp_catalog_table.html',
            'struct': 'wamp_catalog_struct.html',
            'enum': 'wamp_catalog_enum.html',
            'service': 'wamp_catalog_service.html',
        }
        for rpath, route_template in routes.items():
            # compute full absolute URL of route to be added - ending in Werkzeug/Routes URL pattern
            _rp = []
            if path != '/':
                _rp.append(path)
            if rpath != '/':
                _rp.append(rpath)
            route_url = os.path.join('/', '/'.join(_rp))

            route_endpoint = jinja_env.get_template(route_template)
            route_rule = Rule(route_url, methods=['GET'], endpoint=route_endpoint)
            adapter_map.add(route_rule)

        # https://werkzeug.palletsprojects.com/en/2.1.x/routing/#werkzeug.routing.Map.bind
        self._map_adapter: MapAdapter = adapter_map.bind('localhost', '/')

        # FIXME
        self._repo: FbsRepository = FbsRepository('FIXME')
        self._repo.load(self._config['filename'])

    def render(self, request):

        # https://twistedmatrix.com/documents/current/api/twisted.web.resource.Resource.html#render
        # The encoded path of the request URI (_not_ (!) including query arguments),
        full_path = request.path.decode('utf-8')

        # HTTP request method
        http_method = request.method.decode()
        if http_method not in ['GET']:
            request.setResponseCode(511)
            return self._render_error(
                'Method not allowed on path "{full_path}" [werkzeug.routing.MapAdapter.match]'.format(
                    full_path=full_path), request)

        # parse and decode any query parameters
        query_args = {}
        if request.args:
            for key, values in request.args.items():
                key = key.decode()
                # we only process the first header value per key (!)
                value = values[0].decode()
                query_args[key] = value
            self.log.info('Parsed query parameters: {query_args}', query_args=query_args)

        # parse client announced accept-header
        client_accept = request.getAllHeaders().get(b'accept', None)
        if client_accept:
            client_accept = client_accept.decode()

        # flag indicating the client wants to get plain JSON results (not rendered HTML)
        # client_return_json = client_accept == 'application/json'

        # client cookie processing
        cookie = request.received_cookies.get(b'session_cookie')
        self.log.debug('Session Cookie is ({})'.format(cookie))

        try:
            # werkzeug.routing.MapAdapter
            # https://werkzeug.palletsprojects.com/en/2.1.x/routing/#werkzeug.routing.MapAdapter.match
            template, kwargs = self._map_adapter.match(full_path, method=http_method, query_args=query_args)

            if kwargs:
                if query_args:
                    kwargs.update(query_args)
            else:
                kwargs = query_args

            kwargs['repo'] = self._repo
            kwargs['created'] = time_ns()

            self.log.info(
                'CatalogResource request on path "{full_path}" mapped to template "{template}" '
                'using kwargs\n{kwargs}',
                full_path=full_path,
                template=template,
                kwargs=pformat(kwargs))

            rendered = template.render(**kwargs).encode('utf8')
            self.log.info('successfully rendered HTML result: {rendered} bytes', rendered=len(rendered))
            request.setResponseCode(200)
            return rendered

        except NotFound:
            self.log.warn('URL "{url}" not found (method={method})', url=full_path, method=http_method)
            request.setResponseCode(404)
            return self._render_error(
                'Path "{full_path}" not found [werkzeug.routing.MapAdapter.match]'.format(full_path=full_path),
                request)

        except MethodNotAllowed:
            self.log.warn('method={method} not allowed on URL "{url}"', url=full_path, method=http_method)
            request.setResponseCode(511)
            return self._render_error(
                'Method not allowed on path "{full_path}" [werkzeug.routing.MapAdapter.match]'.format(
                    full_path=full_path), request)

        except Exception as e:
            self.log.warn('error while processing method={method} on URL "{url}": {e}',
                          url=full_path,
                          method=http_method,
                          e=e)
            request.setResponseCode(500)
            return self._render_error(
                'Unknown error with path "{full_path}" [werkzeug.routing.MapAdapter.match]'.format(
                    full_path=full_path), request)

    def _render_error(self, message, request, client_return_json=False):
        """
        Error renderer, display a basic error message to tell the user that there
        was a problem and roughly what the problem was.

        :param message: The current error message
        :param request: The original HTTP request
        :return: HTML formatted error string
        """
        if client_return_json:
            return self.ser.serialize({'error': message})
        else:
            return """
                <html>
                    <title>API Error</title>
                    <body>
                        <h3 style="color: #f00">Crossbar WAMP Application Page Error</h3>
                        <pre>{}</pre>
                    </body>
                </html>
            """.format(escape(message)).encode('utf8')


class RouterWebServiceCatalog(RouterWebService):
    """
    WAMP API FbsRepository Web service.
    """
    @staticmethod
    def check(personality, config: Dict[str, Any]):
        """
        Checks the configuration item. When errors are found, an
        :class:`crossbar.common.checkconfig.InvalidConfigException` is raised.

        :param personality: The node personality class.
        :param config: The Web service configuration item.
        """
        if 'type' not in config:
            raise InvalidConfigException("missing mandatory attribute 'type' in Web service configuration")

        if config['type'] != 'catalog':
            raise InvalidConfigException('unexpected Web service type "{}"'.format(config['type']))

        check_dict_args(
            {
                # ID of webservice (must be unique for the web transport)
                'id': (False, [str]),

                # must be equal to "catalog"
                'type': (True, [str]),

                # filename (relative to node directory) to FbsRepository file (*.bfbs, *.zip or *.zip.sig)
                'filename': (True, [str]),

                # path to provide to Werkzeug/Routes (eg "/test" rather than "test")
                'path': (False, [str]),
            },
            config,
            'FbsRepository Web service configuration:\n{}'.format(pformat(config)))

    @staticmethod
    def create(transport, path: str, config: Dict[str, Any]) -> 'RouterWebServiceCatalog':
        """
        Create a new FbsRepository Web service using a FbsRepository archive file or on-chain address.

        :param transport: Web-transport on which to add the web service.
        :param path: HTTP path on which to add the web service.
        :param config: Web service configuration.
        :return: Web service instance.
        """
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['catalog'](personality, config)

        _resource = CatalogResource(transport.templates, transport.worker, config, path)
        if path == '/':
            _resource = RootResource(_resource, {})

        return RouterWebServiceCatalog(transport, path, config, _resource)
