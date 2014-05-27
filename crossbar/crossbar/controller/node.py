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

__all__ = ['Node']


import os
import sys
import json
import traceback

from twisted.python import log
from twisted.internet.defer import Deferred, \
                                   DeferredList, \
                                   returnValue, \
                                   inlineCallbacks

from autobahn import wamp
from autobahn.wamp.types import CallDetails
from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSessionFactory

from crossbar.common import checkconfig
from crossbar.controller.process import NodeControllerSession


from autobahn.wamp.types import ComponentConfig




class Node:
   """
   A Crossbar.io node is the running a controller process
   and one or multiple worker processes.

   A single Crossbar.io node runs exactly one instance of
   this class, hence this class can be considered a system
   singleton.
   """

   def __init__(self, reactor, options):
      """
      Ctor.

      :param reactor: Reactor to run on.
      :type reactor: obj
      :param options: Options from command line.
      :type options: obj
      """
      self._reactor = reactor

      self._cbdir = options.cbdir

      with open(options.config) as config_file:
         self._config = json.load(config_file)

      self._reactor_shortname = options.reactor

      self.debug = False

      self._worker_workers = {}

      ## the node's name (must be unique within the management realm)
      self._node_id = self._config['controller']['id']

      ## the node's management realm
      self._realm = self._config['controller'].get('realm', 'crossbar')

      ## node controller session (a singleton ApplicationSession embedded
      ## in the node's management router)
      self._controller = None



   def start(self):
      """
      Starts this node. This will start a node controller
      and then spawn new worker processes as needed.

      The node controller will watch spawned processes,
      communicate via stdio with the worker, and start
      and restart the worker processes as needed.
      """
      try:
         import setproctitle
      except ImportError:
         log.msg("Warning, could not set process title (setproctitle not installed)")
      else:
         setproctitle.setproctitle("crossbar-controller")

      ## the node controller singleton WAMP application session
      ##
      #session_config = ComponentConfig(realm = options.realm, extra = options)

      self._controller = NodeControllerSession(self)

      ## router and factory that creates router sessions
      ##
      self._router_factory = RouterFactory(
         options = wamp.types.RouterOptions(uri_check = wamp.types.RouterOptions.URI_CHECK_LOOSE),
         debug = False)
      self._router_session_factory = RouterSessionFactory(self._router_factory)

      ## add the node controller singleton session to the router
      ##
      self._router_session_factory.add(self._controller)

      ## Detect WAMPlets
      ##
      wamplets = self._controller._get_wamplets()
      if len(wamplets) > 0:
         log.msg("Detected {} WAMPlets in environment:".format(len(wamplets)))
         for wpl in wamplets:
            log.msg("WAMPlet {}.{}".format(wpl['dist'], wpl['name']))
      else:
         log.msg("No WAMPlets detected in enviroment.")


