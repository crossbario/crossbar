#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from mock import MagicMock

from twisted.trial import unittest
from twisted.internet.defer import Deferred
from twisted.internet import task

# WebSocket protocol gets used below, and the latter
# calls txaio.make_logger(). If we don't explicitly select
# the network framework before, we get an exception
# "To use txaio, you must first select a framework" from txaio
import txaio

txaio.use_twisted()  # noqa

from crossbar.node.node import NodeController


class CleanupHandler(unittest.TestCase):
    def setUp(self):
        self.transport = MagicMock()
        self.worker = MagicMock()
        self.worker.proto.transport = self.transport
        self.worker.pid = '42'
        self.worker.ready = Deferred()
        self.worker.exit = Deferred()

    def test_kill_after_term(self):
        reactor = task.Clock()
        NodeController._cleanup_worker(reactor, self.worker)

        # should have sent TERM now
        calls = self.worker.proto.transport.method_calls
        self.assertTrue(calls[0][0] == "signalProcess")
        self.assertTrue(calls[0][1] == ('TERM', ))

        # skip ahead until our KILL. we loop because we only run one
        # timed-out thing on each advance maybe? Anyway it runs
        # timeout() only twice if I advance(30) here instead...
        for x in range(30):
            reactor.advance(1)

        calls = self.worker.proto.transport.method_calls
        self.assertTrue(calls[1][0] == "signalProcess")
        self.assertTrue(calls[1][1] == ("KILL", ))
