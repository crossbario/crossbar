from __future__ import print_function

import click
import attr
import sys

from collections import deque
from texttable import Texttable

from twisted.internet.protocol import Protocol, ClientFactory
from twisted.logger import globalLogBeginner, textFileLogObserver
from crossbar.adapter.mqtt.protocol import MQTTClientParser


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
@click.option("--host")
@click.option("--port")
def run(host, port):

    #globalLogBeginner.beginLoggingTo([textFileLogObserver(sys.stdout)])

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
        fmt_results.append((r.name,
                            "True" if r.success else "False", r.reason, r.transcript))

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
        self._buffer = b""
        self._waiting_for_nothing = None
        self._client = MQTTClientParser()

    def connectionMade(self):

        if self._record[0].send:
            self.transport.write(self._record.popleft().data)

    def dataReceived(self, data):
        self.factory._timer.reset(5)
        self._buffer = self._buffer + data

        self.factory.client_transcript.extend(self._client.data_received(data))

        if self._waiting_for_nothing:
            self.factory.reason = "Got unexpected data " + repr(self._buffer)
            self.factory.success = False
            self.factory.reactor.stop()
            return

        if len(self._record) > 0 and len(self._buffer) == len(self._record[0].data):
            reading = self._record.popleft()

            if self._buffer == reading.data:
                pass
            else:
                self.factory.success = False
                self.factory.reason = (self._buffer, reading.data)
                self.factory.reactor.stop()
                return

            self._buffer = b''

            if len(self._record) > 0:
                if self._record[0].send:
                    self.transport.write(self._record.popleft().data)

                # Then if we are supposed to wait...
                if isinstance(self._record[0], Frame) and self._record[0].send is False and self._record[0].data == b"":
                    def wait():
                        self._waiting_for_nothing = None
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
            self.reason = "Timeout (buffer was " + repr(p._buffer) + ", remaining assertions were " + repr(p._record) + ")"
            self.reactor.stop()

        self._timer = self.reactor.callLater(5, disconnect)
        return p


if __name__ == "__main__":
    run()
