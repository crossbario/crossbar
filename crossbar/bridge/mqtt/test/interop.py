#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""
Server interop tests, making sure Crossbar's MQTT adapter responds the same as
other MQTT servers.
"""

import click
import attr
import sys

from collections import deque
from texttable import Texttable

from twisted.internet.protocol import Protocol, ClientFactory
from crossbar.bridge.mqtt.protocol import MQTTClientParser


@attr.s
class Frame(object):
    send = attr.ib()
    data = attr.ib()


class ConnectionLoss(object):
    send = False
    data = b""


@attr.s
class Result(object):
    name = attr.ib()
    success = attr.ib()
    reason = attr.ib()
    transcript = attr.ib()


@click.command()
@click.option("--host", help='Host address to test.')
@click.option("--port", type=int, help='Post of the host to test.')
def run(host, port):

    port = int(port)

    from . import interop_tests
    test_names = [x for x in dir(interop_tests) if x.startswith("test_")]

    tests = [getattr(interop_tests, test_name) for test_name in test_names]

    results = []
    with click.progressbar(tests, label="Running interop tests...") as _tests:
        for test in _tests:
            results.append(test(host, port))

    fmt_results = []
    for r in results:
        fmt_results.append((r.name, "True" if r.success else "False", r.reason if r.reason else "", r.transcript))

    t = Texttable()
    t.set_cols_width([20, 10, 80, 60])
    rows = [["Name", "Successful", "Reason", "Client Transcript"]]
    rows.extend(fmt_results)
    t.add_rows(rows)
    print(t.draw(), file=sys.__stdout__)

    failures = []
    for x in results:
        if not x.success:
            failures.append(False)

    if failures:
        sys.exit(len(failures))
    sys.exit(0)


class ReplayProtocol(Protocol):
    def __init__(self, factory):
        self.factory = factory
        self._record = deque(self.factory.record)
        self._waiting_for_nothing = None
        self._client = MQTTClientParser()

    def connectionMade(self):

        if self._record[0].send:
            to_send = self._record.popleft()
            if isinstance(to_send.data, bytes):
                self.transport.write(to_send.data)
            else:
                self.transport.write(to_send.data.serialise())

    def dataReceived(self, data):
        self.factory._timer.reset(7)

        got_data = self._client.data_received(data)
        self.factory.client_transcript.extend(got_data)

        if self._waiting_for_nothing:
            if data == b"":
                got_data.append(b"")
                self._waiting_for_nothing = None
            else:
                self.factory.reason = "Got unexpected data " + repr(got_data)
                self.factory.success = False
                self.factory.reactor.stop()
                return

        if len(self._record) > 0 and got_data:
            for x in got_data:
                reading = self._record.popleft()

                if x == reading.data:
                    pass
                elif isinstance(reading.data, list) and x in reading.data:
                    reading.data.remove(x)
                else:
                    self.factory.success = False
                    self.factory.reason = (x, reading.data)
                    self.factory.reactor.stop()
                    return

                if len(self._record) > 0:
                    while len(self._record) > 0 and self._record[0].send:
                        to_send = self._record.popleft()
                        if isinstance(to_send.data, bytes):
                            self.transport.write(to_send.data)
                        else:
                            self.transport.write(to_send.data.serialise())

                if isinstance(reading.data, list):
                    if reading.data:
                        self._record.appendleft(reading)

                if len(self._record) > 0:

                    # Then if we are supposed to wait...
                    if isinstance(self._record[0],
                                  Frame) and self._record[0].send is False and self._record[0].data == b"":

                        def wait():
                            self.dataReceived(b"")

                        self._waiting_for_nothing = self.factory.reactor.callLater(2, wait)
                        return

    def connectionLost(self, reason):
        if self.factory.reactor.running:
            if self._record and isinstance(self._record[0], ConnectionLoss):
                self.factory.success = True
            else:
                self.factory.success = False
                self.factory.reason = "Premature disconnection"
            self.factory.reactor.stop()


@attr.s
class ReplayClientFactory(ClientFactory):
    reactor = attr.ib()
    record = attr.ib()
    success = attr.ib(default=None)
    reason = attr.ib(default=None)
    protocol = ReplayProtocol
    noisy = False

    def buildProtocol(self, addr):

        self.client_transcript = []

        p = self.protocol(self)

        def disconnect():
            self.reason = "Timeout (remaining assertions were " + repr(p._record) + ")"
            self.reactor.stop()

        self._timer = self.reactor.callLater(7, disconnect)
        return p


if __name__ == "__main__":
    run()
