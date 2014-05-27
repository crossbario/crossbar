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

from twisted.python import log
from twisted.internet.defer import Deferred, \
                                   DeferredList, \
                                   returnValue, \
                                   inlineCallbacks

from autobahn import wamp
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
      self._realm = self._config['controller']['realm']

      ## node controller session (a singleton ApplicationSession embedded
      ## in the node's management router)
      self._node_controller_session = None



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

      self._node_controller_session = NodeControllerSession(self)

      ## router and factory that creates router sessions
      ##
      self._router_factory = RouterFactory(
         options = wamp.types.RouterOptions(uri_check = wamp.types.RouterOptions.URI_CHECK_LOOSE),
         debug = False)
      self._router_session_factory = RouterSessionFactory(self._router_factory)

      ## add the node controller singleton session to the router
      ##
      self._router_session_factory.add(self._node_controller_session)

      ## Detect WAMPlets
      ##
      wamplets = self._node_controller_session._get_wamplets()
      if len(wamplets) > 0:
         log.msg("Detected {} WAMPlets in environment:".format(len(wamplets)))
         for wpl in wamplets:
            log.msg("WAMPlet {}.{}".format(wpl['dist'], wpl['name']))
      else:
         log.msg("No WAMPlets detected in enviroment.")


#      self._start_from_local_config(configfile = os.path.join(self._cbdir, self._options.config))
      self._node_controller_session.run_node_config(self._config)

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
         self._node_controller_session.run_node_config(config)
