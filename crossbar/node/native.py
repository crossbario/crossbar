#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.twisted.websocket import WampWebSocketClientFactory, \
    WampWebSocketClientProtocol

from twisted.internet.error import ProcessDone, ProcessTerminated
from twisted.internet.error import ConnectionDone

from txaio import make_logger

from crossbar._util import hltype

__all__ = ('create_native_worker_client_factory', )


class NativeWorkerClientProtocol(WampWebSocketClientProtocol):

    log = make_logger()

    def connectionMade(self):
        WampWebSocketClientProtocol.connectionMade(self)
        self._pid = self.transport.pid
        self.factory.proto = self

        # native workers are implicitly trusted
        self._authid = 'crossbar.process.{}'.format(self._pid)
        self._authrole = self.factory._authrole

        # the worker is actively spawned by the node controller,
        # and we talk over the pipes that were create during
        # process creation. this established implicit trust.
        self._authmethod = 'trusted'

        # the trust is established implicitly by the way the
        # the client (worker) is created
        self._authprovider = 'programcode'

    def connectionLost(self, reason):
        if isinstance(reason.value, ConnectionDone):
            self.log.info("Native worker connection closed cleanly.")
        else:
            self.log.warn("Native worker connection closed uncleanly: {reason}", reason=reason.value)

        WampWebSocketClientProtocol.connectionLost(self, reason)
        self.factory.proto = None

        if isinstance(reason.value, ProcessTerminated):
            if not self.factory._on_ready.called:
                # the worker was never ready in the first place ..
                self.factory._on_ready.errback(reason)
            else:
                # the worker _did_ run (was ready before), but now exited with error
                if not self.factory._on_exit.called:
                    self.factory._on_exit.errback(reason)
                else:
                    self.log.error("unhandled code path (1) in WorkerClientProtocol.connectionLost: {reason}",
                                   reason=reason.value)
        elif isinstance(reason.value, (ProcessDone, ConnectionDone)):
            # the worker exited cleanly
            if not self.factory._on_exit.called:
                self.factory._on_exit.callback(None)
            else:
                self.log.error("unhandled code path (2) in WorkerClientProtocol.connectionLost: {reason}",
                               reason=reason.value)
        else:
            # should not arrive here
            self.log.error("unhandled code path (3) in WorkerClientProtocol.connectionLost: {reason}",
                           reason=reason.value)


class NativeWorkerClientFactory(WampWebSocketClientFactory):

    log = make_logger()

    def __init__(self, *args, **kwargs):
        self.log.debug('{func}(*args={_args}, **kwargs={_kwargs})',
                       _args=args,
                       _kwargs=kwargs,
                       func=hltype(NativeWorkerClientFactory.__init__))
        self._authrole = kwargs.pop('authrole')
        WampWebSocketClientFactory.__init__(self, *args, **kwargs)
        self.proto = None

    def buildProtocol(self, addr):
        self.proto = NativeWorkerClientProtocol()
        self.proto.factory = self
        return self.proto

    def stopFactory(self):
        WampWebSocketClientFactory.stopFactory(self)
        if self.proto:
            self.proto.close()
            # self.proto.transport.loseConnection()


def create_native_worker_client_factory(router_session_factory, authrole, on_ready, on_exit):
    """
    Create a transport factory for talking to native workers.

    The node controller talks WAMP-WebSocket-over-STDIO with spawned (native) workers.

    The node controller runs a client transport factory, and the native worker
    runs a server transport factory. This is a little non-intuitive, but just the
    way that Twisted works when using STDIO transports.

    :param router_session_factory: Router session factory to attach to.
    :type router_session_factory: :class:`crossbar.router.session.RouterSessionFactory`
    """
    factory = NativeWorkerClientFactory(router_session_factory, 'ws://localhost', authrole=authrole)

    # we need to increase the opening handshake timeout in particular, since starting up a worker
    # on PyPy will take a little (due to JITting)
    factory.setProtocolOptions(failByDrop=False, openHandshakeTimeout=90, closeHandshakeTimeout=5)

    # on_ready is resolved in crossbar/node/process.py:on_worker_ready around 175
    # after crossbar.node.<ID>.on_worker_ready is published to (in the controller session)
    # that happens in crossbar/worker/worker.py:publish_ready which itself happens when
    # the native worker joins the realm (part of onJoin)
    factory._on_ready = on_ready
    factory._on_exit = on_exit

    return factory
