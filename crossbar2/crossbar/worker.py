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
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.types import PublishOptions



class WorkerProcess(ApplicationSession):
   """
   A Crossbar.io worker process connects back to the node router
   via WAMP-over-stdio.
   """

   def onConnect(self):
      self.debug = self.factory.options.debug
      self.debug = True

      self._pid = os.getpid()
      self._node_name = '918234'

      if self.debug:
         log.msg("Connected to node router.")

      self._router_module = None

      self._class_hosts = {}
      self._class_host_seq = 0

      self.join("crossbar")


   @inlineCallbacks
   def onJoin(self, details):

      def get_cpu_affinity():
         """
         Get CPU affinity of this process.
         """
         p = psutil.Process(self._pid)
         return p.get_cpu_affinity()

      yield self.register(get_cpu_affinity, 'crossbar.node.{}.worker.{}.get_cpu_affinity'.format(self._node_name, self._pid))


      def set_cpu_affinity(cpus):
         """
         Set CPU affinity of this process.
         """
         p = psutil.Process(self._pid)
         p.set_cpu_affinity(cpus)

      yield self.register(set_cpu_affinity, 'crossbar.node.{}.worker.{}.set_cpu_affinity'.format(self._node_name, self._pid))


      def utcnow():
         """
         Return current time in this process as UTC.
         """
         now = datetime.datetime.utcnow()
         return now.strftime("%Y-%m-%dT%H:%M:%SZ")

      yield self.register(utcnow, 'crossbar.node.{}.worker.{}.now'.format(self._node_name, self._pid))


      def get_pythonpath():
         """
         Returns the current Python module search path.
         """
         return sys.path

      yield self.register(get_pythonpath, 'crossbar.node.{}.worker.{}.get_pythonpath'.format(self._node_name, self._pid))


      def add_pythonpath(paths, prepend = True):
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

      yield self.register(add_pythonpath, 'crossbar.node.{}.worker.{}.add_pythonpath'.format(self._node_name, self._pid))


      from crossbar.router.module import RouterModule
      self._router_module = RouterModule(self.factory.options.cbdir)

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
      from crossbar.router.component import ComponentModule

      self._componentModule = ComponentModule(self, self._pid, self.factory.options.cbdir)


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


   def startComponent(self):
      pass




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

   parser.add_argument('-n',
                       '--name',
                       default = None,
                       help = 'Optional process name to set.')

   options = parser.parse_args()


   ## make sure logging to something else than stdio is setup _first_
   ##
   from crossbar.process import BareFormatFileLogObserver
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
      if options.name:
         setproctitle.setproctitle(options.name)
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
