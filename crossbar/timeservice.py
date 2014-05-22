###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  Licensed under the Apache License, Version 2.0 (the "License");
##  you may not use this file except in compliance with the License.
##  You may obtain a copy of the License at
##
##      http://www.apache.org/licenses/LICENSE-2.0
##
##  Unless required by applicable law or agreed to in writing, software
##  distributed under the License is distributed on an "AS IS" BASIS,
##  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
##  See the License for the specific language governing permissions and
##  limitations under the License.
##
###############################################################################

import datetime

from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession

FOO = 25
#dfdfg

def foo():
   return FOO

from foobar import getfoo


## WAMP application component with our app code.
##
class Timeservice(ApplicationSession):

   @inlineCallbacks
   def onJoin(self, details):

      self._f = open(__file__, 'r')

      ## register a function that can be called remotely
      ##
      def utcnow():
         now = datetime.datetime.utcnow()
         print FOO, foo()
         #return "foo"
         return getfoo()
         return now.strftime("%Y-%m-%dT%H:%M:%SZ")

      try:
         reg = yield self.register(utcnow, 'com.timeservice.now')
      except Exception as e:
         self.leave()
      else:
         print("xx Procedure registered with ID {}".format(reg.id))


   def onDisconnect(self):
      print("onDisconnect")
      reactor.stop()



def make(config):
   ##
   ## This component factory creates instances of the
   ## application component to run.
   ##
   ## The function will get called either during development
   ## using the ApplicationRunner below, or as  a plugin running
   ## hosted in a WAMPlet container such as a Crossbar.io worker.
   ##
   if config:
      return Timeservice(config)
   else:
      ## if no config given, return a description of this WAMPlet ..
      return {'label': 'Awesome WAMPlet 1',
              'description': 'This is just a test WAMPlet that provides some procedures to call.'}



if __name__ == '__main__':
   from autobahn.twisted.wamp import ApplicationRunner

   ## test drive the component during development ..
   runner = ApplicationRunner(
      url = "ws://127.0.0.1:8080/ws",
      realm = "realm1",
      debug = False, ## low-level WebSocket debugging
      debug_wamp = False, ## WAMP protocol-level debugging
      debug_app = True) ## app-level debugging

   runner.run(make)
