#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import importlib
import pkg_resources
from pprint import pformat

from collections.abc import Mapping, Sequence

from werkzeug.routing import Map, Rule
from werkzeug.exceptions import NotFound, MethodNotAllowed
from werkzeug.utils import escape

from jinja2 import Environment, FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment

from txaio import make_logger

from twisted.web import resource
from twisted.web import server
from twisted.internet.defer import succeed

from autobahn.wamp.serializer import JsonObjectSerializer
from autobahn.wamp.types import ComponentConfig
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationSession

from crossbar.webservice.base import RootResource, RouterWebService
from crossbar.common.checkconfig import InvalidConfigException, check_dict_args

from crossbar._util import hlid, hltype

__all__ = ('RouterWebServiceWap', )


class WapResource(resource.Resource):
    """
    Twisted Web resource for WAMP Application Page web service.

    This resource uses templates loaded into a Jinja2 environment to render HTML pages with data retrieved
    from a WAMP procedure call, triggered from the original Web request.
    """

    log = make_logger()

    ser = JsonObjectSerializer()

    isLeaf = True

    def __init__(self, worker, config, path):
        """
        :param worker: The router worker controller within this Web service is started.
        :type worker: crossbar.worker.router.RouterController

        :param config: The Web service configuration item.
        :type config: dict
        """
        resource.Resource.__init__(self)
        self._worker = worker
        self._config = config
        self._session_cache = {}

        self._realm_name = config.get('wamp', {}).get('realm', None)
        self._authrole = config.get('wamp', {}).get('authrole', 'anonymous')
        self._service_agent = worker.realm_by_name(self._realm_name).session

        #   TODO:
        #       We need to lookup the credentials for the current user based on the pre-established
        #       HTTP session cookie, this will establish the 'authrole' the user is running as.
        #       This 'authrole' can then be used to authorize the back-end topic call.
        #   QUESTION:
        #       Does the topic need the authid, if so, how do we pass it?
        #
        #   This is our default (anonymous) session for unauthenticated users
        #
        router = worker._router_factory.get(self._realm_name)
        self._default_session = ApplicationSession(ComponentConfig(realm=self._realm_name, extra=None))
        worker._router_session_factory.add(self._default_session, router, authrole=self._authrole)

        # Setup Jinja2 to point to our templates folder or a package resource
        #
        templates_config = config.get("templates")

        if type(templates_config) == str:
            # resolve specified template directory path relative to node directory
            templates_dir = os.path.abspath(os.path.join(self._worker.config.extra.cbdir, templates_config))
            templates_source = 'directory'

        elif type(templates_config) == dict:

            # in case we got a dict, that must contain "package" and "resource" attributes
            if 'package' not in templates_config:
                raise ApplicationError('crossbar.error.invalid_configuration',
                                       'missing attribute "resource" in WAP web service configuration')

            if 'resource' not in templates_config:
                raise ApplicationError('crossbar.error.invalid_configuration',
                                       'missing attribute "resource" in WAP web service configuration')

            try:
                importlib.import_module(templates_config['package'])
            except ImportError as e:
                emsg = 'Could not import resource {} from package {}: {}'.format(templates_config['resource'],
                                                                                 templates_config['package'], e)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)
            else:
                try:
                    # resolve template directory from package resource
                    templates_dir = os.path.abspath(
                        pkg_resources.resource_filename(templates_config['package'], templates_config['resource']))
                except Exception as e:
                    emsg = 'Could not import resource {} from package {}: {}'.format(
                        templates_config['resource'], templates_config['package'], e)
                    raise ApplicationError('crossbar.error.invalid_configuration', emsg)

            templates_source = 'package'
        else:
            raise ApplicationError(
                'crossbar.error.invalid_configuration',
                'invalid type "{}" for attribute "templates" in WAP web service configuration'.format(
                    type(templates_config)))

        if config.get('sandbox', True):
            # The sandboxed environment. It works like the regular environment but tells the compiler to
            # generate sandboxed code.
            # https://jinja.palletsprojects.com/en/2.11.x/sandbox/#jinja2.sandbox.SandboxedEnvironment
            env = SandboxedEnvironment(loader=FileSystemLoader(templates_dir), autoescape=True)
        else:
            env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

        self.log.info(
            'WapResource created (realm="{realm}", authrole="{authrole}", templates_dir="{templates_dir}", templates_source="{templates_source}", jinja2_env={jinja2_env})',
            realm=hlid(self._realm_name),
            authrole=hlid(self._authrole),
            templates_dir=hlid(templates_dir),
            templates_source=hlid(templates_source),
            jinja2_env=hltype(env.__class__))

        # http://werkzeug.pocoo.org/docs/dev/routing/#werkzeug.routing.Map
        map = Map()

        # Add all our routes into 'map', note each route endpoint is a tuple of the
        # topic to call, and the template to use when rendering the results.
        for route in config.get('routes', {}):

            # compute full absolute URL of route to be added - ending in Werkzeug/Routes URL pattern
            rpath = route['path']
            _rp = []
            if path != '/':
                _rp.append(path)
            if rpath != '/':
                _rp.append(rpath)
            route_url = os.path.join('/', '/'.join(_rp))

            route_method = route.get('method', 'GET')
            assert route_method in ['GET', 'POST'], 'invalid HTTP method "{}" for route on URL "{}"'.format(
                route_method, route_url)

            route_methods = [route_method]

            # note the WAMP procedure to call and the Jinja2 template to render as HTTP response
            route_endpoint = (route['call'], env.get_template(route['render']))
            route_rule = Rule(route_url, methods=route_methods, endpoint=route_endpoint)
            map.add(route_rule)
            self.log.info(
                'WapResource route added (url={route_url}, methods={route_methods}, endpoint={route_endpoint})',
                route_url=hlid(route_url),
                route_methods=hlid(route_methods),
                route_endpoint=route_endpoint)

        # http://werkzeug.pocoo.org/docs/dev/routing/#werkzeug.routing.MapAdapter
        # http://werkzeug.pocoo.org/docs/dev/routing/#werkzeug.routing.MapAdapter.match
        self._map_adapter = map.bind('/')

    def _after_call_success(self, result, request, client_return_json):
        """
        When the WAMP call attached to the URL returns, render the WAMP result
        into a Jinja2 template and return HTML to client. Alternatively, return
        the call result as plain JSON.

        :param result: The dict returned from the WAMP procedure call.
        :param request: The HTTP request.
        :param client_return_json: Flag indicating to return plain JSON (no HTML rendering.)
        """
        try:
            if client_return_json:
                rendered = self.ser.serialize(result)
                self.log.info('WapResource successfully serialized JSON result:\n{result}', result=pformat(result))
            else:
                rendered = request.template.render(result).encode('utf8')
                self.log.info('WapResource successfully rendered HTML result: {rendered} bytes',
                              rendered=len(rendered))
        except Exception as e:
            self.log.failure()
            emsg = 'WapResource render error for WAMP result of type "{}": {}'.format(type(result), e)
            self.log.warn(emsg)
            request.setResponseCode(500)
            request.write(self._render_error(emsg, request, client_return_json))
        else:
            request.write(rendered)
        request.finish()

    def _after_call_error(self, error, request, client_return_json):
        """
        Deferred error, write out the error template and finish the request

        :param error: The current deferred error object
        :param request: The original HTTP request
        """
        self.log.error('WapResource error: {error}', error=error)
        request.setResponseCode(500)
        request.write(self._render_error(error.value.error, request, client_return_json))
        request.finish()

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

    def render(self, request):
        """
        Initiate the rendering of a HTTP/GET request by calling a WAMP procedure, the
        resulting ``dict`` is rendered together with the specified Jinja2 template
        for this URL.

        :param request: The HTTP request.
        :returns: server.NOT_DONE_YET (special)
        """
        # https://twistedmatrix.com/documents/current/api/twisted.web.resource.Resource.html#render
        # The encoded path of the request URI (_not_ (!) including query arguments),
        full_path = request.path.decode('utf-8')

        # HTTP request method (GET, POST, ..)
        http_method = request.method.decode()
        if http_method not in ['GET', 'POST']:
            request.setResponseCode(511)
            return self._render_error(
                'Method not allowed on path "{full_path}" [werkzeug.routing.MapAdapter.match]'.format(
                    full_path=full_path), request)

        # in case of HTTP/POST, read request body as one binary string
        if http_method == 'POST' and request.content:
            content_type = request.getAllHeaders().get(b'content-type', b'application/octet-stream').decode()

            # https://stackoverflow.com/a/11549600/884770
            # http://marianoiglesias.com.ar/python/file-uploading-with-multi-part-encoding-using-twisted/
            body_data = request.content.read()
            self.log.info('POST data len = {newdata_len}', newdata_len=len(body_data))
        else:
            content_type = None
            body_data = None

        # parse and decode any query parameters
        query_args = {}
        if request.args:
            for key, values in request.args.items():
                key = key.decode()
                # we only process the first header value per key (!)
                value = values[0].decode()
                query_args[key] = value
            self.log.info('Parsed query parameters: {query_args}', query_args=query_args)

        # parse client announced accept header
        client_accept = request.getAllHeaders().get(b'accept', None)
        if client_accept:
            client_accept = client_accept.decode()

        # flag indicating the client wants to get plain JSON results (not rendered HTML)
        client_return_json = client_accept == 'application/json'

        # client cookie processing
        cookie = request.received_cookies.get(b'session_cookie')
        self.log.debug('Session Cookie is ({})'.format(cookie))
        if cookie:
            session = self._session_cache.get(cookie)
            if not session:
                # FIXME: lookup role for current session
                self.log.debug('Creating a new session for cookie ({})'.format(cookie))
                authrole = 'anonymous'
                session = ApplicationSession(ComponentConfig(realm=self._realm_name, extra=None))
                self._worker._router_session_factory.add(session, authrole=authrole)
                self._session_cache[cookie] = session
            else:
                self.log.debug('Using a cached session for ({})'.format(cookie))
        else:
            self.log.debug('No session cookie, falling back on default session')
            session = self._default_session

        try:
            # werkzeug.routing.MapAdapter
            # http://werkzeug.pocoo.org/docs/dev/routing/#werkzeug.routing.MapAdapter.match
            (procedure, request.template), kwargs = self._map_adapter.match(full_path,
                                                                            method=http_method,
                                                                            query_args=query_args)
            if kwargs and query_args:
                kwargs.update(query_args)
            else:
                kwargs = query_args
            self.log.info('WapResource on path "{full_path}" mapped to procedure "{procedure}"',
                          full_path=full_path,
                          procedure=procedure)

            # FIXME: how do we allow calling WAMP procedures with positional args?
            if procedure:
                self.log.info('calling procedure "{procedure}" with kwargs={kwargs} and body_data_len={body_data_len}',
                              procedure=procedure,
                              kwargs=kwargs,
                              body_data_len=len(body_data) if body_data else 0)

                # we need a session to call
                if not session:
                    self.log.error('could not call procedure - no session')
                    return self._render_error('could not call procedure - no session', request)

                if body_data:
                    if kwargs:
                        d = session.call(procedure, **kwargs, data=body_data, data_type=content_type)
                    else:
                        d = session.call(procedure, data=body_data, data_type=content_type)
                else:
                    if kwargs:
                        d = session.call(procedure, **kwargs)
                    else:
                        d = session.call(procedure)
            else:
                d = succeed({})

            d.addCallbacks(self._after_call_success,
                           self._after_call_error,
                           callbackArgs=[request, client_return_json],
                           errbackArgs=[request, client_return_json])

            return server.NOT_DONE_YET

        except NotFound:
            self.log.info('URL "{url}" not found (method={method})', url=full_path, method=http_method)
            request.setResponseCode(404)
            return self._render_error(
                'Path "{full_path}" not found [werkzeug.routing.MapAdapter.match]'.format(full_path=full_path),
                request)

        except MethodNotAllowed:
            self.log.info('method={method} not allowed on URL "{url}"', url=full_path, method=http_method)
            request.setResponseCode(511)
            return self._render_error(
                'Method not allowed on path "{full_path}" [werkzeug.routing.MapAdapter.match]'.format(
                    full_path=full_path), request)

        except Exception as e:
            self.log.info('error while processing method={method} on URL "{url}": {e}',
                          url=full_path,
                          method=http_method,
                          e=e)
            request.setResponseCode(500)
            request.write(
                self._render_error(
                    'Unknown error with path "{full_path}" [werkzeug.routing.MapAdapter.match]'.format(
                        full_path=full_path), request))
            raise


