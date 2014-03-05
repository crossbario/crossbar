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

import sys
import os
import datetime
import argparse
import jinja2
import pkg_resources
import psutil

import twisted
from twisted.python import log
from twisted.internet.defer import DeferredList
from twisted.internet.endpoints import serverFromString

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.router import RouterFactory
from autobahn.wamp.protocol import RouterApplicationSession

from autobahn.twisted.websocket import WampWebSocketServerFactory
from autobahn.twisted.wamp import RouterSessionFactory
from autobahn.twisted.wamp import ApplicationSession

from crossbar.router.router import CrossbarRouterFactory, \
                                   CrossbarRouterSessionFactory, \
                                   CrossbarWampWebSocketServerFactory


class RouterTransport:
   def __init__(self, id, config, port):
      self.id = id
      self.config = config
      self.port = port



class RouterClass:
   def __init__(self, id, klassname, realm):
      self.id = id
      self.klassname = klassname
      self.realm = realm



class RouterModule:
   """
   Entities:
      - Realms
      - Transports
      - Links
      - Classes
   """

   def __init__(self, session, index, cbdir):
      self._session = session
      self._index = index
      self._pid = session._pid
      self._node_name = session._node_name
      self._cbdir = cbdir

      self.debug = self._session.factory.options.debug

      ## Jinja2 templates for Web (like WS status page et al)
      ##
      templates_dir = os.path.abspath(pkg_resources.resource_filename("crossbar", "web/templates"))
      if self.debug:
         log.msg("Worker {}: Using Crossbar.io web templates from {}".format(self._pid, templates_dir))
      self._templates = jinja2.Environment(loader = jinja2.FileSystemLoader(templates_dir))

      self._component_sessions = {}
      self._component_no = 0

      self._router_factory = None


   def start(self):

      print "QQQ2"

      assert(self._router_factory is None)

      self._router_factory = CrossbarRouterFactory()
      self._router_session_factory = CrossbarRouterSessionFactory(self._router_factory)

      print "QQQ2"
      self._router_transports = {}
      self._router_transport_no = 0

      dl = []

