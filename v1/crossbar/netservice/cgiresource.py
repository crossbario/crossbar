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


import sys, os

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

   def __init__(self, pathname, filter):
      Resource.__init__(self)
      FilePath.__init__(self, pathname)
      self.filter = filter

   def getChild(self, path, request):
      fnp = self.child(path)
      print fnp.path
      if not fnp.exists():
         return File.childNotFound
      elif fnp.isdir():
         return CgiDirectory(fnp.path, self.filter)
      else:
         return self.cgiscript(fnp.path, self.filter)
      return NoResource()

   def render(self, request):
      notFound = NoResource("CGI directories do not support directory listing.")
      return notFound.render(request)
