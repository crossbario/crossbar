#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
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

from autobahn.twisted.websocket import WampWebSocketClientFactory, \
    WampWebSocketClientProtocol

from twisted.internet.error import ProcessDone, ProcessTerminated
from twisted.internet.error import ConnectionDone

from txaio import make_logger

__all__ = ('create_native_worker_client_factory',)


class NativeWorkerClientProtocol(WampWebSocketClientProtocol):

    log = make_logger()

    def connectionMade(self):
        WampWebSocketClientProtocol.connectionMade(self)
        self._pid = self.transport.pid
        self.factory.proto = self

        # native workers are implicitly trusted
        self._authid = u'crossbar.process.{}'.format(self._pid)
        self._authrole = self.factory._authrole

        # the worker is actively spawned by the node controller,
        # and we talk over the pipes that were create during
        # process creation. this established implicit trust.
        self._authmethod = u'trusted'

        # the trust is established implicitly by the way the
        # the client (worker) is created
        self._authprovider = u'programcode'

        # FIXME / CHECKME
        self._cbtid = None
        self._transport_info = None

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
                    self.log.error("unhandled code path (1) in WorkerClientProtocol.connectionLost: {reason}", reason=reason.value)
        elif isinstance(reason.value, (ProcessDone, ConnectionDone)):
            # the worker exited cleanly
            if not self.factory._on_exit.called:
                self.factory._on_exit.callback(None)
            else:
                self.log.error("unhandled code path (2) in WorkerClientProtocol.connectionLost: {reason}", reason=reason.value)
        else:
            # should not arrive here
            self.log.error("unhandled code path (3) in WorkerClientProtocol.connectionLost: {reason}", reason=reason.value)


class NativeWorkerClientFactory(WampWebSocketClientFactory):

    log = make_logger()

    def __init__(self, *args, **kwargs):
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
    :type router_session_factory: obj
    """
    factory = NativeWorkerClientFactory(router_session_factory, u'ws://localhost', authrole=authrole)

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
