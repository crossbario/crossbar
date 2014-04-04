import datetime
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.wamp import ApplicationSession


class TimeService(ApplicationSession):

   def __init__(self, config):
      print "XX", config.extra
      ApplicationSession.__init__(self)
      self.config = config

   def onConnect(self):
      self.join(self.config.realm)

   @inlineCallbacks
   def onJoin(self, details):

      def utcnow():
         print("I am being called;)")
         now = datetime.datetime.utcnow()
         return now.strftime("%Y-%m-%dT%H:%M:%SZ")

      try:
         reg = yield self.register(utcnow, 'com.timeservice.now2')
         print("Ok, registered procedure for WAMP RPC ({})".format(reg.id))
      except Exception as e:
         print("Failed to register procedure: {}".format(e))
