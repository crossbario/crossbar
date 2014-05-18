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
import pkg_resources

from twisted.internet import reactor

from twisted.python import log
from twisted.internet.defer import DeferredList
from twisted.internet.defer import inlineCallbacks

from twisted.internet.endpoints import serverFromString

from autobahn.wamp.exception import ApplicationError

from crossbar.router.session import CrossbarRouterSessionFactory, \
                                    CrossbarRouterFactory

from crossbar.router.protocol import CrossbarWampWebSocketServerFactory, \
                                     CrossbarWampRawSocketServerFactory

from crossbar.worker.testee import TesteeServerFactory


from twisted.web.wsgi import WSGIResource
from autobahn.twisted.resource import WebSocketResource, \
                                      WSGIRootResource, \
                                      HTTPChannelHixie76Aware


import importlib
import pkg_resources

from twisted.web.server import Site

## monkey patch the Twisted Web server identification
import twisted
import crossbar
twisted.web.server.version = "Crossbar/{}".format(crossbar.__version__)


from twisted.web.static import File
from twisted.web.resource import Resource

from autobahn.twisted.resource import WebSocketResource

from crossbar.twisted.site import createHSTSRequestFactory
from crossbar.twisted.resource import FileNoListing, JsonResource, Resource404, CgiDirectory, RedirectResource

from autobahn.wamp.types import ComponentConfig
from autobahn.twisted.wamp import ApplicationSession

from crossbar.worker.native import NativeWorker



EXTRA_MIME_TYPES = {
   '.svg': 'image/svg+xml',
   '.jgz': 'text/javascript'
}



class RouterRealm:
   """
   A realm managed by a router.
   """
   def __init__(self, id, realm, config):
      """
      Ctor.

      :param id: The realm index within the router.
      :type id: int
      :param realm: The realm name.
      :type realm: str
      :param config: The realm configuration.
      :type config: str
      """
      self.id = id
      self.realm = realm
      self.config = config



class RouterTransport:
   """
   A transport attached to a router.
   """
   def __init__(self, id, config, port):
      """
      Ctor.

      :param id: The transport index within the router.
      :type id: int
      :param config: The transport's configuration.
      :type config: dict
      :param port: The transport's listening port (https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IListeningPort.html)
      :type port: obj
      """
      self.id = id
      self.config = config
      self.port = port



class RouterComponent:
   """
   An embedded application component running inside a router instance.
   """
   def __init__(self, id, realm, config, session):
      """
      Ctor.

      :param id: The component index within the router instance.
      :type id: int
      :param realm: The realm within the router instance this component runs in.
      :type realm: str
      :param config: The component's configuration.
      :type config: dict
      :param session: The component application session.
      :type session: obj (instance of ApplicationSession)
      """
      self.id = id
      self.realm = realm
      self.config = config
      self.session = session



