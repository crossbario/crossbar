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

import importlib
import os
import sys
import tempfile
import six

import pkg_resources
from autobahn.twisted import ApplicationSession
from autobahn.twisted.resource import WebSocketResource, WSGIRootResource
from autobahn.wamp import ApplicationError, ComponentConfig
from crossbar.adapter.rest import PublisherResource, WebhookResource, CallerResource
from crossbar.router.protocol import WampWebSocketServerFactory, WebSocketReverseProxyServerFactory
from crossbar.twisted.fileupload import FileUploadResource
from crossbar.twisted.resource import StaticResource, StaticResourceNoListing, Resource404, RedirectResource, \
    NodeInfoResource, JsonResource, CgiDirectory, WampLongPollResource, SchemaDocResource
from crossbar.twisted.site import patchFileContentTypes
from twisted.python.threadpool import ThreadPool

DEFAULT_CACHE_TIMEOUT = 12 * 60 * 60
EXTRA_MIME_TYPES = {
    '.svg': 'image/svg+xml',
    '.jgz': 'text/javascript'
}

try:
    from twisted.web.wsgi import WSGIResource
    _HAS_WSGI = True
except (ImportError, SyntaxError):
    # Twisted hasn't ported this to Python 3 yet
    _HAS_WSGI = False

from crossbar.twisted.resource import _HAS_CGI

if _HAS_CGI:
    pass


def create_resource(reactor, path_config, templates, log, cbdir, _router_session_factory, node, nested=True):
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
            nested_resource = create_resource(reactor, nested_paths['/'], templates, cbdir)
        else:
            nested_resource = Resource404(templates, b'')

        # nest subpaths under the current entry
        #
        add_paths(reactor, nested_resource, nested_paths, templates, log, cbdir, _router_session_factory, node)

        return nested_resource

    else:
        raise ApplicationError(u"crossbar.error.invalid_configuration",
                               "invalid Web path type '{}' in {} config".format(path_config['type'],
                                                                                'nested' if nested else 'root'))


def add_paths(reactor, resource, paths, templates, log, cbdir, _router_session_factory, node):
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
                create_resource(reactor, paths[path], templates, log, cbdir, _router_session_factory, node)
            )


def remove_paths(reactor, resource, paths):
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
