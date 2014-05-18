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

from twisted.internet.defer import DeferredList

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import ComponentConfig

from twisted.python import log
import pkg_resources


class ContainerInstance:
   def __init__(self, id):
      self.id = id


class ContainerModule:
   """
   The ComponentModule creates component hosts in a Worker
   process. Component hosts can dynamically load, reload and
   unload Python application classes and components (WAMPlets).
   """

   def __init__(self, cbdir, debug = False):
      self._cbdir = cbdir
      self.debug = debug
      self._client = None
      self._session = None


   def connect(self, session):
      assert(self._session is None)

      self._session = session
      self._pid = session._pid
      self._node_name = session._node_name

      dl = []
      procs = [
         'start_component',
      ]

      for proc in procs:
         uri = 'crossbar.node.{}.worker.{}.container.{}'.format(self._node_name, self._pid, proc)
         dl.append(self._session.register(getattr(self, proc), uri))

      d = DeferredList(dl)
      return d


   def start_component(self, component, router):
      """
      Starts a Class or WAMPlet in this component container.
      """
      ## create component
      ##
      if component['type'] == 'wamplet':

         try:
            dist = component['dist']
            name = component['entry']

            if self.debug:
               log.msg("Worker {}: starting WAMPlet '{}/{}' in realm '{}' ..".format(self._pid, dist, name, router['realm']))

            ## make is supposed to make instances of ApplicationSession
            make = pkg_resources.load_entry_point(dist, 'autobahn.twisted.wamplet', name)

         except Exception as e:
            log.msg("Worker {}: failed to import class - {}".format(e))
            raise ApplicationError("crossbar.error.class_import_failed", str(e))
   
      elif component['type'] == 'class':

         try:
            klassname = component['name']

            if self.debug:
               log.msg("Worker {}: starting class '{}' in realm '{}' ..".format(self._pid, klassname, router['realm']))

            import importlib
            c = klassname.split('.')
            mod, kls = '.'.join(c[:-1]), c[-1]
            app = importlib.import_module(mod)

            ## make is supposed to be of class ApplicationSession
            make = getattr(app, kls)

         except Exception as e:
            log.msg("Worker {}: failed to import class - {}".format(e))
            raise ApplicationError("crossbar.error.class_import_failed", str(e))

      else:
         raise ApplicationError("crossbar.error.invalid_configuration", "unknown component type '{}'".format(component['type']))


      def create():
         cfg = ComponentConfig(realm = router['realm'], extra = component.get('extra', None))
         c = make(cfg)
         return c


      ## create the WAMP transport
      ##
      transport_config = router['transport']
      transport_debug = transport_config.get('debug', False)

      if transport_config['type'] == 'websocket':

         ## create a WAMP-over-WebSocket transport client factory
         ##
         #from autobahn.twisted.websocket import WampWebSocketClientFactory
         #transport_factory = WampWebSocketClientFactory(create, transport_config['url'], debug = transport_debug, debug_wamp = transport_debug)
         from crossbar.router.protocol import CrossbarWampWebSocketClientFactory
         transport_factory = CrossbarWampWebSocketClientFactory(create, transport_config['url'], debug = transport_debug, debug_wamp = transport_debug)
         transport_factory.setProtocolOptions(failByDrop = False)

      elif transport_config['type'] == 'rawsocket':

         from crossbar.router.protocol import CrossbarWampRawSocketClientFactory
         transport_factory = CrossbarWampRawSocketClientFactory(create, transport_config)

      else:
         raise ApplicationError("crossbar.error.invalid_configuration", "unknown transport type '{}'".format(transport_config['type']))


      self._foo = transport_factory

      ## create client endpoint
      ##
      from twisted.internet import reactor
      from twisted.internet.endpoints import TCP4ClientEndpoint, UNIXClientEndpoint
      from twisted.internet.endpoints import clientFromString

      try:
         from twisted.internet.endpoints import SSL4ClientEndpoint
         from crossbar.twisted.tlsctx import TlsClientContextFactory
         HAS_TLS = True
      except:
         HAS_TLS = False

      try:
         endpoint_config = transport_config['endpoint']

         ## a TCP4 endpoint
         ##
         if endpoint_config['type'] == 'tcp':

            ## the host to connect ot
            ##
            host = str(endpoint_config['host'])

            ## the port to connect to
            ##
            port = int(endpoint_config['port'])

            ## connection timeout in seconds
            ##
            timeout = int(endpoint_config.get('timeout', 10))

            if 'tls' in endpoint_config:

               ctx = TlsClientContextFactory()

               ## create a TLS client endpoint
               ##
               self._client = SSL4ClientEndpoint(reactor,
                                                 host,
                                                 port,
                                                 ctx,
                                                 timeout = timeout)
            else:
               ## create a non-TLS client endpoint
               ##
               self._client = TCP4ClientEndpoint(reactor,
                                                 host,
                                                 port,
                                                 timeout = timeout)

         ## a Unix Domain Socket endpoint
         ##
         elif endpoint_config['type'] == 'unix':

            ## the path
            ##
            path = os.path.abspath(os.path.join(self._cbdir, endpoint_config['path']))

            ## connection timeout in seconds
            ##
            timeout = int(endpoint_config.get('timeout', 10))

            ## create the endpoint
            ##
            self._client = UNIXClientEndpoint(reactor, path, timeout = timeout)

         else:
            raise ApplicationError("crossbar.error.invalid_configuration", "invalid endpoint type '{}'".format(endpoint_config['type']))

      except Exception as e:
         log.msg("endpoint creation failed: {}".format(e))
         raise e


      ## now connect the client
      ##
      retry = True
      retryDelay = 1000

      def try_connect():
         if self.debug:
            log.msg("Worker {}: connecting to router ..".format(self._pid))

         d = self._client.connect(transport_factory)

         def success(res):
            if self.debug:
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
