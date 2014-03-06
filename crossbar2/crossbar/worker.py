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

from autobahn.twisted.wamp import ApplicationSession

from crossbar.router.component import ComponentModule
from crossbar.router.module import RouterModule


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
         log.msg("Worker {}: Connected to node router.".format(self._pid))

      self._routers = {}
      self._router_seq = 100

      self._class_hosts = {}
      self._class_host_seq = 100

      self.join("crossbar")


   def onJoin(self, details):

      def get_cpu_affinity():
         p = psutil.Process(self._pid)
         return p.get_cpu_affinity()

      self.register(get_cpu_affinity, 'crossbar.node.{}.process.{}.get_cpu_affinity'.format(self._node_name, self._pid))


      def set_cpu_affinity(cpus):
         p = psutil.Process(self._pid)
         p.set_cpu_affinity(cpus)

      self.register(set_cpu_affinity, 'crossbar.node.{}.process.{}.set_cpu_affinity'.format(self._node_name, self._pid))


      def utcnow():
         now = datetime.datetime.utcnow()
         return now.strftime("%Y-%m-%dT%H:%M:%SZ")

      self.register(utcnow, 'crossbar.node.{}.process.{}.now'.format(self._node_name, self._pid))


      def get_classpaths():
         return sys.path

      self.register(get_classpaths, 'crossbar.node.{}.process.{}.get_classpaths'.format(self._node_name, self._pid))


      def add_classpaths(paths, prepend = True):
         if prepend:
            sys.path = paths + sys.path
         else:
            sys.path.extend(paths)

      self.register(add_classpaths, 'crossbar.node.{}.process.{}.add_classpaths'.format(self._node_name, self._pid))


      ## Modules
      ##
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

      ## FIXME
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
