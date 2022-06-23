#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.internet.endpoints import _WrapIProtocol, ProcessEndpoint
from twisted.internet.address import _ProcessAddress
from twisted.internet import defer
from twisted.python.runtime import platform

__all__ = ('WorkerProcessEndpoint', )

if platform.isWindows():
    # On Windows, we're only using FDs 0, 1, and 2.

    class _WorkerWrapIProtocol(_WrapIProtocol):  # type: ignore
        """
        Wraps an IProtocol into an IProcessProtocol which forwards data
        received on Worker._log_fds to WorkerProcess.log().
        """
        def childDataReceived(self, childFD, data):
            """
            Some data has come in from the process child. If it's one of our
            log FDs ([2]), log it. Otherwise, let _WrapIProtocol deal with it.
            """
            # track bytes received per child FD
            self._worker.track_stats(childFD, len(data))

            if childFD in self._worker._log_fds:
                self._worker.log(childFD, data)
            else:
                _WrapIProtocol.childDataReceived(self, childFD, data)

else:
    # On UNIX-likes, we're logging FD1/2, and using FD3 for our own
    # communication.

    class _WorkerWrapIProtocol(_WrapIProtocol):  # type: ignore
        """
        Wraps an IProtocol into an IProcessProtocol which forwards data
        received on Worker._log_fds to WorkerProcess.log().
        """
        def childDataReceived(self, childFD, data):
            """
            Some data has come in from the process child. If it's one of our
            log FDs ([1, 2]), log it. If it's on FD3, send it to the WAMP connection.
            Otherwise, let _WrapIProtocol deal with it.
            """
            # track bytes received per child FD
            self._worker.track_stats(childFD, len(data))

            if childFD in self._worker._log_fds:
                self._worker.log(childFD, data)
            elif childFD == 3:
                self.protocol.dataReceived(data)
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

            self._spawnProcess(wrapped, self._executable, self._args, self._env, self._path, self._uid, self._gid,
                               self._usePTY, self._childFDs)
        except:
            return defer.fail()
        else:
            return defer.succeed(proto)
