###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

from __future__ import absolute_import

__all__ = ['RouterWorker']


import os
import jinja2
import importlib
import pkg_resources
from datetime import datetime


from twisted.internet import reactor

from twisted.python import log
from twisted.internet.defer import DeferredList
from twisted.internet.defer import inlineCallbacks

from twisted.internet.endpoints import serverFromString

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from crossbar.router.session import CrossbarRouterSessionFactory, \
                                    CrossbarRouterFactory, \
                                    CrossbarRouterServiceSession

from crossbar.router.protocol import CrossbarWampWebSocketServerFactory, \
                                     CrossbarWampRawSocketServerFactory

from crossbar.worker.testee import TesteeServerFactory

from twisted.internet import reactor
from crossbar.twisted.endpoint import create_listening_port_from_config

from autobahn.wamp.types import PublishOptions, \
                                RegisterOptions


try:
   from twisted.web.wsgi import WSGIResource
   _HAS_WSGI = True
except ImportError:
   ## Twisted hasn't ported this to Python 3 yet
   _HAS_WSGI = False


from autobahn.twisted.resource import WebSocketResource, \
                                      WSGIRootResource, \
                                      HTTPChannelHixie76Aware

from crossbar.twisted.resource import WampLongPollResource, \
                                      SchemaDocResource

import importlib
import pkg_resources

from twisted.web.server import Site

## monkey patch the Twisted Web server identification
import twisted
import crossbar
twisted.web.server.version = "Crossbar/{}".format(crossbar.__version__)

try:
   from twisted.web.static import File
   from crossbar.twisted.resource import FileNoListing
   _HAS_STATIC = True
except ImportError:
   ## Twisted hasn't ported this to Python 3 yet
   _HAS_STATIC = False


from twisted.web.resource import Resource

from crossbar.twisted.site import createHSTSRequestFactory

from crossbar.twisted.resource import JsonResource, \
                                      Resource404, \
                                      RedirectResource, \
                                      PusherResource

from crossbar.twisted.resource import _HAS_STATIC, _HAS_CGI

if _HAS_CGI:
   from crossbar.twisted.resource import CgiDirectory



from autobahn.wamp.types import ComponentConfig
from autobahn.twisted.wamp import ApplicationSession

from crossbar.worker.native import NativeWorkerSession

from crossbar.common import checkconfig
from crossbar.twisted.site import patchFileContentTypes



EXTRA_MIME_TYPES = {
   '.svg': 'image/svg+xml',
   '.jgz': 'text/javascript'
}



class RouterTransport:
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



class RouterComponent:
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



class RouterRealm:
   """
   A realm managed by a router.
   """

   def __init__(self, id, config, session):
      """
      Ctor.

      :param id: The realm ID within the router.
      :type id: str
      :param config: The realm configuration.
      :type config: dict
      """
      self.id = id
      self.config = config
      self.session = session
      self.created = datetime.utcnow()
      self.roles = {}



