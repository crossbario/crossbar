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

import sys
import os
import datetime

import psutil

from twisted.python import log

from autobahn.twisted.wamp import ApplicationSession



class Component(ApplicationSession):

   def onConnect(self):
      log.msg("Connected to node.")
      self.join("realm1")


   def onJoin(self, details):
      log.msg("Realm joined.")

      def get_cpu_affinity():
         p = psutil.Process(os.getpid())
         return p.get_cpu_affinity()

      self.register(get_cpu_affinity, 'crossbar.node.component.get_cpu_affinity')


      def set_cpu_affinity(cpus):
         p = psutil.Process(os.getpid())
         p.set_cpu_affinity(cpus)

      self.register(set_cpu_affinity, 'crossbar.node.component.set_cpu_affinity')


      def utcnow():
         now = datetime.datetime.utcnow()
         return now.strftime("%Y-%m-%dT%H:%M:%SZ")

      self.register(utcnow, 'com.timeservice.now')


      log.msg("Procedures registered.")



if __name__ == '__main__':

   ## Command line args:
   ## debug: true / false
   ## log: file / stderr / none
   ## loglevel

   ## make sure logging to something else than stdio
   ## is setup _first_
   log.startLogging(sys.stderr)
   #log.startLogging(open('test.log', 'w'))

   log.msg("Node component starting with PID {} ..".format(os.getpid()))

   ## we use an Autobahn utility to import the "best" available Twisted reactor
   ##
   from autobahn.twisted.choosereactor import install_reactor
   reactor = install_reactor()
   from twisted.python.reflect import qual
   log.msg("Running on reactor {}".format(qual(reactor.__class__)))

   try:

      ## create a WAMP application session factory
      ##
      from autobahn.twisted.wamp import ApplicationSessionFactory
      session_factory = ApplicationSessionFactory()
      session_factory.session = Component

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
      log.msg("Starting reactor ..")
      reactor.run()

   except Exception as e:
      log.msg("Unhandled exception in node component: {}".format(e))
