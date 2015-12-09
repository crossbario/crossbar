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

from __future__ import absolute_import

import os
import sys
import importlib
import pkg_resources
import tempfile
import six

from datetime import datetime

from twisted.internet.defer import DeferredList
from twisted.internet.defer import inlineCallbacks
from twisted.python.threadpool import ThreadPool

from autobahn.util import utcstr
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from crossbar.twisted.resource import StaticResource, StaticResourceNoListing

from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceSession
from crossbar.router.router import RouterFactory

from crossbar.router.protocol import WampWebSocketServerFactory, \
    WampRawSocketServerFactory

from crossbar.worker import _appsession_loader
from crossbar.worker.testee import WebSocketTesteeServerFactory, \
    StreamTesteeServerFactory

from crossbar.twisted.endpoint import create_listening_port_from_config

from autobahn.wamp.types import RegisterOptions

try:
    from twisted.web.wsgi import WSGIResource
    _HAS_WSGI = True
except (ImportError, SyntaxError):
    # Twisted hasn't ported this to Python 3 yet
    _HAS_WSGI = False

from autobahn.twisted.resource import WebSocketResource, WSGIRootResource

from crossbar.twisted.resource import WampLongPollResource, \
    SchemaDocResource

from twisted.web.server import Site

import twisted
import crossbar

from twisted.web.resource import Resource

from crossbar.twisted.site import createHSTSRequestFactory

from crossbar.twisted.resource import JsonResource, \
    Resource404, \
    FileUploadResource, \
    RedirectResource

from crossbar.twisted.flashpolicy import FlashPolicyFactory

from autobahn.wamp.types import ComponentConfig

from crossbar.worker.worker import NativeWorkerSession

from crossbar.common import checkconfig
from crossbar.twisted.site import patchFileContentTypes

from crossbar.twisted.resource import _HAS_CGI

from crossbar.adapter.rest import PublisherResource, CallerResource
from crossbar.adapter.rest import WebhookResource

if _HAS_CGI:
    from crossbar.twisted.resource import CgiDirectory

__all__ = ('RouterWorkerSession',)


# monkey patch the Twisted Web server identification
twisted.web.server.version = "Crossbar/{}".format(crossbar.__version__)


# 12 hours as default cache timeout for static resources
DEFAULT_CACHE_TIMEOUT = 12 * 60 * 60

EXTRA_MIME_TYPES = {
    '.svg': 'image/svg+xml',
    '.jgz': 'text/javascript'
}


class RouterTransport(object):

    """
    A transport attached to a router.
    """

    def __init__(self, id, config, factory, port):
        """
        Ctor.

        :param id: The transport ID within the router.
        :type id: str
        :param config: The transport's configuration.
        :type config: dict
        :param factory: The transport factory in use.
        :type factory: obj
        :param port: The transport's listening port (https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IListeningPort.html)
        :type port: obj
        """
        self.id = id
        self.config = config
        self.factory = factory
        self.port = port
        self.created = datetime.utcnow()


class RouterComponent(object):

    """
    An embedded application component running inside a router instance.
    """

    def __init__(self, id, config, session):
        """
        Ctor.

        :param id: The component ID within the router instance.
        :type id: str
        :param config: The component's configuration.
        :type config: dict
        :param session: The component application session.
        :type session: obj (instance of ApplicationSession)
        """
        self.id = id
        self.config = config
        self.session = session
        self.created = datetime.utcnow()


class RouterRealm(object):

    """
    A realm managed by a router.
    """

    def __init__(self, id, config, session=None):
        """
        Ctor.

        :param id: The realm ID within the router.
        :type id: str
        :param config: The realm configuration.
        :type config: dict
        :param session: The realm service session.
        :type session: instance of CrossbarRouterServiceSession
        """
        self.id = id
        self.config = config
        self.session = session
        self.created = datetime.utcnow()
        self.roles = {}


