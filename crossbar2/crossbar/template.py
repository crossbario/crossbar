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

## Web serving:
##
##   - static Web content
##   - CGI
##
##   - WAMP-REST bridge (incoming)
##   - long-poll fallback for WAMP
##
##   - native WAMP-WebSocket
##

## serving static content
## serving CGI scripts
## serving REST bridge

## /
## /ws
## /longpoll
## /cgi
## /rest
##

config = {

   'web': {
      'endpoint': 'tcp:localhost:80',
      'services': {
         'ws': {'type': 'websocket'},
         'rest': {'type': 'restbridge'}
      }

   },

   'router': {

      'transports': [
         {'type': 'websocket', 'endpoint': 'tcp:localhost:9000'},
         {'type': 'websocket', 'endpoint': 'unix:/tmp/mywebsocket'},
         {'type': 'longpoll': 'endpoint': 'tcp:localhost:9001'}
      ],

      'realms': {
         'myrealm1': {
            

         }
      },
   }

   'restbridge': {
      'endpoint': 'tcp:localhost:9002',
      'router': 'unix:/tmp/mywebsocket'
   },

   'postgresbridge': {
      'dbconnect': '',
      'router'
   }
}


## standalone router
##
config = {
   'myrouter1': {
      'type': 'router',
      'realms': {
         'myrealm1': {
         }
      },
      'transports': [
         'websocket': 'tcp:localhost:80',
         'websocket': 'ssl:port=443:privateKey=/etc/ssl/server.pem',
         'longpoll': 'tcp:localhost:8080',
         'raw': 'tcp:localhost:5000'
      ],
      'workers': 4
   }
}


config = {
   'myrouter1': {
      'type': 'router',
      'realms': {
         'myrealm1': {
         }
      },
      'transports': [
         {
            'type': 'web',
            'endpoint': 'ssl:port=443:privateKey=/etc/ssl/server.pem',
            'paths': {
               '/': {
                  'type': 'static',
                  'directory': './web1'
               },
               '/ws': {
                  'type': 'websocket'
               },
               '/longpoll': {
                  'type': 'longpoll'
               }
            }
         },
         {
            'type': 'websocket',
            'endpoint': 'tcp:localhost:9090'
         },
         {
            'type': 'longpoll',
            'endpoint': 'tcp:localhost:8080'
         },
         {
            'type': 'raw',
            'endpoint': 'tcp:localhost:5000'
         }
      ],
      'workers': 4
   }
}


config = {
   'myweb1': {
      'paths': {
         '/ws': '',
         '/longpoll': ''
      },
      'workers': 4
   }
}

## standalone Oracle bridge
##
config = {
   'mybridge01': {
      'type': 'oraclebridge',
      'database': {
         'host': 'db1',
         'user': 'crossbar',
         'password': '98$jmF'
      },
      'router': {
         'endpoint': 'tcp:cb7.tavendo.de:80',
         'realm': 'myrealm01'
      }
   }
}

## standalone SRDP bridge
##
config = {
   'mybridge2': {
      'type': 'srdpbridge',
      'serial': {
         'port': '/dev/tty3',
         'rate': 115200
      },
      'router': {
         'endpoint': 'tcp:cb7.tavendo.de:80',
         'realm': 'myrealm01'
      }
   }
}

## standalone REST bridge
##
config = {
   'mybridge3': {
      'type': 'restbridge',
      'rest': {
         'endpoint': 'tcp:localhost:8080'
      },
      'forwards': [{
            'type': 'event',
            'uri': 'com.myapp.foobar',
            'match': 'prefix'
            'forward': 'http://someserver.com/somepath3'
         }, {
            'type': 'call',
            'uri': 'com.myapp3..procs',
            'match': 'wildcard'
            'forward': 'http://otherserver.com/proc'
         }
      ],
      'router': {
         'endpoint': 'tcp:cb7.tavendo.de:80',
         'realm': 'myrealm01'
      }
   }
}


config = {
   'router1': {
      'type': 'router'
      'realms': {
      }
   },

   'myweb1': {
      'type': 'web',
      'endpoint': 'tcp:localhost:9090',
      'paths': {
         '/': {
            'type': 'static',
            'path': './web1'
         }
         '/rest': {

         },
         '/cgi': {

         },
         '/ws': {
            'type': 'websocket',
            'router': 'router1'
         }
      }
   },

   'mybridge01': {
      'type': 'oraclebridge',
      'database': {
         'host': 'db1',
         'user': 'crossbar',
         'password': '98$jmF'
      },
      'router': 'router1'
   }
}


config = {
   'router1': {
      'type': 'router',
      'transport': 'crossbar@db1:1521',

      'embedded': {
         'bridge1': {
            'type': 'oraclebridge',
            'database': 'crossbar@db1:1521'
         }
      }
   }
}