class RouterRealmRole:
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
      yield NativeWorkerSession.onJoin(self, details, publish_ready = False)

      ## Jinja2 templates for Web (like WS status page et al)
      ##
      templates_dir = os.path.abspath(pkg_resources.resource_filename("crossbar", "web/templates"))
      if self.debug:
         log.msg("Using Web templates from {}".format(templates_dir))
      self._templates = jinja2.Environment(loader = jinja2.FileSystemLoader(templates_dir))

      ## factory for producing (per-realm) routers
      self.factory = CrossbarRouterFactory()

      ## factory for producing router sessions
      self.session_factory = CrossbarRouterSessionFactory(self.factory)

      ## map: realm ID -> RouterRealm
      self.realms = {}

      ## map: realm URI -> realm ID
      self.realm_to_id = {}

      ## map: transport ID -> RouterTransport
      self.transports = {}

      ## map: link ID -> RouterLink
      self.links = {}

      ## map: component ID -> RouterComponent
      self.components = {}


      ## the procedures registered
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
         if self.debug:
            log.msg("Registering procedure '{}'".format(uri))
         dl.append(self.register(getattr(self, proc), uri, options = RegisterOptions(details_arg = 'details', discloseCaller = True)))

      regs = yield DeferredList(dl)

      if self.debug:
         log.msg("RouterWorker registered {} procedures".format(len(regs)))

      ## NativeWorkerSession.publish_ready()
      yield self.publish_ready()



   def get_router_realms(self, details = None):
      """
      List realms currently managed by this router.
      """
      if self.debug:
         log.msg("{}.get_router_realms".format(self.__class__.__name__))

      raise NotImplementedError()



   def start_router_realm(self, id, config, schemas = None, details = None):
      """
      Starts a realm managed by this router.

      :param id: The ID of the realm to start.
      :type id: str
      :param config: The realm configuration.
      :type config: dict
      :param schemas: An (optional) initial schema dictionary to load.
      :type schemas: dict
      """
      if self.debug:
         log.msg("{}.start_router_realm".format(self.__class__.__name__), id, config, schemas)

      realm = config['name']
      cfg = ComponentConfig(realm)
      session = CrossbarRouterServiceSession(cfg, schemas)

      rlm = RouterRealm(id, config, session)

      self.realms[id] = rlm
      self.realm_to_id[realm] = id

      self.factory.start_realm(rlm)

      self.session_factory.add(session, authrole = 'trusted')



   def stop_router_realm(self, id, close_sessions = False, details = None):
      """
      Stop a router realm.

      When a realm has stopped, no new session will be allowed to attach to the realm.
      Optionally, close all sessions currently attached to the realm.

      :param id: ID of the realm to stop.
      :type id: str
      :param close_sessions: If `True`, close all session currently attached.
      :type close_sessions: bool
      """
      if self.debug:
         log.msg("{}.stop_router_realm".format(self.__class__.__name__), id, close_sessions)

      raise NotImplementedError()



   def get_router_realm_roles(self, id, details = None):
      """

      :param id: The ID of the router realm to list roles for.
      :type id: str

      :returns: list -- A list of roles.
      """
      if self.debug:
         log.msg("{}.get_router_realm_roles".format(self.__class__.__name__), id)

      if id not in self.realms:
         raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

      return self.realms[id].roles.values()



   def start_router_realm_role(self, id, role_id, config, details = None):
      """
      Adds a role to a realm.

      :param id: The ID of the realm the role should be added to.
      :type id: str
      :param role_id: The ID of the role to add.
      :type role_id: str
      :param config: The role configuration.
      :type config: dict
      """
      if self.debug:
         log.msg("{}.add_router_realm_role".format(self.__class__.__name__), id, role_id, config)

      if id not in self.realms:
         raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

      if role_id in self.realms[id].roles:
         raise ApplicationError("crossbar.error.already_exists", "A role with ID '{}' already exists in realm with ID '{}'".format(role_id, id))

      self.realms[id].roles[role_id] = RouterRealmRole(role_id, config)

      realm = self.realms[id].config['name']
      self.factory.add_role(realm, config)



   def stop_router_realm_role(self, id, role_id, details = None):
      """
      Drop a role from a realm.

      :param id: The ID of the realm to drop a role from.
      :type id: str
      :param role_id: The ID of the role within the realm to drop.
      :type role_id: str
      """
      if self.debug:
         log.msg("{}.drop_router_realm_role".format(self.__class__.__name__), id, role_id)

      if id not in self.realms:
         raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

      if role_id not in self.realms[id].roles:
         raise ApplicationError("crossbar.error.no_such_object", "No role with ID '{}' in realm with ID '{}'".format(role_id, id))

      del self.realms[id].roles[role_id]



   def get_router_components(self, details = None):
      """
      List application components currently running (embedded) in this router.
      """
      if self.debug:
         log.msg("{}.get_router_components".format(self.__class__.__name__))

      res = []
      for component in sorted(self._components.values(), key = lambda c: c.created):
         res.append({
            'id': component.id,
            'created': utcstr(component.created),
            'config': component.config,
         })
      return res



   def start_router_component(self, id, config, details = None):
      """
      Dynamically start an application component to run next to the router in "embedded mode".

      :param id: The ID of the component to start.
      :type id: str
      :param config: The component configuration.
      :type config: obj
      """
      if self.debug:
         log.msg("{}.start_router_component".format(self.__class__.__name__), id, config)

      ## prohibit starting a component twice
      ##
      if id in self.components:
         emsg = "ERROR: could not start component - a component with ID '{}'' is already running (or starting)".format(id)
         log.msg(emsg)
         raise ApplicationError('crossbar.error.already_running', emsg)

      ## check configuration
      ##
      try:
         checkconfig.check_router_component(config)
      except Exception as e:
         emsg = "ERROR: invalid router component configuration ({})".format(e)
         log.msg(emsg)
         raise ApplicationError("crossbar.error.invalid_configuration", emsg)
      else:
         if self.debug:
            log.msg("Starting {}-component on router.".format(config['type']))


      realm = config['realm']
      cfg = ComponentConfig(realm = realm, extra = config.get('extra', None))

      if config['type'] == 'class':

         try:
            klassname = config['classname']

            if self.debug:
               log.msg("Starting class '{}'".format(klassname))
           
            c = klassname.split('.')
            module_name, klass_name = '.'.join(c[:-1]), c[-1]
            module = importlib.import_module(module_name)
            make = getattr(module, klass_name)

         except Exception as e:
            emsg = "Failed to import class '{}' - {}".format(klassname, e)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.class_import_failed", emsg)

      elif config['type'] == 'wamplet':

         try:
            dist = config['package']
            name = config['entrypoint']

            if self.debug:
               log.msg("Starting WAMPlet '{}/{}'".format(dist, name))

            ## make is supposed to make instances of ApplicationSession
            make = pkg_resources.load_entry_point(dist, 'autobahn.twisted.wamplet', name)

         except Exception as e:
            emsg = "Failed to import wamplet '{}/{}' - {}".format(dist, name, e)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.class_import_failed", emsg)

      else:
         raise ApplicationError("crossbar.error.invalid_configuration", "invalid component type '{}'".format(config['type']))


      ## .. and create and add an WAMP application session to
      ## run the component next to the router
      ##
      try:
         session = make(cfg)
      except Exception as e:
         raise ApplicationError("crossbar.error.class_import_failed", str(e))

      if not isinstance(session, ApplicationSession):
         raise ApplicationError("crossbar.error.class_import_failed", "session not derived of ApplicationSession")


      self.components[id] = RouterComponent(id, config, session)
      self.session_factory.add(session, authrole = config.get('role', 'anonymous'))



   def stop_router_component(self, id, details = None):
      """
      Stop an application component running on this router.

      :param id: The ID of the component to stop.
      :type id: str
      """
      if self.debug:
         log.msg("{}.stop_router_component".format(self.__class__.__name__), id)

      if id in self._components:
         if self.debug:
            log.msg("Worker {}: stopping component {}".format(self.config.extra.worker, id))

         try:
            #self._components[id].disconnect()
            self._session_factory.remove(self._components[id])
            del self._components[id]
         except Exception as e:
            raise ApplicationError("crossbar.error.component.cannot_stop", "Failed to stop component {}: {}".format(id, e))
      else:
         raise ApplicationError("crossbar.error.no_such_component", "No component {}".format(id))



   def get_router_transports(self, details = None):
      """
      List currently running transports.
      """
      if self.debug:
         log.msg("{}.get_router_transports".format(self.__class__.__name__))

      res = {}
      for key, transport in self._transports.items():
         res[key] = transport.config
      return res
      #return sorted(self._transports.keys())



   def start_router_transport(self, id, config, details = None):
      """
      Start a transport on this router.

      :param id: The ID of the transport to start.
      :type id: str
      :param config: The transport configuration.
      :type config: dict
      """
      if self.debug:
         log.msg("{}.start_router_transport".format(self.__class__.__name__), id, config)

      ## prohibit starting a transport twice
      ##
      if id in self.transports:
         emsg = "ERROR: could not start transport - a transport with ID '{}'' is already running (or starting)".format(id)
         log.msg(emsg)
         raise ApplicationError('crossbar.error.already_running', emsg)

      ## check configuration
      ##
      try:
         checkconfig.check_router_transport(config)
      except Exception as e:
         emsg = "ERROR: invalid router transport configuration ({})".format(e)
         log.msg(emsg)
         raise ApplicationError("crossbar.error.invalid_configuration", emsg)
      else:
         if self.debug:
            log.msg("Starting {}-transport on router.".format(config['type']))


      ## standalone WAMP-RawSocket transport
      ##
      if config['type'] == 'rawsocket':

         transport_factory = CrossbarWampRawSocketServerFactory(self.session_factory, config)
         transport_factory.noisy = False


      ## standalone WAMP-WebSocket transport
      ##
      elif config['type'] == 'websocket':

         transport_factory = CrossbarWampWebSocketServerFactory(self.session_factory, self.config.extra.cbdir, config, self._templates)
         transport_factory.noisy = False


      ## Twisted Web based transport
      ##
      elif config['type'] == 'web':

         options = config.get('options', {})

         ## create Twisted Web root resource
         ##
         root_config = config['paths']['/']

         root_type = root_config['type']
         root_options = root_config.get('options', {})


         ## Static file hierarchy root resource
         ##
         if root_type == 'static':

            if 'directory' in root_config:

               root_dir = os.path.abspath(os.path.join(self.config.extra.cbdir, root_config['directory']))

            elif 'package' in root_config:

               if not 'resource' in root_config:
                  raise ApplicationError("crossbar.error.invalid_configuration", "missing resource")

               try:
                  mod = importlib.import_module(root_config['package'])
               except ImportError as e:
                  emsg = "ERROR: could not import resource '{}' from package '{}' - {}".format(root_config['resource'], root_config['package'], e)
                  log.msg(emsg)
                  raise ApplicationError("crossbar.error.invalid_configuration", emsg)
               else:
                  try:
                     root_dir = os.path.abspath(pkg_resources.resource_filename(root_config['package'], root_config['resource']))
                  except Exception as e:
                     emsg = "ERROR: could not import resource '{}' from package '{}' - {}".format(root_config['resource'], root_config['package'], e)
                     log.msg(emsg)
                     raise ApplicationError("crossbar.error.invalid_configuration", emsg)
                  else:
                     mod_version = getattr(mod, '__version__', '?.?.?')
                     log.msg("Loaded static Web resource '{}' from package '{} {}' (filesystem path {})".format(root_config['resource'], root_config['package'], mod_version, root_dir))

            else:
               raise ApplicationError("crossbar.error.invalid_configuration", "missing web spec")

            root_dir = root_dir.encode('ascii', 'ignore') # http://stackoverflow.com/a/20433918/884770
            if self.debug:
               log.msg("Starting Web service at root directory {}".format(root_dir))


            ## create resource for file system hierarchy
            ##
            if root_options.get('enable_directory_listing', False):
               root = File(root_dir)
            else:
               root = FileNoListing(root_dir)

            ## set extra MIME types
            ##
            root.contentTypes.update(EXTRA_MIME_TYPES)
            if 'mime_types' in root_options:
               root.contentTypes.update(root_options['mime_types'])
            patchFileContentTypes(root)

            ## render 404 page on any concrete path not found
            ##
            root.childNotFound = Resource404(self._templates, root_dir)


         ## WSGI root resource
         ##
         elif root_type == 'wsgi':

            if not _HAS_WSGI:
               raise ApplicationError("crossbar.error.invalid_configuration", "WSGI unsupported")

            wsgi_options = root_config.get('options', {})

            if not 'module' in root_config:
               raise ApplicationError("crossbar.error.invalid_configuration", "missing module")

            if not 'object' in root_config:
               raise ApplicationError("crossbar.error.invalid_configuration", "missing object")

            try:
               mod = importlib.import_module(root_config['module'])
            except ImportError:
               raise ApplicationError("crossbar.error.invalid_configuration", "module import failed")
            else:
               if not root_config['object'] in mod.__dict__:
                  raise ApplicationError("crossbar.error.invalid_configuration", "object not in module")
               else:
                  app = getattr(mod, root_config['object'])

            ## create a Twisted Web WSGI resource from the user's WSGI application object
            try:
               wsgi_resource = WSGIResource(reactor, reactor.getThreadPool(), app)
            except Exception as e:
               raise ApplicationError("crossbar.error.invalid_configuration", "could not instantiate WSGI resource: {}".format(e))
            else:
               ## create a root resource serving everything via WSGI
               root = WSGIRootResource(wsgi_resource, {})


         ## Redirecting root resource
         ##
         elif root_type == 'redirect':

            redirect_url = root_config['url'].encode('ascii', 'ignore')
            root = RedirectResource(redirect_url)


         ## Pusher resource
         ##
         elif root_type == 'pusher':

            ## create a vanilla session: the pusher will use this to inject events
            ##
            pusher_session_config = ComponentConfig(realm = root_config['realm'], extra = None)
            pusher_session = ApplicationSession(pusher_session_config)

            ## add the pushing session to the router
            ##
            self.session_factory.add(pusher_session, root_config.get('role', 'anonymous'))

            ## now create the pusher Twisted Web resource and add it to resource tree
            ##
            root = PusherResource(root_config.get('options', {}), pusher_session)


         ## Invalid root resource
         ##
         else:
            raise ApplicationError("crossbar.error.invalid_configuration", "invalid Web root path type '{}'".format(root_type))


         ## create Twisted Web resources on all non-root paths configured
         ##
         for path in sorted(config.get('paths', [])):

            if path != "/":

               path_config = config['paths'][path]

               ## websocket_echo
               ## websocket_testee
               ## s3mirror
               ## websocket_stdio
               ##

               ## WAMP-WebSocket resource
               ##
               if path_config['type'] == 'websocket':

                  ws_factory = CrossbarWampWebSocketServerFactory(self.session_factory, self.config.extra.cbdir, path_config, self._templates)

                  ## FIXME: Site.start/stopFactory should start/stop factories wrapped as Resources
                  ws_factory.startFactory()

                  ws_resource = WebSocketResource(ws_factory)
                  root.putChild(path, ws_resource)


               ## Static file hierarchy resource
               ##
               elif path_config['type'] == 'static':

                  static_options = path_config.get('options', {})

                  if 'directory' in path_config:

                     static_dir = os.path.abspath(os.path.join(self.config.extra.cbdir, path_config['directory']))

                  elif 'package' in path_config:

                     if not 'resource' in path_config:
                        raise ApplicationError("crossbar.error.invalid_configuration", "missing resource")

                     try:
                        mod = importlib.import_module(path_config['package'])
                     except ImportError as e:
                        emsg = "ERROR: could not import resource '{}' from package '{}' - {}".format(path_config['resource'], path_config['package'], e)
                        log.msg(emsg)
                        raise ApplicationError("crossbar.error.invalid_configuration", emsg)
                     else:
                        try:
                           static_dir = os.path.abspath(pkg_resources.resource_filename(path_config['package'], path_config['resource']))
                        except Exception as e:
                           emsg = "ERROR: could not import resource '{}' from package '{}' - {}".format(path_config['resource'], path_config['package'], e)
                           log.msg(emsg)
                           raise ApplicationError("crossbar.error.invalid_configuration", emsg)

                  else:

                     raise ApplicationError("crossbar.error.invalid_configuration", "missing web spec")

                  static_dir = static_dir.encode('ascii', 'ignore') # http://stackoverflow.com/a/20433918/884770

                  ## create resource for file system hierarchy
                  ##
                  if static_options.get('enable_directory_listing', False):
                     static_resource = File(static_dir)
                  else:
                     static_resource = FileNoListing(static_dir)

                  ## set extra MIME types
                  ##
                  static_resource.contentTypes.update(EXTRA_MIME_TYPES)
                  if 'mime_types' in static_options:
                     static_resource.contentTypes.update(static_options['mime_types'])
                  patchFileContentTypes(static_resource)

                  ## render 404 page on any concrete path not found
                  ##
                  static_resource.childNotFound = Resource404(self._templates, static_dir)

                  root.putChild(path, static_resource)


               ## WSGI resource
               ##
               elif path_config['type'] == 'wsgi':

                  if not _HAS_WSGI:
                     raise ApplicationError("crossbar.error.invalid_configuration", "WSGI unsupported")

                  wsgi_options = path_config.get('options', {})

                  if not 'module' in path_config:
                     raise ApplicationError("crossbar.error.invalid_configuration", "missing module")

                  if not 'object' in path_config:
                     raise ApplicationError("crossbar.error.invalid_configuration", "missing object")

                  try:
                     mod = importlib.import_module(path_config['module'])
                  except ImportError as e:
                     raise ApplicationError("crossbar.error.invalid_configuration", "module import failed - {}".format(e))
                  else:
                     if not path_config['object'] in mod.__dict__:
                        raise ApplicationError("crossbar.error.invalid_configuration", "object not in module")
                     else:
                        app = getattr(mod, path_config['object'])

                  ## create a Twisted Web WSGI resource from the user's WSGI application object
                  try:
                     wsgi_resource = WSGIResource(reactor, reactor.getThreadPool(), app)
                  except Exception as e:
                     raise ApplicationError("crossbar.error.invalid_configuration", "could not instantiate WSGI resource: {}".format(e))
                  else:
                     root.putChild(path, wsgi_resource)


               ## Redirecting resource
               ##
               elif path_config['type'] == 'redirect':
                  redirect_url = path_config['url'].encode('ascii', 'ignore')
                  redirect_resource = RedirectResource(redirect_url)
                  root.putChild(path, redirect_resource)


               ## JSON value resource
               ##
               elif path_config['type'] == 'json':
                  value = path_config['value']

                  json_resource = JsonResource(value)
                  root.putChild(path, json_resource)


               ## CGI script resource
               ##
               elif path_config['type'] == 'cgi':

                  cgi_processor = path_config['processor']
                  cgi_directory = os.path.abspath(os.path.join(self.config.extra.cbdir, path_config['directory']))
                  cgi_directory = cgi_directory.encode('ascii', 'ignore') # http://stackoverflow.com/a/20433918/884770

                  cgi_resource = CgiDirectory(cgi_directory, cgi_processor, Resource404(self._templates, cgi_directory))

                  root.putChild(path, cgi_resource)


               ## WAMP-Longpoll transport resource
               ##
               elif path_config['type'] == 'longpoll':

                  path_options = path_config.get('options', {})

                  lp_resource = WampLongPollResource(self.session_factory,
                     timeout = path_options.get('request_timeout', 10),
                     killAfter = path_options.get('session_timeout', 30),
                     queueLimitBytes = path_options.get('queue_limit_bytes', 128 * 1024),
                     queueLimitMessages = path_options.get('queue_limit_messages', 100),
                     debug = path_options.get('debug', False),
                     debug_transport_id = path_options.get('debug_transport_id', None)
                  )
                  lp_resource._templates = self._templates

                  root.putChild(path, lp_resource)


               ## Pusher resource
               ##
               elif path_config['type'] == 'pusher':

                  ## create a vanilla session: the pusher will use this to inject events
                  ##
                  pusher_session_config = ComponentConfig(realm = path_config['realm'], extra = None)
                  pusher_session = ApplicationSession(pusher_session_config)

                  ## add the pushing session to the router
                  ##
                  self.session_factory.add(pusher_session, path_config.get('role', 'anonymous'))

                  ## now create the pusher Twisted Web resource and add it to resource tree
                  ##
                  pusher_resource = PusherResource(path_config.get('options', {}), pusher_session)
                  root.putChild(path, pusher_resource)


               ## Schema Docs resource
               ##
               elif path_config['type'] == 'schemadoc':

                  realm = path_config['realm']

                  if not realm in self.realm_to_id:
                     raise ApplicationError("crossbar.error.no_such_object", "No realm with URI '{}' configured".format(realm))

                  realm_id = self.realm_to_id[realm]

                  realm_schemas = self.realms[realm_id].session._schemas

                  schemadoc_resource = SchemaDocResource(self._templates, realm, realm_schemas)
                  root.putChild(path, schemadoc_resource)

               else:
                  raise ApplicationError("crossbar.error.invalid_configuration", "invalid Web path type '{}'".format(path_config['type']))


         ## create the actual transport factory
         ##
         transport_factory = Site(root)
         transport_factory.noisy = False


         ## Web access logging
         ##
         if not options.get('access_log', False):
            transport_factory.log = lambda _: None

         ## Traceback rendering
         ##
         transport_factory.displayTracebacks = options.get('display_tracebacks', False)

         ## HSTS
         ##
         if options.get('hsts', False):
            if 'tls' in config['endpoint']:
               hsts_max_age = int(options.get('hsts_max_age', 31536000))
               transport_factory.requestFactory = createHSTSRequestFactory(transport_factory.requestFactory, hsts_max_age)
            else:
               log.msg("Warning: HSTS requested, but running on non-TLS - skipping HSTS")

         ## enable Hixie-76 on Twisted Web
         ##
         if options.get('hixie76_aware', False):
            transport_factory.protocol = HTTPChannelHixie76Aware # needed if Hixie76 is to be supported

      else:
         ## should not arrive here, since we did check_transport() in the beginning
         raise Exception("logic error")


      ## create transport endpoint / listening port from transport factory
      ##
      d = create_listening_port_from_config(config['endpoint'], transport_factory, self.config.extra.cbdir, reactor)

      def ok(port):
         self.transports[id] = RouterTransport(id, config, transport_factory, port)
         if self.debug:
            log.msg("Router transport '{}'' started and listening".format(id))
         return

      def fail(err):
         emsg = "ERROR: cannot listen on transport endpoint ({})".format(err.value)
         log.msg(emsg)
         raise ApplicationError("crossbar.error.cannot_listen", emsg)

      d.addCallbacks(ok, fail)
      return d



   def stop_router_transport(self, id, details = None):
      """
      Stop a transport on this router on this router.

      :param id: The ID of the transport to stop.
      :type id: dict
      """
      if self.debug:
         log.msg("{}.stop_router_transport".format(self.__class__.__name__), id)

      if not id in self.transports or self.transports['id'] != 'started':
         emsg = "ERROR: cannot stop transport - no transport with ID '{}' (or already stopping)".format(id)
         log.msg(emsg)
         raise ApplicationError('crossbar.error.not_running', emsg)

      if self.debug:
         log.msg("Stopping transport with ID '{}'".format(id))

      d = self._transports[id].port.stopListening()

      def ok(_):
         del self._transports[id]

      def fail(err):
         raise ApplicationError("crossbar.error.cannot_stop", "Failed to stop transport: {}".format(str(err.value)))

      d.addCallbacks(ok, fail)
      return d



   def get_router_links(self, details = None):
      """
      List currently running router links.
      """
      if self.debug:
         log.msg("{}.get_router_links".format(self.__class__.__name__))

      raise NotImplementedError()



   def start_router_link(self, id, config, details = None):
      """
      Start a link on this router.

      :param id: The ID of the link to start.
      :type id: str
      :param config: The link configuration.
      :type config: dict
      """
      if self.debug:
         log.msg("{}.start_router_link".format(self.__class__.__name__), id, config)

      raise NotImplementedError()



   def stop_router_link(self, id, details = None):
      """
      Stop a link on this router.

      :param id: The ID of the link to stop.
      :type id: str
      """
      if self.debug:
         log.msg("{}.stop_router_link".format(self.__class__.__name__), id)

      raise NotImplementedError()
