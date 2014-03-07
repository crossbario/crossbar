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

from autobahn.wamp.types import RegisterOptions
from autobahn.twisted.wamp import ApplicationSession



class TimeService(ApplicationSession):
   """
   A simple time service application component.
   """

   def __init__(self, realm = "realm1"):
      ApplicationSession.__init__(self)
      self._realm = realm


   def onConnect(self):
      self.join(self._realm)


   def onJoin(self, details):

      def utcnow(details = None):
         ## details is an instance of autobahn.wamp.types.CallDetails
         ## and provides information on the caller
         now = datetime.datetime.utcnow()
         now = now.strftime("%Y-%m-%dT%H:%M:%SZ")
         return "{} (called by session {} / authid '{}' / authrole '{}')".format(\
            now, details.caller, details.authid, details.authrole)

      ## To get caller information when being called, we need to
      ## register with options ..
      self.register(utcnow, 'com.timeservice.now',
         options = RegisterOptions(details_arg = 'details', discloseCaller = True))
