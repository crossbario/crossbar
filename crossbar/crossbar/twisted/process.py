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


import os

from twisted.python import util
from twisted.python import log
from twisted.python.log import FileLogObserver, textFromEventDict

from twisted.internet.endpoints import _WrapIProtocol, ProcessEndpoint
from twisted.internet.address import _ProcessAddress
from twisted.internet import defer



class _CustomWrapIProtocol(_WrapIProtocol):
   """
   Wraps an IProtocol into an IProcessProtocol which logs
   stderr in a format that includes a settable name and the PID
   of the process from which we receive.
   """

   def childDataReceived(self, childFD, data):
      if childFD == 2:
         for msg in data.split('\n'):
            msg = msg.strip()
            if msg != "":
               name = self._name or "Child"
               log.msg(msg, system = "{:<10} {:>6}".format(name, self.transport.pid))
      else:
         _WrapIProtocol.childDataReceived(self, childFD, data)



class CustomProcessEndpoint(ProcessEndpoint):
   """
   A custom process endpoint with a settable name which will be used for logging.
   """

   def __init__(self, *args, **kwargs):
      self._name = kwargs.pop('name', None)
      ProcessEndpoint.__init__(self, *args, **kwargs)

   def connect(self, protocolFactory):
      proto = protocolFactory.buildProtocol(_ProcessAddress())
      try:
         wrapped = _CustomWrapIProtocol(proto, self._executable, self._errFlag)
         wrapped._name = self._name
         self._spawnProcess(wrapped,
            self._executable, self._args, self._env, self._path, self._uid,
            self._gid, self._usePTY, self._childFDs)
      except:
         return defer.fail()
      else:
         return defer.succeed(proto)



class BareFormatFileLogObserver(FileLogObserver):
   """
   Log observer without any additional formatting (such as timestamps).
   """

   def emit(self, eventDict):
      text = textFromEventDict(eventDict)
      if text:
         util.untilConcludes(self.write, text + "\n")
         util.untilConcludes(self.flush)



class DefaultSystemFileLogObserver(FileLogObserver):
   """
   Log observer with default settable system.
   """

   def __init__(self, f, system = None):
      FileLogObserver.__init__(self, f)
      if system:
         self._system = system
      else:
         self._system = "Process {}".format(os.getpid())


   def emit(self, eventDict):
      if not 'system' in eventDict or eventDict['system'] == "-":
         eventDict['system'] = self._system
      FileLogObserver.emit(self, eventDict)
