###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from autobahn.wamp import types
from autobahn.wamp import auth
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.python import log
from os.path import join

import pytest

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import *

# enough authentication tests to at least provide coverage for all
# txaio.* usages inside crossbar/router/session


@inlineCallbacks
def test_wamp_cra_success(auth_crossbar):
    # setup
    d0 = sleep(5)
    d1 = functest_auth_session()
    (value, idx) = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True)
    assert idx != 0, "Shouldn't time out"
    assert d1.called, "Should have a session"
    session = yield d1
    assert session is value
    yield session.leave()


class AnonymousSession(AuthenticatedSession):
    def onConnect(self):
        self.join(u"auth_realm", authmethods=[u'anonymous'])


@inlineCallbacks
def test_anonymous_auth(auth_crossbar):
    # setup
    d0 = sleep(5)
    d1 = functest_auth_session(session_factory=AnonymousSession)
    (value, idx) = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True)
    assert idx != 0, "Shouldn't time out"
    assert d1.called, "Should have a session"
    session = yield d1
    assert session is value
    yield session.leave()


class TicketSession(AuthenticatedSession):
    def onConnect(self):
        self.done = Deferred()
        self.join(
            u"auth_realm",
            authid=u'foo',
            authmethods=[u'ticket', u'cookie'],
            authextra={u"foo": "quux"},
        )

    def onJoin(self, details):
        self.config.extra['running'].callback(self)
        try:
            cookie = self._transport.http_headers[u'set-cookie']
            cookie = cookie.split(';')[0]
        except KeyError as e:
            assert False, "No set-cookie header {}".format(e)
        self.done.callback(cookie)

    def onChallenge(self, challenge):
        assert challenge.method == u"ticket"
        return "seekr1t!!"

    def onLeave(self, reason):
        if not self.done.called:
            self.done.errback(self)


class CookieSession(ApplicationSession):
    def onConnect(self):
        self.join(
            u"auth_realm",
            authid=u'foo',
            authmethods=[u'cookie'],
        )

    def onJoin(self, details):
        # XXX i had spelled this "self.extra" before, but why isn't
        # *something* logging an error on this?
        if details.authmethod != u'ticket':
            self.config.extra[u'running'].errback(
                RuntimeError("Wrong authmethod {}".format(details.authmethod))
            )

        if details.authextra != dict(foo='quux'):
            self.config.extra[u'running'].errback(
                RuntimeError(
                    "authextra={}, not dict(foo='quux')".format(details.authextra)
                )
            )
        self.config.extra[u'running'].callback(self)

    def onChallenge(self, challenge):
        self.config.extra[u'running'].errback(
            RuntimeError("Shouldn't get a challenge")
        )


@inlineCallbacks
def _run_cookie_session(url, realm, cookie):
    """
    A helper that returns a Deferred that yields a fresh
    HelperSession running against the local test crossbar
    instance. "running" means onJoin was just called.

    Any extra kwargs are passed through to the ApplicationSession
    instance via the "confg.extra" dict.

    For more advanced test-cases, you can pass in the url, realm
    and/or the ApplicationSession subclass (or factory function) if
    you need control of those. The factory-method is passed the config
    object, a :class:`autobahn.wamp.types.ComponentConfig` instance.

    Note if you do this and aren't using HelperSession, you'll
    have to arrange for the Deferred passed in self.config.extra['running'] to
    have its callback or errback invoked.
    """
    running_d = Deferred()
    session_factory = CookieSession
    headers = {
        'cookie': cookie,
    }
    runner = ApplicationRunner(url, realm=realm, extra={u'running': running_d}, headers=headers)
    d = runner.run(session_factory, start_reactor=False)
    session = yield running_d
    returnValue(session)


@inlineCallbacks
def test_ticket_auth(auth_crossbar):
    # setup
    d0 = sleep(5)
    d1 = functest_auth_session(session_factory=TicketSession)
    (value, idx) = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True)
    assert idx != 0, "Shouldn't time out"
    assert d1.called, "Should have a session"
    session = yield d1
    cookie = yield session.done

    d0 = sleep(10)
    d1 = _run_cookie_session(u'ws://localhost:7575/test_wampcra', u'auth_realm', cookie)
    (value, idx) = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True)
    assert idx != 0, "Shouldn't time out (cookie)"


@inlineCallbacks
def test_wrong_password(auth_crossbar):
    """
    """
    # setup
    d0 = sleep(5)
    d1 = functest_auth_session(password=u"bogus")
    try:
        (value, idx) = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True, consumeErrors=True)
        assert False, "Should get exception from onLeave"
    except FirstError as e:
        real_e = e.subFailure.value
        assert isinstance(real_e, RuntimeError)
        assert "signature is invalid" in str(real_e)


@inlineCallbacks
def test_wrong_realm(auth_crossbar):
    """
    Connect with a non-existant realm.
    """
    # setup
    d0 = sleep(5)
    d1 = functest_auth_session(realm=u'auth_realmmmmmm')
    try:
        (value, idx) = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True, consumeErrors=True)
        assert False, "Should get exception from onLeave"
    except FirstError as e:
        real_e = e.subFailure.value
        assert isinstance(real_e, RuntimeError)
        assert 'auth_realmmmmmm' in str(real_e)


@inlineCallbacks
def _test_wrong_realm_but_auto_realm(crossbar):
    """
    Connect with a non-existant realm. However, the "crossbar" fixture
    includes configuration to turn on auto-realm creation, so this one
    *should* succeed, unlike above.
    """
    # setup
    d0 = sleep(5)
    d1 = functest_session(realm=u'realmmmmmm')
    (value, idx) = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True)
    assert not d0.called
    assert d1.called


class IncorrectChallengeSession(AuthenticatedSession):
    def onChallenge(self, challenge):
        return b'\x00' * 32


@inlineCallbacks
def test_bogus_challenge(auth_crossbar):
    """
    completely bogus response to challenge
    """
    # setup
    d0 = sleep(5)
    d1 = functest_auth_session(session_factory=IncorrectChallengeSession)
    try:
        (value, idx) = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True, consumeErrors=True)
    except Exception as e:
        # this will be a FirstError exception, since fireOnOneErrback
        # is True (see Twisted docs)
        assert(isinstance(e, FirstError))
        real_e = e.subFailure.value
        assert(isinstance(real_e, RuntimeError))
        assert('signature is invalid' in str(real_e))
