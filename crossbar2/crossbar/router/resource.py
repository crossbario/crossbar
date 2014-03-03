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



import os

from twisted.python import log
from twisted.python.filepath import FilePath
from twisted.web.resource import Resource, NoResource

## trigers module level reactor import
## https://twistedmatrix.com/trac/ticket/6849#comment:5
from twisted.web.twcgi import CGIScript, CGIProcessProtocol

## triggers module level reactor import
## https://twistedmatrix.com/trac/ticket/6849#comment:4
from twisted.web.static import File


class CgiScript(CGIScript):

   def __init__(self, filename, filter):
      CGIScript.__init__(self, filename)
      self.filter = filter

   def runProcess(self, env, request, qargs = []):
      p = CGIProcessProtocol(request)
      from twisted.internet import reactor
      reactor.spawnProcess(p, self.filter, [self.filter, self.filename], env, os.path.dirname(self.filename))



class CgiDirectory(Resource, FilePath):

   cgiscript = CgiScript

   def __init__(self, pathname, filter, childNotFound = None):
      Resource.__init__(self)
      FilePath.__init__(self, pathname)
      self.filter = filter
      if childNotFound:
         self.childNotFound = childNotFound
      else:
         self.childNotFound = NoResource("CGI directories do not support directory listing.")

   def getChild(self, path, request):
      fnp = self.child(path)
      if not fnp.exists():
         return File.childNotFound
      elif fnp.isdir():
         return CgiDirectory(fnp.path, self.filter, self.childNotFound)
      else:
         return self.cgiscript(fnp.path, self.filter)
      return NoResource()

   def render(self, request):
      return self.childNotFound.render(request)
