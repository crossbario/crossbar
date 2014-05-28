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


import os


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
   "default": {
      "help": "A minimal WAMP router",
      "config": CONFIG_DEFAULT,
   },
   "python": {
      "help": "A Python WAMP application with a WAMP router",
      "config": CONFIG_DEFAULT,
      "basedir": "templates/python"
   }
   #"demos": CONFIG_DEMOS,
   #"testee": CONFIG_TESTEE,
}


def print_templates_help():
   print("\nAvailable Crossbar.io node templates:\n")
   for t in CONFIG_TEMPLATES:
      print("  {} {}".format(t.ljust(20, ' '), CONFIG_TEMPLATES[t]['help']))
   print("")



import jinja2
import pkg_resources

   #    templates_dir = os.path.abspath(pkg_resources.resource_filename("crossbar", "web/templates"))
   #    if self.debug:
   #       log.msg("Using Web templates from {}".format(templates_dir))
   #    self._templates = jinja2.Environment(loader = jinja2.FileSystemLoader(templates_dir))

   #    self._page = templates.get_template('cb_web_404.html')
   #    self._directory = directory

   # def render_GET(self, request):
   #    s = self._page.render(cbVersion = crossbar.__version__,
   #                          directory = self._directory)


class Templates:

   def __init__(self):
      self._templates = CONFIG_TEMPLATES

   def __contains__(self, template):
      return template in self._templates

   def init(self, cbdir, template, dryrun = True):
      template = self._templates[template]
      basedir = os.path.abspath(pkg_resources.resource_filename("crossbar", template['basedir']))

      appdir = os.path.abspath(os.path.join(cbdir, '..'))
      #print basedir

      kk = jinja2.Environment(loader = jinja2.FileSystemLoader(basedir))

      parameters = {}
      parameters['node_id'] = "node123"
      parameters['realm_id'] = "myrealm1"

      page = kk.get_template('.crossbar/config.json')
      #print page.render(**parameters)

      created = []
      try:
         for root, dirs, files in os.walk(basedir):
            for d in dirs:
               create_dir_path = os.path.join(appdir, os.path.relpath(os.path.join(root, d), basedir))
               print("Creating directory {}".format(create_dir_path))
               if not dryrun:
                  os.mkdir(create_dir_path)
               created.append(('dir', create_dir_path))

            for f in files:
               src_file = os.path.join(root, f)
               dst_dir_path = os.path.join(appdir, os.path.relpath(root, basedir))
               dst_file = os.path.abspath(os.path.join(dst_dir_path, f))
               print("Copying {} to {}".format(src_file, dst_file))
               if not dryrun:
                  pass
               created.append(('file', dst_file))
         a = 1/0
      except Exception as e:
         print("Error encountered - rolling back")
         for ptype, path in reversed(created):
            if ptype == 'file':
               try:
                  print("Removing file {}".format(path))
                  if not dryrun:
                     os.remove(path)
               except:
                  print("Warning: could not remove file {}".format(path))
            elif ptype == 'dir':
               try:
                  print("Removing directory {}".format(path))
                  if not dryrun:
                     os.rmdir(path)
               except:
                  print("Warning: could not remove directory {}".format(path))
            else:
               raise Exception("logic error")
         raise e

      return

      with open(os.path.join(cbdir, 'config.json'), 'wb') as outfile:
         outfile.write(config)
      print("Node configuration created from template '{}'".format(template))
