###############################################################################
##
##  Copyright (C) 2014, Tavendo GmbH and/or collaborators. All rights reserved.
##
##  Redistribution and use in source and binary forms, with or without
##  modification, are permitted provided that the following conditions are met:
##
##  1. Redistributions of source code must retain the above copyright notice,
##     this list of conditions and the following disclaimer.
##
##  2. Redistributions in binary form must reproduce the above copyright notice,
##     this list of conditions and the following disclaimer in the documentation
##     and/or other materials provided with the distribution.
##
##  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
##  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
##  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
##  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
##  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
##  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
##  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
##  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
##  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
##  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
##  POSSIBILITY OF SUCH DAMAGE.
##
###############################################################################

import sys

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import clientFromString

from autobahn.twisted import wamp, websocket
from autobahn.wamp import types
from autobahn.wamp import auth
from autobahn.wamp.types import PublishOptions


PRINCIPAL = u'joe'
TICKET = u'secret!!!'


class MyFrontendComponent(wamp.ApplicationSession):

   def onConnect(self):
      print("connected. joining realm {}, performing Ticket-based authentication as principal {} ...".format(self.config.realm, PRINCIPAL))
      self.join(self.config.realm, [u"ticket"], PRINCIPAL)

   def onChallenge(self, challenge):
      print("authentication challenge received: {}".format(challenge))
      if challenge.method == u"ticket":
         return TICKET
      else:
         raise Exception("don't know how to compute challenge for authmethod {}".format(challenge.method))

   @inlineCallbacks
   def onJoin(self, details):
      print("ok, session joined!")

      ## call a procedure we are allowed to call (so this should succeed)
      ##
      try:
         res = yield self.call(u'com.example.add2', 2, 3)
         print("call result: {}".format(res))
      except Exception as e:
         print("call error: {}".format(e))

      ## (try to) register a procedure where we are not allowed to (so this should fail)
      ##
      try:
         reg = yield self.register(lambda x, y: x * y, u'com.example.mul2')
      except Exception as e:
         print("registration failed - this is expected: {}".format(e))

      ## (try to) publish to some topics
      ##
      topics = [
         u'com.example.topic1',
         u'com.example.topic2',
         u'com.foobar.topic1',
         u'com.foobar.topic2'
      ]

      for topic in topics:
         try:
            yield self.publish(topic, options = PublishOptions(acknowledge = True))
            print("ok, event published to topic {}".format(topic))
         except Exception as e:
            print("publication to topic {} failed: {}".format(topic, e))

      self.leave()

   def onLeave(self, details):
      print("onLeave: {}".format(details))
      self.disconnect()

   def onDisconnect(self):
      reactor.stop()


if __name__ == '__main__':

   from autobahn.twisted.wamp import ApplicationRunner

   runner = ApplicationRunner(url = "ws://localhost:8080/ws", realm = "realm1")
   runner.run(MyFrontendComponent)
