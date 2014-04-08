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



## 4-core optimized router
##
SMP4_ROUTER = {
   "name": "mynode1",
   "modules": {
      "myrouter1": {
         "type": "router",
         "realms": {
            "myrealm1": {
            }
         },
         "transports": [
            {
               "type": "websocket",
               "endpoint": "tcp:localhost:80"
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/myrouter1"
            }
         ],
         "links": [
            {
               "type": "websocket",
               "endpoint": "tcp:somehost.net:80"
            }
         ],
         "options": {
            "cpu_affinity": [3]
         }
      },
      "myrouter2": {
         "type": "router",
         "realms": {
            "myrealm1": {
            }
         },
         "transports": [
            {
               "type": "websocket",
               "endpoint": "tcp:localhost:80"
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/myrouter2"
            }
         ],
         "links": [
            {
               "type": "websocket",
               "endpoint": "tcp:somehost.net:80"
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/myrouter1"
            }
         ]
      },
      "myrouter3": {
         "type": "router",
         "realms": {
            "myrealm1": {
            }
         },
         "transports": [
            {
               "type": "websocket",
               "extensions": {
                  "permessage-deflate": {
                     "max-window-bits": 10
                  }
               },
               "options": {
                  "opening-timeout": 800
               },
               "authentication": {
                  "challenge_response": "myplugin1.start"
               },
               "endpoint": "tcp:localhost:80"
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/myrouter3"
            },
            {
               "type": "web",
               "endpoint": "tcp:80:shared",
               "paths": {
                  "/": {
                     "type": "static",
                     "directory": "~/.docroot"
                  },
                  "/ws": {
                     "type": "websocket",
                     "serializer": ["msgpack", "json"]
                  },
                  "/cgi": {
                     "type": "cgi",
                     "directory": "~/.cgi"
                  },
                  "/longpoll": {
                     "type": "longpoll",
                     "session_timeout": 2000
                  }
               }
            }
         ],
         "links": [
            {
               "type": "websocket",
               "endpoint": "tcp:somehost.net:80",
               "authentication": {
                  "tls_cacert": "keys/myca1.cert",
                  "tls_mykey": "keys/mykey1.key"
               },
               "realms": ["myrealm01", "myrealm02"]
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/myrouter1",
               "realms": "all"
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/myrouter2",
               "realms": "all"
            }
         ]
      }
   }
}

## standalone SRDP bridge
##
SRDP_BRIDGE = {
   "mybridge2": {
      "type": "srdpbridge",
      "serial": {
         "port": "/dev/tty3",
         "rate": 115200
      },
      "router": {
         "endpoint": "tcp:cb7.tavendo.de:80",
         "realm": "myrealm01"
      }
   }
}

## standalone REST bridge
##
REST_BRIDGE = {
   "mybridge3": {
      "type": "restbridge",
      "rest": {
         "endpoint": "tcp:localhost:8080"
      },
      "forwards": [{
            "type": "event",
            "uri": "com.myapp.foobar",
            "match": "prefix",
            "forward": "http://someserver.com/somepath3"
         }, {
            "type": "call",
            "uri": "com.myapp3..procs",
            "match": "wildcard",
            "forward": "http://otherserver.com/proc"
         }
      ],
      "router": {
         "endpoint": "tcp:cb7.tavendo.de:80",
         "realm": "myrealm01"
      }
   }
}

## standalone Postgres bridge
##
POSTGRES_BRIDGE = {
   "mybridge01": {
      "type": "postgresbridge",
      "database": {
         "host": "db1",
         "user": "crossbar",
         "password": "98$jmF"
      },
      "router": {
         "endpoint": "tcp:cb7.tavendo.de:80",
         "realm": "myrealm01"
      }
   }
}

## standalone Oracle bridge
##
ORACLE_BRIDGE = {
   "mybridge01": {
      "type": "oraclebridge",
      "database": {
         "host": "db1",
         "user": "crossbar",
         "password": "98$jmF"
      },
      "router": {
         "endpoint": "tcp:cb7.tavendo.de:80",
         "realm": "myrealm01"
      }
   }
}