class RouterWorker(NativeWorker):
   """
   A native Crossbar.io worker that runs a WAMP router which can manage
   multiple realms, run multiple transports and links, as well as host
   multiple (embedded) application components.
   """
   WORKER_TYPE = 'router'


   @inlineCallbacks
   def onJoin(self, details):
      """
      """
      ## Jinja2 templates for Web (like WS status page et al)
      ##
      templates_dir = os.path.abspath(pkg_resources.resource_filename("crossbar", "web/templates"))
      if self.debug:
         log.msg("Using Crossbar.io web templates from {}".format(templates_dir))
      self._templates = jinja2.Environment(loader = jinja2.FileSystemLoader(templates_dir))

      ## factory for producing (per-realm) routers
      self.factory = CrossbarRouterFactory()

      ## factory for producing router sessions
      self.session_factory = CrossbarRouterSessionFactory(self.factory)

      ## map: realm index -> RouterRealm
      self.realms = {}
      self.realm_no = 0

      ## map: transport index -> RouterTransport
      self.transports = {}
      self.transport_no = 0

      ## map: link index -> RouterLink
      self.links = {}
      self.link_no = 0

      ## map: component index -> RouterComponent
      self.components = {}
      self.component_no = 0


      ## the procedures registered
      procs = [
         'list_realms',
         'start_realm',
         'stop_realm',
         'list_components',
         'start_component',
         'stop_component',
         'list_transports',
         'start_transport',
         'stop_transport',
         'list_links',
         'start_link',
         'stop_link'
      ]

      dl = []
      for proc in procs:
         uri = 'crossbar.node.{}.worker.{}.router.{}'.format(self.config.extra.node, self.config.extra.pid, proc)
         dl.append(self.register(getattr(self, proc), uri))

      regs = yield DeferredList(dl)

      if self.debug:
         log.msg("RouterWorker procedures registered.")

      yield NativeWorker.onJoin(self, details)



   def list_realms(self, router_index):
      ## FIXME
      return []



   def start_realm(self, realm, config):
      if self.debug:
         log.msg("Worker {}: realm started".format(self.config.extra.pid))
      return 1



   def stop_realm(self, realm_index):
      ## FIXME
      pass



   def list_components(self, router_index):
      """
      List currently running application components.
      """
      if not router_index in self._routers:
         raise ApplicationError("crossbar.error.no_such_router", router_index)

      router = self._routers[router_index]

      res = {}
      for component in router.components.values():
         res[component.id] = component.config

      return res



   def start_component(self, router_index, realm, config):
      """
      Dynamically start an application component to run next to the router in "embedded mode".

      :param realm: The realm in which to start the component.
      :type realm: str
      :param config: The component configuration.
      :type config: obj

      :returns int -- The component index assigned.
      """
      if not router_index in self._routers:
         raise ApplicationError("crossbar.error.no_such_router", router_index)

      router = self._routers[router_index]

      cfg = ComponentConfig(realm = realm, extra = config.get('extra', None))

      if config['type'] == 'class':

         try:
            klassname = config['name']

            if self.debug:
               log.msg("Worker {}: starting class '{}' in realm '{}' ..".format(self.config.extra.pid, klassname, realm))

            import importlib
            c = klassname.split('.')
            mod, klass = '.'.join(c[:-1]), c[-1]
            app = importlib.import_module(mod)
            make = getattr(app, klass)

         except Exception as e:
            log.msg("Worker {}: failed to import class - {}".format(e))
            raise ApplicationError("crossbar.error.class_import_failed", str(e))

      elif config['type'] == 'wamplet':

         try:
            dist = config['dist']
            name = config['entry']

            if self.debug:
               log.msg("Worker {}: starting WAMPlet '{}/{}' in realm '{}' ..".format(self.config.extra.pid, dist, name, realm))

            ## make is supposed to make instances of ApplicationSession
            make = pkg_resources.load_entry_point(dist, 'autobahn.twisted.wamplet', name)

         except Exception as e:
            log.msg("Worker {}: failed to import class - {}".format(e))
            raise ApplicationError("crossbar.error.class_import_failed", str(e))

      else:
         raise ApplicationError("crossbar.error.invalid_configuration", "invalid component type '{}'".format(config['type']))


      ## .. and create and add an WAMP application session to
      ## run the component next to the router
      ##
      try:
         comp = make(cfg)
      except Exception as e:
         raise ApplicationError("crossbar.error.class_import_failed", str(e))

      if not isinstance(comp, ApplicationSession):
         raise ApplicationError("crossbar.error.class_import_failed", "session not derived of ApplicationSession")


      router.session_factory.add(comp)

      router.component_no += 1
      router.components[router.component_no] = RouterComponent(router.component_no, realm, config, comp)

      return router.component_no



   def stop_component(self, router_index, component_index):
      """
      Stop an application component on this router.
      """
      if id in self._components:
         if self.debug:
            log.msg("Worker {}: stopping component {}".format(self.config.extra.pid, id))

         try:
            #self._components[id].disconnect()
            self._session_factory.remove(self._components[id])
            del self._components[id]
         except Exception as e:
            raise ApplicationError("crossbar.error.component.cannot_stop", "Failed to stop component {}: {}".format(id, e))
      else:
         raise ApplicationError("crossbar.error.no_such_component", "No component {}".format(id))



   def list_transports(self, router_index):
      """
      List currently running transports.
      """
      res = {}
      for key, transport in self._transports.items():
         res[key] = transport.config
      return res
      #return sorted(self._transports.keys())



   def start_transport(self, config):
      """
      Start a transport on this router module.
      """
      router = self


      if self.debug:
         log.msg("Worker {}: starting '{}' transport on router module.".format(config['type'], self.config.extra.pid))


      ## check for valid transport type
      ##
      if not config['type'] in ['websocket', 'websocket.testee', 'web', 'rawsocket']:
         raise ApplicationError("crossbar.error.invalid_transport", "Unknown transport type '{}'".format(config['type']))


      ## standalone WAMP-RawSocket transport
      ##
      if config['type'] == 'rawsocket':

         transport_factory = CrossbarWampRawSocketServerFactory(router.session_factory, config)


      ## standalone WAMP-WebSocket transport
      ##
      elif config['type'] == 'websocket':

         transport_factory = CrossbarWampWebSocketServerFactory(router.session_factory, self.config.extra.cbdir, config, self._templates)


      ## standalone WebSocket testee transport
      ##
      elif config['type'] == 'websocket.testee':

         transport_factory = TesteeServerFactory(config, self._templates)


      ## Twisted Web transport
      ##
      elif config['type'] == 'web':

         options = config.get('options', {})


         ## create Twisted Web root resource
         ##
         root_config = config['paths']['/']
         root_type = root_config['type']


         ## Static file hierarchy root resource
         ##
         if root_type == 'static':


            if 'directory' in root_config:

               root_dir = os.path.abspath(os.path.join(self.config.extra.cbdir, root_config['directory']))

            elif 'module' in root_config:
               if not 'resource' in root_config:
                  raise ApplicationError("crossbar.error.invalid_configuration", "missing module")

               try:
                  mod = importlib.import_module(root_config['module'])
               except ImportError:
                  raise ApplicationError("crossbar.error.invalid_configuration", "module import failed")
               else:
                  try:
                     root_dir = os.path.abspath(pkg_resources.resource_filename(root_config['module'], root_config['resource']))
                  except Exception, e:
                     raise ApplicationError("crossbar.error.invalid_configuration", str(e))
                  else:
                     mod_version = getattr(mod, '__version__', '?.?.?')
                     log.msg("Loaded static Web resource '{}' from module '{} {}' (filesystem path {})".format(root_config['resource'], root_config['module'], mod_version, root_dir))

            else:
               raise ApplicationError("crossbar.error.invalid_configuration", "missing web spec")

            root_dir = root_dir.encode('ascii', 'ignore') # http://stackoverflow.com/a/20433918/884770
            if self.debug:
               log.msg("Starting Web service at root directory {}".format(root_dir))


            ## create resource for file system hierarchy
            ##
            if options.get('enable_directory_listing', False):
               root = File(root_dir)
            else:
               root = FileNoListing(root_dir)

            ## set extra MIME types
            ##
            root.contentTypes.update(EXTRA_MIME_TYPES)

            ## render 404 page on any concrete path not found
            ##
            root.childNotFound = Resource404(self._templates, root_dir)


         ## WSGI root resource
         ##
         elif root_type == 'wsgi':

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
                  ws_factory = CrossbarWampWebSocketServerFactory(router.session_factory, self.config.extra.cbdir, path_config, self._templates)

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

                  elif 'module' in path_config:

                     if not 'resource' in path_config:
                        raise ApplicationError("crossbar.error.invalid_configuration", "missing module")

                     try:
                        mod = importlib.import_module(path_config['module'])
                     except ImportError:
                        raise ApplicationError("crossbar.error.invalid_configuration", "module import failed")
                     else:
                        try:
                           static_dir = os.path.abspath(pkg_resources.resource_filename(path_config['module'], path_config['resource']))
                        except Exception, e:
                           raise ApplicationError("crossbar.error.invalid_configuration", str(e))

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

                  ## render 404 page on any concrete path not found
                  ##
                  static_resource.childNotFound = Resource404(self._templates, static_dir)

                  root.putChild(path, static_resource)


               ## WSGI resource
               ##
               elif path_config['type'] == 'wsgi':

                  wsgi_options = path_config.get('options', {})

                  if not 'module' in path_config:
                     raise ApplicationError("crossbar.error.invalid_configuration", "missing module")

                  if not 'object' in path_config:
                     raise ApplicationError("crossbar.error.invalid_configuration", "missing object")

                  try:
                     mod = importlib.import_module(path_config['module'])
                  except ImportError:
                     raise ApplicationError("crossbar.error.invalid_configuration", "module import failed")
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

                  log.msg("Web path type 'longpoll' not implemented")

               else:
                  raise ApplicationError("crossbar.error.invalid_configuration", "invalid Web path type '{}'".format(path_config['type']))


         ## create the actual transport factory
         ##
         transport_factory = Site(root)


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
         raise Exception("logic error")


      ## create transport endpoint / listening port from transport factory
      ##
      from crossbar.twisted.endpoint import create_listening_port_from_config
      from twisted.internet import reactor

      d = create_listening_port_from_config(config['endpoint'], transport_factory, self.config.extra.cbdir, reactor)

      def ok(port):
         router.transport_no += 1
         router.transports[router.transport_no] = RouterTransport(router.transport_no, config, port)
         return router.transport_no

      def fail(err):
         log.msg("cannot listen on endpoint: {}".format(err.value))
         raise ApplicationError("crossbar.error.cannotlisten", str(err.value))

      d.addCallbacks(ok, fail)
      return d



   def stop_transport(self, transport_index):
      """
      Stop a transport on this router on this router.

      :param transport_index: Index of the transport to stop.
      :type transport_index: int
      """
      if not transport_index in self._transports:
         raise ApplicationError("crossbar.error.no_such_transport", "No transport started with index {}".format(transport_index))

      if self.debug:
         log.msg("Worker {}: stopping transport {}".format(self.config.extra.pid, transport_index))

      try:
         d = self._transports[transport_index].port.stopListening()

         def ok(_):
            del self._transports[transport_index]

         def fail(err):
            raise ApplicationError("crossbar.error.transport.cannot_stop", "Failed to stop transport {}: {}".format(id, str(err.value)))

         d.addCallbacks(ok, fail)
         return d

      except Exception as e:
         raise ApplicationError("crossbar.error.transport.cannot_stop", "Failed to stop transport {}: {}".format(id, e))



   def list_links(self, router_index):
      """
      List currently running links.
      """
      return []



   def start_link(self, router_index, config):
      """
      Start a link on this router.
      """
      if self.debug:
         log.msg("Worker {}: starting router link".format(self.config.extra.pid))



   def stop_link(self, router_index, link_index):
      """
      Stop a link on this router.
      """
      if self.debug:
         log.msg("Worker {}: stopping router link {}".format(self.config.extra.pid, id))
