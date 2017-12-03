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

from __future__ import absolute_import

import os
import sys
import importlib
import pkg_resources
import tempfile
import six

from datetime import datetime

from twisted.internet.defer import Deferred, DeferredList, maybeDeferred
from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure
from twisted.python.threadpool import ThreadPool

from autobahn.util import utcstr
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn import wamp

from crossbar.twisted.resource import StaticResource, StaticResourceNoListing

from crossbar._util import class_name
from crossbar.router import uplink
from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceSession
from crossbar.router.router import RouterFactory

from crossbar.router.protocol import WampWebSocketServerFactory, \
    WampRawSocketServerFactory, WebSocketReverseProxyServerFactory

from crossbar.router.unisocket import UniSocketServerFactory

from crossbar.worker import _appsession_loader
from crossbar.worker.testee import WebSocketTesteeServerFactory, \
    StreamTesteeServerFactory

from crossbar.twisted.endpoint import create_listening_port_from_config

from autobahn.wamp.types import PublishOptions

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
from twisted.web.http import HTTPChannel, _GenericHTTPChannelProtocol

import twisted
import crossbar

from crossbar.twisted.site import createHSTSRequestFactory

from crossbar.twisted.resource import JsonResource, \
    Resource404, RedirectResource, NodeInfoResource

from crossbar.adapter.mqtt.wamp import WampMQTTServerFactory

from crossbar.twisted.fileupload import FileUploadResource

from crossbar.twisted.flashpolicy import FlashPolicyFactory

from autobahn.wamp.types import ComponentConfig

from crossbar.worker.worker import NativeWorkerSession

from crossbar.common import checkconfig
from crossbar.twisted.site import patchFileContentTypes

from crossbar.twisted.resource import _HAS_CGI

from crossbar.adapter.rest import PublisherResource, CallerResource
from crossbar.adapter.rest import WebhookResource

from txaio import make_logger

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
    A (listening) transport running on a router worker.
    """

    def __init__(self, id, config, factory, root_resource, port):
        """

        :param id: The transport ID within the router.
        :type id: str

        :param config: The transport's configuration.
        :type config: dict

        :param factory: The transport factory in use.
        :type factory: obj

        :param root_resource: Twisted Web root resource (used with Site factory), when
            using a Web transport.
        :type root_resource: obj

        :param port: The transport's listening port (https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IListeningPort.html)
        :type port: obj
        """
        self.id = id
        self.config = config
        self.factory = factory
        self.root_resource = root_resource
        self.port = port
        self.created = datetime.utcnow()


class RouterComponent(object):

    """
    A application component hosted and running inside a router worker.
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

    def marshal(self):
        """
        Marshal object information for use with WAMP calls/events.
        """
        now = datetime.utcnow()
        return {
            u'id': self.id,
            # 'started' is used by container-components; keeping it
            # for consistency in the public API
            u'started': utcstr(self.created),
            u'uptime': (now - self.created).total_seconds(),
            u'config': self.config
        }


