###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

from autobahn.wamp import types, exception
from autobahn.twisted.util import sleep
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.logger import globalLogPublisher

import pytest

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import *


@pytest.fixture(
    scope="function",
    params=[
        dict(ack=True, exclude=True),
        dict(ack=False, exclude=True),

        dict(ack=True, exclude=False),
        dict(ack=False, exclude=False),
    ]
)
def publish_options(request):
    p = request.param
    kwargs = dict()
    kwargs['acknowledge'] = p['ack']
    kwargs['exclude_me'] = p['exclude']
    return types.PublishOptions(**kwargs)


@inlineCallbacks
def test_two_session_pub_sub(crossbar, publish_options):
    '''
    A simple publish/subscribe test between two sessions.
    '''
    # setup
    pub_session = yield functest_session()
    sub_session = yield functest_session()

    pub_d = Deferred()
    sub = yield sub_session.subscribe(pub_d.callback, u"test_topic")
    try:
        assert not pub_d.called

        # execute
        yield pub_session.publish(
            u"test_topic", ("foo", "bar"),
            options=publish_options,
        )
        yield wait_for(pub_d, 1, "waiting for two-session publish callback")

        # test
        assert pub_d.called, "Failed to get publish callback"
        # we should have published our two args
        # NOTE: any sequence converted to list...
        assert pub_d.result == ["foo", "bar"]
    finally:
        yield sub.unsubscribe()


@inlineCallbacks
def test_authenticated_two_session_pub_sub(auth_crossbar):
    """
    authenticated publisher and subscriber
    """
    # setup
    pub_session = yield functest_auth_session()
    sub_session = yield functest_auth_session()

    pub_d = Deferred()
    sub = yield sub_session.subscribe(pub_d.callback, u"auth_topic")
    try:
        assert not pub_d.called

        # execute
        pub = yield pub_session.publish(
            u"auth_topic", ("foo", "bar"),
            options=types.PublishOptions(
                acknowledge=True,
                # XXX need a "legitimate" way to get session id?
                eligible=[sub_session._session_id],
            )
        )
        yield wait_for(pub_d, 5, "waiting for two-session publish callback")

        # test
        assert pub_d.called, "Failed to get publish callback"
        # we should have published our two args
        # NOTE: any sequence converted to list...
        assert pub_d.result == ["foo", "bar"]
    finally:
        yield sub.unsubscribe()


@inlineCallbacks
def test_three_session_pub_sub(crossbar, publish_options):
    '''
    Pub/sub with on publisher and two subscribers.
    '''
    # setup
    pub_session = yield functest_session()
    sub_session0 = yield functest_session()
    sub_session1 = yield functest_session()

    pub0_d = Deferred()
    pub1_d = Deferred()
    sub0 = yield sub_session0.subscribe(pub0_d.callback, u"test_topic")
    sub1 = yield sub_session1.subscribe(pub1_d.callback, u"test_topic")
    try:
        assert not pub0_d.called
        assert not pub1_d.called

        # execute
        yield pub_session.publish(
            u"test_topic", ("foo", "bar"),
            #options=types.PublishOptions(acknowledge=True)
            options=publish_options,
        )
        yield wait_for(pub0_d, 1, "waiting for publish0")
        yield wait_for(pub1_d, 1, "waiting for publish1")

        # test
        assert pub0_d.called, "Failed to get publish callback"
        assert pub1_d.called, "Failed to get publish callback"
        # NOTE: any sequence converted to list...
        assert pub0_d.result == ["foo", "bar"]
        assert pub1_d.result == ["foo", "bar"]
    finally:
        yield sub0.unsubscribe()
        yield sub1.unsubscribe()


@inlineCallbacks
def test_blacklist_publish_authid(auth_crossbar):
    '''
    One publisher, 3 subscribers and blacklisting
    '''
    # setup
    pub_session = yield functest_auth_session(authid=u'steve')
    sub_session0 = yield functest_auth_session(authid=u'alice')
    sub_session1 = yield functest_auth_session(authid=u'bob')
    sub_session2 = yield functest_auth_session(authid=u'carol')

    alice = Deferred()
    bob = Deferred()
    carol = Deferred()

    sub0 = yield sub_session0.subscribe(alice.callback, u"test_topic")
    sub1 = yield sub_session1.subscribe(bob.callback, u"test_topic")
    sub2 = yield sub_session2.subscribe(carol.callback, u"test_topic")
    try:
        # execute
        yield pub_session.publish(
            u"test_topic", "nothing",
            options=types.PublishOptions(
                exclude_authid=[u'alice']
            )
        )

        # we should have received two publishes: for bob and carol but
        # *not* alice
        yield wait_for(bob, 1, "waiting for publish0")
        yield wait_for(carol, 1, "waiting for publish1")

        assert not alice.called

    finally:
        yield sub0.unsubscribe()
        yield sub1.unsubscribe()
        yield sub2.unsubscribe()


