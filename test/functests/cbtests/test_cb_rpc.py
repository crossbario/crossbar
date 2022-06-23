###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import
from contextlib import contextmanager

from autobahn.wamp import types
from autobahn.wamp import exception
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.python import log

import pytest

 # do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import *

# XXX move to a utils or something if this works out

@contextmanager
def registration(session, callback, uri):
    """
    Creates a temporary registration that is cleaned up by removing it
    from the session. Returns a Deferred that must be waited for (the
    Deferred returns the registration object).
    """
    d = session.register(callback, uri)
    registers = []  # because we can't closure around "plain" local

    def registered(reg):
        registers.append(reg)
        return reg
    d.addCallback(registered)
    # note this will return the *Deferred* to the caller; we can't be
    # @inlineCallbacks as we're already @contextmanager (which uses
    # yield itself)
    yield d

    # cleanup
    if len(registers) != 1:
        print("Expected 1 register not {}.".format(len(registers)))
    for reg in registers:
        reg.unregister()


@inlineCallbacks
def test_single_simple_registration(crossbar):
    '''
    One session registers, one calls it.
    '''
    # setup
    caller_session = yield functest_session()
    callee_session = yield functest_session(debug=False)

    rpc_called_d = Deferred()
# XXX commented code is without the contextmanager; "explicit better"
# probably favours the try..finally.
#    reg = yield callee_session.register(rpc_called_d.callback, "test_rpc")
#    try:

    with registration(callee_session, rpc_called_d.callback, u"test_rpc") as d:
        reg = yield d
        assert not rpc_called_d.called

        # execute
        yield caller_session.call(u"test_rpc", "foo")

        # test
        yield wait_for(rpc_called_d, 1, "waiting for RPC call")
        assert rpc_called_d.called, "Failed to get RPC call"
        assert rpc_called_d.result == "foo"

#    finally:
#        reg.unregister()


@inlineCallbacks
def test_single_double_registration(crossbar):
    '''
    error when two things register for same URI
    '''
    # setup
    session0 = yield functest_session()
    session1 = yield functest_session()

    rpc_called_d = Deferred()
    with registration(session0, rpc_called_d.callback, u"double_rpc") as d0:
        reg0 = yield d0
        assert not rpc_called_d.called

        # execute
        with registration(session1, rpc_called_d.callback, u"double_rpc") as d1:
            try:
                reg1 = yield d1
                assert "Should have gotten error"

            except exception.ApplicationError as e:
                assert e.error == 'wamp.error.procedure_already_exists'


@inlineCallbacks
def test_unregistered_method(crossbar):
    '''
    error if unregistered method called
    '''
    # setup
    session = yield functest_session()
    timeout = sleep(5)

    try:
        test_rpc = session.call(u"test_rpc", "foo")
        res = yield DeferredList([test_rpc, timeout], fireOnOneErrback=True, fireOnOneCallback=True)
        assert res[0][0] == False, "Should have gotten error."

    except FirstError as e:
        real_e = e.subFailure.value
        print(real_e)


@inlineCallbacks
def test_decorator_multi_register(crossbar):
    """
    subscribe with a class using decorators, multiple times
    """
    # setup
    foo_called = Deferred()
    bar_called = Deferred()

    from autobahn import wamp
    class TestSession(HelperSession):

        @wamp.register(u"test.foo")
        def foo(self, data):
            print("FOO:", data)
            foo_called.callback(data)

        @wamp.register(u"test.bar")
        def bar(self, data):
            print("BAR:", data)
            bar_called.callback(data)

        @inlineCallbacks
        def onJoin(self, details):
            HelperSession.onJoin(self, details)
            yield self.register(self)

    reg_session = yield functest_session(session_factory=TestSession)
    call_session = yield functest_session()

    # execute
    d0 = call_session.call(u"test.foo", "some data")
    d1 = call_session.call(u"test.bar", "different data")
    timeout = sleep(5)

    try:
        test_results = DeferredList([d0, d1, foo_called, bar_called], fireOnOneErrback=True)
        res = yield DeferredList([test_results, timeout], fireOnOneCallback=True, fireOnOneErrback=True)
    except Exception as e:
        print("ERROR", e)
        raise

    yield reg_session.leave()
    yield call_session.leave()

    assert not timeout.called, "timed out"
    assert foo_called.called, "test.foo should have been called"
    assert bar_called.called, "test.bar should have been called"


@inlineCallbacks
def test_decorator_redundant_register(crossbar):
    """
    register two methods to same endpoint in same session
    """
    pytest.skip("needs patch in autobahn")
    # setup
    died = Deferred()
    from autobahn import wamp
    class TestSession(HelperSession):
        @wamp.register(u"decorator.foo")
        def foo(self, data):
            print("FOO:", data)

        @wamp.register(u"decorator.foo")  # note: same endpoint as above
        def bar(self, data):
            print("BAR:", data)

        @inlineCallbacks
        def onJoin(self, details):
            HelperSession.onJoin(self, details)
            try:
                results = yield self.register(self)
                print("KERBLING!", results)
                for x in results:
                    print(x)
                died.callback(None)
            except Exception as e:
                died.callback("it worked")

    reg_session = yield functest_session(session_factory=TestSession)
    x = yield died
    assert x is not None, "Session should have gotten exception in onJoin"


@inlineCallbacks
def test_concurrency_errors(crossbar):
    """
    a returned error should reduce outstanding concurrency counter

    see: https://github.com/crossbario/crossbar/issues/1105
    """

    # what we do here is register one function with concurrency=2 that
    # will report errors on the first two invocations -- so our third
    # invocation should work fine.
    session = yield functest_session()

    def a_thing(*args, **kw):
        print("a thing {} {}".format(args, kw))
        if len(a_thing.errors) and a_thing.errors.pop():
            raise RuntimeError("a thing went wrong")
    a_thing.errors = [True, True]

    yield session.register(
        a_thing, u'foo.method',
        options=types.RegisterOptions(concurrency=2),
    )

    errors = []
    results = []
    try:
        res0 = yield session.call(u'foo.method')
        results.append(res0)
    except Exception as e:
        errors.append(e)

    try:
        res1 = yield session.call(u'foo.method')
        results.append(res1)
    except Exception as e:
        errors.append(e)

    try:
        res2 = yield session.call(u'foo.method')
        results.append(res2)
    except Exception as e:
        errors.append(e)

    print("results: {}".format(results))
    print(" errors: {}".format(errors))
    assert len(errors) == 2
    for err in errors:
        assert "a thing went wrong" in str(err)

    assert len(results) == 1
    assert results == [None]


@inlineCallbacks
def test_wrong_args(crossbar):
    """
    if we call a method with incorrect number of args, an error should
    be returned (not, e.g., the connection dropped)

    see: https://github.com/crossbario/autobahn-python/issues/1122
    """

    session = yield functest_session()

    def takes_two_args(arg0, arg1):
        return 42

    yield session.register(
        takes_two_args, u'takes_two_args',
    )

    # this one should work fine
    yield session.call(u'takes_two_args', 'one', 'two')

    # this one should return an ApplicationError
    try:
        yield session.call(u'takes_two_args')
        assert False, "should get ApplicationError"
    except exception.ApplicationError as e:
        assert "missing 2 required positional arguments" in str(e)
    except:
        assert False, "shouldn't get other weird exceptions"
