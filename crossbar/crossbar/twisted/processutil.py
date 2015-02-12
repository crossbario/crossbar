#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

import os

from twisted.python import util
from twisted.python.log import FileLogObserver, textFromEventDict

from twisted.internet.endpoints import _WrapIProtocol, ProcessEndpoint
from twisted.internet.address import _ProcessAddress
from twisted.internet import defer

__all__ = ('WorkerProcessEndpoint', 'BareFormatFileLogObserver', 'DefaultSystemFileLogObserver')


class _WorkerWrapIProtocol(_WrapIProtocol):

    """
    Wraps an IProtocol into an IProcessProtocol which forwards data
    received on Worker._log_fds to WorkerProcess.log().
    """

    def childDataReceived(self, childFD, data):
        if childFD in self._worker._log_fds:
            self._worker.log(childFD, data)
        else:
            _WrapIProtocol.childDataReceived(self, childFD, data)


class WorkerProcessEndpoint(ProcessEndpoint):

    """
    A custom process endpoint for workers.

    :see: http://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.ProcessEndpoint.html
    """

    def __init__(self, *args, **kwargs):
        """
        Ctor.

        :param worker: The worker this endpoint is being used for.
        :type worker: instance of WorkerProcess
        """
        self._worker = kwargs.pop('worker')
        ProcessEndpoint.__init__(self, *args, **kwargs)

    def connect(self, protocolFactory):
        """
        See base class.
        """
        proto = protocolFactory.buildProtocol(_ProcessAddress())
        try:
            wrapped = _WorkerWrapIProtocol(proto, self._executable, self._errFlag)
            wrapped._worker = self._worker
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

    def __init__(self, f, system=None, override=True):
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
            if self._override or ('system' not in eventDict) or eventDict['system'] == "-":
                eventDict['system'] = self._system
        FileLogObserver.emit(self, eventDict)