@inlineCallbacks
def test_whitelist_publish_authid(auth_crossbar):
    '''
    One publisher, 3 subscribers and blacklisting
    '''
    # setup
    pub_session = yield functest_auth_session(authid=u'steve')
    sub_session0 = yield functest_auth_session(authid=u'alice')
    sub_session1 = yield functest_auth_session(authid=u'bob')
    sub_session2 = yield functest_auth_session(authid=u'carol')

    alice = Deferred()
    bob = Deferred()
    carol = Deferred()

    sub0 = yield sub_session0.subscribe(alice.callback, u"test_topic")
    sub1 = yield sub_session1.subscribe(bob.callback, u"test_topic")
    sub2 = yield sub_session2.subscribe(carol.callback, u"test_topic")
    try:
        # execute
        yield pub_session.publish(
            u"test_topic", "nothing",
            options=types.PublishOptions(
                eligible_authid=[u'alice', u'carol', u'eve']
            )
        )

        # alice, carol only should get the pub
        yield wait_for(alice, 1, "waiting for publish0")
        yield wait_for(carol, 1, "waiting for publish1")
        assert not bob.called

    finally:
        yield sub0.unsubscribe()
        yield sub1.unsubscribe()
        yield sub2.unsubscribe()


@inlineCallbacks
def test_blacklist_publish_authrole(auth_crossbar):
    '''
    One publisher, 3 subscribers and blacklisting
    '''
    # setup
    pub_session = yield functest_auth_session(authid=u'steve')
    sub_session0 = yield functest_auth_session(authid=u'alice')
    sub_session1 = yield functest_auth_session(authid=u'bob')
    sub_session2 = yield functest_auth_session(authid=u'carol')

    publishes = []
    got_pubs = [Deferred(), Deferred(), Deferred(), Deferred(), Deferred(), Deferred()]
    notify_pubs = [x for x in got_pubs]

    alice = Deferred()
    bob = Deferred()
    carol = Deferred()

    sub0 = yield sub_session0.subscribe(alice.callback, u"test_topic")
    sub1 = yield sub_session1.subscribe(bob.callback, u"test_topic")
    sub2 = yield sub_session2.subscribe(carol.callback, u"test_topic")
    try:
        # execute
        yield pub_session.publish(
            u"test_topic", "nothing",
            options=types.PublishOptions(
                exclude_authrole=[u'role1']
            )
        )

        # we should have received two publishes: for alice and bob but
        # *not* carol (who is in role1 instead of role0)
        yield wait_for(alice, 1, "waiting for publish0")
        yield wait_for(bob, 1, "waiting for publish1")

        assert not carol.called

    finally:
        yield sub0.unsubscribe()
        yield sub1.unsubscribe()
        yield sub2.unsubscribe()


@inlineCallbacks
def test_whitelist_publish_authrole(auth_crossbar):
    '''
    One publisher, 3 subscribers and blacklisting
    '''
    # setup
    pub_session = yield functest_auth_session(authid=u'steve')
    sub_session0 = yield functest_auth_session(authid=u'alice')
    sub_session1 = yield functest_auth_session(authid=u'bob')
    sub_session2 = yield functest_auth_session(authid=u'carol')

    publishes = []
    got_pubs = [Deferred(), Deferred(), Deferred(), Deferred(), Deferred(), Deferred()]
    notify_pubs = [x for x in got_pubs]

    alice = Deferred()
    bob = Deferred()
    carol = Deferred()

    sub0 = yield sub_session0.subscribe(alice.callback, u"test_topic")
    sub1 = yield sub_session1.subscribe(bob.callback, u"test_topic")
    sub2 = yield sub_session2.subscribe(carol.callback, u"test_topic")
    try:
        # execute
        yield pub_session.publish(
            u"test_topic", "nothing",
            options=types.PublishOptions(
                eligible_authrole=u'role1'
            )
        )

        # we should have received two publishes: for alice and bob but
        # *not* carol (who is in role1 instead of role0)
        yield wait_for(carol, 1, "waiting for publish0")
        yield sleep(0.1)  # give spurious alice, bob messages time to arrive
        assert not alice.called
        assert not bob.called

    finally:
        yield sub0.unsubscribe()
        yield sub1.unsubscribe()
        yield sub2.unsubscribe()