class RouterRealmRole(object):

    """
    A role in a realm managed by a router.
    """

    def __init__(self, id, config):
        """
        Ctor.

        :param id: The role ID within the realm.
        :type id: str
        :param config: The role configuration.
        :type config: dict
        """


class RouterWorkerSession(NativeWorkerSession):
    """
    A native Crossbar.io worker that runs a WAMP router which can manage
    multiple realms, run multiple transports and links, as well as host
    multiple (embedded) application components.
    """
    WORKER_TYPE = 'router'

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        yield NativeWorkerSession.onJoin(self, details, publish_ready=False)

        # factory for producing (per-realm) routers
        self._router_factory = RouterFactory()

        # factory for producing router sessions
        self._router_session_factory = RouterSessionFactory(self._router_factory)

        # map: realm ID -> RouterRealm
        self.realms = {}

        # map: realm URI -> realm ID
        self.realm_to_id = {}

        # map: transport ID -> RouterTransport
        self.transports = {}

        # map: link ID -> RouterLink
        self.links = {}

        # map: component ID -> RouterComponent
        self.components = {}

        # the procedures registered
        procs = [
            'get_router_realms',
            'start_router_realm',
            'stop_router_realm',

            'get_router_realm_roles',
            'start_router_realm_role',
            'stop_router_realm_role',

            'get_router_components',
            'start_router_component',
            'stop_router_component',

            'get_router_transports',
            'start_router_transport',
            'stop_router_transport',

            'get_router_links',
            'start_router_link',
            'stop_router_link'
        ]

        dl = []
        for proc in procs:
            uri = '{}.{}'.format(self._uri_prefix, proc)
            self.log.debug("Registering management API procedure {proc}", proc=uri)
            dl.append(self.register(getattr(self, proc), uri, options=RegisterOptions(details_arg='details')))

        regs = yield DeferredList(dl)

        self.log.debug("Registered {cnt} management API procedures", cnt=len(regs))

        # NativeWorkerSession.publish_ready()
        yield self.publish_ready()

    def get_router_realms(self, details=None):
        """
        List realms currently managed by this router.
        """
        self.log.debug("{}.get_router_realms".format(self.__class__.__name__))

        raise Exception("not implemented")

    def start_router_realm(self, id, config, schemas=None, details=None):
        """
        Starts a realm managed by this router.

        :param id: The ID of the realm to start.
        :type id: str
        :param config: The realm configuration.
        :type config: dict
        :param schemas: An (optional) initial schema dictionary to load.
        :type schemas: dict
        """
        self.log.debug("{}.start_router_realm".format(self.__class__.__name__),
                       id=id, config=config, schemas=schemas)

        # URI of the realm to start
        realm = config['name']

        # track realm
        rlm = RouterRealm(id, config)
        self.realms[id] = rlm
        self.realm_to_id[realm] = id

        # create a new router for the realm
        router = self._router_factory.start_realm(rlm)

        # add a router/realm service session
        cfg = ComponentConfig(realm)
        rlm.session = RouterServiceSession(cfg, router, schemas)
        self._router_session_factory.add(rlm.session, authrole=u'trusted')

    def stop_router_realm(self, id, close_sessions=False, details=None):
        """
        Stop a router realm.

        When a realm has stopped, no new session will be allowed to attach to the realm.
        Optionally, close all sessions currently attached to the realm.

        :param id: ID of the realm to stop.
        :type id: str
        :param close_sessions: If `True`, close all session currently attached.
        :type close_sessions: bool
        """
        self.log.debug("{}.stop_router_realm".format(self.__class__.__name__),
                       id=id, close_sessions=close_sessions)

        # FIXME
        raise NotImplementedError()

    def get_router_realm_roles(self, id, details=None):
        """

        :param id: The ID of the router realm to list roles for.
        :type id: str

        :returns: list -- A list of roles.
        """
        self.log.debug("{}.get_router_realm_roles".format(self.__class__.__name__), id=id)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        return self.realms[id].roles.values()

    def start_router_realm_role(self, id, role_id, config, details=None):
        """
        Adds a role to a realm.

        :param id: The ID of the realm the role should be added to.
        :type id: str
        :param role_id: The ID of the role to add.
        :type role_id: str
        :param config: The role configuration.
        :type config: dict
        """
        self.log.debug("{}.add_router_realm_role".format(self.__class__.__name__),
                       id=id, role_id=role_id, config=config)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        if role_id in self.realms[id].roles:
            raise ApplicationError(u"crossbar.error.already_exists", "A role with ID '{}' already exists in realm with ID '{}'".format(role_id, id))

        self.realms[id].roles[role_id] = RouterRealmRole(role_id, config)

        realm = self.realms[id].config['name']
        self._router_factory.add_role(realm, config)

    def stop_router_realm_role(self, id, role_id, details=None):
        """
        Drop a role from a realm.

        :param id: The ID of the realm to drop a role from.
        :type id: str
        :param role_id: The ID of the role within the realm to drop.
        :type role_id: str
        """
        self.log.debug("{}.drop_router_realm_role".format(self.__class__.__name__),
                       id=id, role_id=role_id)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        if role_id not in self.realms[id].roles:
            raise ApplicationError(u"crossbar.error.no_such_object", "No role with ID '{}' in realm with ID '{}'".format(role_id, id))

        del self.realms[id].roles[role_id]

    def get_router_components(self, details=None):
        """
        List application components currently running (embedded) in this router.
        """
        self.log.debug("{}.get_router_components".format(self.__class__.__name__))

        res = []
        for component in sorted(self.components.values(), key=lambda c: c.created):
            res.append({
                'id': component.id,
                'created': utcstr(component.created),
                'config': component.config,
            })
        return res

    def start_router_component(self, id, config, details=None):
        """
        Dynamically start an application component to run next to the router in "embedded mode".

        :param id: The ID of the component to start.
        :type id: str
        :param config: The component configuration.
        :type config: obj
        """
        self.log.debug("{}.start_router_component".format(self.__class__.__name__),
                       id=id, config=config)

        # prohibit starting a component twice
        #
        if id in self.components:
            emsg = "Could not start component: a component with ID '{}'' is already running (or starting)".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        # check configuration
        #
        try:
            checkconfig.check_router_component(config)
        except Exception as e:
            emsg = "Invalid router component configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
        else:
            self.log.debug("Starting {type}-component on router.",
                           type=config['type'])

        # resolve references to other entities
        #
        references = {}
        for ref in config.get('references', []):
            ref_type, ref_id = ref.split(':')
            if ref_type == u'connection':
                if ref_id in self._connections:
                    references[ref] = self._connections[ref_id]
                else:
                    emsg = "cannot resolve reference '{}' - no '{}' with ID '{}'".format(ref, ref_type, ref_id)
                    self.log.error(emsg)
                    raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
            else:
                emsg = "cannot resolve reference '{}' - invalid reference type '{}'".format(ref, ref_type)
                self.log.error(emsg)
                raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # create component config
        #
        realm = config['realm']
        extra = config.get('extra', None)
        component_config = ComponentConfig(realm=realm, extra=extra)
        create_component = _appsession_loader(config)

        # .. and create and add an WAMP application session to
        # run the component next to the router
        #
        try:
            session = create_component(component_config)

            # any exception spilling out from user code in onXXX handlers is fatal!
            def panic(fail, msg):
                self.log.error("Fatal error in component: {} - {}".format(msg, fail.value))
                session.disconnect()
            session._swallow_error = panic
        except Exception as e:
            msg = "{}".format(e).strip()
            self.log.error("Component instantiation failed:\n\n{err}", err=msg)
            raise

        self.components[id] = RouterComponent(id, config, session)
        self._router_session_factory.add(session, authrole=config.get('role', u'anonymous'))
        self.log.debug("Added component {id}", id=id)

    def stop_router_component(self, id, details=None):
        """
        Stop an application component running on this router.

        **Usage:**

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.stop_router_component``

        **Errors:**

        The procedure may raise the following errors:

        * ``crossbar.error.no_such_object`` - no component with given ID is currently running in this router
        * ``crossbar.error.cannot_stop`` - failed to stop the component running in this router

        :param id: The ID of the component to stop.
        :type id: unicode
        """
        self.log.debug("{}.stop_router_component".format(self.__class__.__name__), id=id)

        if id in self.components:
            self.log.debug("Worker {}: stopping component {}".format(self.config.extra.worker, id))

            try:
                # self._components[id].disconnect()
                self._session_factory.remove(self.components[id])
                del self.components[id]
            except Exception as e:
                raise ApplicationError(u"crossbar.error.cannot_stop", "Failed to stop component {}: {}".format(id, e))
        else:
            raise ApplicationError(u"crossbar.error.no_such_object", "No component {}".format(id))

    def get_router_transports(self, details=None):
        """
        List currently running transports.

        **Usage:**

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.get_router_transports``

        :returns: List of transports currently running.
        :rtype: list of dict
        """
        self.log.debug("{}.get_router_transports".format(self.__class__.__name__))

        res = []
        for transport in sorted(self.transports.values(), key=lambda c: c.created):
            res.append({
                'id': transport.id,
                'created': utcstr(transport.created),
                'config': transport.config,
            })
        return res

    def start_router_transport(self, id, config, details=None):
        """
        Start a transport on this router and return when the transport has started.

        **Usage:**

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.start_router_transport``

        The procedure takes a WAMP transport configuration with a listening endpoint, e.g.

        .. code-block:: javascript

            {
                "type": "websocket",
                "endpoint": {
                    "type": "tcp",
                    "port": 8080
                }
            }

        **Errors:**

        The procedure may raise the following errors:

        * ``crossbar.error.invalid_configuration`` - the provided transport configuration is invalid
        * ``crossbar.error.already_running`` - a transport with the given ID is already running (or starting)
        * ``crossbar.error.cannot_listen`` - could not listen on the configured listening endpoint of the transport
        * ``crossbar.error.class_import_failed`` - a side-by-side component could not be instantiated

        **Events:**

        The procedure will publish an event when the transport **is starting** to

        * ``crossbar.node.<node_id>.worker.<worker_id>.on_router_transport_starting``

        and publish an event when the transport **has started** to

        * ``crossbar.node.<node_id>.worker.<worker_id>.on_router_transport_started``

        :param id: The ID of the transport to start.
        :type id: unicode
        :param config: The transport configuration.
        :type config: dict
        """
        self.log.debug("{}.start_router_transport".format(self.__class__.__name__),
                       id=id, config=config)

        # prohibit starting a transport twice
        #
        if id in self.transports:
            emsg = "Could not start transport: a transport with ID '{}' is already running (or starting)".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        # check configuration
        #
        try:
            checkconfig.check_router_transport(config)
        except Exception as e:
            emsg = "Invalid router transport configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
        else:
            self.log.debug("Starting {}-transport on router.".format(config['type']))

        # standalone WAMP-RawSocket transport
        #
        if config['type'] == 'rawsocket':

            transport_factory = WampRawSocketServerFactory(self._router_session_factory, config)
            transport_factory.noisy = False

        # standalone WAMP-WebSocket transport
        #
        elif config['type'] == 'websocket':

            transport_factory = WampWebSocketServerFactory(self._router_session_factory, self.config.extra.cbdir, config, self._templates)
            transport_factory.noisy = False

        # Flash-policy file server pseudo transport
        #
        elif config['type'] == 'flashpolicy':

            transport_factory = FlashPolicyFactory(config.get('allowed_domain', None), config.get('allowed_ports', None))

        # WebSocket testee pseudo transport
        #
        elif config['type'] == 'websocket.testee':

            transport_factory = WebSocketTesteeServerFactory(config, self._templates)

        # Stream testee pseudo transport
        #
        elif config['type'] == 'stream.testee':

            transport_factory = StreamTesteeServerFactory()

        # Twisted Web based transport
        #
        elif config['type'] == 'web':

            options = config.get('options', {})

            # create Twisted Web root resource
            #
            if '/' in config['paths']:
                root_config = config['paths']['/']
                root = self.create_resource(root_config, nested=False)
            else:
                root = Resource404(self._templates, b'')

            # create Twisted Web resources on all non-root paths configured
            #
            self.add_paths(root, config.get('paths', {}))

            # create the actual transport factory
            #
            transport_factory = Site(root)
            transport_factory.noisy = False

            # Web access logging
            #
            if not options.get('access_log', False):
                transport_factory.log = lambda _: None

            # Traceback rendering
            #
            transport_factory.displayTracebacks = options.get('display_tracebacks', False)

            # HSTS
            #
            if options.get('hsts', False):
                if 'tls' in config['endpoint']:
                    hsts_max_age = int(options.get('hsts_max_age', 31536000))
                    transport_factory.requestFactory = createHSTSRequestFactory(transport_factory.requestFactory, hsts_max_age)
                else:
                    self.log.warn("Warning: HSTS requested, but running on non-TLS - skipping HSTS")

        # Unknown transport type
        #
        else:
            # should not arrive here, since we did check_transport() in the beginning
            raise Exception("logic error")

        # create transport endpoint / listening port from transport factory
        #
        d = create_listening_port_from_config(config['endpoint'], transport_factory, self.config.extra.cbdir, self._reactor)

        def ok(port):
            self.transports[id] = RouterTransport(id, config, transport_factory, port)
            self.log.debug("Router transport '{}'' started and listening".format(id))
            return

        def fail(err):
            emsg = "Cannot listen on transport endpoint: {log_failure}"
            self.log.error(emsg, log_failure=err)
            raise ApplicationError(u"crossbar.error.cannot_listen", emsg)

        d.addCallbacks(ok, fail)
        return d

    def add_paths(self, resource, paths):
        """
        Add all configured non-root paths under a resource.

        :param resource: The parent resource under which to add paths.
        :type resource: Resource
        :param paths: The path configurations.
        :type paths: dict
        """
        for path in sorted(paths):

            if isinstance(path, six.text_type):
                webPath = path.encode('utf8')
            else:
                webPath = path

            if path != b"/":
                resource.putChild(webPath, self.create_resource(paths[path]))

    def create_resource(self, path_config, nested=True):
        """
        Creates child resource to be added to the parent.

        :param path_config: Configuration for the new child resource.
        :type path_config: dict

        :returns: Resource -- the new child resource
        """
        # WAMP-WebSocket resource
        #
        if path_config['type'] == 'websocket':

            ws_factory = WampWebSocketServerFactory(self._router_session_factory, self.config.extra.cbdir, path_config, self._templates)

            # FIXME: Site.start/stopFactory should start/stop factories wrapped as Resources
            ws_factory.startFactory()

            return WebSocketResource(ws_factory)

        # Static file hierarchy resource
        #
        elif path_config['type'] == 'static':

            static_options = path_config.get('options', {})

            if 'directory' in path_config:

                static_dir = os.path.abspath(os.path.join(self.config.extra.cbdir, path_config['directory']))

            elif 'package' in path_config:

                if 'resource' not in path_config:
                    raise ApplicationError(u"crossbar.error.invalid_configuration", "missing resource")

                try:
                    mod = importlib.import_module(path_config['package'])
                except ImportError as e:
                    emsg = "Could not import resource {} from package {}: {}".format(path_config['resource'], path_config['package'], e)
                    self.log.error(emsg)
                    raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
                else:
                    try:
                        static_dir = os.path.abspath(pkg_resources.resource_filename(path_config['package'], path_config['resource']))
                    except Exception as e:
                        emsg = "Could not import resource {} from package {}: {}".format(path_config['resource'], path_config['package'], e)
                        self.log.error(emsg)
                        raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

            else:

                raise ApplicationError(u"crossbar.error.invalid_configuration", "missing web spec")

            static_dir = static_dir.encode('ascii', 'ignore')  # http://stackoverflow.com/a/20433918/884770

            # create resource for file system hierarchy
            #
            if static_options.get('enable_directory_listing', False):
                static_resource_class = StaticResource
            else:
                static_resource_class = StaticResourceNoListing

            cache_timeout = static_options.get('cache_timeout', DEFAULT_CACHE_TIMEOUT)

            static_resource = static_resource_class(static_dir, cache_timeout=cache_timeout)

            # set extra MIME types
            #
            static_resource.contentTypes.update(EXTRA_MIME_TYPES)
            if 'mime_types' in static_options:
                static_resource.contentTypes.update(static_options['mime_types'])
            patchFileContentTypes(static_resource)

            # render 404 page on any concrete path not found
            #
            static_resource.childNotFound = Resource404(self._templates, static_dir)

            return static_resource

        # WSGI resource
        #
        elif path_config['type'] == 'wsgi':

            if not _HAS_WSGI:
                raise ApplicationError(u"crossbar.error.invalid_configuration", "WSGI unsupported")

            if 'module' not in path_config:
                raise ApplicationError(u"crossbar.error.invalid_configuration", "missing WSGI app module")

            if 'object' not in path_config:
                raise ApplicationError(u"crossbar.error.invalid_configuration", "missing WSGI app object")

            # import WSGI app module and object
            mod_name = path_config['module']
            try:
                mod = importlib.import_module(mod_name)
            except ImportError as e:
                raise ApplicationError(u"crossbar.error.invalid_configuration", "WSGI app module '{}' import failed: {} - Python search path was {}".format(mod_name, e, sys.path))
            else:
                obj_name = path_config['object']
                if obj_name not in mod.__dict__:
                    raise ApplicationError(u"crossbar.error.invalid_configuration", "WSGI app object '{}' not in module '{}'".format(obj_name, mod_name))
                else:
                    app = getattr(mod, obj_name)

            # Create a threadpool for running the WSGI requests in
            pool = ThreadPool(maxthreads=path_config.get("maxthreads", 20),
                              minthreads=path_config.get("minthreads", 0),
                              name="crossbar_wsgi_threadpool")
            self._reactor.addSystemEventTrigger('before', 'shutdown', pool.stop)
            pool.start()

            # Create a Twisted Web WSGI resource from the user's WSGI application object
            try:
                wsgi_resource = WSGIResource(self._reactor, pool, app)

                if not nested:
                    wsgi_resource = WSGIRootResource(wsgi_resource, {})
            except Exception as e:
                raise ApplicationError(u"crossbar.error.invalid_configuration", "could not instantiate WSGI resource: {}".format(e))
            else:
                return wsgi_resource

        # Redirecting resource
        #
        elif path_config['type'] == 'redirect':
            redirect_url = path_config['url'].encode('ascii', 'ignore')
            return RedirectResource(redirect_url)

        # JSON value resource
        #
        elif path_config['type'] == 'json':
            value = path_config['value']

            return JsonResource(value)

        # CGI script resource
        #
        elif path_config['type'] == 'cgi':

            cgi_processor = path_config['processor']
            cgi_directory = os.path.abspath(os.path.join(self.config.extra.cbdir, path_config['directory']))
            cgi_directory = cgi_directory.encode('ascii', 'ignore')  # http://stackoverflow.com/a/20433918/884770

            return CgiDirectory(cgi_directory, cgi_processor, Resource404(self._templates, cgi_directory))

        # WAMP-Longpoll transport resource
        #
        elif path_config['type'] == 'longpoll':

            path_options = path_config.get('options', {})

            lp_resource = WampLongPollResource(self._router_session_factory,
                                               timeout=path_options.get('request_timeout', 10),
                                               killAfter=path_options.get('session_timeout', 30),
                                               queueLimitBytes=path_options.get('queue_limit_bytes', 128 * 1024),
                                               queueLimitMessages=path_options.get('queue_limit_messages', 100),
                                               debug=path_options.get('debug', False),
                                               debug_transport_id=path_options.get('debug_transport_id', None)
                                               )
            lp_resource._templates = self._templates

            return lp_resource

        # Publisher resource (part of REST-bridge)
        #
        elif path_config['type'] == 'publisher':

            # create a vanilla session: the publisher will use this to inject events
            #
            publisher_session_config = ComponentConfig(realm=path_config['realm'], extra=None)
            publisher_session = ApplicationSession(publisher_session_config)

            # add the publisher session to the router
            #
            self._router_session_factory.add(publisher_session, authrole=path_config.get('role', 'anonymous'))

            # now create the publisher Twisted Web resource
            #
            return PublisherResource(path_config.get('options', {}), publisher_session)

        # Webhook resource (part of REST-bridge)
        #
        elif path_config['type'] == 'webhook':

            # create a vanilla session: the webhook will use this to inject events
            #
            webhook_session_config = ComponentConfig(realm=path_config['realm'], extra=None)
            webhook_session = ApplicationSession(webhook_session_config)

            # add the webhook session to the router
            #
            self._router_session_factory.add(webhook_session, authrole=path_config.get('role', 'anonymous'))

            # now create the webhook Twisted Web resource
            #
            return WebhookResource(path_config.get('options', {}), webhook_session)

        # Caller resource (part of REST-bridge)
        #
        elif path_config['type'] == 'caller':

            # create a vanilla session: the caller will use this to inject calls
            #
            caller_session_config = ComponentConfig(realm=path_config['realm'], extra=None)
            caller_session = ApplicationSession(caller_session_config)

            # add the calling session to the router
            #
            self._router_session_factory.add(caller_session, authrole=path_config.get('role', 'anonymous'))

            # now create the caller Twisted Web resource
            #
            return CallerResource(path_config.get('options', {}), caller_session)

        # File Upload resource
        #
        elif path_config['type'] == 'upload':

            upload_directory = os.path.abspath(os.path.join(self.config.extra.cbdir, path_config['directory']))
            upload_directory = upload_directory.encode('ascii', 'ignore')  # http://stackoverflow.com/a/20433918/884770
            if not os.path.isdir(upload_directory):
                emsg = "configured upload directory '{}' in file upload resource isn't a directory".format(upload_directory)
                self.log.error(emsg)
                raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

            if 'temp_directory' in path_config:
                temp_directory = os.path.abspath(os.path.join(self.config.extra.cbdir, path_config['temp_directory']))
                temp_directory = temp_directory.encode('ascii', 'ignore')  # http://stackoverflow.com/a/20433918/884770
            else:
                temp_directory = os.path.abspath(tempfile.gettempdir())
                temp_directory = os.path.join(temp_directory, 'crossbar-uploads')
                if not os.path.exists(temp_directory):
                    os.makedirs(temp_directory)

            if not os.path.isdir(temp_directory):
                emsg = "configured temp directory '{}' in file upload resource isn't a directory".format(temp_directory)
                self.log.error(emsg)
                raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

            # file upload progress and finish events are published via this session
            #
            upload_session_config = ComponentConfig(realm=path_config['realm'], extra=None)
            upload_session = ApplicationSession(upload_session_config)

            self._router_session_factory.add(upload_session, authrole=path_config.get('role', 'anonymous'))

            self.log.info("File upload resource started. Uploads to {upl} using temp folder {tmp}.", upl=upload_directory, tmp=temp_directory)

            return FileUploadResource(upload_directory, temp_directory, path_config['form_fields'], upload_session, path_config.get('options', {}))

        # Generic Twisted Web resource
        #
        elif path_config['type'] == 'resource':

            try:
                klassname = path_config['classname']

                self.log.debug("Starting class '{}'".format(klassname))

                c = klassname.split('.')
                module_name, klass_name = '.'.join(c[:-1]), c[-1]
                module = importlib.import_module(module_name)
                make = getattr(module, klass_name)

                return make(path_config.get('extra', {}))

            except Exception as e:
                emsg = "Failed to import class '{}' - {}".format(klassname, e)
                self.log.error(emsg)
                self.log.error("PYTHONPATH: {pythonpath}", pythonpath=sys.path)
                raise ApplicationError(u"crossbar.error.class_import_failed", emsg)

        # Schema Docs resource
        #
        elif path_config['type'] == 'schemadoc':

            realm = path_config['realm']

            if realm not in self.realm_to_id:
                raise ApplicationError(u"crossbar.error.no_such_object", "No realm with URI '{}' configured".format(realm))

            realm_id = self.realm_to_id[realm]

            realm_schemas = self.realms[realm_id].session._schemas

            return SchemaDocResource(self._templates, realm, realm_schemas)

        # Nested subpath resource
        #
        elif path_config['type'] == 'path':

            nested_paths = path_config.get('paths', {})

            if '/' in nested_paths:
                nested_resource = self.create_resource(nested_paths['/'])
            else:
                nested_resource = Resource()

            # nest subpaths under the current entry
            #
            self.add_paths(nested_resource, nested_paths)

            return nested_resource

        else:
            raise ApplicationError(u"crossbar.error.invalid_configuration",
                                   "invalid Web path type '{}' in {} config".format(path_config['type'],
                                                                                    'nested' if nested else 'root'))

    def stop_router_transport(self, id, details=None):
        """
        Stop a transport currently running in this router and return when
        the transport has stopped.

        **Usage:**

        This procedure is registered under

        * ``crossbar.node.<node_id>.worker.<worker_id>.stop_router_transport``

        **Errors:**

        The procedure may raise the following errors:

        * ``crossbar.error.not_running`` - no transport with given ID is currently running on this router (or the transport is already stopping)
        * ``crossbar.error.cannot_stop`` - could not stop listening on the transport listening endpoint

        **Events:**

        The procedure will publish an event when the transport **is stopping** to

        * ``crossbar.node.<node_id>.worker.<worker_id>.on_router_transport_stopping``

        and publish an event when the transport **has stopped** to

        * ``crossbar.node.<node_id>.worker.<worker_id>.on_router_transport_stopped``

        :param id: The ID of the transport to stop.
        :type id: unicode
        """
        self.log.debug("{}.stop_router_transport".format(self.__class__.__name__), id=id)

        # FIXME
        if id not in self.transports:
            #      if not id in self.transports or self.transports[id].status != 'started':
            emsg = "Cannot stop transport: no transport with ID '{}' or transport is already stopping".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        self.log.debug("Stopping transport with ID '{}'".format(id))

        d = self.transports[id].port.stopListening()

        def ok(_):
            del self.transports[id]

        def fail(err):
            raise ApplicationError(u"crossbar.error.cannot_stop", "Failed to stop transport: {}".format(str(err.value)))

        d.addCallbacks(ok, fail)
        return d

    def get_router_links(self, details=None):
        """
        List currently running router links.
        """
        self.log.debug("{}.get_router_links".format(self.__class__.__name__))

        raise NotImplementedError()

    def start_router_link(self, id, config, details=None):
        """
        Start a link on this router.

        :param id: The ID of the link to start.
        :type id: str
        :param config: The link configuration.
        :type config: dict
        """
        self.log.debug("{}.start_router_link".format(self.__class__.__name__),
                       id=id, config=config)

        raise NotImplementedError()

    def stop_router_link(self, id, details=None):
        """
        Stop a link on this router.

        :param id: The ID of the link to stop.
        :type id: str
        """
        self.log.debug("{}.stop_router_link".format(self.__class__.__name__),
                       id=id)

        raise NotImplementedError()