#      dl.append(self._session.register(self.start,           'crossbar.node.{}.process.{}.router.{}.start'.format(self._node_name, self._pid, self._index)))
      uri = 'crossbar.node.{}.process.{}.router.{}.stop'.format(self._node_name, self._pid, self._index)
      print "QQQQ", uri
      dl.append(self._session.register(self.stop, uri))

      dl.append(self._session.register(self.startClass,      'crossbar.node.{}.process.{}.router.{}.start_class'.format(self._node_name, self._pid, self._index)))
      dl.append(self._session.register(self.stopClass,       'crossbar.node.{}.process.{}.router.{}.stop_class'.format(self._node_name, self._pid, self._index)))

      dl.append(self._session.register(self.startRealm,      'crossbar.node.{}.process.{}.router.{}.start_realm'.format(self._node_name, self._pid, self._index)))
      #dl.append(self._session.register(self.stopRealm,       'crossbar.node.{}.module.{}.router.stop_realm'.format(self._node_name, self._pid, self._index)))

      dl.append(self._session.register(self.startTransport,  'crossbar.node.{}.process.{}.router.{}.start_transport'.format(self._node_name, self._pid, self._index)))
      dl.append(self._session.register(self.stopTransport,   'crossbar.node.{}.process.{}.router.{}.stop_transport'.format(self._node_name, self._pid, self._index)))
      dl.append(self._session.register(self.listTransports,  'crossbar.node.{}.process.{}.router.{}.list_transports'.format(self._node_name, self._pid, self._index)))

      dl.append(self._session.register(self.startLink,       'crossbar.node.{}.process.{}.router.{}.start_link'.format(self._node_name, self._pid, self._index)))
      dl.append(self._session.register(self.stopLink,        'crossbar.node.{}.process.{}.router.{}.stop_link'.format(self._node_name, self._pid, self._index)))

      d = DeferredList(dl)

      return d


   def stop(self):
      if self.debug:
         log.msg("Worker {}: stopping router module".format(self._pid))


   def startRealm(self, name, config):
      if self.debug:
         log.msg("Worker {}: realm started".format(self._pid))



   def listClasses(self):
      """
      List currently running application components.
      """
      return sorted(self._component_sessions.keys())


   def startClass(self, klassname, realm):
      """
      Dynamically start an application component to run next to the router in "embedded mode".
      """

      ## dynamically load the application component ..
      ##
      try:
         if self.debug:
            log.msg("Worker {}: starting class '{}' in realm '{}' ..".format(self._pid, klassname, realm))

         import importlib
         c = klassname.split('.')
         mod, klass = '.'.join(c[:-1]), c[-1]
         app = importlib.import_module(mod)
         SessionKlass = getattr(app, klass)

      except Exception as e:
         if self.debug:
            log.msg("Worker {}: failed to import class - {}".format(e))
         raise ApplicationError("crossbar.error.class_import_failed", str(e))

      else:
         ## .. and create and add an WAMP application session to
         ## run the component next to the router
         ##
         comp = SessionKlass(realm)
         self._router_session_factory.add(comp)

         self._component_no += 1
         self._component_sessions[self._component_no] = comp
         return self._component_no


   def stopClass(self, id):
      """
      Stop a application component on this router.
      """
      if id in self._component_sessions:
         if self.debug:
            log.msg("Worker {}: stopping component {}".format(self._pid, id))

         try:
            #self._component_sessions[id].disconnect()
            self._router_session_factory.remove(self._component_sessions[id])
            del self._component_sessions[id]
         except Exception as e:
            raise ApplicationError("crossbar.error.component.cannot_stop", "Failed to stop component {}: {}".format(id, e))
      else:
         raise ApplicationError("crossbar.error.no_such_component", "No component {}".format(id))


   def listTransports(self):
      """
      List currently running transports.
      """
      return sorted(self._router_transports.keys())


   def startTransport(self, config):
      """
      Start a transport on this router module.
      """
      print "Starting {} transport".format(config['type'])
      if self.debug:
         log.msg("Worker {}: starting transport on router module.".format(self._pid))

      self._router_transport_no += 1

      if config['type'] in ['websocket', 'web']:

         if config['type'] == 'websocket':

            transport_factory = CrossbarWampWebSocketServerFactory(self._router_session_factory, config, self._templates)

         elif config['type'] == 'web':

            options = config.get('options', {})

            ## this is here to avoid module level reactor imports
            ## https://twistedmatrix.com/trac/ticket/6849
            ##
            from twisted.web.server import Site
            from twisted.web.static import File
            from twisted.web.resource import Resource

            from autobahn.twisted.resource import WebSocketResource
            from crossbar.router.resource import JsonResource, Resource404, CgiDirectory, RedirectResource


            ## Web directory static file serving
            ##
            root_type = config['paths']['/']['type']

            if root_type == 'static':

               rd = config['paths']['/']['directory']
               root_dir = os.path.abspath(os.path.join(self._cbdir, rd))
               root_dir = root_dir.encode('ascii', 'ignore') # http://stackoverflow.com/a/20433918/884770
               print "Starting Web service at root directory {}".format(root_dir)
               root = File(root_dir)

               ## render 404 page on any concrete path not found
               ##
               root.childNotFound = Resource404(self._templates, root_dir)

               ## disable directory listing and render 404
               ##
               if not options.get('enable_directory_listing', False):
                  root.directoryListing = lambda: root.childNotFound

            elif root_type == 'redirect':

               redirect_url = config['paths']['/']['url'].encode('ascii', 'ignore')
               root = RedirectResource(redirect_url)

            else:
               print "invalid type for root path", root_type


            for path in sorted(config.get('paths', [])):

               if path != "/":

                  path_config = config['paths'][path]

                  ## websocket_echo
                  ## websocket_testee
                  ## s3mirror
                  ## websocket_stdio
                  ##

                  if path_config['type'] == 'websocket':
                     ws_factory = CrossbarWampWebSocketServerFactory(self._router_session_factory, path_config, self._templates)

                     ## FIXME: Site.start/stopFactory should start/stop factories wrapped as Resources
                     ws_factory.startFactory()

                     ws_resource = WebSocketResource(ws_factory)
                     root.putChild(path, ws_resource)

                  elif path_config['type'] == 'static':

                     static_options = path_config.get('options', {})
                     
                     static_dir = os.path.abspath(os.path.join(self._cbdir, path_config['directory']))
                     static_dir = static_dir.encode('ascii', 'ignore') # http://stackoverflow.com/a/20433918/884770
                     
                     static_resource = File(static_dir)

                     ## render 404 page on any concrete path not found
                     ##
                     static_resource.childNotFound = Resource404(self._templates, static_dir)

                     ## disable directory listing and render 404
                     ##
                     if not static_options.get('enable_directory_listing', False):
                        static_resource.directoryListing = lambda: static_resource.childNotFound

                     root.putChild(path, static_resource)

                  elif path_config['type'] == 'redirect':
                     redirect_url = path_config['url'].encode('ascii', 'ignore')
                     redirect_resource = RedirectResource(redirect_url)
                     root.putChild(path, redirect_resource)

                  elif path_config['type'] == 'json':
                     value = path_config['value']
                     
                     json_resource = JsonResource(value)
                     root.putChild(path, json_resource)

                  elif path_config['type'] == 'cgi':

                     cgi_processor = path_config['processor']
                     cgi_directory = os.path.abspath(os.path.join(self._cbdir, path_config['directory']))
                     cgi_directory = cgi_directory.encode('ascii', 'ignore') # http://stackoverflow.com/a/20433918/884770

                     cgi_resource = CgiDirectory(cgi_directory, cgi_processor, Resource404(self._templates, cgi_directory))

                     root.putChild(path, cgi_resource)

                  elif path_config['type'] == 'longpoll':

                     log.msg("Web path type 'longpoll' not implemented")

                  else:
                     print "Web path type '{}' not implemented.".format(path_config['type'])

            transport_factory = Site(root)
            transport_factory.log = lambda _: None # disable any logging
            #transport_factory.protocol = HTTPChannelHixie76Aware # needed if Hixie76 is to be supported

         else:
            raise Exception("logic error")

         id = self._router_transport_no

         if True:
            from twisted.internet import reactor

            # IListeningPort or an CannotListenError
            server = serverFromString(reactor, str(config['endpoint']))
            d = server.listen(transport_factory)

            def ok(port):
               self._router_transports[id] = RouterTransport(id, config, port)
               return id

            def fail(err):
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
               self._router_transports[id] = RouterTransport(id, config, port)
               return id
      else:
         raise ApplicationError("crossbar.error.invalid_transport", "Unknown transport type '{}'".format(config['type']))



   def stopTransport(self, id):
      """
      Stop a transport on this router module.
      """
      if id in self._router_transports:
         if self.debug:
            log.msg("Worker {}: stopping transport {}".format(self._pid, id))

         try:
            d = self._router_transports[id].port.stopListening()

            def ok(_):
               del self._router_transports[id]

            def fail(err):
               raise ApplicationError("crossbar.error.transport.cannot_stop", "Failed to stop transport {}: {}".format(id, str(err.value)))

            d.addCallbacks(ok, fail)
            return d

         except Exception as e:
            raise ApplicationError("crossbar.error.transport.cannot_stop", "Failed to stop transport {}: {}".format(id, e))
      else:
         raise ApplicationError("crossbar.error.no_such_transport", "No transport {}".format(id))



   def listLinks(self):
      """
      List currently running links.
      """
      return []


   def startLink(self, config):
      """
      Start a link on this router.
      """
      if self.debug:
         log.msg("Worker {}: starting router link".format(self._pid))


   def stopLink(self, id):
      """
      Stop a link on this router.
      """
      if self.debug:
         log.msg("Worker {}: stopping router link {}".format(self._pid, id))