@inlineCallbacks
def test_subscription_handler_err(crossbar, request, publish_options):
    '''
    Ensure a RuntimeError from callback ends up in the logs.
    '''
    # setup
    pub_session = yield functest_session()
    sub_session = yield functest_session()
    def disconnect():
        # XXX why don't these return Deferreds? How do we know we've left?
        pub_session.leave()
        sub_session.leave()
    request.addfinalizer(disconnect)

    # this might be a little fragile, but what we're doing is raising
    # a known error-message from a callback (publish, in this case)
    # and ensuring we see the error in the logs.
    error_string = 'Test error message from publish callback.'
    def publish_callback(*args):
        raise RuntimeError(error_string)
    sub = yield sub_session.subscribe(publish_callback, u"test_topic")

    try:
        got_err_d = Deferred()
        def observer(event):
            if error_string in event.get('traceback', ''):
                got_err_d.callback(True)
        globalLogPublisher.addObserver(observer)
        def remove_observer():
            globalLogPublisher.removeObserver(observer)
        request.addfinalizer(remove_observer)

        # execute
        yield pub_session.publish(
            u"test_topic", "foo",
            options=publish_options
        )

        # wait up to 5 seconds for our log-message to appear
        yield wait_for(got_err_d, 5, "Timeout waiting for error message")
    finally:
        yield sub.unsubscribe()


@inlineCallbacks
def test_single_session_pub_sub(crossbar):
    '''
    Ensure we don't publish to our own session by default.
    '''
    # setup
    session = yield functest_session()
    pub_session = session
    sub_session = session

    pub_d = Deferred()
    sub = yield sub_session.subscribe(pub_d.callback, u"test_topic")

    try:
        # execute
        assert not pub_d.called
        yield pub_session.publish(
            u"test_topic", "foo",
            options=types.PublishOptions(acknowledge=True)
        )

        # test
        try:
            yield wait_for(pub_d, 1, "Expected this timeout")
            assert False, "Should have gotten an exception"
        except RuntimeError as e:
            pass
        assert not pub_d.called, "Shouldn't publish to ourselves"
    finally:
        yield sub.unsubscribe()


@inlineCallbacks
def test_single_session_pub_sub_to_self(crossbar):
    '''
    With exclude_me=False we should get our own publish
    '''
    # setup
    session = yield functest_session()
    pub_session = session
    sub_session = session

    pub_d = Deferred()
    sub = yield sub_session.subscribe(pub_d.callback, u"test_topic")

    try:
        # execute
        assert not pub_d.called
        yield pub_session.publish(
            u"test_topic", "foo",
            options=types.PublishOptions(acknowledge=True, exclude_me=False)
        )

        # test
        try:
            yield wait_for(pub_d, 1, "Expected this timeout")
        except RuntimeError as e:
            assert False, "Should have gotten a publish"
        assert pub_d.called, "Should publish to ourselves with exclude_me=False"

    finally:
        yield sub.unsubscribe()


@inlineCallbacks
def test_single_session_pub_sub_success(crossbar):
    """
    Override exclude_me so we publish to ourselves as well.

    Note: not paramterized over publish_options because we need to
    know the status of "exclude_me"
    """
    # setup
    session = yield functest_session()

    pub_d = Deferred()
    sub = yield session.subscribe(pub_d.callback, u"test_topic")
    try:
        assert not pub_d.called

        # execute
        yield session.publish(
            u"test_topic", "foo",
            options=types.PublishOptions(acknowledge=True, exclude_me=False)
        )

        # test
        yield wait_for(pub_d, 5, "Waiting for our publish callback")
        assert pub_d.called, "Should publish to ourselves with exclude_me=False"
        assert pub_d.result == "foo"
    finally:
        yield sub.unsubscribe()


