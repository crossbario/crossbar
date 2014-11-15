import math
import random

from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread
from twisted.internet.task import LoopingCall

from autobahn.twisted.wamp import ApplicationSession



class MyComponent(ApplicationSession):

   @inlineCallbacks
   def onJoin(self, details):
      print("session ready")

      self._tick = 0
      self._cpu_temp_celsius = None

      def scanTemperature():
         self._cpu_temp_celsius = float(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000.
         self.publish("com.example.on_temperature", self._tick, self._cpu_temp_celsius)
         self._tick += 1

      scan = LoopingCall(scanTemperature)
      scan.start(1)

      try:
         yield self.register(self.getTemperature, "com.example.get_temperature")
         yield self.register(self.imposeStress, "com.example.impose_stress")
         print("ok, procedures registered")
      except Exception as e:
         print("could not register procedure: {}".format(e))


   def getTemperature(self):
      return self._cpu_temp_celsius


   def imposeStress(self, n):
      def _stress():
         val = 0
         for _ in range(0, n):
            val += math.sin(random.random())
         return val / float(n)

      return deferToThread(_stress)



if __name__ == "__main__":
   from autobahn.twisted.wamp import ApplicationRunner

   print("WAMP component starting - please be patient ..")

   runner = ApplicationRunner(url = "ws://127.0.0.1:8080/ws", realm = "realm1")
   runner.run(MyComponent)
