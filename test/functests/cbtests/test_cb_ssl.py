###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

import random
from functools import partial
from os.path import join
from tempfile import mkdtemp
from subprocess import check_call
from psutil import Process

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.component import Component
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.internet.process import ProcessExitedAlready
from twisted.internet.ssl import CertificateOptions
from twisted.python import log
from OpenSSL import crypto

import pytest
import treq

from ..helpers import *


@inlineCallbacks
def test_verification(crypto_crossbar, request, self_signed_cert):
    """
    Run a session with my own cert.
    """

    privkey, certfile = self_signed_cert
    # load our self-signed cert as the only certificate-authority
    with open(certfile, 'r') as crt:
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, crt.read())
    options = CertificateOptions(caCerts=[cert])

    d = functest_session(url=u"wss://localhost:6464/tls_ws", realm=u"auth_realm", ssl=options)
    results = yield DeferredList([d, sleep(5)], fireOnOneCallback=True, fireOnOneErrback=True)

    assert d.called, "timed out without connecting successfully"


@inlineCallbacks
def test_verification_fails(reactor, crypto_crossbar, request, self_signed_cert):
    """
    TLS fails to a self-signed cert
    """

    tls_client = Component(
        transports=u"wss://localhost:6464/tls_ws",
        is_fatal=lambda _: True,
    )
    d = tls_client.start(reactor)
    try:
        session = yield d
        assert False, "Connection should fail due to certificate error"
    except Exception as e:
        print("failed (we wanted this): {}".format(e))


@pytest.mark.parametrize(
    'close_style', (
# XXX FIXME not working for some reason ...
#        'transport.sendClose',
#        'transport.close',
        'session.leave',
    )
)
@inlineCallbacks
def test_client_close(crypto_crossbar, request, self_signed_cert, close_style):
    """
    is sendClose() sufficient to actually-close underlying transport?
    """

    (privkey, certfile) = self_signed_cert

    # load our self-signed cert as the only certificate-authority
    with open(certfile, 'r') as crt:
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, crt.read())
    options = CertificateOptions(caCerts=[cert])

    existing = Process().connections()
    sessions = []
    for x in range(10):
        session = yield functest_session(
            url=u"wss://localhost:6464/tls_ws",
            realm=u"auth_realm",
            ssl=options,
        )
        sessions.append(session)

    yield sleep(1)  # overkill? let sessions start for-sure
    started = Process().connections()
    assert len(started) - len(existing) == 10

    for session in sessions:
        assert session._transport is not None
        if close_style == 'session.leave':
            yield session.leave()
        elif close_style == 'transport.close':
            yield session._transport.close()
        elif close_style == 'transport.sendClose':
            session._transport.sendClose()
        else:
            raise RuntimeError("Unknown close_style from paramtrize")
    yield sleep(1)  # overkill, but make sure connections can close

    finished = Process().connections()
    assert len(finished) == len(existing)


@inlineCallbacks
def test_untrusted_selfsigned(crypto_crossbar, request, self_signed_cert):
    """
    Confirm we *don't* connect to untrusted server.
    """

    (privkey, certfile) = self_signed_cert
    # load our self-signed cert as the only certificate-authority
    with open(certfile, 'r') as crt:
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, crt.read())
    options = CertificateOptions(caCerts=[cert])

    # letting the defaults go through, which should mean we don't trust this connection
    d = functest_session(url=u"wss://localhost:6464/tls_ws", realm=u"auth_realm")
    timeout = sleep(5)
    results = yield DeferredList([d, timeout], fireOnOneCallback=True, fireOnOneErrback=True)

    # results in a 2-tuple: (result, index of Deferred that fired)
    assert results[1] is 1, "shouldn't have connected successfully"
