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

__all__ = ['ContainerWorkerSession']


import os
import sys
import importlib
import pkg_resources
import traceback
import StringIO
from datetime import datetime

from twisted.internet import reactor
from twisted import internet
from twisted.python import log
from twisted.internet.defer import Deferred, \
                                   DeferredList, \
                                   inlineCallbacks, \
                                   returnValue

from autobahn.util import utcnow, utcstr
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import ComponentConfig, \
                                PublishOptions, \
                                RegisterOptions

from crossbar import common
from crossbar.worker.native import NativeWorkerSession
from crossbar.router.protocol import CrossbarWampWebSocketClientFactory, \
                                     CrossbarWampRawSocketClientFactory

from crossbar.twisted.endpoint import create_connecting_endpoint_from_config



class ContainerComponent:
   """
   An application component running inside a container.

   This class is for _internal_ use within ContainerWorkerSession.
   """
   def __init__(self, id, config, proto, session):
      """
      Ctor.

      :param id: The ID of the component within the container.
      :type id: int
      :param config: The component configuration the component was created from.
      :type config: dict
      :param proto: The transport protocol instance the component runs for talking
                    to the application router.
      :type proto: instance of CrossbarWampWebSocketClientProtocol or CrossbarWampRawSocketClientProtocol
      :param session: The application session of this component.
      :type session: Instance derived of ApplicationSession.
      """
      self.started = datetime.utcnow()
      self.id = id
      self.config = config
      self.proto = proto
      self.session = session


   def marshal(self):
      """
      Marshal object information for use with WAMP calls/events.
      """
      now = datetime.utcnow()
      return {
         'id': self.id,
         'started': utcstr(self.started),
         'uptime': (now - self.started).total_seconds(),
         'config': self.config
      }




