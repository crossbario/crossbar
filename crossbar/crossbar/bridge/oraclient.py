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


from autobahn.wamp import json_dumps


class OraConnect:
   """
   Oracle Connect.
   """

   def __init__(self,
                id,
                host,
                port,
                sid,
                user,
                password,
                demoUser,
                demoPassword,
                connectionTimeout):

      ## 2 connects are equal (unchanged) iff the following are equal (unchanged)
      self.id = str(id)
      self.host = str(host)
      self.port = int(port)
      self.sid = str(sid)
      self.user = str(user)
      self.password = str(password)
      self.demoUser = str(demoUser) if demoUser is not None else None
      self.demoPassword = str(demoPassword) if demoPassword is not None else None

      self.connectionTimeout = connectionTimeout

   def __eq__(self, other):
      if isinstance(other, OraConnect):
         return self.id == other.id and \
                self.host == other.host and \
                self.port == other.port and \
                self.sid == other.sid and \
                self.user == other.user and \
                self.password == other.password and \
                self.demoUser == other.demoUser and \
                self.demoPassword == other.demoPassword
      return NotImplemented

   # http://jcalderone.livejournal.com/32837.html !!
   def __ne__(self, other):
      result = self.__eq__(other)
      if result is NotImplemented:
         return result
      return not result

   def __repr__(self):
      r = {'id': self.id,
           #'connectionTimeout': self.connectionTimeout,
           'host': self.host,
           'port': self.port,
           'sid': self.sid,
           'user': self.user,
           'password': self.password,
           'demo-user': self.demoUser,
           'demo-password': self.demoPassword,
           }
      return json_dumps(r)
