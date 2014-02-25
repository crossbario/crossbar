###############################################################################
##
##  Copyright (C) 2011-2014 Tavendo GmbH
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

__all__ = ['ProcessProxy']


from twisted.python import log
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession

import os


class ProcessProxy(ApplicationSession):
   """
   WAMP protocol to talk to node processes forked from the
   node controller. Usually running over stdio.
   """
   def __init__(self, pid = None, config = None):
      ApplicationSession.__init__(self)
      self._pid = pid
      self._config = config


   def onConnect(self):
      self.join("crossbar")


   @inlineCallbacks
   def onJoin(self, details):

      @inlineCallbacks
      def startup():

         print("Node component started: {}".format(self._config))

         options = self._config.get('options', {})
         if 'classpaths' in options:
            yield self.call('crossbar.node.component.{}.add_classpaths'.format(self._pid), options['classpaths'])
#         yield self.call('crossbar.node.component.{}.add_classpaths'.format(self._pid), [os.getcwd()])

         try:

            if self._config['type'] == 'router':


               res = yield self.call('crossbar.node.module.{}.router.start'.format(self._pid), options)
               print "Router started", res

               for realm_name in self._config['realms']:
                  print "Realm", realm_name
                  realm = self._config['realms'][realm_name]
                  res = yield self.call('crossbar.node.module.{}.router.start_realm'.format(self._pid), realm_name, realm)
                  print "Realm started", res

                  try:
                     print "----"
                     for klassname in realm.get('classes', []):
                        print ".."
                        res = yield self.call('crossbar.node.module.{}.router.start_class'.format(self._pid), klassname, realm_name)
                        print "Class started", res
                        #res = yield self.call('crossbar.node.module.{}.router.stop_class'.format(self._pid), res)
                        #print "Class stopped", res
                  except Exception as e:
                     print e, e.args

               for transport in self._config['transports']:
                  res = yield self.call('crossbar.node.module.{}.router.start_transport'.format(self._pid), transport)
                  print "Transport started", res


         except Exception as e:
            print e, e.error, e.args


      @inlineCallbacks
      def on_node_component_start(evt):
         print "9"*10
         yield startup()


      @inlineCallbacks
      def on_node_component_start2(evt):
         pid = evt['pid']
         print("Node component started: {}".format(evt))
         print(self._config)

         affinities = yield self.call('crossbar.node.component.{}.get_cpu_affinity'.format(pid))
         print("CPU affinity: {}".format(affinities))

         try:
            if False:
               config = {'url': 'ws://localhost:9000', 'endpoint': 'tcp:9000'}
               res = yield self.call('crossbar.node.component.{}.start'.format(pid), config)
               print res

            if True:
#               res = yield self.call('crossbar.{}.{}.{}.start'.format(hostname, pid, 'router1'), {})
#               res = yield self.call('crossbar.node.{}.process.{}.module.{}.start'.format(hostname, pid, 'router1'), {})
               res = yield self.call('crossbar.node.module.{}.router.start'.format(pid), {})
               print res

               tid1 = yield self.call('crossbar.node.module.{}.router.start_transport'.format(pid), {'type': 'websocket', 'url': 'ws://localhost:9000', 'endpoint': 'tcp:9000'})
               print tid1

               tid2 = yield self.call('crossbar.node.module.{}.router.start_transport'.format(pid), {'type': 'websocket', 'url': 'ws://localhost:9001', 'endpoint': 'tcp:9001'})
               print tid2

               res = yield self.call('crossbar.node.module.{}.router.list_transports'.format(pid))
               print res

               res = yield self.call('crossbar.node.module.{}.router.stop_transport'.format(pid), tid2)
               print res

               res = yield self.call('crossbar.node.module.{}.router.list_transports'.format(pid))
               print res

         except Exception as e:
            print e.error, e.args

      #yield on_node_component_start({'pid': self._pid})
      yield self.subscribe(on_node_component_start, 'crossbar.node.component.on_start')