## development router
##
DEV_ROUTER = {
   "myrouter1": {
      "type": "router",
      "realms": {
         "myrealm1": {
            "auth": {
               "create": {
                  "allow": "any"
               },
               "join": {
                  "allow": "any"
               }
            },
            "permissions": {
               ## application
               "com.myapp1": {
                  ## application.role
                  "developer": {
                     ## application.role.resource
                     "com.myapp1.monitor.*": {
                        ## application.role.resource.permission
                        "publish": True,
                        "subscribe": True,
                        "call": True,
                        "register": False
                     }
                  }
               }
            },
         }
      },
      "transports": [
         {
            "type": "websocket",
            "endpoint": "tcp:localhost:8080"
         },
         {
            "type": "websocket",
            "endpoint": "unix:/tmp/sock3"
         }
      ]
   }
}



DEV_ROUTER = {
   "processes": [
      {
         "type": "router",
         "realms": {
            "myrealm1": {
               "auth": {
                  "create": {
                     "allow": "any"
                  },
                  "join": {
                     "allow": "any"
                  }
               },
               "permissions": {
                  ## application
                  "com.myapp1": {
                     ## application.role
                     "developer": {
                        ## application.role.resource
                        "com.myapp1.monitor.*": {
                           ## application.role.resource.permission
                           "publish": True,
                           "subscribe": True,
                           "call": True,
                           "register": False
                        }
                     }
                  }
               },
            }
         },
         "transports": [
            {
               "type": "websocket",
               "endpoint": "tcp:8080",
               "url": "ws://localhost:8080"
            }
         ]
      }
   ]
}


DEV_ROUTER = {
   "processes": [
      {
         "type": "router",
         "options": {
            "pythonpath": [".", "/home/oberstet/scm/tavendo/autobahn/AutobahnPython/examples/twisted/wamp/basic"]
         },
         "realms": {
            "com.example.realm1": {
               "roles": {
                  "com.example.anonymous": {
                     "authentication": None,
                     "grants": {
                        "create": True,
                        "join": True,
                        "access": {
                           "*": {
                              "publish": True,
                              "subscribe": True,
                              "call": True,
                              "register": True
                           }
                        }
                     }
                  }
               },
               "classes": [
                  "rpc.timeservice.backend.Component",
                  "rpc.progress.backend.Component"
               ]
            }
         },
         "transports": [
            {
               "type": "websocket",
               "endpoint": "tcp:9000",
               "url": "ws://localhost:9000"
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/mysocket",
               "url": "ws://localhost"
            }
         ]
      },
      {
         "type": "component.python",
         "options": {
            "pythonpath": [".", "/home/oberstet/scm/tavendo/autobahn/AutobahnPython/examples/twisted/wamp/basic"]
         },
         "class": "rpc.arguments.backend.Component",
         "router": {
            "type": "websocket",
            "endpoint": "unix:/tmp/mysocket",
            "url": "ws://localhost",
            "realm": "realm1"
         }
      },
      # {
      #    "type": "component.python",
      #    "classes": [
      #       "crossbar.component.mathservice.MathService"
      #    ],
      #    "router": {
      #       "type": "websocket",
      #       "endpoint": "unix:/tmp/mysocket",
      #       "url": "ws://localhost",
      #       "realm": "com.example.realm1"
      #    }
      # },
      # {
      #    "type": "component.program",
      #    "command": "/usr/bin/node myapp.js",
      #    "router": {
      #       "type": "websocket",
      #       "endpoint": "tcp:localhost:8080",
      #       "url": "ws://localhost:8080",
      #       "realm": "com.example.realm1"
      #    }
      # }
   ]
}



DEV_ROUTER = """{
   "processes": [
      {
         "type": "router",
         "options": {
            "pythonpath": ["."]
         },
         "realms": {
            "realm1": {
               "roles": {
                  "com.example.anonymous": {
                     "authentication": null,
                     "grants": {
                        "create": true,
                        "join": true,
                        "access": {
                           "*": {
                              "publish": true,
                              "subscribe": true,
                              "call": true,
                              "register": true
                           }
                        }
                     }
                  }
               },
               "classes": [
                  "crossbardemo.basic.TimeService"
               ]
            }
         },
         "transports": [
            {
               "type": "websocket",
               "endpoint": "tcp:9000",
               "url": "ws://localhost:9000"
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/mysocket",
               "url": "ws://localhost"
            }
         ]
      },
      {
         "type": "component.python",
         "options": {
            "pythonpath": ["."]
         },
         "class": "crossbardemo.basic.TickService",
         "router": {
            "type": "websocket",
            "endpoint": "unix:/tmp/mysocket",
            "url": "ws://localhost",
            "realm": "realm1"
         }
      }
   ]
}
"""



