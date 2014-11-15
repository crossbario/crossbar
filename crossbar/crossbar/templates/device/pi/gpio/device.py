from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall

from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationSession

import RPi.GPIO as GPIO


class MyComponent(ApplicationSession):

   @inlineCallbacks
   def onJoin(self, details):
      print("session ready")

      cfg = self.config.extra

      self.LED_PINS = cfg["led_pins"]
      self.BUTTON_PINS = cfg["button_pins"]
      self.SCAN_RATE = cfg["scan_rate"]

      ## init GPIO
      ##
      GPIO.setwarnings(False)
      GPIO.setmode(GPIO.BCM)
      GPIO.cleanup()
      for led_pin in self.LED_PINS:
         GPIO.setup(led_pin, GPIO.OUT)
      for btn_pin in self.BUTTON_PINS:
         GPIO.setup(btn_pin, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)

      self._led_status = [False for led in self.LED_PINS]
      self._btn_status = [GPIO.input(btn_pin) == 1 for btn_pin in self.BUTTON_PINS]

      try:
         res = yield self.register(self)
         print("ok, {} procedures registered".format(len(res)))
      except Exception as e:
         print("could not register procedures: {}".format(e))

      self._button_scanner = LoopingCall(self._scan_buttons)
      self._button_scanner.start(1./float(self.SCAN_RATE))


   def _check_led_arg(self, led):
      if led not in range(0, len(self.LED_PINS)):
         raise ApplicationError("com.example.invalid_argument", "No LED with ID {}".format(led))


   @wamp.register(u"com.example.set_led")
   def setLed(self, led, status):
      """
      Set an LED status.
      """
      self._check_led_arg(led)

      if type(status) != bool:
         raise ApplicationError("com.example.invalid_argument", "status must be a bool")

      if self._led_status[led] != status:
         self._led_status[led] = status
         GPIO.output(self.LED_PINS[led], GPIO.HIGH if status else GPIO.LOW)
         self.publish("com.example.on_led_set", led = led, status = status)
         if status:
            print("LED {} turned on".format(led))
         else:
            print("LED {} turned off".format(led))
         return True
      else:
         return False


   @wamp.register(u"com.example.get_led")
   def getLed(self, led = None):
      """
      Get an LED status.
      """
      if led is not None:
         self._check_led_arg(led)
         return self._led_status[led]
      else:
         return self._led_status


   @wamp.register(u"com.example.toggle_led")
   def toggleLed(self, led):
      self._check_led_arg(led)
      self.setLed(led, not self._led_status[led])
      return self._led_status[led]


   def _check_button_arg(self, button):
      if button not in range(0, len(self.BUTTON_PINS)):
         raise ApplicationError("com.example.invalid_argument", "No Button with ID {}".format(button))


   @wamp.register(u"com.example.get_button")
   def getButton(self, button = None):
      """
      Get a Button status.
      """
      if button is not None:
         self._check_button_arg(button)
         return self._btn_status[button]
      else:
         return self._btn_status


   def _scan_buttons(self):
      for btn in range(0, len(self.BUTTON_PINS)):
         pressed = GPIO.input(self.BUTTON_PINS[btn]) == 1
         if self._btn_status[btn] != pressed:
            self._btn_status[btn] = pressed
            self.publish("com.example.on_button", button = btn, pressed = pressed)
            if pressed:
               print("button {} pressed".format(btn))
            else:
               print("button {} released".format(btn))



if __name__ == "__main__":
   from autobahn.twisted.wamp import ApplicationRunner

   print("WAMP component starting - please be patient ..")

   extra = {
      ## these Pins are wired to LEDs
      ##
      "led_pins": [21, 22],

      ## these Pins are wired to Buttons
      ##
      "button_pins": [17],

      ## we will scan the buttons at this rate (Hz)
      ##
      "scan_rate": 50
   }

   runner = ApplicationRunner(url = "ws://127.0.0.1:8080/ws", realm = "realm1", extra = extra)
   runner.run(MyComponent)