class RouterWebServiceWap(RouterWebService):
    """
    WAMP Application Page service.
    """
    @staticmethod
    def check(personality, config):
        """
        Checks the configuration item. When errors are found, an
        InvalidConfigException exception is raised.

        :param personality: The node personality class.
        :param config: The Web service configuration item.
        :raises: crossbar.common.checkconfig.InvalidConfigException
        """
        if 'type' not in config:
            raise InvalidConfigException("missing mandatory attribute 'type' in Web service configuration")

        if config['type'] != 'wap':
            raise InvalidConfigException('unexpected Web service type "{}"'.format(config['type']))

        check_dict_args(
            {
                # ID of webservice (must be unique for the web transport)
                'id': (False, [str]),

                # must be equal to "wap"
                'type': (True, [str]),

                # path to prvide to Werkzeug/Routes (eg "/test" rather than "test")
                'path': (False, [str]),

                # local directory or package+resource
                'templates': (True, [str, Mapping]),

                # create sandboxed jinja2 environment
                'sandbox': (False, [bool]),

                # Web routes
                'routes': (True, [Sequence]),

                # WAMP connection configuration
                'wamp': (True, [Mapping]),
            },
            config,
            "WAMP Application Page (WAP) service configuration: {}".format(config))

        if isinstance(config['templates'], Mapping):
            check_dict_args({
                'package': (True, [str]),
                'resource': (True, [str]),
            }, config['templates'], "templates in WAP service configuration")

        for route in config['routes']:
            check_dict_args(
                {
                    'path': (True, [str]),
                    'method': (True, [str]),
                    'call': (False, [str, type(None)]),
                    'render': (True, [str]),
                }, route, "route in WAP service configuration")

        check_dict_args({
            'realm': (True, [str]),
            'authrole': (True, [str]),
        }, config['wamp'], "wamp in WAP service configuration")

    @staticmethod
    def create(transport, path, config):
        """
        Factory to create a Web service instance of this class.

        :param transport: The Web transport in which this Web service is created on.
        :param path: The (absolute) URL path on which the Web service is to be attached.
        :param config: The Web service configuration item.
        :return: An instance of this class.
        """
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['wap'](personality, config)

        resource = WapResource(transport.worker, config, path)
        if path == '/':
            resource = RootResource(resource, {})

        return RouterWebServiceWap(transport, path, config, resource)
