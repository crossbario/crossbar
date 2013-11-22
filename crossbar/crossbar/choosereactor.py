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

import sys, json

## Install Twisted reactor. This needs to be done here,
## before importing any other Twisted/Autobahn stuff!
##
if 'bsd' in sys.platform or sys.platform.startswith('darwin'):
   try:
      v = sys.version_info
      if v[0] == 1 or (v[0] == 2 and v[1] < 6) or (v[0] == 2 and v[1] == 6 and v[2] < 5):
         raise Exception("Python version too old (%s)" % sys.version)
      from twisted.internet import kqreactor
      kqreactor.install()
   except Exception, e:
      print """
WARNING: Running on BSD or Darwin, but cannot use kqueue Twisted reactor.

 => %s

To use the kqueue Twisted reactor, you will need:

  1. Python >= 2.6.5 or PyPy > 1.8
  2. Twisted > 12.0

Note the use of >= and >.

Will let Twisted choose a default reactor (potential performance degradation).
""" % str(e)
      pass

if sys.platform in ['win32']:
   try:
      from twisted.application.reactors import installReactor
      installReactor("iocp")
   except Exception, e:
      print """
WARNING: Running on Windows, but cannot use IOCP Twisted reactor.

 => %s

Will let Twisted choose a default reactor (potential performance degradation).
""" % str(e)

if sys.platform.startswith('linux'):
   try:
      from twisted.internet import epollreactor
      epollreactor.install()
   except Exception, e:
      print """
WARNING: Running on Linux, but cannot use Epoll Twisted reactor.

 => %s

Will let Twisted choose a default reactor (potential performance degradation).
""" % str(e)
