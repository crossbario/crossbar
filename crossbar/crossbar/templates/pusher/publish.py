###############################################################################
##
##  Copyright (C) 2012-2014 Tavendo GmbH
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


import crossbarconnect


if __name__ == '__main__':

   ## create a new Crossbar.io push client (once)
   ##
   client = crossbarconnect.Client("http://127.0.0.1:8080/push")

   ## publish an event without payload
   ##
   client.publish("com.myapp.topic1")

   ## publish an event with (positional) payload and get publication ID
   ##
   event_id = client.publish("com.myapp.topic1", "Hello, world!", 23)
   print("event published with ID {0}".format(event_id))

   ## publish 5 events with complex payload
   ##
   for i in range(5):
      client.publish("com.myapp.topic1", i, sq = i * i, msg = "Hello, world!")
