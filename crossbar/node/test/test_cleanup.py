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
        self.assertTrue(calls[0][1] == ('TERM',))

        # skip ahead until our KILL. we loop because we only run one
        # timed-out thing on each advance maybe? Anyway it runs
        # timeout() only twice if I advance(30) here instead...
        for x in range(30):
            reactor.advance(1)

        calls = self.worker.proto.transport.method_calls
        self.assertTrue(calls[1][0] == "signalProcess")
        self.assertTrue(calls[1][1] == ("KILL",))