DEV_ROUTER = """{
   "processes": [
      {
         "type": "router",
         "options": {
            "pythonpath": [".."]
         },
         "realms": {
            "realm1": {
               "roles": {
                  "com.example.anonymous": {
                     "authentication": null,
                     "grants": {
                        "create": true,
                        "join": true,
                        "access": {
                           "*": {
                              "publish": true,
                              "subscribe": true,
                              "call": true,
                              "register": true
                           }
                        }
                     }
                  }
               },
               "classes": [
                  "crossbardemo.basic.TimeService"
               ]
            }
         },
         "transports": [
            {
               "type": "websocket",
               "endpoint": "tcp:9000",
               "url": "ws://localhost:9000"
            }
         ]
      },
      {
         "type": "component.python",
         "options": {
            "pythonpath": ["."]
         },
         "class": "crossbardemo.basic.TickService",
         "router": {
            "type": "websocket",
            "endpoint": "tcp:localhost:9000",
            "url": "ws://localhost:9000",
            "realm": "realm1"
         }
      }
   ]
}
"""



DEV_ROUTER = """{
   "processes": [
      {
         "type": "router",
         "realms": {
            "realm1": {
               "permissions": {
                  "anonymous": {
                     "create": true,
                     "join": true,
                     "access": {
                        "*": {
                           "publish": true,
                           "subscribe": true,
                           "call": true,
                           "register": true
                        }
                     }
                  }
               }
            }
         },
         "transports": [
            {
               "type": "web",
               "endpoint": {
                  "type": "tcp",
                  "port": 8080
               },
               "paths": {
                  "/": {
                     "type": "static",
                     "directory": ".."
                  },
                  "ws": {
                     "type": "websocket",
                     "url": "ws://localhost:8080/ws"
                  }
               }
            }
         ]
      }
   ]
}
"""



DEV_ROUTER_WITH_DEMOS = """{
   "processes": [
      {
         "type": "router",
         "options": {
            "pythonpath": [".."]
         },
         "realms": {
            "realm1": {
               "permissions": {
                  "anonymous": {
                     "create": true,
                     "join": true,
                     "access": {
                        "*": {
                           "publish": true,
                           "subscribe": true,
                           "call": true,
                           "register": true
                        }
                     }
                  }
               },
               "classes": [
                  "crossbardemo.basic.TimeService",
                  "crossbardemo.basic.TickService",
                  "crossbardemo.basic.MathService"                  
               ]
            }
         },
         "transports": [
            {
               "type": "web",
               "endpoint": {
                  "type": "tcp",
                  "port": 8080
               },
               "paths": {
                  "/": {
                     "type": "static",
                     "module": "crossbardemo",
                     "resource": "web"
                  },
                  "ws": {
                     "type": "websocket",
                     "url": "ws://localhost:8080/ws"
                  }
               }
            }
         ]
      }
   ]
}
"""


TESTEE = """{
   "processes": [
      {
         "type": "router",
         "realms": {
            "realm1": {
               "permissions": {
                  "anonymous": {
                     "create": true,
                     "join": true,
                     "access": {
                        "*": {
                           "publish": true,
                           "subscribe": true,
                           "call": true,
                           "register": true
                        }
                     }
                  }
               }
            }
         },
         "transports": [
            {
               "type": "websocket.testee",
               "endpoint": {
                  "type": "tcp",
                  "port": 9001
               },
               "url": "ws://localhost:9001",
               "options": {
                  "compression": {
                     "deflate": {
                     }
                  }
               }
            }
         ]
      }
   ]
}
"""

TEMPLATES = {
   "router": DEV_ROUTER,
   "demos": DEV_ROUTER_WITH_DEMOS,
   "testee": TESTEE,
   #"router-smp4": SMP4_ROUTER,
   #"bridge-rest": REST_BRIDGE,
   #"bridge-srdp": SRDP_BRIDGE,
   #"bridge-postgres": POSTGRES_BRIDGE,
   #"bridge-oracle": ORACLE_BRIDGE,
   #"yun": ARDUINO_YUN,
   #"pi": RASPBERRY_PI
}

## crossbar init --template pi --data ~/.cbdata

## .. edit ~/.cbdata/config.json

## crossbar start --data ~/.cbdata --local

