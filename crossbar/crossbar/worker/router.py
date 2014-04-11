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

import os
import jinja2
import pkg_resources

from twisted.internet import reactor

from twisted.python import log
from twisted.internet.defer import DeferredList
from twisted.internet.endpoints import serverFromString

from autobahn.wamp.exception import ApplicationError

from crossbar.router.session import CrossbarRouterFactory

from crossbar.router.protocol import CrossbarRouterSessionFactory, \
                                     CrossbarWampWebSocketServerFactory, \
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




class RouterTransport:
   def __init__(self, id, config, port):
      self.id = id
      self.config = config
      self.port = port



class RouterComponent:
   def __init__(self, id, realm, config, session):
      self.id = id
      self.realm = realm
      self.config = config
      self.session = session



from twisted.internet.defer import inlineCallbacks




class RouterInstance:
   def __init__(self, id):
      self.id = id

      self.factory = CrossbarRouterFactory()
      self.session_factory = CrossbarRouterSessionFactory(self.factory)

      self.transports = {}
      self.transport_no = 0

      self.components = {}
      self.component_no = 0




class RouterModule:
   """
   Entities:
      - Realms
      - Transports
      - Links
      - Components
   """

   def __init__(self, cbdir, debug = False):
      self._cbdir = cbdir
      self.debug = debug

      ## Jinja2 templates for Web (like WS status page et al)
      ##
      templates_dir = os.path.abspath(pkg_resources.resource_filename("crossbar", "web/templates"))
      if self.debug:
         log.msg("Using Crossbar.io web templates from {}".format(templates_dir))
      self._templates = jinja2.Environment(loader = jinja2.FileSystemLoader(templates_dir))

      self._session = None

      self._routers = {}
      self._router_no = 0


   def connect(self, session):
      assert(self._session is None)

      self._session = session
      self._pid = session._pid
      self._node_name = session._node_name

      dl = []
      procs = [
         'list',
         'start',
         'stop',
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

      for proc in procs:
         uri = 'crossbar.node.{}.worker.{}.router.{}'.format(self._node_name, self._pid, proc)
         dl.append(self._session.register(getattr(self, proc), uri))

      d = DeferredList(dl)
      return d



   def list(self):
      """
      List currently running router instances.
      """
      res = []
      for router in self._routers.values():
         r = {
            'id': router.id,
            'transports': len(router.transports),
            'components': len(router.components)
         }
         res.append(r)
      return res


   def start(self):
      """
      Start a new router instance.
      """
      self._router_no += 1
      self._routers[self._router_no] = RouterInstance(self._router_no)
      return self._router_no



   def stop(self, router_index):
      if self.debug:
         log.msg("Worker {}: stopping router module".format(self._pid))



   def list_realms(self, router_index):
      ## FIXME
      return []



   def start_realm(self, router_index, realm, config):
      if self.debug:
         log.msg("Worker {}: realm started".format(self._pid))



   def stop_realm(self, router_index, realm):
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
               log.msg("Worker {}: starting class '{}' in realm '{}' ..".format(self._pid, klassname, realm))

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
               log.msg("Worker {}: starting WAMPlet '{}/{}' in realm '{}' ..".format(self._pid, dist, name, realm))

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
            log.msg("Worker {}: stopping component {}".format(self._pid, id))

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



   def start_transport(self, router_index, config):
      """
      Start a transport on this router module.
      """
      if not router_index in self._routers:
         raise ApplicationError("crossbar.error.no_such_router", router_index)

      router = self._routers[router_index]


      if self.debug:
         log.msg("Worker {}: starting '{}' transport on router module.".format(config['type'], self._pid))


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

         transport_factory = CrossbarWampWebSocketServerFactory(router.session_factory, config, self._templates)


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

               root_dir = os.path.abspath(os.path.join(self._cbdir, root_config['directory']))

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
                  ws_factory = CrossbarWampWebSocketServerFactory(router.session_factory, path_config, self._templates)

                  ## FIXME: Site.start/stopFactory should start/stop factories wrapped as Resources
                  ws_factory.startFactory()

                  ws_resource = WebSocketResource(ws_factory)
                  root.putChild(path, ws_resource)


               ## Static file hierarchy resource
               ##
               elif path_config['type'] == 'static':

                  static_options = path_config.get('options', {})

                  if 'directory' in path_config:
                  
                     static_dir = os.path.abspath(os.path.join(self._cbdir, path_config['directory']))

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
                  cgi_directory = os.path.abspath(os.path.join(self._cbdir, path_config['directory']))
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
      if True:
         from twisted.internet.endpoints import TCP4ServerEndpoint, SSL4ServerEndpoint, UNIXServerEndpoint
         from twisted.internet.endpoints import serverFromString
         
         from crossbar.twisted.tlsctx import TlsServerContextFactory

         #server = serverFromString(reactor, "ssl:8080:privateKey=.crossbar/server.key:certKey=.crossbar/server.crt")

         try:
            endpoint_config = config.get('endpoint')

            ## a TCP4 endpoint
            ##
            if endpoint_config['type'] == 'tcp':

               ## the listening port
               ##
               port = int(endpoint_config['port'])

               ## the listening interface
               ##
               interface = str(endpoint_config.get('interface', '').strip())

               ## the TCP accept queue depth
               ##
               backlog = int(endpoint_config.get('backlog', 50))

               if 'tls' in endpoint_config:

                  key_filepath = os.path.abspath(os.path.join(self._cbdir, endpoint_config['tls']['key']))
                  cert_filepath = os.path.abspath(os.path.join(self._cbdir, endpoint_config['tls']['certificate']))

                  with open(key_filepath) as key_file:
                     with open(cert_filepath) as cert_file:

                        if 'dhparam' in endpoint_config['tls']:
                           dhparam_filepath = os.path.abspath(os.path.join(self._cbdir, endpoint_config['tls']['dhparam']))
                        else:
                           dhparam_filepath = None

                        ## create a TLS context factory
                        ##
                        key = key_file.read()
                        cert = cert_file.read()
                        ciphers = endpoint_config['tls'].get('ciphers')
                        ctx = TlsServerContextFactory(key, cert, ciphers = ciphers, dhParamFilename = dhparam_filepath)

                  ## create a TLS server endpoint
                  ##
                  server = SSL4ServerEndpoint(reactor,
                                              port,
                                              ctx,
                                              backlog = backlog,
                                              interface = interface)
               else:
                  ## create a non-TLS server endpoint
                  ##
                  server = TCP4ServerEndpoint(reactor,
                                              port,
                                              backlog = backlog,
                                              interface = interface)

            ## a Unix Domain Socket endpoint
            ##
            elif endpoint_config['type'] == 'unix':

               ## the accept queue depth
               ##
               backlog = int(endpoint_config.get('backlog', 50))

               ## the path
               ##
               path = os.path.abspath(os.path.join(self._cbdir, endpoint_config['path']))

               ## create the endpoint
               ##
               server = UNIXServerEndpoint(reactor, path, backlog = backlog)

            else:
               raise ApplicationError("crossbar.error.invalid_configuration", "invalid endpoint type '{}'".format(endpoint_config['type']))

         except Exception as e:
            log.msg("endpoint creation failed: {}".format(e))
            raise e


         d = server.listen(transport_factory)

         def ok(port):
            router.transport_no += 1
            router.transports[router.transport_no] = RouterTransport(router.transport_no, config, port)
            return router.transport_no

         def fail(err):
            log.msg("cannot listen on endpoint: {}".format(err.value))
            raise ApplicationError("crossbar.error.cannotlisten", str(err.value))

         d.addCallbacks(ok, fail)
         return d

      else:        
         # http://stackoverflow.com/questions/12542700/setsockopt-before-connect-for-reactor-connecttcp
         # http://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IReactorSocket.html
         # http://stackoverflow.com/questions/10077745/twistedweb-on-multicore-multiprocessor

         ## start the WebSocket server from a custom port that share TCP ports
         ##
         port = CustomPort(9000, transport_factory, reuse = True)
         try:
            port.startListening()
         except twisted.internet.error.CannotListenError as e:
            raise ApplicationError("crossbar.error.cannotlisten", str(e))
         else:
            self._transport_no += 1
            self._transports[self._transport_no] = RouterTransport(self._transport_no, config, port)
            return self._transport_no



   def stop_transport(self, router_index, transport_index):
      """
      Stop a transport on this router module.
      """
      if id in self._transports:
         if self.debug:
            log.msg("Worker {}: stopping transport {}".format(self._pid, id))

         try:
            d = self._transports[id].port.stopListening()

            def ok(_):
               del self._transports[id]

            def fail(err):
               raise ApplicationError("crossbar.error.transport.cannot_stop", "Failed to stop transport {}: {}".format(id, str(err.value)))

            d.addCallbacks(ok, fail)
            return d

         except Exception as e:
            raise ApplicationError("crossbar.error.transport.cannot_stop", "Failed to stop transport {}: {}".format(id, e))
      else:
         raise ApplicationError("crossbar.error.no_such_transport", "No transport {}".format(id))



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
         log.msg("Worker {}: starting router link".format(self._pid))



   def stop_link(self, router_index, link_index):
      """
      Stop a link on this router.
      """
      if self.debug:
         log.msg("Worker {}: stopping router link {}".format(self._pid, id))
