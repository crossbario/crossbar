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

import json

from twisted.web.resource import Resource

import crossbar


class JsonResource(Resource):
   """
   Static Twisted Web resource that renders to a JSON document.
   """

   def __init__(self, value):
      Resource.__init__(self)
      self._data = json.dumps(value)

   def render_GET(self, request):
      return self._data



class Resource404(Resource):
   """
   Custom error page (404).
   """
   def __init__(self, templates, directory):
      Resource.__init__(self)
      self._page = templates.get_template('cb_web_404.html')
      self._directory = directory

   def render_GET(self, request):
      s = self._page.render(cbVersion = crossbar.__version__,
                            directory = self._directory)
      return s.encode('utf8')