class ComponentSessionFactory:

   session = None

   def __init__(self, realm):
      self._realm = realm

   def __call__(self):
      session = self.session(self._realm)
      session.factory = self
      return session



class ComponentModule:
   """
   """

   def __init__(self, session, pid):
      self._session = session
      self._pid = pid
      self._client = None

      self.debug = self._session.factory.options.debug

      session.register(self.start, 'crossbar.node.module.{}.component.start'.format(self._pid))


   def start(self, transport, klassname, realm):
      """
      Dynamically start an application component to run next to the router in "embedded mode".
      """

      ## dynamically load the application component ..
      ##
      try:
         if self.debug:
            log.msg("Worker {}: starting class '{}' in realm '{}' ..".format(self._pid, klassname, realm))

         import importlib
         c = klassname.split('.')
         mod, klass = '.'.join(c[:-1]), c[-1]
         app = importlib.import_module(mod)
         SessionKlass = getattr(app, klass)

      except Exception as e:
         if self.debug:
            log.msg("Worker {}: failed to import class - {}".format(e))
         raise ApplicationError("crossbar.error.class_import_failed", str(e))

      else:
         ## create a WAMP application session factory
         ##
         #from autobahn.twisted.wamp import ApplicationSessionFactory
         #session_factory = ApplicationSessionFactory()
         session_factory = ComponentSessionFactory(realm)
         session_factory.session = SessionKlass

         ## create a WAMP-over-WebSocket transport client factory
         ##
         from autobahn.twisted.websocket import WampWebSocketClientFactory
         transport_factory = WampWebSocketClientFactory(session_factory, transport['url'], debug = self.debug)
         transport_factory.setProtocolOptions(failByDrop = False)

         ## start a WebSocket client from an endpoint
         ##
         from twisted.internet import reactor
         from twisted.internet.endpoints import clientFromString
         self._client = clientFromString(reactor, transport['endpoint'])

         from twisted.internet import reactor

         retry = True
         retryDelay = 1000

         def try_connect():
            print "Trying to connect .."
            d = self._client.connect(transport_factory)

            def success(res):
               if True or self.debug:
                  log.msg("Worker {}: client connected to router".format(self._pid))

            def error(err):
               log.msg("Worker {}: client failed to connect to router - {}".format(self._pid, err))
               if retry:
                  log.msg("Worker {}: retrying in {} ms".format(self._pid, retryDelay))
                  reactor.callLater(float(retryDelay) / 1000., try_connect)
               else:
                  log.msg("Worker {}: giving up.".format(seld._pid))

            d.addCallbacks(success, error)

         try_connect()