class ContainerWorkerSession(NativeWorkerSession):
   """
   A container is a native worker process that hosts application components
   written in Python. A container connects to an application router (creating
   a WAMP transport) and attached to a given realm on the application router.
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
         'get_components',
         'start_component',
         'stop_component',
         'restart_component'
      ]

      for proc in procs:
         uri = 'crossbar.node.{}.worker.{}.container.{}'.format(self.config.extra.node, self.config.extra.worker, proc)
         dl.append(self.register(getattr(self, proc), uri, options = RegisterOptions(details_arg = 'details', discloseCaller = True)))

      regs = yield DeferredList(dl)

      yield NativeWorkerSession.onJoin(self, details)



   def start_component(self, config, reload_modules = False, details = None):
      """
      Starts a Class or WAMPlet in this component container.

      :param config: Component configuration.
      :type config: dict
      :param reload_modules: If `True`, enforce reloading of modules (user code)
                             that were modified (see: TrackingModuleReloader).
      :type reload_modules: bool
      :param details: Caller details.
      :type details: instance of :class:`autobahn.wamp.types.CallDetails`

      :returns dict -- A dict with combined info from component starting.
      """
      try:
         common.config.check_container_component(config)
      except Exception as e:
         emsg = "ERROR: could not start container component - invalid configuration ({})".format(e)
         log.msg(emsg)
         raise ApplicationError('crossbar.error.invalid_configuration', emsg)


      ## 1) create WAMP application component factory
      ##
      if config['type'] == 'wamplet':

         package = config['package']
         entrypoint = config['entrypoint']

         try:
            ## create_component() is supposed to make instances of ApplicationSession later
            ##
            create_component = pkg_resources.load_entry_point(package, 'autobahn.twisted.wamplet', entrypoint)

         except Exception as e:
            tb = traceback.format_exc()
            emsg = 'ERROR: failed to import WAMPlet {}.{} ("{}")'.format(package, entrypoint, e)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.cannot_import", emsg, tb)

         else:
            if self.debug:
               log.msg("Creating component from WAMPlet {}.{}".format(package, entrypoint))


      elif config['type'] == 'class':

         qualified_classname = config['classname']

         try:
            c = qualified_classname.split('.')
            module_name, class_name = '.'.join(c[:-1]), c[-1]
            module = importlib.import_module(module_name)

            ## create_component() is supposed to make instances of ApplicationSession later
            ##
            create_component = getattr(module, class_name)

         except Exception as e:
            tb = traceback.format_exc()
            emsg = 'ERROR: failed to import class {} ("{}")'.format(qualified_classname, e)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.cannot_import", emsg, tb)

         else:
            if self.debug:
               log.msg("Creating component from class {}".format(qualified_classname))

      else:
         ## should not arrive here, since we did `check_container_component()`
         raise Exception("logic error")


      ## force reload of modules (user code)
      ##
      if reload_modules:
         self._module_tracker.reload()


      ## WAMP application session factory
      ##
      def create_session():
         cfg = ComponentConfig(realm = config['router']['realm'],
            extra = config.get('extra', None))
         c = create_component(cfg)
         return c


      ## 2) create WAMP transport factory
      ##
      transport_config = config['router']['transport']
      transport_debug = transport_config.get('debug', False)
      transport_debug_wamp = transport_config.get('debug_wamp', False)


      ## WAMP-over-WebSocket transport
      ##
      if transport_config['type'] == 'websocket':

         ## create a WAMP-over-WebSocket transport client factory
         ##
         transport_factory = CrossbarWampWebSocketClientFactory(create_session,
            transport_config['url'],
            debug = transport_debug,
            debug_wamp = transport_debug_wamp)

      ## WAMP-over-RawSocket transport
      ##
      elif transport_config['type'] == 'rawsocket':

         transport_factory = CrossbarWampRawSocketClientFactory(create_session,
            transport_config)

      else:
         ## should not arrive here, since we did `check_container_component()`
         raise Exception("logic error")


      ## 3) create and connect client endpoint
      ##
      endpoint = create_connecting_endpoint_from_config(transport_config['endpoint'],
         self.config.extra.cbdir,
         reactor)


      ## now connect the client
      ##
      d = endpoint.connect(transport_factory)

      def success(proto):
         self.component_id += 1
         self.components[self.component_id] = ContainerComponent(self.component_id,
            config, proto, None)

         ## publish event "on_component_start" to all but the caller
         ##
         topic = 'crossbar.node.{}.worker.{}.container.on_component_start'.format(self.config.extra.node, self.config.extra.worker)
         event = {'id': self.component_id}
         self.publish(topic, event, options = PublishOptions(exclude = [details.caller]))

         return event

      def error(err):
         ## https://twistedmatrix.com/documents/current/api/twisted.internet.error.ConnectError.html
         if isinstance(err.value, internet.error.ConnectError):
            emsg = "ERROR: could not connect container component to router - transport establishment failed ({})".format(err.value)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.cannot_connect', emsg)
         else:
            ## should not arrive here (since all errors arriving here should be subclasses of ConnectError)
            raise err

      d.addCallbacks(success, error)

      return d



   @inlineCallbacks
   def restart_component(self, id, reload_modules = False, details = None):
      """
      Restart a component currently running within this container using the
      same configuration that was used when first starting the component.

      :param id: The ID of the component to restart.
      :type id: int
      :param reload_modules: If `True`, enforce reloading of modules (user code)
                             that were modified (see: TrackingModuleReloader).
      :type reload_modules: bool
      :param details: Caller details.
      :type details: instance of :class:`autobahn.wamp.types.CallDetails`

      :returns dict -- A dict with combined info from component stopping/starting.
      """
      if id not in self.components:
         raise ApplicationError('crossbar.error.no_such_object', 'no component with ID {} running in this container'.format(id))

      config = self.components[id].config
      stopped = yield self.stop_component(id, details = details)
      started = yield self.start_component(config, reload_modules = reload_modules, details = details)
      returnValue({'stopped': stopped, 'started': started})



   def stop_component(self, id, details = None):
      """
      Stop a component currently running within this container.

      :param id: The ID of the component to stop.
      :type id: int
      :param details: Caller details.
      :type details: instance of :class:`autobahn.wamp.types.CallDetails`

      :returns dict -- A dict with component start information.
      """
      if id not in self.components:
         raise ApplicationError('crossbar.error.no_such_object', 'no component with ID {} running in this container'.format(id))

      now = datetime.utcnow()

      ## FIXME: should we session.leave() first and only close the transport then?
      ## This gives the app component a better hook to do any cleanup.
      self.components[id].proto.close()

      c = self.components[id]
      event = {
         'id': id,
         'started': utcstr(c.started),
         'stopped': utcstr(now),
         'uptime': (now - c.started).total_seconds()
      }

      ## publish event "on_component_stop" to all but the caller
      ##
      topic = 'crossbar.node.{}.worker.{}.container.on_component_stop'.format(self.config.extra.node, self.config.extra.worker)
      self.publish(topic, event, options = PublishOptions(exclude = [details.caller]))

      del self.components[id]

      return event



   def get_components(self, details = None):
      """
      Get components currently running within this container.

      :param details: Caller details.
      :type details: instance of :class:`autobahn.wamp.types.CallDetails`

      :returns list -- List of components.
      """
      res = []
      for c in self.components.values():
         res.append(c.marshal())
      return res