@inlineCallbacks
def test_duplicate_subcription(crossbar, publish_options):
    '''
    Call subscribe() twice on the same session.
    '''
    # setup
    pub_session = yield functest_session()
    sub_session = yield functest_session()

    pub0_d = Deferred()
    pub1_d = Deferred()
    # two different callbacks on the same session and same topic
    # (possibly related to #335 in AutobahnPython repo?)
    sub0 = yield sub_session.subscribe(pub0_d.callback, u"test_topic")
    sub1 = yield sub_session.subscribe(pub1_d.callback, u"test_topic")
    try:
        assert not pub0_d.called
        assert not pub1_d.called

        # execute
        yield pub_session.publish(
            u"test_topic", 42,
            #options=types.PublishOptions(acknowledge=True)
            options=publish_options,
        )
        # looks like "last one wins" currently?
        yield wait_for(pub1_d, 1, "waiting for second subscriber")
        yield wait_for(pub0_d, 1, "waiting for first subscriber")

        # test
        assert pub0_d.called, "Failed to get publish callback"
        assert pub1_d.called, "Failed to get publish callback"
        assert pub0_d.result == 42
        assert pub1_d.result == 42
    finally:
        yield sub0.unsubscribe()
        yield sub1.unsubscribe()


def test_assumptions():
    from autobahn.wamp.message import _URI_PAT_LOOSE_NON_EMPTY
    assert _URI_PAT_LOOSE_NON_EMPTY.match(".") is None

# FIXME: this requires AB 19.7.2+ - it will throw InvalidUriError
# @inlineCallbacks
# def test_invalid_uri(crossbar):
#     """
#     publish to an invalid uri
#     """
#     # setup
#     # XXX add all_done= kwarg to start_session plz!
#     pub_session = yield functest_session(debug=False)
#     on_leave = Deferred()
#     pub_session.config.extra['all_done'] = on_leave

#     # execute
#     d0 = pub_session.publish(
#         u".", 42,  # invalid URI
#         options=types.PublishOptions(acknowledge=True),
#     )
#     d1 = sleep(10)
#
#     try:
#         yield DeferredList([d0, d1, on_leave], fireOnOneCallback=True, fireOnOneErrback=True)
#     except FirstError as e:
#         assert isinstance(e.subFailure.value, exception.ApplicationError)
#     else:
#         assert False, "should have gotten ProtocolError"

@inlineCallbacks
def test_internal_uri(crossbar):
    """
    publish to crossbar.* should be denied
    """
    # setup
    pub_session = yield functest_session()

    # execute
    d0 = pub_session.publish(
        u"wamp.awesome", "arg",
        options=types.PublishOptions(acknowledge=True),
    )
    d1 = sleep(5)


    try:
        res = yield DeferredList([d0, d1], fireOnOneCallback=True, fireOnOneErrback=True)
        assert False, "Should have gotten error"
    except FirstError as e:
        real_e = e.subFailure.value
        assert 'restricted topic' in str(real_e)

    assert not d1.called


@inlineCallbacks
def test_decorator_multi_subscribe(crossbar):
    """
    subscribe with a class using decorators, multiple times
    """
    # setup
    foo_pub = Deferred()
    bar_pub = Deferred()
    from autobahn import wamp
    class TestSession(HelperSession):

        @wamp.subscribe(u"test.foo")
        def foo(self, data):
            print("FOO:", data)
            foo_pub.callback(data)

        @wamp.subscribe(u"test.bar")
        def bar(self, data):
            print("BAR:", data)
            bar_pub.callback(data)

        def onJoin(self, details):
            HelperSession.onJoin(self, details)
            self.subscribe(self)

    sub_session = yield functest_session(session_factory=TestSession)
    pub_session = yield functest_session()

    # execute
    d0 = pub_session.publish(
        u"test.foo", "foo_arg",
        options=types.PublishOptions(acknowledge=True),
    )
    d1 = pub_session.publish(
        u"test.bar", "bar_arg",
        options=types.PublishOptions(acknowledge=True),
    )
    timeout = sleep(5)

    try:
        test_results = DeferredList([d0, d1, foo_pub, bar_pub], fireOnOneErrback=True)
        res = yield DeferredList([test_results, timeout], fireOnOneCallback=True, fireOnOneErrback=True)
    except Exception as e:
        print("ERROR", e)
        raise

    assert not timeout.called, "timed out"
    assert foo_pub.called, "test.foo should have been subscribed"
    assert bar_pub.called, "test.bar should have been subscribed"