class WorkerProcess(ApplicationSession):

   def onConnect(self):
      self.debug = self.factory.options.debug
      self.debug = True
      if self.debug:
         log.msg("Connected to node.")

      self._component = None

      self._routers = {}
      self._router_seq = 100

      self.join("crossbar")


   def onJoin(self, details):
      if self.debug:
         log.msg("Realm joined.")

      self._pid = os.getpid()
      self._node_name = '918234'

      def get_cpu_affinity():
         p = psutil.Process(self._pid)
         return p.get_cpu_affinity()

      self.register(get_cpu_affinity, 'crossbar.node.{}.process.{}.get_cpu_affinity'.format(self._node_name, self._pid))


      def set_cpu_affinity(cpus):
         p = psutil.Process(self._pid)
         p.set_cpu_affinity(cpus)

      self.register(set_cpu_affinity, 'crossbar.node.component.{}.set_cpu_affinity'.format(self._pid))


      def utcnow():
         now = datetime.datetime.utcnow()
         return now.strftime("%Y-%m-%dT%H:%M:%SZ")

      self.register(utcnow, 'crossbar.node.component.{}.now'.format(self._pid))


      def get_classpaths():
         return sys.path

      self.register(get_classpaths, 'crossbar.node.component.{}.get_classpaths'.format(self._pid))


      def add_classpaths(paths, prepend = True):
         sys.path = paths + sys.path

      self.register(add_classpaths, 'crossbar.node.component.{}.add_classpaths'.format(self._pid))


      def start_router():
         self._router_seq += 1
         index = self._router_seq

         self._routers[index] = RouterModule(self, index, self.factory.options.cbdir)
         d = self._routers[index].start()

         def onstart(res):
            return index

         d.addCallback(onstart)
         return d

      self.register(start_router, 'crossbar.node.{}.process.{}.start_router'.format(self._node_name, self._pid))

      ## Modules
      ##
      #self._routerModule = RouterModule(self, self.factory.options.cbdir)
      self._componentModule = ComponentModule(self, self._pid)


      if self.debug:
         log.msg("Worker {}: Procedures registered.".format(self._pid))

      ## signal that this worker is ready for setup. the actual setup procedure
      ## will either be sequenced from the local node configuration file or remotely
      ## from a management service
      ##
      self.publish('crossbar.node.{}.on_worker_ready'.format(self._node_name), {'pid': self._pid, 'cmd': [sys.executable] + sys.argv})


   def startComponent(self):
      pass



