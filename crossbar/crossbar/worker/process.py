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
import psutil
import datetime

from twisted.python import log
from twisted.internet.defer import DeferredList, inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions



class WorkerProcess(ApplicationSession):
   """
   A Crossbar.io worker process connects back to the node router
   via WAMP-over-stdio.
   """

   def onConnect(self):
      self.debug = self.factory.options.debug

      self._pid = os.getpid()
      self._node_name = '918234'
      self._started = datetime.datetime.utcnow()

      if self.debug:
         log.msg("Connected to node router.")

      self._router_module = None
      self._manhole_listening_port = None

      self._class_hosts = {}
      self._class_host_seq = 0

      self.join("crossbar")


   @inlineCallbacks
   def onJoin(self, details):
      procs = [
         (self.start_manhole, 'start_manhole'),
         (self.stop_manhole, 'stop_manhole'),
         (self.trigger_gc, 'trigger_gc'),
         (self.get_cpu_affinity, 'get_cpu_affinity'),
         (self.set_cpu_affinity, 'set_cpu_affinity'),
         (self.utcnow, 'utcnow'),
         (self.started, 'started'),
         (self.uptime, 'uptime'),
         (self.get_pythonpath, 'get_pythonpath'),
         (self.add_pythonpath, 'add_pythonpath'),
      ]

      dl = []
      for proc in procs:
         dl.append(self.register(proc[0], 'crossbar.node.{}.worker.{}.{}'.format(self._node_name, self._pid, proc[1])))

      regs = yield DeferredList(dl)


      from crossbar.worker.router import RouterModule
      self._router_module = RouterModule(self.factory.options.cbdir, debug = self.debug)

      yield self._router_module.connect(self)

      # ## Router Module
      # ##
      # def start_router():
      #    """
      #    Start a router module in this process.
      #    """

      #    from crossbar.router.module import RouterModule

      #    self._router_seq += 1
      #    index = self._router_seq

      #    self._routers[index] = RouterModule(index, self.factory.options.cbdir)
      #    d = self._routers[index].start(self)

      #    def onstart(_):
      #       return index

      #    d.addCallback(onstart)
      #    return d

      # yield self.register(start_router, 'crossbar.node.{}.process.{}.router.start'.format(self._node_name, self._pid))


      ## Component Module
      ##

      ## FIXME
      from crossbar.worker.container import ContainerModule

      self._container_module = ContainerModule(self.factory.options.cbdir, debug = self.debug)

      yield self._container_module.connect(self)

      if self.debug:
         log.msg("Worker procedures registered.")

      ## signal that this worker is ready for setup. the actual setup procedure
      ## will either be sequenced from the local node configuration file or remotely
      ## from a management service
      ##
      pub = yield self.publish('crossbar.node.{}.on_worker_ready'.format(self._node_name),
         {'pid': self._pid, 'cmd': [sys.executable] + sys.argv},
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

      from crossbar.twisted.endpoint import create_endpoint_from_config
      from twisted.internet import reactor
      cbdir = self.factory.options.cbdir

      server = create_endpoint_from_config(config['endpoint'], cbdir, reactor)

      try:
         self._manhole_listening_port = yield server.listen(factory)
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
      p = psutil.Process(self._pid)
      return p.get_cpu_affinity()



   def set_cpu_affinity(self, cpus):
      """
      Set CPU affinity of this process.
      """
      p = psutil.Process(self._pid)
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
      cbdir = self.factory.options.cbdir
      paths = [os.path.abspath(os.path.join(cbdir, p)) for p in paths]
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



def run():
   """
   Entry point into background worker process. This wires up stuff such that
   a WorkerProcess instance is talking WAMP over stdio to the node controller.
   """
   ## create the top-level parser
   ##
   import argparse
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

   parser.add_argument('-t',
                       '--title',
                       default = None,
                       help = 'Optional process title to set.')

   options = parser.parse_args()


   ## make sure logging to something else than stdio is setup _first_
   ##
   from crossbar.twisted.process import BareFormatFileLogObserver
   flo = BareFormatFileLogObserver(sys.stderr)
   log.startLoggingWithObserver(flo.emit)


   ## the worker's PID
   ##
   pid = os.getpid()


   try:
      import setproctitle
   except ImportError:
      log.msg("Warning, could not set process title (setproctitle not installed)")
   else:
      ## set process title if requested to
      ##
      if options.title:
         setproctitle.setproctitle(options.title)
      else:
         setproctitle.setproctitle("Crossbar.io Worker")


   ## Crossbar.io node directory
   ##
   if hasattr(options, 'cbdir') and not options.cbdir:
      if os.environ.has_key("CROSSBAR_DIR"):
         options.cbdir = os.environ['CROSSBAR_DIR']
      else:
         options.cbdir = '.crossbar'

   options.cbdir = os.path.abspath(options.cbdir)
   log.msg("Starting from node directory {}.".format(options.cbdir))

   os.chdir(options.cbdir)


   ## we use an Autobahn utility to import the "best" available Twisted reactor
   ##
   from autobahn.twisted.choosereactor import install_reactor
   reactor = install_reactor(options.reactor)

   from twisted.python.reflect import qual
   log.msg("Running on {} reactor.".format(qual(reactor.__class__).split('.')[-1]))


   from autobahn.twisted.websocket import WampWebSocketServerProtocol

   class WorkerServerProtocol(WampWebSocketServerProtocol):

      def connectionLost(self, reason):
         try:
            log.msg("Connection to node controller lost.")
            WampWebSocketServerProtocol.connectionLost(self, reason)
         except:
            pass
         finally:
            ## loosing the connection to the node controller (the pipes) is fatal.
            ## stop the reactor and exit with error
            if reactor.running:
               reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
               reactor.stop()
            else:
               sys.exit(1)

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
      transport_factory.protocol = WorkerServerProtocol
      transport_factory.setProtocolOptions(failByDrop = False)

      ## create a protocol instance and wire up to stdio
      ##
      from twisted.internet import stdio
      proto = transport_factory.buildProtocol(None)
      stdio.StandardIO(proto)

      ## now start reactor loop
      ##
      log.msg("Entering event loop ..")

      #reactor.callLater(4, reactor.stop)
      reactor.run()

   except Exception as e:
      log.msg("Unhandled exception - {}".format(e))
      if reactor.running:
         reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
         reactor.stop()
      else:
         sys.exit(1)



if __name__ == '__main__':
   run()
