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


import sys
import datetime
import logging

import twisted

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


class LevelFileLogObserver(twisted.python.log.FileLogObserver):
   """

   NOTSET   = 0
   DEBUG    = 10
   INFO     = 20
   WARN     = 30
   WARNING  = 30
   ERROR    = 40
   CRITICAL = 50
   FATAL    = 50
   """

   def __init__(self, f, level = logging.INFO):
      twisted.python.log.FileLogObserver.__init__(self, f)
      self.logLevel = level


   def emit(self, eventDict):
      if eventDict['isError']:
         level = logging.ERROR
      elif 'level' in eventDict:
         level = eventDict['level']
      else:
         level = logging.INFO
      if level >= self.logLevel:
         twisted.python.log.FileLogObserver.emit(self, eventDict)

# trace

def debug(*args, **kwargs):
   kwargs['level'] = logging.DEBUG
   twisted.python.log.msg(*args, **kwargs)

def info(*args, **kwargs):
   kwargs['level'] = logging.INFO
   twisted.python.log.msg(*args, **kwargs)

def warning(*args, **kwargs):
   kwargs['level'] = logging.WARNING
   twisted.python.log.msg(*args, **kwargs)

if True:
   def error(*args, **kwargs):
      kwargs['level'] = logging.ERROR
      twisted.python.log.err(*args, **kwargs)
else:
   error = twisted.python.log.err

def critical(*args, **kwargs):
   kwargs['level'] = logging.CRITICAL
   twisted.python.log.msg(*args, **kwargs)

# http://docs.jboss.org/process-guide/en/html/logging.html
# FATAL - Use the FATAL level priority for events that indicate a critical service failure. If a service issues a FATAL error it is completely unable to service requests of any kind.
# ERROR - Use the ERROR level priority for events that indicate a disruption in a request or the ability to service a request. A service should have some capacity to continue to service requests in the presence of ERRORs.
# WARN - Use the WARN level priority for events that may indicate a non-critical service error. Resumable errors, or minor breaches in request expectations fall into this category. The distinction between WARN and ERROR may be hard to discern and so its up to the developer to judge. The simplest criterion is would this failure result in a user support call. If it would use ERROR. If it would not use WARN.
# INFO - Use the INFO level priority for service life-cycle events and other crucial related information. Looking at the INFO messages for a given service category should tell you exactly what state the service is in.
# DEBUG - Use the DEBUG level priority for log messages that convey extra information regarding life-cycle events. Developer or in depth information required for support is the basis for this priority. The important point is that when the DEBUG level priority is enabled, the JBoss server log should not grow proportionally with the number of server requests. Looking at the DEBUG and INFO messages for a given service category should tell you exactly what state the service is in, as well as what server resources it is using: ports, interfaces, log files, etc.
# TRACE - Use TRACE the level priority for log messages that are directly associated with activity that corresponds requests. Further, such messages should not be submitted to a Logger unless the Logger category priority threshold indicates that the message will be rendered. Use the Logger.isTraceEnabled() method to determine if the category priority threshold is enabled. The point of the TRACE priority is to allow for deep probing of the JBoss server behavior when necessary. When the TRACE level priority is enabled, you can expect the number of messages in the JBoss server log to grow at least a x N, where N is the number of requests received by the server, a some constant. The server log may well grow as power of N depending on the request-handling layer being traced. 

# #log.msg("HELLO")
# #log.msg("HELLO INFO", level = logging.INFO)
# #log.msg("HELLO ERROR", level = logging.ERROR)
# #log.msg("HELLO DEBUG", level = logging.DEBUG)
# logger.debug("HELLO DEBUG 2")
# try:
#    x = 1/0
# except:
#    logger.error()
#    #twisted.python.log.err()
# #   except Exception, e:
# #      logger.error(e)