def run():
   """
   Entry point into background worker process. This wires up stuff such that
   a WorkerProcess instance is talking WAMP over stdio to the node controller.
   """
   ## create the top-level parser
   ##
   parser = argparse.ArgumentParser()

   parser.add_argument('-d',
                       '--debug',
                       action = 'store_true',
                       help = 'Debug on.')

   parser.add_argument('--reactor',
                       default = None,
                       choices = ['select', 'poll', 'epoll', 'kqueue', 'iocp'],
                       help = 'Explicit Twisted reactor selection')

   parser.add_argument('--cbdir',
                       type = str,
                       default = None,
                       help = "Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

   parser.add_argument('-l',
                       '--logfile',
                       default = None,
                       help = 'Log to log file instead of stderr.')

   options = parser.parse_args()

   ## make sure logging to something else than stdio is setup _first_
   ##
   if options.logfile:
      log.startLogging(open(options.logfile, 'a'))
   else:
      log.startLogging(sys.stderr)


   pid = os.getpid()

   ## Crossbar.io node directory
   ##
   if hasattr(options, 'cbdir') and not options.cbdir:
      if os.environ.has_key("CROSSBAR_DIR"):
         options.cbdir = os.environ['CROSSBAR_DIR']
      else:
         options.cbdir = '.crossbar'

   options.cbdir = os.path.abspath(options.cbdir)


   ## we use an Autobahn utility to import the "best" available Twisted reactor
   ##
   from autobahn.twisted.choosereactor import install_reactor
   reactor = install_reactor(options.reactor)

   ##
   from twisted.python.reflect import qual
   log.msg("Worker {}: starting at node directory {} on {} ..".format(pid, options.cbdir, qual(reactor.__class__).split('.')[-1]))

   try:
      ## create a WAMP application session factory
      ##
      from autobahn.twisted.wamp import ApplicationSessionFactory
      session_factory = ApplicationSessionFactory()
      session_factory.options = options
      session_factory.session = WorkerProcess

      ## create a WAMP-over-WebSocket transport server factory
      ##
      from autobahn.twisted.websocket import WampWebSocketServerFactory
      transport_factory = WampWebSocketServerFactory(session_factory, "ws://localhost", debug = False)
      transport_factory.setProtocolOptions(failByDrop = False)

      ## create a protocol instance and wire up to stdio
      ##
      from twisted.internet import stdio
      proto = transport_factory.buildProtocol(None)
      stdio.StandardIO(proto)

      ## now start reactor loop
      ##
      log.msg("Worker {}: entering event loop ..".format(pid))
      reactor.run()

   except Exception as e:
      log.msg("Worker {}: Unhandled exception - {}".format(pid, e))
      raise e
      sys.exit(1)



if __name__ == '__main__':
   run()
