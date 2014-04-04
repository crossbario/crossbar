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

__all__ = ['NodeSession']


from twisted.python import log
from twisted.internet.defer import Deferred, DeferredList, returnValue, inlineCallbacks

from twisted.internet.error import ProcessDone, \
                                   ProcessTerminated, \
                                   ConnectionDone, \
                                   ConnectionClosed, \
                                   ConnectionLost, \
                                   ConnectionAborted


from autobahn.twisted.wamp import ApplicationSession

import os, sys
import json

from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSessionFactory
from autobahn.twisted.websocket import WampWebSocketClientFactory, WampWebSocketClientProtocol
from twisted.internet.endpoints import ProcessEndpoint, StandardErrorBehavior

import pkg_resources
from sys import argv, executable

from autobahn.twisted.wamp import ApplicationSessionFactory
from twisted.internet.endpoints import clientFromString

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp import types

from autobahn.util import utcnow

import socket
import os

from twisted.internet.protocol import ProcessProtocol
from crossbar.process import CustomProcessEndpoint

from twisted.internet import protocol
import re, json





class NodeManagementSession(ApplicationSession):
   """
   """
   def __init__(self):
      ApplicationSession.__init__(self)


   def onConnect(self):
      self.join("crossbar.cloud")


   def is_paired(self):
      return False


   @inlineCallbacks
   def onJoin(self, details):
      log.msg("Connected to Crossbar.io Management Cloud.")

      from twisted.internet import reactor

      self.factory.node_session.setControllerSession(self)

      if not self.is_paired():
         try:
            node_info = {}
            node_publickey = "public key"
            activation_code = yield self.call('crossbar.cloud.get_activation_code', node_info, node_publickey)
         except Exception as e:
            log.msg("internal error: {}".format(e))
         else:
            log.msg("Log into https://console.crossbar.io to configure your instance using the activation code: {}".format(activation_code))

            reg = None

            def activate(node_id, certificate):
               ## check if certificate was issued by Tavendo
               ## check if certificate matches node key
               ## persist node_id
               ## persist certificate
               ## restart node
               reg.unregister()

               self.publish('crossbar.node.onactivate', node_id)

               log.msg("Restarting node in 5 seconds ...")
               reactor.callLater(5, self.factory.node_controller_session.restart_node)

            reg = yield self.register(activate, 'crossbar.node.activate.{}'.format(activation_code))
      else:
         pass

      res = yield self.register(self.factory.node_controller_session.get_node_worker_processes, 'crossbar.node.get_node_worker_processes')

      self.publish('com.myapp.topic1', os.getpid())

