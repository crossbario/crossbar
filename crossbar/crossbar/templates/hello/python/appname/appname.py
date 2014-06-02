from autobahn.twisted.wamp import ApplicationSession

class AppSession(ApplicationSession):

   def onJoin(self, details):

      def hello():
         return "Hello from Python!"

      self.register(hello, 'com.{{ appname }}.hello')
