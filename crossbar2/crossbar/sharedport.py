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

import sys
import socket

from twisted.python import log
from twisted.internet import tcp



class CustomPort(tcp.Port):
   """
   A custom port which sets socket options for sharing TCP ports
   between multiple processes.
   """

   def __init__(self, port, factory, backlog = 50, interface = '', reactor = None, reuse = False):
      tcp.Port.__init__(self, port, factory, backlog, interface, reactor)
      self._reuse = reuse


   def createInternetSocket(self):
      s = tcp.Port.createInternetSocket(self)
      if self._reuse:
         ##
         ## reuse IP Port
         ##
         if 'bsd' in sys.platform or \
             sys.platform.startswith('linux') or \
             sys.platform.startswith('darwin'):
            ## reuse IP address/port 
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

         elif sys.platform == 'win32':
            ## on Windows, REUSEADDR already implies REUSEPORT
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

         else:
            raise Exception("don't know how to set SO_RESUSEPORT on platform {}".format(sys.platform))

      return s
