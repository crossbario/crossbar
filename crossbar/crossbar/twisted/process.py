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
from collections import deque

from twisted.python import util
from twisted.python import log
from twisted.python.log import FileLogObserver, textFromEventDict

from twisted.internet.endpoints import _WrapIProtocol, ProcessEndpoint
from twisted.internet.address import _ProcessAddress
from twisted.internet import defer



class _CustomWrapIProtocol(_WrapIProtocol):
   """
   Wraps an IProtocol into an IProcessProtocol which logs `stderr` in
   a format that includes a settable name and the PID of the process
   from which we receive.
   """

   def childDataReceived(self, childFD, data):
      if childFD == 2:
         for msg in data.split('\n'):
            msg = msg.strip()
            if msg != "":
               if self._log is not None:
                  self._log.append(msg)
                  if self._keeplog > 0 and len(self._log) > self._keeplog:
                     self._log.popleft()
               name = self._name or "Child"
               log.msg(msg, system = "{:<10} {:>6}".format(name, self.transport.pid), override_system = True)
      else:
         _WrapIProtocol.childDataReceived(self, childFD, data)



class CustomProcessEndpoint(ProcessEndpoint):
   """
   A custom process endpoint that supports advanced log features.

   :see: http://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.ProcessEndpoint.html
   """

   def __init__(self, *args, **kwargs):
      """
      Ctor.

      :param name: The log system name to use for logging messages
                   received from process child over stderr.
      :type name: str
      :param keeplog: If not `None`, buffer log message received to be later
                      retrieved via getlog(). If `0`, keep infinite log internally.
                      If `> 0`, keep at most such many log entries in buffer.
      :type keeplog: int or None
      """
      self._name = kwargs.pop('name', None)
      self._keeplog = kwargs.pop('keeplog', None)

      if self._keeplog is not None:
         self._log = deque()
      else:
         self._log = None

      ProcessEndpoint.__init__(self, *args, **kwargs)


   def getlog(self):
      """
      Get buffered log.

      :returns: list -- Buffered log.
      """
      if self._log:
         return list(self._log)
      else:
         return []


   def connect(self, protocolFactory):
      """
      See base class ctor.
      """
      proto = protocolFactory.buildProtocol(_ProcessAddress())
      try:
         wrapped = _CustomWrapIProtocol(proto, self._executable, self._errFlag)
         wrapped._name = self._name
         wrapped._log = self._log
         wrapped._keeplog = self._keeplog
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

   def __init__(self, f, system = None, override = True):
      FileLogObserver.__init__(self, f)
      if system:
         self._system = system
      else:
         self._system = "Process {}".format(os.getpid())
      self._override = override


   def emit(self, eventDict):
      if 'system' in eventDict and 'override_system' in eventDict and eventDict['override_system']:
         pass
      else:
         if self._override or (not 'system' in eventDict) or eventDict['system'] == "-":
            eventDict['system'] = self._system
      FileLogObserver.emit(self, eventDict)
