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
import sys
import datetime

from twisted.python import log
from twisted.internet.defer import DeferredList, inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import ComponentConfig, PublishOptions



class NativeWorker(ApplicationSession):
   """
   A native Crossbar.io worker process. The worker will be connected
   to the node's management router via WAMP-over-stdio.  
   """

   def onConnect(self):
      """
      Called when the worker has connected to the node's management router.
      """
      self.debug = self.config.extra.debug

      if self.debug:
         log.msg("Worker connected to node management router.")

      self._started = datetime.datetime.utcnow()

      self._manhole_listening_port = None

      #self.join(self._node_realm)
      print "X"*100, self.config.realm
      self.join(self.config.realm)



   @inlineCallbacks
   def onJoin(self, details):
      """
      Called when worker process has joined the node's management realm.
      """
      procs = [
         'start_manhole',
         'stop_manhole',
         'trigger_gc',
         'get_cpu_affinity',
         'set_cpu_affinity',
         'utcnow',
         'started',
         'uptime',
         'get_pythonpath',
         'add_pythonpath'
      ]

      dl = []
      for proc in procs:
         uri = 'crossbar.node.{}.worker.{}.{}'.format(self.config.extra.node, self.config.extra.pid, proc)
         dl.append(self.register(getattr(self, proc), uri))

      regs = yield DeferredList(dl)

      if self.debug:
         log.msg("Worker procedures registered.")

      ## signal that this worker is ready for setup. the actual setup procedure
      ## will either be sequenced from the local node configuration file or remotely
      ## from a management service
      ##
      pub = yield self.publish('crossbar.node.{}.on_worker_ready'.format(self.config.extra.node),
         {'pid': self.config.extra.pid, 'cmd': [sys.executable] + sys.argv},
         options = PublishOptions(acknowledge = True))

      if self.debug:
         log.msg("Worker ready published ({})".format(pub.id))



   def trigger_gc(self):
      """
      Triggers a garbage collection.
      """
      import gc
      gc.collect()



   @inlineCallbacks
   def start_manhole(self, config):
      """
      Start a manhole (SSH) within this worker.
      """
      if self._manhole_listening_port:
         raise ApplicationError("wamp.error.could_not_start", "Could not start manhole - already started")

      ## manhole
      ##
      from twisted.cred import checkers, portal
      from twisted.conch.manhole import ColoredManhole
      from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm

      checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
      for user in config['users']:
         checker.addUser(user['user'], user['password'])

      namespace = {'worker': self}

      rlm = TerminalRealm()
      rlm.chainedProtocolFactory.protocolFactory = lambda _: ColoredManhole(namespace)

      ptl = portal.Portal(rlm, [checker])

      factory = ConchFactory(ptl)

      from crossbar.twisted.endpoint import create_listening_port_from_config
      from twisted.internet import reactor

      try:
         self._manhole_listening_port = yield create_listening_port_from_config(config['endpoint'], factory, self.config.extra.cbdir, reactor)
      except Exception as e:
         raise ApplicationError("wamp.error.could_not_listen", "Could not start manhole: '{}'".format(e))



   @inlineCallbacks
   def stop_manhole(self):
      """
      Start a manhole (SSH) within this worker.
      """
      if self._manhole_listening_port:
         yield self._manhole_listening_port.stopListening()
         self._manhole_listening_port = None
      else:
         raise ApplicationError("wamp.error.could_not_stop", "Could not stop manhole - not started")



   def get_cpu_affinity(self):
      """
      Get CPU affinity of this process.
      """
      try:
         import psutil
      except ImportError:
         log.msg("Warning: could not get process CPU affinity - psutil not installed")
         return []
      else:
         p = psutil.Process(self.config.extra.pid)
         return p.get_cpu_affinity()



   def set_cpu_affinity(self, cpus):
      """
      Set CPU affinity of this process.
      """
      try:
         import psutil
      except ImportError:
         log.msg("Warning: could not set process CPU affinity - psutil not installed")
      else:
         p = psutil.Process(self.config.extra.pid)
         p.set_cpu_affinity(cpus)



   def get_pythonpath(self):
      """
      Returns the current Python module search path.
      """
      return sys.path



   def add_pythonpath(self, paths, prepend = True):
      """
      Add paths to Python module search path.
      """
      ## transform all paths (relative to cbdir) into absolute paths.
      paths = [os.path.abspath(os.path.join(self.config.extra.cbdir, p)) for p in paths]
      if prepend:
         sys.path = paths + sys.path
      else:
         sys.path.extend(paths)
      return paths



   def utcnow(self):
      """
      Return current time in this process as UTC (ISO 8601 string).
      """
      now = datetime.datetime.utcnow()
      return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"



   def started(self):
      """
      Return start time of this process as UTC (ISO 8601 string).
      """
      return self._started.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"



   def uptime(self):
      """
      Returns uptime of this process in seconds (as float).
      """
      now = datetime.datetime.utcnow()
      return (now - self._started).total_seconds()
