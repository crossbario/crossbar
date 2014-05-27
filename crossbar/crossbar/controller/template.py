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

__all__ = ['CONFIG_TEMPLATES']


CONFIG_DEFAULT = """{
   "processes": [
      {
         "type": "worker",
         "modules": [
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
   ]
}
"""

CONFIG_DEFAULT = """
{
   "controller": {
      "id": "node1"
   },
   "workers": [
      {
         "id": "router1",
         "type": "router",
         "realms": [
            {
               "id": "realm1",
               "name": "realm1",
               "roles": [
                  {
                     "id": "anonymous",
                     "permissions": [
                        {
                           "id": "perm1",
                           "uri": "*",
                           "publish": true,
                           "subscribe": true,
                           "call": true,
                           "register": true
                        }
                     ]
                  }
               ]
            }
         ],
         "transports": [
            {
               "id": "transport1",
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
                     "type": "websocket"
                  }
               }
            }
         ]
      }
   ]
}
"""


CONFIG_DEMOS = """{
   "processes": [
      {
         "type": "worker",
         "options": {
            "pythonpath": [".."]
         },
         "modules": [
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
                     },
                     "components": [
                        {
                           "type": "class",
                           "name": "crossbardemo.basic.TimeService"
                        },
                        {
                           "type": "class",
                           "name": "crossbardemo.basic.TickService"
                        },
                        {
                           "type": "class",
                           "name": "crossbardemo.basic.MathService"
                        }
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
   ]
}
"""



CONFIG_TESTEE = """{
   "processes": [
      {
         "type": "worker",
         "modules": [
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
   ]
}
"""



CONFIG_TEMPLATES = {
   "default": CONFIG_DEFAULT,
   "demos": CONFIG_DEMOS,
   "testee": CONFIG_TESTEE,
}
