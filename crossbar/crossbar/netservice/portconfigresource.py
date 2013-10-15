###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
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


from twisted.web.resource import Resource

from autobahn.wamp import json_dumps

from crossbar.database import Database


class PortConfigResource(Resource):
   """
   REST interface to read port configuration from the database.
   """

   def __init__(self, config, port):
      Resource.__init__(self)
      self.config = config
      self.port = port

   def render_GET(self, request):
      port = self.config.get(self.port + "-port", None)
      tls = self.config.get(self.port + "-tls", None)
      if self.port == "hub-websocket":
         path = self.config.get("ws-websocket-path", "")
         res = (port, tls, path)
      else:
         res = (port, tls)
      return json_dumps(res)


def addPortConfigResource(config, root, path):
   """
   Add port configuration Twisted Web resource to path hierachy.

   :param config: Reference to config service.
   :type config: obj
   :param root: Twisted Web root resource where to add child resources.
   :type root: obj
   :param path: Base path under which to add port resources.
   :type path: str
   """
   cfg = Resource()
   root.putChild(path, cfg)
   for port in Database.NETPORTS_TLS_PREFIXES:
      cfg.putChild(port, PortConfigResource(config, port))
