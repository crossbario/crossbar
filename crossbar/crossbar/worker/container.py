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

__all__ = ['ContainerWorker']


import os

from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import ComponentConfig

from twisted.python import log
from twisted import internet
import pkg_resources

from crossbar import controller
from crossbar.worker.native import NativeWorkerSession

from crossbar.router.protocol import CrossbarWampWebSocketClientFactory, \
                                     CrossbarWampRawSocketClientFactory


from datetime import datetime
from autobahn.util import utcnow, utcstr

from autobahn.wamp.types import PublishOptions, RegisterOptions




class ContainerComponent:
   """
   """
   def __init__(self, id, config, proto, session):
      """
      """
      self.started = datetime.utcnow()
      self.id = id
      self.config = config
      self.proto = proto
      self.session = session


   def marshal(self):
      now = datetime.utcnow()
      return {
         'id': self.id,
         'started': utcstr(self.started),
         'uptime': (now - self.started).total_seconds(),
         'config': self.config
      }




class ContainerWorkerSession(NativeWorkerSession):
   """
   A container worker hosts application components written in Python, and
   connects to an application router.
   """
   WORKER_TYPE = 'container'


   @inlineCallbacks
   def onJoin(self, details):
      """
      Called when worker process has joined the node's management realm.
      """
      ## map: component id -> ContainerComponent
      self.components = {}
      self.component_id = 0


      dl = []
      procs = [
         'start_component',
         'stop_component',
         'get_components'
      ]

      for proc in procs:
         uri = 'crossbar.node.{}.worker.{}.container.{}'.format(self.config.extra.node, self.config.extra.id, proc)
         dl.append(self.register(getattr(self, proc), uri, options = RegisterOptions(details_arg = 'details', discloseCaller = True)))

      regs = yield DeferredList(dl)

      yield NativeWorkerSession.onJoin(self, details)



   def start_component(self, config, details = None):
      """
      Starts a Class or WAMPlet in this component container.

      :param config: Component configuration.
      :type config: dict

      :returns int -- The component index assigned.
      """
      try:
         controller.config.check_container_component(config)
      except Exception as e:
         emsg = "ERROR: could not start container component - invalid configuration ({})".format(e)
         log.msg(emsg)
         raise ApplicationError('crossbar.error.invalid_configuration', emsg)


      ## 1) create WAMP application component factory
      ##
      if config['type'] == 'wamplet':

         try:
            dist = config['dist']
            name = config['entry']

            if self.debug:
               log.msg("Starting WAMPlet '{}/{}' in realm '{}' ..".format(dist, name, config['router']['realm']))

            ## make is supposed to make instances of ApplicationSession
            make = pkg_resources.load_entry_point(dist, 'autobahn.twisted.wamplet', name)

         except Exception as e:
            log.msg("Failed to import class - {}".format(e))
            raise ApplicationError("crossbar.error.class_import_failed", str(e))

      elif config['type'] == 'class':

         try:
            klassname = config['name']

            if self.debug:
               log.msg("Worker {}: starting class '{}' in realm '{}' ..".format(self.config.extra.id, klassname, config['router']['realm']))

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
         ## should not arrive here, since we did `check_container_component()`
         raise Exception("logic error")


      ## WAMP application session factory
      ##
      def create_session():
         cfg = ComponentConfig(realm = config['router']['realm'], extra = config.get('extra', None))
         c = make(cfg)
         return c


      ## 2) create WAMP transport factory
      ##
      transport_config = config['router']['transport']
      transport_debug = transport_config.get('debug', False)


      ## WAMP-over-WebSocket transport
      ##
      if transport_config['type'] == 'websocket':

         ## create a WAMP-over-WebSocket transport client factory
         ##
         transport_factory = CrossbarWampWebSocketClientFactory(create_session, transport_config['url'], debug = transport_debug, debug_wamp = transport_debug)

      ## WAMP-over-RawSocket transport
      ##
      elif transport_config['type'] == 'rawsocket':

         transport_factory = CrossbarWampRawSocketClientFactory(create_session, transport_config)

      else:
         ## should not arrive here, since we did `check_container_component()`
         raise Exception("logic error")


      ## 3) create and connect client endpoint
      ##
      from twisted.internet import reactor
      from crossbar.twisted.endpoint import create_connecting_endpoint_from_config

      endpoint = create_connecting_endpoint_from_config(transport_config['endpoint'], self.config.extra.cbdir, reactor)

      ## now connect the client
      ##
      d = endpoint.connect(transport_factory)

      def success(proto):
         print "T"*10, proto
         self.component_id += 1
         self.components[self.component_id] = ContainerComponent(self.component_id, config, proto, None)
         if self.debug:
            log.msg("Connected to application router")
         return self.component_id

      def error(err):
         ## https://twistedmatrix.com/documents/current/api/twisted.internet.error.ConnectError.html
         if isinstance(err.value, internet.error.ConnectError):
            emsg = "ERROR: could not connect container component to router - transport establishment failed ({})".format(err.value)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.cannot_connect', emsg)
         else:
            raise err

      d.addCallbacks(success, error)

      return d



      #onconnect = Deferred()

      # retry = True
      # retryDelay = 1000

      # def try_connect():
      #    if self.debug:
      #       log.msg("Connecting to application router ..")

      #    d = endpoint.connect(transport_factory)

      #    def success(proto):
      #       if self.debug:
      #          log.msg("Connected to application router")

      #    def error(err):
      #       ## https://twistedmatrix.com/documents/current/api/twisted.internet.error.ConnectError.html
      #       if isinstance(err.value, internet.error.ConnectError):
      #          ## twisted.internet.error.ConnectionRefusedError
      #          print "YYY", err.value, isinstance(err.value, internet.error.ConnectError)
      #          log.msg("Failed to connect to application router: {}".format(err))
      #          if retry:
      #             log.msg("Retrying to connect in {} ms".format(retryDelay))
      #             reactor.callLater(float(retryDelay) / 1000., try_connect)
      #          else:
      #             log.msg("Could not connect to application router - giving up.")
      #       else:
      #          pass

      #    d.addCallbacks(success, error)

      # try_connect()

      # return onconnect

   def stop_component(self, id, details = None):
      """
      """
      if id not in self.components:
         raise ApplicationError('crossbar.error.no_such_object', 'No component with ID {}'.format(id))

      self.components[id].proto.close()

      topic = 'crossbar.node.{}.process.{}.container.on_component_stop'.format(self.config.extra.node, self.config.extra.id)
      event = {'id': id}
      self.publish(topic, event, options = PublishOptions(exclude = [details.caller]))

      del self.components[id]


   def get_components(self, details = None):
      """
      """
      res = []
      for c in self.components.values():
         res.append(c.marshal())
      return res

