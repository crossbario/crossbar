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
import pkg_resources

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
            templates_dir = os.path.abspath(
                os.path.join(self._worker.config.extra.cbdir, templates_config))
            templates_source = 'directory'

        elif type(templates_config) == dict:

            # in case we got a dict, that must contain "package" and "resource" attributes
            if 'package' not in templates_config:
                raise ApplicationError('crossbar.error.invalid_configuration', 'missing attribute "resource" in WAP web service configuration')

            if 'resource' not in templates_config:
                raise ApplicationError('crossbar.error.invalid_configuration', 'missing attribute "resource" in WAP web service configuration')

            try:
                importlib.import_module(templates_config['package'])
            except ImportError as e:
                emsg = 'Could not import resource {} from package {}: {}'.format(templates_config['resource'], templates_config['package'], e)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)
            else:
                try:
                    # resolve template directory from package resource
                    templates_dir = os.path.abspath(pkg_resources.resource_filename(templates_config['package'], templates_config['resource']))
                except Exception as e:
                    emsg = 'Could not import resource {} from package {}: {}'.format(templates_config['resource'], templates_config['package'], e)
                    raise ApplicationError('crossbar.error.invalid_configuration', emsg)

            templates_source = 'package'
        else:
            raise ApplicationError('crossbar.error.invalid_configuration', 'invalid type "{}" for attribute "templates" in WAP web service configuration'.format(type(templates_config)))

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
            route_url = '/' + '/'.join(_rp)
            route_methods = [route.get('method')]

            # note the WAMP procedure to call and the Jinja2 template to render as HTTP response
            route_endpoint = (route['call'], env.get_template(route['render']))
            map.add(Rule(route_url, methods=route_methods, endpoint=route_endpoint))
            self.log.info(
                'WapResource route added (url={route_url}, methods={route_methods}, endpoint={route_endpoint})',
                route_url=hlid(route_url),
                route_methods=hlid(route_methods),
                route_endpoint=route_endpoint)

        # http://werkzeug.pocoo.org/docs/dev/routing/#werkzeug.routing.MapAdapter
        # http://werkzeug.pocoo.org/docs/dev/routing/#werkzeug.routing.MapAdapter.match
        self._map_adapter = map.bind('/')

    def _after_call_success(self, result, request):
        """
        When the WAMP call attached to the URL returns, render the WAMP result
        into a Jinja2 template and return HTML to client.

        :param payload: The dict returned from the topic
        :param request: The HTTP request.
        :return: server.NOT_DONE_YET (special)
        """
        try:
            rendered_html = request.template.render(result)
        except Exception as e:
            self.log.failure()
            emsg = 'WabResource render error for WAMP result of type "{}": {}'.format(type(result), e)
            self.log.warn(emsg)
            request.setResponseCode(500)
            request.write(self._render_error(emsg, request))
        else:
            request.write(rendered_html.encode('utf8'))
        request.finish()

    def _after_call_error(self, error, request):
        """
        Deferred error, write out the error template and finish the request

        :param error: The current deferred error object
        :param request: The original HTTP request
        :return: None
        """
        self.log.error('WapResource error: {error}', error=error)
        request.setResponseCode(500)
        request.write(self._render_error(error.value.error, request))
        request.finish()

    def _render_error(self, message, request):
        """
        Error renderer, display a basic error message to tell the user that there
        was a problem and roughly what the problem was.

        :param message: The current error message
        :param request: The original HTTP request
        :return: HTML formatted error string
        """
        return """
            <html>
                <title>API Error</title>
                <body>
                    <h3 style="color: #f00">Crossbar WAMP Application Page Error</h3>
                    <pre>{}</pre>
                </body>
            </html>
        """.format(escape(message)).encode('utf8')

    def render_GET(self, request):
        """
        Initiate the rendering of a HTTP/GET request by calling a WAMP procedure, the
        resulting ``dict`` is rendered together with the specified Jinja2 template
        for this URL.

        :param request: The HTTP request.
        :returns: server.NOT_DONE_YET (special)
        """
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

        if not session:
            self.log.error('could not call procedure - no session')
            return self._render_error('could not call procedure - no session', request)

        full_path = request.uri.decode('utf-8')
        try:
            # werkzeug.routing.MapAdapter
            # http://werkzeug.pocoo.org/docs/dev/routing/#werkzeug.routing.MapAdapter.match
            (procedure, request.template), kwargs = self._map_adapter.match(full_path)

            self.log.debug(
                'WapResource HTTP/GET "{full_path}" mapped to procedure "{procedure}"',
                full_path=full_path,
                procedure=procedure)

            if procedure:
                # FIXME: how do we allow calling WAMP procedures with positional args?
                if kwargs:
                    d = session.call(procedure, **kwargs)
                else:
                    d = session.call(procedure)
            else:
                d = succeed({})

            # d.addCallback(self._after_call_success, request)
            # d.addErrback(self._after_call_error, request)
            d.addCallbacks(
                self._after_call_success,
                self._after_call_error,
                callbackArgs=[request],
                errbackArgs=[request])

            return server.NOT_DONE_YET

        except NotFound:
            request.setResponseCode(404)
            return self._render_error('Path "{full_path}" not found [werkzeug.routing.MapAdapter.match]'.format(full_path=full_path), request)

        except MethodNotAllowed:
            request.setResponseCode(511)
            return self._render_error('Method not allowed on path "{full_path}" [werkzeug.routing.MapAdapter.match]'.format(full_path=full_path), request)

        except Exception:
            request.setResponseCode(500)
            request.write(self._render_error('Unknown error with path "{full_path}" [werkzeug.routing.MapAdapter.match]'.format(full_path=full_path), request))
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

        check_dict_args({
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

        }, config, "WAMP Application Page (WAP) service configuration".format(config))

        if isinstance(config['templates'], Mapping):
            check_dict_args({
                'package': (True, [str]),
                'resource': (True, [str]),
            }, config['templates'], "templates in WAP service configuration")

        for route in config['routes']:
            check_dict_args({
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