class RouterRealm(object):

    """
    A realm running in a router worker.
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
        self.uplinks = {}

    def marshal(self):
        return {
            u'id': self.id,
            u'config': self.config,
            u'created': self.created,
            u'roles': self.roles,
        }


class RouterRealmRole(object):

    """
    A role in a realm running in a router worker.
    """

    def __init__(self, id, config):
        """
        Ctor.

        :param id: The role ID within the realm.
        :type id: str
        :param config: The role configuration.
        :type config: dict
        """
        self.id = id
        self.config = config


class RouterRealmUplink(object):

    """
    An uplink in a realm running in a router worker.
    """

    def __init__(self, id, config):
        """
        Ctor.

        :param id: The uplink ID within the realm.
        :type id: str
        :param config: The uplink configuration.
        :type config: dict
        """
        self.id = id
        self.config = config
        self.session = None


class _LessNoisyHTTPChannel(HTTPChannel):
    """
    Internal helper.

    This is basically exactly what Twisted does, except without using
    "log.msg" so we can put it at debug log-level instead
    """
    log = make_logger()

    def timeoutConnection(self):
        self.log.debug(
            "Timing out client: {peer}",
            peer=self.transport.getPeer(),
        )
        if self.abortTimeout is not None:
            self._abortingCall = self.callLater(
                self.abortTimeout, self.forceAbortClient
            )
        self.loseConnection()


def create_transport_from_config(reactor, name, config, cbdir, log, node,
                                 _router_session_factory=None,
                                 _web_templates=None, add_paths=False):
    """
    :return: a Deferred that fires with a new RouterTransport instance
        (or error) representing the given transport using config for
        settings. Raises ApplicationError if the configuration is wrong.
    """

    # check configuration
    #
    try:
        checkconfig.check_router_transport(config)
    except Exception as e:
        emsg = "Invalid router transport configuration: {}".format(e)
        log.error(emsg)
        raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
    else:
        log.debug("Starting {type}-transport on router.", ttype=config['type'])

    # only set (down below) when running a Web transport
    root_resource = None

    # standalone WAMP-RawSocket transport
    #
    if config['type'] == 'rawsocket':

        transport_factory = WampRawSocketServerFactory(_router_session_factory, config)
        transport_factory.noisy = False

    # standalone WAMP-WebSocket transport
    #
    elif config['type'] == 'websocket':

        if _web_templates is None:
            raise ApplicationError(
                "Transport with type='websocket.testee' requires templates"
            )
        transport_factory = WampWebSocketServerFactory(_router_session_factory, cbdir, config, _web_templates)
        transport_factory.noisy = False

    # Flash-policy file server pseudo transport
    #
    elif config['type'] == 'flashpolicy':

        transport_factory = FlashPolicyFactory(config.get('allowed_domain', None), config.get('allowed_ports', None))

    # WebSocket testee pseudo transport
    #
    elif config['type'] == 'websocket.testee':

        if _web_templates is None:
            raise ApplicationError(
                "Transport with type='websocket.testee' requires templates"
            )
        transport_factory = WebSocketTesteeServerFactory(config, _web_templates)

    # Stream testee pseudo transport
    #
    elif config['type'] == 'stream.testee':

        transport_factory = StreamTesteeServerFactory()

    # MQTT legacy adapter transport
    #
    elif config['type'] == 'mqtt':

        transport_factory = WampMQTTServerFactory(
            _router_session_factory, config, reactor)
        transport_factory.noisy = False

    # Twisted Web based transport
    #
    elif config['type'] == 'web':

        if _web_templates is None:
            raise ApplicationError(
                u"Transport with type='web' requires templates"
            )
        transport_factory, root_resource = _create_web_factory(
            reactor,
            config,
            u'tls' in config[u'endpoint'],
            _web_templates,
            log,
            cbdir,
            _router_session_factory,
            node,
            add_paths=add_paths
        )

    # Universal transport
    #
    elif config['type'] == 'universal':
        if 'web' in config:
            if _web_templates is None:
                raise ApplicationError(
                    u"Universal transport with type='web' requires templates"
                )
            web_factory, root_resource = _create_web_factory(
                reactor,
                config['web'],
                u'tls' in config['endpoint'],
                _web_templates,
                log,
                cbdir,
                _router_session_factory,
                node,
                add_paths=add_paths
            )
        else:
            web_factory = None

        if 'rawsocket' in config:
            rawsocket_factory = WampRawSocketServerFactory(_router_session_factory, config['rawsocket'])
            rawsocket_factory.noisy = False
        else:
            rawsocket_factory = None

        if 'mqtt' in config:
            mqtt_factory = WampMQTTServerFactory(
                _router_session_factory, config['mqtt'], reactor)
            mqtt_factory.noisy = False
        else:
            mqtt_factory = None

        if 'websocket' in config:
            if _web_templates is None:
                raise ApplicationError(
                    "Transport with type='websocket.testee' requires templates"
                )
            websocket_factory_map = {}
            for websocket_url_first_component, websocket_config in config['websocket'].items():
                websocket_transport_factory = WampWebSocketServerFactory(_router_session_factory, cbdir, websocket_config, _web_templates)
                websocket_transport_factory.noisy = False
                websocket_factory_map[websocket_url_first_component] = websocket_transport_factory
                log.debug('hooked up websocket factory on request URI {request_uri}', request_uri=websocket_url_first_component)
        else:
            websocket_factory_map = None

        transport_factory = UniSocketServerFactory(web_factory, websocket_factory_map, rawsocket_factory, mqtt_factory)

    # Unknown transport type
    #
    else:
        # should not arrive here, since we did check_transport() in the beginning
        raise Exception("logic error")

    # create transport endpoint / listening port from transport factory
    #
    d = create_listening_port_from_config(
        config['endpoint'],
        cbdir,
        transport_factory,
        reactor,
        log,
    )

    def is_listening(port):
        return RouterTransport(id, config, transport_factory, root_resource, port)
    d.addCallback(is_listening)
    return d


def _create_web_factory(reactor, config, is_secure, templates, log, cbdir, _router_session_factory, node, add_paths=False):
    assert templates is not None

    options = config.get('options', {})

    # create Twisted Web root resource
    if '/' in config['paths']:
        root_config = config['paths']['/']
        root = _create_resource(reactor, root_config, templates, log, cbdir, _router_session_factory, node, nested=False)
    else:
        root = Resource404(templates, b'')

    # create Twisted Web resources on all non-root paths configured
    paths = config.get('paths', {})
    if add_paths and paths:
        _add_paths(reactor, root, paths, templates, log, cbdir, _router_session_factory, node)

    # create the actual transport factory
    transport_factory = Site(
        root,
        timeout=options.get('client_timeout', None),
    )
    transport_factory.noisy = False

    # we override this factory so that we can inject
    # _LessNoisyHTTPChannel to avoid info-level logging on timing
    # out web clients (which happens all the time).
    def channel_protocol_factory():
        return _GenericHTTPChannelProtocol(_LessNoisyHTTPChannel())
    transport_factory.protocol = channel_protocol_factory

    # Web access logging
    if not options.get('access_log', False):
        transport_factory.log = lambda _: None

    # Traceback rendering
    transport_factory.displayTracebacks = options.get('display_tracebacks', False)

    # HSTS
    if options.get('hsts', False):
        if is_secure:
            hsts_max_age = int(options.get('hsts_max_age', 31536000))
            transport_factory.requestFactory = createHSTSRequestFactory(transport_factory.requestFactory, hsts_max_age)
        else:
            log.warn("Warning: HSTS requested, but running on non-TLS - skipping HSTS")

    return transport_factory, root


def _add_paths(reactor, resource, paths, templates, log, cbdir, _router_session_factory, node):
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
            resource.putChild(
                webPath,
                _create_resource(reactor, paths[path], templates, log, cbdir, _router_session_factory, node)
            )


def _remove_paths(reactor, resource, paths):
    """
    Remove (non-root) paths from a resource.

    :param resource: The parent resource from which to remove paths.
    :type resource: Resource

    :param paths: The paths to remove.
    :type paths: dict
    """
    for path in sorted(paths):

        if isinstance(path, six.text_type):
            webPath = path.encode('utf8')
        else:
            webPath = path

        if webPath != b"/":
            if webPath in resource.children:
                del resource.children[webPath]


def _create_resource(reactor, path_config, templates, log, cbdir, _router_session_factory, node, nested=True):
    """
    Creates child resource to be added to the parent.

    :param path_config: Configuration for the new child resource.
    :type path_config: dict

    :returns: Resource -- the new child resource
    """
    assert templates is not None

    # WAMP-WebSocket resource
    #
    if path_config['type'] == 'websocket':

        ws_factory = WampWebSocketServerFactory(_router_session_factory, cbdir, path_config, templates)

        # FIXME: Site.start/stopFactory should start/stop factories wrapped as Resources
        ws_factory.startFactory()

        return WebSocketResource(ws_factory)

    # Reverse WebSocket resource
    #
    elif path_config['type'] == 'websocket-reverseproxy':
        ws_rproxy_factory = WebSocketReverseProxyServerFactory(reactor, path_config)
        ws_rproxy_factory.startFactory()

        return WebSocketResource(ws_rproxy_factory)

    # Static file hierarchy resource
    #
    elif path_config['type'] == 'static':

        static_options = path_config.get('options', {})

        if 'directory' in path_config:

            static_dir = os.path.abspath(os.path.join(cbdir, path_config['directory']))

        elif 'package' in path_config:

            if 'resource' not in path_config:
                raise ApplicationError(u"crossbar.error.invalid_configuration", "missing resource")

            try:
                mod = importlib.import_module(path_config['package'])
            except ImportError as e:
                emsg = "Could not import resource {} from package {}: {}".format(path_config['resource'], path_config['package'], e)
                log.error(emsg)
                raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
            else:
                try:
                    static_dir = os.path.abspath(pkg_resources.resource_filename(path_config['package'], path_config['resource']))
                except Exception as e:
                    emsg = "Could not import resource {} from package {}: {}".format(path_config['resource'], path_config['package'], e)
                    log.error(emsg)
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
        allow_cross_origin = static_options.get('allow_cross_origin', True)

        static_resource = static_resource_class(static_dir, cache_timeout=cache_timeout, allow_cross_origin=allow_cross_origin)

        # set extra MIME types
        #
        static_resource.contentTypes.update(EXTRA_MIME_TYPES)
        if 'mime_types' in static_options:
            static_resource.contentTypes.update(static_options['mime_types'])
        patchFileContentTypes(static_resource)

        # render 404 page on any concrete path not found
        #
        static_resource.childNotFound = Resource404(templates, static_dir)

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
        reactor.addSystemEventTrigger('before', 'shutdown', pool.stop)
        pool.start()

        # Create a Twisted Web WSGI resource from the user's WSGI application object
        try:
            wsgi_resource = WSGIResource(reactor, pool, app)

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

    # Node info resource
    #
    elif path_config['type'] == 'nodeinfo':
        return NodeInfoResource(templates, node)

    # Reverse proxy resource
    #
    elif path_config['type'] == 'reverseproxy':

        # Import late because t.w.proxy imports the reactor
        from twisted.web.proxy import ReverseProxyResource

        host = path_config['host']
        port = int(path_config.get('port', 80))
        path = path_config.get('path', '').encode('ascii', 'ignore')
        return ReverseProxyResource(host, port, path)

    # JSON value resource
    #
    elif path_config['type'] == 'json':
        value = path_config['value']

        return JsonResource(value)

    # CGI script resource
    #
    elif path_config['type'] == 'cgi':

        cgi_processor = path_config['processor']
        cgi_directory = os.path.abspath(os.path.join(cbdir, path_config['directory']))
        cgi_directory = cgi_directory.encode('ascii', 'ignore')  # http://stackoverflow.com/a/20433918/884770

        return CgiDirectory(cgi_directory, cgi_processor, Resource404(templates, cgi_directory))

    # WAMP-Longpoll transport resource
    #
    elif path_config['type'] == 'longpoll':

        path_options = path_config.get('options', {})

        lp_resource = WampLongPollResource(_router_session_factory,
                                           timeout=path_options.get('request_timeout', 10),
                                           killAfter=path_options.get('session_timeout', 30),
                                           queueLimitBytes=path_options.get('queue_limit_bytes', 128 * 1024),
                                           queueLimitMessages=path_options.get('queue_limit_messages', 100),
                                           debug_transport_id=path_options.get('debug_transport_id', None)
                                           )
        lp_resource._templates = templates

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
        _router_session_factory.add(publisher_session, authrole=path_config.get('role', 'anonymous'))

        # now create the publisher Twisted Web resource
        #
        return PublisherResource(path_config.get('options', {}), publisher_session, auth_config=path_config.get('auth', {}))

    # Webhook resource (part of REST-bridge)
    #
    elif path_config['type'] == 'webhook':

        # create a vanilla session: the webhook will use this to inject events
        #
        webhook_session_config = ComponentConfig(realm=path_config['realm'], extra=None)
        webhook_session = ApplicationSession(webhook_session_config)

        # add the webhook session to the router
        #
        _router_session_factory.add(webhook_session, authrole=path_config.get('role', 'anonymous'))

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
        _router_session_factory.add(caller_session, authrole=path_config.get('role', 'anonymous'))

        # now create the caller Twisted Web resource
        #
        return CallerResource(path_config.get('options', {}), caller_session)

    # File Upload resource
    #
    elif path_config['type'] == 'upload':

        upload_directory = os.path.abspath(os.path.join(cbdir, path_config['directory']))
        upload_directory = upload_directory.encode('ascii', 'ignore')  # http://stackoverflow.com/a/20433918/884770
        if not os.path.isdir(upload_directory):
            emsg = "configured upload directory '{}' in file upload resource isn't a directory".format(upload_directory)
            log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        if 'temp_directory' in path_config:
            temp_directory = os.path.abspath(os.path.join(cbdir, path_config['temp_directory']))
            temp_directory = temp_directory.encode('ascii', 'ignore')  # http://stackoverflow.com/a/20433918/884770
        else:
            temp_directory = os.path.abspath(tempfile.gettempdir())
            temp_directory = os.path.join(temp_directory, 'crossbar-uploads')
            if not os.path.exists(temp_directory):
                os.makedirs(temp_directory)

        if not os.path.isdir(temp_directory):
            emsg = "configured temp directory '{}' in file upload resource isn't a directory".format(temp_directory)
            log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # file upload progress and finish events are published via this session
        #
        upload_session_config = ComponentConfig(realm=path_config['realm'], extra=None)
        upload_session = ApplicationSession(upload_session_config)

        _router_session_factory.add(upload_session, authrole=path_config.get('role', 'anonymous'))

        log.info("File upload resource started. Uploads to {upl} using temp folder {tmp}.", upl=upload_directory, tmp=temp_directory)

        return FileUploadResource(upload_directory, temp_directory, path_config['form_fields'], upload_session, path_config.get('options', {}))

    # Generic Twisted Web resource
    #
    elif path_config['type'] == 'resource':

        try:
            klassname = path_config['classname']

            log.debug("Starting class '{name}'", name=klassname)

            c = klassname.split('.')
            module_name, klass_name = '.'.join(c[:-1]), c[-1]
            module = importlib.import_module(module_name)
            make = getattr(module, klass_name)

            return make(path_config.get('extra', {}))

        except Exception as e:
            emsg = "Failed to import class '{}' - {}".format(klassname, e)
            log.error(emsg)
            log.error("PYTHONPATH: {pythonpath}", pythonpath=sys.path)
            raise ApplicationError(u"crossbar.error.class_import_failed", emsg)

    # Schema Docs resource
    #
    elif path_config['type'] == 'schemadoc':

        realm = path_config['realm']

        if realm not in node.realm_to_id:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with URI '{}' configured".format(realm))

        realm_id = node.realm_to_id[realm]

        realm_schemas = node.realms[realm_id].session._schemas

        return SchemaDocResource(templates, realm, realm_schemas)

    # Nested subpath resource
    #
    elif path_config['type'] == 'path':

        nested_paths = path_config.get('paths', {})

        if '/' in nested_paths:
            nested_resource = _create_resource(reactor, nested_paths['/'], templates, cbdir)
        else:
            nested_resource = Resource404(templates, b'')

        # nest subpaths under the current entry
        #
        _add_paths(reactor, nested_resource, nested_paths, templates, log, cbdir, _router_session_factory, node)

        return nested_resource

    else:
        raise ApplicationError(u"crossbar.error.invalid_configuration",
                               "invalid Web path type '{}' in {} config".format(path_config['type'],
                                                                                'nested' if nested else 'root'))


class RouterWorkerSession(NativeWorkerSession):
    """
    A native Crossbar.io worker that runs a WAMP router which can manage
    multiple realms, run multiple transports and links, as well as host
    multiple (embedded) application components.
    """
    WORKER_TYPE = u'router'
    WORKER_TITLE = u'Router'
    router_realm_class = RouterRealm
    router_factory_class = RouterFactory

    def __init__(self, config=None, reactor=None):
        NativeWorkerSession.__init__(self, config, reactor)

        # factory for producing (per-realm) routers
        self._router_factory = self.router_factory_class(None, self)

        # factory for producing router sessions
        self._router_session_factory = RouterSessionFactory(self._router_factory)

        # map: realm ID -> RouterRealm
        self.realms = {}

        # map: realm URI -> realm ID
        self.realm_to_id = {}

        # map: component ID -> RouterComponent
        self.components = {}

        # "global" shared between all components
        self.components_shared = {
            u'reactor': reactor
        }

        # map: transport ID -> RouterTransport
        self.transports = {}

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        self.log.info('Router worker "{worker_id}" session {session_id} initializing ..', worker_id=self._worker_id, session_id=details.session)

        yield NativeWorkerSession.onJoin(self, details, publish_ready=False)

        self.log.info('Router worker "{worker_id}" session ready', worker_id=self._worker_id)

        # NativeWorkerSession.publish_ready()
        yield self.publish_ready()

    def onLeave(self, details):
        # when this router is shutting down, we disconnect all our
        # components so that they have a chance to shutdown properly
        # -- e.g. on a ctrl-C of the router.
        leaves = []
        if self.components:
            for component in self.components.values():
                if component.session.is_connected():
                    d = maybeDeferred(component.session.leave)

                    def done(_):
                        self.log.info(
                            "component '{id}' disconnected",
                            id=component.id,
                        )
                        component.session.disconnect()
                    d.addCallback(done)
                    leaves.append(d)
        dl = DeferredList(leaves, consumeErrors=True)
        # we want our default behavior, which disconnects this
        # router-worker, effectively shutting it down .. but only
        # *after* the components got a chance to shutdown.
        dl.addBoth(lambda _: super(RouterWorkerSession, self).onLeave(details))

    @wamp.register(None)
    def get_router_realms(self, details=None):
        """
        Get realms currently running on this router worker.

        :returns: List of realms currently running.
        :rtype: list of str
        """
        self.log.debug("{name}.get_router_realms", name=self.__class__.__name__)

        return sorted(self.realms.keys())

    @wamp.register(None)
    def get_router_realm(self, realm_id, details=None):
        """
        Return realm detail information.

        :returns: realm information object
        :rtype: dict
        """
        self.log.debug("{name}.get_router_realm(realm_id={realm_id})", name=self.__class__.__name__, realm_id=realm_id)

        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        return self.realms[realm_id].marshal()

    @wamp.register(None)
    @inlineCallbacks
    def start_router_realm(self, realm_id, realm_config, details=None):
        """
        Starts a realm on this router worker.

        :param realm_id: The ID of the realm to start.
        :type realm_id: str

        :param realm_config: The realm configuration.
        :type realm_config: dict
        """
        self.log.debug("{name}.start_router_realm", name=self.__class__.__name__)

        # prohibit starting a realm twice
        #
        if realm_id in self.realms:
            emsg = "Could not start realm: a realm with ID '{}' is already running (or starting)".format(realm_id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        # check configuration
        #
        try:
            checkconfig.check_router_realm(realm_config)
        except Exception as e:
            emsg = "Invalid router realm configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # URI of the realm to start
        realm = realm_config['name']

        # router/realm wide options
        options = realm_config.get('options', {})

        enable_meta_api = options.get('enable_meta_api', True)

        # expose router/realm service API additionally on local node management router
        bridge_meta_api = options.get('bridge_meta_api', False)
        if bridge_meta_api:
            # FIXME
            bridge_meta_api_prefix = u'crossbar.worker.{worker_id}.realm.{realm_id}.root.'.format(worker_id=self._worker_id, realm_id=realm_id)
        else:
            bridge_meta_api_prefix = None

        # track realm
        rlm = self.router_realm_class(realm_id, realm_config)
        self.realms[realm_id] = rlm
        self.realm_to_id[realm] = realm_id

        # create a new router for the realm
        router = self._router_factory.start_realm(rlm)

        # add a router/realm service session
        extra = {
            # the RouterServiceSession will fire this when it is ready
            'onready': Deferred(),

            # if True, forward the WAMP meta API (implemented by RouterServiceSession)
            # that is normally only exposed on the app router/realm _additionally_
            # to the local node management router.
            'enable_meta_api': enable_meta_api,
            'bridge_meta_api': bridge_meta_api,
            'bridge_meta_api_prefix': bridge_meta_api_prefix,

            # the management session on the local node management router to which
            # the WAMP meta API is exposed to additionally, when the bridge_meta_api option is set
            'management_session': self,
        }
        cfg = ComponentConfig(realm, extra)
        rlm.session = RouterServiceSession(cfg, router)
        self._router_session_factory.add(rlm.session, authrole=u'trusted')

        yield extra['onready']

        self.log.info("Realm '{realm}' started", realm=realm)

        self.publish(u'{}.on_realm_started'.format(self._uri_prefix), realm_id)

    @wamp.register(None)
    def stop_router_realm(self, realm_id, details=None):
        """
        Stop a realm currently running on this router worker.

        When a realm has stopped, no new session will be allowed to attach to the realm.
        Optionally, close all sessions currently attached to the realm.

        :param id: ID of the realm to stop.
        :type id: str
        """
        self.log.info("{name}.stop_router_realm", name=self.__class__.__name__)

        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        rlm = self.realms[realm_id]
        realm_name = rlm.config['name']

        detached_sessions = self._router_factory.stop_realm(realm_name)

        del self.realms[realm_id]
        del self.realm_to_id[realm_name]

        realm_stopped = {
            u'id': realm_id,
            u'name': realm_name,
            u'detached_sessions': sorted(detached_sessions)
        }

        return realm_stopped

    @wamp.register(None)
    def get_router_realm_roles(self, id, details=None):
        """
        Get roles currently running on a realm running on this router worker.

        :param id: The ID of the realm to list roles for.
        :type id: str

        :returns: A list of roles.
        :rtype: list of dicts
        """
        self.log.debug("{name}.get_router_realm_roles({id})", name=self.__class__.__name__, id=id)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        return self.realms[id].roles.values()

    @wamp.register(None)
    def start_router_realm_role(self, realm_id, role_id, role_config, details=None):
        """
        Start a role on a realm running on this router worker.

        :param id: The ID of the realm the role should be started on.
        :type id: str
        :param role_id: The ID of the role to start under.
        :type role_id: str
        :param config: The role configuration.
        :type config: dict
        """
        self.log.debug("{name}.start_router_realm_role", name=self.__class__.__name__)

        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if role_id in self.realms[realm_id].roles:
            raise ApplicationError(u"crossbar.error.already_exists", "A role with ID '{}' already exists in realm with ID '{}'".format(role_id, realm_id))

        self.realms[realm_id].roles[role_id] = RouterRealmRole(role_id, role_config)

        realm = self.realms[realm_id].config['name']
        self._router_factory.add_role(realm, role_config)

        topic = u'{}.on_router_realm_role_started'.format(self._uri_prefix)
        event = {
            u'id': role_id
        }
        caller = details.caller if details else None
        self.publish(topic, event, options=PublishOptions(exclude=caller))

        self.log.info('role {role_id} on realm {realm_id} started', realm_id=realm_id, role_id=role_id, role_config=role_config)

    @wamp.register(None)
    def stop_router_realm_role(self, id, role_id, details=None):
        """
        Stop a role currently running on a realm running on this router worker.

        :param id: The ID of the realm of the role to be stopped.
        :type id: str
        :param role_id: The ID of the role to be stopped.
        :type role_id: str
        """
        self.log.debug("{name}.stop_router_realm_role", name=self.__class__.__name__)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        if role_id not in self.realms[id].roles:
            raise ApplicationError(u"crossbar.error.no_such_object", "No role with ID '{}' in realm with ID '{}'".format(role_id, id))

        del self.realms[id].roles[role_id]

    @wamp.register(None)
    def get_router_realm_uplinks(self, id, details=None):
        """
        Get uplinks currently running on a realm running on this router worker.

        :param id: The ID of the router realm to list uplinks for.
        :type id: str

        :returns: A list of uplinks.
        :rtype: list of dicts
        """
        self.log.debug("{name}.get_router_realm_uplinks", name=self.__class__.__name__)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        return self.realms[id].uplinks.values()

    @wamp.register(None)
    @inlineCallbacks
    def start_router_realm_uplink(self, realm_id, uplink_id, uplink_config, details=None):
        """
        Start an uplink on a realm running on this router worker.

        :param realm_id: The ID of the realm the uplink should be started on.
        :type realm_id: unicode
        :param uplink_id: The ID of the uplink to start.
        :type uplink_id: unicode
        :param uplink_config: The uplink configuration.
        :type uplink_config: dict
        """
        self.log.debug("{name}.start_router_realm_uplink", name=self.__class__.__name__)

        # check arguments
        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if uplink_id in self.realms[realm_id].uplinks:
            raise ApplicationError(u"crossbar.error.already_exists", "An uplink with ID '{}' already exists in realm with ID '{}'".format(uplink_id, realm_id))

        # create a representation of the uplink
        self.realms[realm_id].uplinks[uplink_id] = RouterRealmUplink(uplink_id, uplink_config)

        # create the local session of the bridge
        realm = self.realms[realm_id].config['name']
        extra = {
            'onready': Deferred(),
            'uplink': uplink_config
        }
        uplink_session = uplink.LocalSession(ComponentConfig(realm, extra))
        self._router_session_factory.add(uplink_session, authrole=u'trusted')

        # wait until the uplink is ready
        try:
            uplink_session = yield extra['onready']
        except Exception:
            self.log.failure(None)
            raise

        self.realms[realm_id].uplinks[uplink_id].session = uplink_session

        self.log.info("Realm is connected to Crossbar.io uplink router")

    @wamp.register(None)
    def stop_router_realm_uplink(self, id, uplink_id, details=None):
        """
        Stop an uplink currently running on a realm running on this router worker.

        :param id: The ID of the realm to stop an uplink on.
        :type id: str
        :param uplink_id: The ID of the uplink within the realm to stop.
        :type uplink_id: str
        """
        self.log.debug("{name}.stop_router_realm_uplink", name=self.__class__.__name__)

        raise NotImplementedError()

    @wamp.register(None)
    def get_router_components(self, details=None):
        """
        Get app components currently running in this router worker.

        :returns: List of app components currently running.
        :rtype: list of dict
        """
        self.log.debug("{name}.get_router_components", name=self.__class__.__name__)

        res = []
        for component in sorted(self.components.values(), key=lambda c: c.created):
            res.append({
                u'id': component.id,
                u'created': utcstr(component.created),
                u'config': component.config,
            })
        return res

    @wamp.register(None)
    def start_router_component(self, id, config, details=None):
        """
        Start an app component in this router worker.

        :param id: The ID of the component to start.
        :type id: str
        :param config: The component configuration.
        :type config: obj
        """
        self.log.debug("{name}.start_router_component", name=self.__class__.__name__)

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
        component_config = ComponentConfig(realm=realm,
                                           extra=extra,
                                           keyring=None,
                                           controller=self if self.config.extra.expose_controller else None,
                                           shared=self.components_shared if self.config.extra.expose_shared else None)
        create_component = _appsession_loader(config)

        # .. and create and add an WAMP application session to
        # run the component next to the router
        #
        try:
            session = create_component(component_config)

            # any exception spilling out from user code in onXXX handlers is fatal!
            def panic(fail, msg):
                self.log.error(
                    "Fatal error in component: {msg} - {log_failure.value}",
                    msg=msg, log_failure=fail
                )
                session.disconnect()
            session._swallow_error = panic
        except Exception:
            self.log.error(
                "Component instantiation failed",
                log_failure=Failure(),
            )
            raise

        # Note that 'join' is fired to listeners *before* onJoin runs,
        # so if you do 'yield self.leave()' in onJoin we'll still
        # publish "started" before "stopped".

        def publish_stopped(session, stop_details):
            self.log.info(
                "stopped component: {session} id={session_id}",
                session=class_name(session),
                session_id=session._session_id,
            )
            topic = self._uri_prefix + '.on_component_stop'
            event = {u'id': id}
            caller = details.caller if details else None
            self.publish(topic, event, options=PublishOptions(exclude=caller))
            return event

        def publish_started(session, start_details):
            self.log.info(
                "started component: {session} id={session_id}",
                session=class_name(session),
                session_id=session._session_id,
            )
            topic = self._uri_prefix + '.on_component_start'
            event = {u'id': id}
            caller = details.caller if details else None
            self.publish(topic, event, options=PublishOptions(exclude=caller))
            return event
        session.on('leave', publish_stopped)
        session.on('join', publish_started)

        self.components[id] = RouterComponent(id, config, session)
        self._router_session_factory.add(session, authrole=config.get('role', u'anonymous'))
        self.log.debug(
            "Added component {id} (type '{name}')",
            id=id,
            name=class_name(session),
        )

    @wamp.register(None)
    def stop_router_component(self, id, details=None):
        """
        Stop an app component currently running in this router worker.

        :param id: The ID of the component to stop.
        :type id: str
        """
        self.log.debug("{name}.stop_router_component({id})", name=self.__class__.__name__, id=id)

        if id in self.components:
            self.log.debug("Worker {worker}: stopping component {id}", worker=self.config.extra.worker, id=id)

            try:
                # self._components[id].disconnect()
                self._session_factory.remove(self.components[id])
                del self.components[id]
            except Exception as e:
                raise ApplicationError(u"crossbar.error.cannot_stop", "Failed to stop component {}: {}".format(id, e))
        else:
            raise ApplicationError(u"crossbar.error.no_such_object", "No component {}".format(id))

    @wamp.register(None)
    def get_router_transports(self, details=None):
        """
        Get transports currently running in this router worker.

        :returns: List of transports currently running.
        :rtype: list of dict
        """
        self.log.debug("{name}.get_router_transports", name=self.__class__.__name__)

        res = []
        for transport in sorted(self.transports.values(), key=lambda c: c.created):
            res.append({
                u'id': transport.id,
                u'created': utcstr(transport.created),
                u'config': transport.config,
            })
        return res

    @wamp.register(None)
    def start_router_transport(self, id, config, add_paths=False, details=None):
        """
        Start a transport on this router worker.

        :param id: The ID of the transport to start.
        :type id: str
        :param config: The transport configuration.
        :type config: dict
        """
        self.log.debug("{name}.start_router_transport", name=self.__class__.__name__)

        # prohibit starting a transport twice
        #
        if id in self.transports:
            emsg = "Could not start transport: a transport with ID '{}' is already running (or starting)".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        d = create_transport_from_config(
            self._reactor, id, config, self.config.extra.cbdir, self.log, self,
            _router_session_factory=self._router_session_factory,
            _web_templates=self._templates, add_paths=add_paths
        )

        def ok(router_transport):
            self.transports[id] = router_transport
            self.log.debug("Router transport '{id}'' started and listening", id=id)
            return

        def fail(err):
            emsg = "Cannot listen on transport endpoint: {log_failure}"
            self.log.error(emsg, log_failure=err)
            raise ApplicationError(u"crossbar.error.cannot_listen", emsg)

        d.addCallbacks(ok, fail)
        return d

    @wamp.register(None)
    def stop_router_transport(self, id, details=None):
        """
        Stop a transport currently running in this router worker.

        :param id: The ID of the transport to stop.
        :type id: str
        """
        self.log.debug("{name}.stop_router_transport", name=self.__class__.__name__)

        # FIXME
        if id not in self.transports:
            #      if not id in self.transports or self.transports[id].status != 'started':
            emsg = "Cannot stop transport: no transport with ID '{}' or transport is already stopping".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        self.log.debug("Stopping transport with ID '{id}'", id=id)

        d = self.transports[id].port.stopListening()

        def ok(_):
            del self.transports[id]

        def fail(err):
            raise ApplicationError(u"crossbar.error.cannot_stop", "Failed to stop transport: {}".format(str(err.value)))

        d.addCallbacks(ok, fail)
        return d

    @wamp.register(None)
    def start_web_transport_service(self, transport_id, path, config, details=None):
        """
        Start a service on a Web transport.

        :param transport_id: The ID of the transport to start the Web transport service on.
        :type transport_id: str

        :param path: The path (absolute URL, eg "/myservice1") on which to start the service.
        :type path: str

        :param config: The Web service configuration.
        :type config: dict
        """
        self.log.info("{name}.start_web_transport_service(transport_id={transport_id}, path={path}, config={config})",
                      name=self.__class__.__name__,
                      transport_id=transport_id,
                      path=path,
                      config=config)

        transport = self.transports.get(transport_id, None)
        if not (transport and (transport.config[u'type'] == u'web' or (transport.config[u'type'] == u'universal' and transport.config.get(u'web', {})))):
            emsg = "Cannot start service on Web transport: no transport with ID '{}' or transport is not a Web transport".format(transport_id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        caller = details.caller if details else None
        self.publish(self._uri_prefix + u'.on_web_transport_service_starting',
                     transport_id,
                     path,
                     options=PublishOptions(exclude=caller))

        paths = {
            path: config
        }
        _add_paths(self._reactor,
                   transport.root_resource,
                   paths,
                   self._templates,
                   self.log,
                   self.config.extra.cbdir,
                   self._router_session_factory,
                   self)

        on_web_transport_service_started = {
            u'transport_id': transport_id,
            u'path': path,
            u'config': config
        }
        caller = details.caller if details else None
        self.publish(self._uri_prefix + u'.on_web_transport_service_started',
                     transport_id,
                     path,
                     on_web_transport_service_started,
                     options=PublishOptions(exclude=caller))

        return on_web_transport_service_started

    @wamp.register(None)
    def stop_web_transport_service(self, transport_id, path, details=None):
        """
        Stop a service on a Web transport.

        :param transport_id: The ID of the transport to stop the Web transport service on.
        :type transport_id: str

        :param path: The path (absolute URL, eg "/myservice1") of the service to stop.
        :type path: str
        """
        self.log.info("{name}.stop_web_transport_service(transport_id={transport_id}, path={path})",
                      name=self.__class__.__name__,
                      transport_id=transport_id,
                      path=path)

        transport = self.transports.get(transport_id, None)
        if not transport or transport.config[u'type'] != u'web':
            emsg = "Cannot stop service on Web transport: no transport with ID '{}' or transport is not a Web transport".format(transport_id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        if isinstance(path, six.text_type):
            webPath = path.encode('utf8')
        else:
            webPath = path

        if webPath not in transport.root_resource.children:
            emsg = "Cannot stop service on Web transport {}: no service running on path '{}'".format(transport_id, path)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        caller = details.caller if details else None
        self.publish(self._uri_prefix + u'.on_web_transport_service_stopping',
                     transport_id,
                     path,
                     options=PublishOptions(exclude=caller))

        _remove_paths(self._reactor, transport.root_resource, [path])

        on_web_transport_service_stopped = {
            u'transport_id': transport_id,
            u'path': path,
            u'config': transport.config
        }
        caller = details.caller if details else None
        self.publish(self._uri_prefix + u'.on_web_transport_service_starting',
                     transport_id,
                     path,
                     on_web_transport_service_stopped,
                     options=PublishOptions(exclude=caller))
