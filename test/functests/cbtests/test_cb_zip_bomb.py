##############################################################################
#
#  Copyright (C) Tavendo GmbH. All rights reserved.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from autobahn.wamp import types
from autobahn.twisted.component import Component, run
from autobahn.twisted.util import sleep
from autobahn.websocket.compress import PerMessageDeflateOffer, \
    PerMessageDeflateResponse, \
    PerMessageDeflateResponseAccept
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.python import log
from os.path import join

import pytest

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import *
from ..helpers import _create_temp, _cleanup_crossbar



@inlineCallbacks
def test_deflate_lots(reactor, crossbar):
    """
    """
    # XXX turning on Deflate seems .. hard
    # XXX also, why do I have to specify max_... in at least 2 places?

    # The extensions offered to the server ..
    offers = [PerMessageDeflateOffer()]

    # Function to accept responses from the server ..
    def accept(response):
        if isinstance(response, PerMessageDeflateResponse):
            return PerMessageDeflateResponseAccept(response, max_message_size=1500)

    # we have two components here: one that has a limit on payloads
    # (component0) and one that doesn't (component1). component0 subscribes
    # and then component1 sends it one "small enough" and then one "too big"
    # message (the second should cause component0 to drop its connection).
    component0 = Component(
        transports=[
            {
                u"url": u"ws://localhost:6565/ws",
                u"options": {
                    u"max_frame_payload_size": 1500,
                    u"per_message_compression_offers": offers,
                    u"per_message_compression_accept": accept,
                }
            },
        ],
        realm=u"functest_realm1",
    )
    component1 = Component(
        transports=[
            {
                u"url": u"ws://localhost:6565/ws",
                u"options": {
                    u"per_message_compression_offers": offers,
                    u"per_message_compression_accept": accept,
                }
            },
        ],
        realm=u"functest_realm1",
    )

    listening = Deferred()  # component1 waits until component0 subscribes
    connection_dropped = Deferred()  # we want component0 to do this
    connections = [0]  # how many times component0 has connected

    @component0.on_join
    @inlineCallbacks
    def listen(session, details):
        connections[0] += 1
        if connections[0] == 2:
            print("comp0: re-connected!")
        elif connections[0] == 1:
            # we await (potentially) two messages; if we get the second, the
            # test should fail
            messages = [Deferred(), Deferred()]
            yield session.subscribe(lambda x: messages.pop(0).callback(x), u"foo")
            listening.callback(None)
            while len(messages):
                msg = yield messages[0]
                print("comp0: message: {}".format(msg))
        print("comp0: done listening")

    @component0.on_disconnect
    def gone(session, was_clean=False):
        print("comp0: session dropped".format(session, was_clean))
        connection_dropped.callback(session)

    @component1.on_join
    @inlineCallbacks
    def send(session, details):
        yield listening
        # this one should be small enough to go through
        yield session.publish(u"foo", u"a" * 20, options=types.PublishOptions(acknowledge=True))

        # this will definitely be over 1500 and should fail (due to the other
        # side's decoder dropping it because the payload is too big). We can't
        # get an error here because the router accepts it, but the other
        # *client* will reject...
        yield session.publish(u"foo", u"a" * 2000, options=types.PublishOptions(acknowledge=True))

    # fail-safe if the test doesn't fail for some other reason, it'll fail
    # after 15s
    timeout = sleep(15)

    done = DeferredList([
        component0.start(reactor),
        component1.start(reactor),
    ])
    yield DeferredList([timeout, done, connection_dropped], fireOnOneErrback=True, fireOnOneCallback=True)

    assert not timeout.called, "shouldn't time out"
    assert connection_dropped.called, "component0 should have dropped connection"