#      self._start_from_local_config(configfile = os.path.join(self._cbdir, self._options.config))
      self.run_node_config(self._config)

      self.start_local_management_transport(endpoint_descriptor = "tcp:9000")



   def start_local_management_transport(self, endpoint_descriptor):
      ## create a WAMP-over-WebSocket transport server factory
      ##
      from autobahn.twisted.websocket import WampWebSocketServerFactory
      from twisted.internet.endpoints import serverFromString

      self._router_server_transport_factory = WampWebSocketServerFactory(self._router_session_factory, debug = self.debug)
      self._router_server_transport_factory.setProtocolOptions(failByDrop = False)
      self._router_server_transport_factory.noisy = False


      ## start the WebSocket server from an endpoint
      ##
      self._router_server = serverFromString(self._reactor, endpoint_descriptor)
      ## FIXME: the following spills out log noise: "WampWebSocketServerFactory starting on 9000"
      self._router_server.listen(self._router_server_transport_factory)



   def _start_from_local_config(self, configfile):
      """
      Start Crossbar.io node from local configuration file.
      """
      configfile = os.path.abspath(configfile)
      log.msg("Starting from local config file '{}'".format(configfile))

      try:
         #config = controller.config.check_config_file(configfile, silence = True)
         config = json.loads(open(configfile, 'rb').read())
      except Exception as e:
         log.msg("Fatal: {}".format(e))
         sys.exit(1)
      else:
         self.run_node_config(config)


   @inlineCallbacks
   def run_node_config(self, config):
      try:
         yield self._run_node_config(config)
      except:
         traceback.print_exc()
         self._reactor.stop()


   @inlineCallbacks
   def _run_node_config(self, config):
      """
      Setup node according to config provided.
      """

      ## fake call details information when calling into
      ## remoted procedure locally
      ##
      call_details = CallDetails(caller = 0, authid = 'node')

      for worker in config.get('workers', []):

         id = worker['id']
         options = worker.get('options', {})

         ## router/container
         ##
         if worker['type'] in ['router', 'container']:

            ## start a new worker process ..
            ##
            try:
               if worker['type'] == 'router':
                  yield self._controller.start_router(id, options, details = call_details)
               elif worker['type'] == 'container':
                  yield self._controller.start_container(id, options, details = call_details)
               else:
                  raise Exception("logic error")
            except Exception as e:
               log.msg("Failed to start worker process: {}".format(e))
               raise e
            else:
               log.msg("Worker {}: Started {}.".format(id, worker['type']))

            ## setup worker generic stuff
            ##
            if 'pythonpath' in options:
               try:
                  added_paths = yield self._controller.call('crossbar.node.{}.worker.{}.add_pythonpath'.format(self._node_id, id),
                     options['pythonpath'])

               except Exception as e:
                  log.msg("Worker {}: Failed to set PYTHONPATH - {}".format(id, e))
               else:
                  log.msg("Worker {}: PYTHONPATH extended for {}".format(id, added_paths))

            if 'cpu_affinity' in options:
               try:
                  yield self._controller.call('crossbar.node.{}.worker.{}.set_cpu_affinity'.format(self._node_id, id),
                     options['cpu_affinity'])

               except Exception as e:
                  log.msg("Worker {}: Failed to set CPU affinity - {}".format(id, e))
               else:
                  log.msg("Worker {}: CPU affinity set.".format(id))

            try:
               cpu_affinity = yield self._controller.call('crossbar.node.{}.worker.{}.get_cpu_affinity'.format(self._node_id, id))
            except Exception as e:
               log.msg("Worker {}: Failed to get CPU affinity - {}".format(id, e))
            else:
               log.msg("Worker {}: CPU affinity is {}".format(id, cpu_affinity))


            ## manhole within worker
            ##
            if 'manhole' in worker:
               yield self._controller.call('crossbar.node.{}.worker.{}.start_manhole'.format(self._node_id, id), worker['manhole'])


            ## WAMP router process
            ##
            if worker['type'] == 'router':

               ## start realms
               ##
               for realm in worker.get('realms', []):

                  yield self._controller.call('crossbar.node.{}.worker.{}.start_router_realm'.format(self._node_id, id), realm['id'], realm)

                  #log.msg("Worker {}: Realm {} ({}) started on router".format(id, realm_name, realm_index))

                  ## start any application components to run embedded in the realm
                  ##
                  for component in realm.get('components', []):

                     yield self._controller.call('crossbar.node.{}.worker.{}.start_router_component'.format(self._node_id, id), component['id'], component)

               ## start transports on router
               ##
               for transport in worker['transports']:

                  transport_index = yield self._controller.call('crossbar.node.{}.worker.{}.start_router_transport'.format(self._node_id, id), transport['id'], transport)

                  #log.msg("Worker {}: Transport {}/{} ({}) started on router".format(id, transport['type'], transport['endpoint']['type'], transport_index))

            ## Setup: Python component host process
            ##
            elif worker['type'] == 'container':

               for component in worker.get('components', []):

                  yield self._controller.call('crossbar.node.{}.worker.{}.start_container_component'.format(self._node_id, id), component['id'], component)

               #yield self.call('crossbar.node.{}.worker.{}.container.start_component'.format(self._node_id, pid), worker['component'], worker['router'])

            else:
               raise Exception("logic error")


         elif worker['type'] == 'guest':

            ## start a new worker process ..
            ##
            try:
               pid = yield self._controller.start_guest(worker, details = call_details)
            except Exception as e:
               log.msg("Failed to start guest process: {}".format(e))
            else:
               log.msg("Guest {}: Started.".format(pid))

         else:
            raise Exception("unknown worker type '{}'".format(worker['type']))


