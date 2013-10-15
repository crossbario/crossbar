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


import datetime

from crossbar.adminwebmodule.uris import URI_EVENT


class Logger:
   """
   Twisted log observer.
   """

   def __init__(self):
      self.dispatch = None
      self.log = []
      self.lineno = 1


   def setDispatch(self, dispatch):
      """
      Set the event dispatcher to publish log WAMP events.
      """
      self.dispatch = dispatch


   def __call__(self, obj):
      """
      Callback fired on logging.
      """
      # time, system, message, isError
      d = datetime.datetime.fromtimestamp(obj['time'])
      ds = d.strftime("%Y-%m-%d %H:%M:%S")
      if obj['isError']:
         loglevel = 'ERROR'
      else:
         loglevel = 'INFO'
      if type(obj['message']) == tuple and len(obj['message']) > 0:
         msg = obj['message'][0]
      else:
         msg = str(obj['message'])
      m = (self.lineno, ds, loglevel, obj['system'], msg)
      #m = (self.lineno, ds, loglevel, obj['system'], '\n'.join(list(obj['message'])))
      self.lineno += 1
      self.log.append(m)
      if self.dispatch:
         try:
            self.dispatch(URI_EVENT + "on-log", m)
         except:
            pass


   def getLog(self, limit = None):
      """
      Get accumulated log lines.
      """
      if limit is not None:
         return self.log[len(self.log) - limit:]
      else:
         return self.log
