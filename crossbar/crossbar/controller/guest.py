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


from __future__ import absolute_import

__all__ = ['create_guest_worker_client_factory']

from twisted.python import log
from twisted.internet import protocol
from twisted.internet.error import ProcessDone, \
                                   ProcessTerminated, \
                                   ConnectionDone, \
                                   ConnectionClosed, \
                                   ConnectionLost, \
                                   ConnectionAborted



class GuestClientProtocol(protocol.ProcessProtocol):

   def __init__(self):
      self._pid = None
      self._name = None

   def _log(self, data):
      for msg in data.split('\n'):
         msg = msg.strip()
         if msg != "":
            log.msg(msg, system = "{:<10} {:>6}".format(self._name, self._pid))

   def connectionMade(self):
      print "guest connectionMade"
      config = self.factory._config

      if 'stdout' in config and config['stdout'] == 'close':
         self.transport.closeStdout()

      if 'stderr' in config and config['stderr'] == 'close':
         self.transport.closeStderr()

      if 'stdin' in config:
         if config['stdin'] == 'close':
            self.transport.closeStdin()
         else:
            if config['stdin']['type'] == 'json':
               self.transport.write(json.dumps(config['stdin']['value']))
            elif config['stdin']['type'] == 'msgpack':
               pass ## FIXME
            else:
               raise Exception("logic error")

            if config['stdin'].get('close', True):
               self.transport.closeStdin()

   def outReceived(self, data):
      config = self.factory._config
      if config.get('stdout', None) == 'log':
         self._log(data)

   def errReceived(self, data):
      config = self.factory._config
      if config.get('stderr', None) == 'log':
         self._log(data)

   def inConnectionLost(self):
      pass

   def outConnectionLost(self):
      pass

   def errConnectionLost(self):
      pass

   def processExited(self, reason):
      print "*"*10, "processExited", reason

   def processEnded(self, reason):
      print "*"*10, "processEnded", reason
      try:
         if isinstance(reason.value,  ProcessDone):
            #log.msg("Guest {}: Ended cleanly.".format(self._pid))
            self.factory._on_exit.callback(None)
         elif isinstance(reason.value, ProcessTerminated):
            #log.msg("Guest {}: Ended with error {}".format(self._pid, reason.value.exitCode))
#            self.factory._on_exit.errback(reason.value.exitCode)
            self.factory._on_exit.errback(reason)
         else:
            ## should not arrive here
            pass
      except Exception as e:
         print "XXXX", e



class GuestClientFactory(protocol.Factory):

   def buildProtocol(self, addr):
      self.proto = GuestClientProtocol()
      self.proto.factory = self
      return self.proto



def create_guest_worker_client_factory(config, on_ready, on_exit):
   factory = GuestClientFactory()
   factory._config = config
   factory._on_ready = on_ready
   factory._on_exit = on_exit
   return factory
