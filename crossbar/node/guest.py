#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import json

from twisted.internet import protocol
from twisted.internet.error import ProcessDone, ProcessTerminated, ProcessExitedAlready
from twisted.internet.error import ConnectionDone

from txaio import make_logger

__all__ = ('create_guest_worker_client_factory', )


class GuestWorkerClientProtocol(protocol.Protocol):

    log = make_logger()

    def __init__(self, config):
        self.config = config

    def connectionMade(self):
        # `self.transport` is now a provider of `twisted.internet.interfaces.IProcessTransport`
        # see: http://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IProcessTransport.html

        options = self.config.get('options', {})

        self.log.debug("GuestWorkerClientProtocol.connectionMade")

        if 'stdout' in options and options['stdout'] == 'close':
            self.transport.closeStdout()
            self.log.debug("GuestWorkerClientProtocol: stdout to guest closed")

        if 'stderr' in options and options['stderr'] == 'close':
            self.transport.closeStderr()
            self.log.debug("GuestWorkerClientProtocol: stderr to guest closed")

        if 'stdin' in options:
            if options['stdin'] == 'close':
                self.transport.closeStdin()
                self.log.debug("GuestWorkerClientProtocol: stdin to guest closed")
            else:
                if options['stdin']['type'] == 'json':
                    self.transport.write(json.dumps(options['stdin']['value'], ensure_ascii=False).encode('utf8'))
                    self.log.debug("GuestWorkerClientProtocol: JSON value written to stdin on guest")

                else:
                    raise Exception("logic error")

                if options['stdin'].get('close', True):
                    self.transport.closeStdin()
                    self.log.debug("GuestWorkerClientProtocol: stdin to guest closed")

        self.factory._on_ready.callback(self)

    def connectionLost(self, reason):
        self.log.debug("GuestWorkerClientProtocol.connectionLost: {reason}", reason=reason)
        try:
            if isinstance(reason.value, (ProcessDone, ConnectionDone)):
                self.log.debug("GuestWorkerClientProtocol: guest ended cleanly")
                self.factory._on_exit.callback(None)

            elif isinstance(reason.value, ProcessTerminated):
                self.log.debug("GuestWorkerClientProtocol: guest ended with error {code}", code=reason.value.exitCode)
                self.factory._on_exit.errback(reason)

            else:
                # get this when subprocess has exited early; should we just log error?
                # should not arrive here
                self.log.error(
                    "GuestWorkerClientProtocol: INTERNAL ERROR - should not arrive here - {reason}",
                    reason=reason,
                )

        except Exception:
            self.log.failure("GuestWorkerClientProtocol: INTERNAL ERROR - {log_failure}")

    def signal(self, sig='TERM'):
        assert (sig in ['KILL', 'TERM', 'INT'])
        try:
            self.transport.signalProcess(sig)
        except ProcessExitedAlready:
            pass
        except OSError:
            self.log.failure(None)


class GuestWorkerClientFactory(protocol.Factory):
    def __init__(self, config, on_ready, on_exit):
        self.proto = None
        self._config = config
        self._on_ready = on_ready
        self._on_exit = on_exit

    def buildProtocol(self, addr):
        self.proto = GuestWorkerClientProtocol(self._config)
        self.proto.factory = self
        return self.proto

    def signal(self, sig='TERM'):
        assert (sig in ['KILL', 'TERM', 'INT'])
        if self.proto:
            self.proto.signal(sig)


def create_guest_worker_client_factory(config, on_ready, on_exit):
    factory = GuestWorkerClientFactory(config, on_ready, on_exit)
    return factory
