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

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks
from twisted.internet.process import ProcessExitedAlready
from twisted.python import log

import pytest

from ..helpers import *

# XXX cleanup: most of these tests don't; they should shut down
# container workers when done.


class PrefixCaller(object):
    """
    Put in util if helpful. Playing with a simple wrapper to
    automagically call-through to underlying RPCs based on prefix
    """
    def __init__(self, session, prefix):
        self._prefix = prefix
        self._session = session

    def __getattr__(self, attr):
        # got an un-found name, so try to make it a method-call by
        # returning an appropriate callable.
        return partial(
            self._session.call,
            self._prefix + '.' + attr,
        )


@inlineCallbacks
def test_container_start(crossbar, request):
    """
    start a component in container, via API
    """
    raise pytest.skip("Needs old-style management API to work")

    manage = yield functest_management_session(debug=False)

    node = PrefixCaller(manage, "crossbar.node.functestee")
    yield node.get_info()

    # XXX this seems to get called with details where caller=None; had
    # to fix some code in crossbar around this, but why is it None?
    container_id = "container{}".format(random.randint(1, 1000))
    yield node.start_container(container_id)

    def cleanup_container():
        pytest.blockon(node.stop_container(container_id))
    request.addfinalizer(cleanup_container)

    config = {
        "type": u"class",
        "classname": u"functests.components.EmptyComponent",
        "realm": u"functest_realm1",
        "transport": {
            "type": u"websocket",
            "id": u"testcase",
            "endpoint": {
                "type": u"tcp",
                "host": u"127.0.0.1",
                "port": 6565,
            },
            "url": u"ws://localhost:6565/ws"
        }
    }
    worker = PrefixCaller(manage, "crossbar.node.functestee.worker.{}".format(container_id))
    yield worker.start_container_component("component99", config)
    def cleanup():
        try:
            pytest.blockon(worker.stop_container_component("component99"))
        except:
           pass
    request.addfinalizer(cleanup)

    yield sleep(1)
    comps = yield worker.get_container_components()
    assert 'component99' in [c['id'] for c in comps]

    # now we try to "start" it again, to trigger an error
    try:
        yield worker.start_container_component("component99", config)
        assert False, "Should get error"
    except ApplicationError as e:
        assert 'already running' in e.message

    if True:
        # restart doesn't work properly yet; the "new" one is dying
        # before even joining the realm (I think)
        yield worker.restart_container_component("component99")
        yield sleep(1)
        comps = yield worker.get_container_components()
        assert 'component99' in [c['id'] for c in comps]

    x = yield worker.stop_container_component("component99")
    assert x['uptime'] >= 1.0
    comps = yield worker.get_container_components()
    assert 'component99' not in [c['id'] for c in comps]

    # give the connections a window to shut down cleanly in
    yield sleep(0.1)


@inlineCallbacks
def test_container_wrong_ids(crossbar, request):
    """
    give unknown IDs to a couple methods
    """
    raise pytest.skip("Needs old-style management API to work")

    manage = yield functest_management_session(debug=False)

    node = PrefixCaller(manage, "crossbar.node.functestee")

    x = yield node.start_container("container101")
    def cleanup_container():
        pytest.blockon(node.stop_container("container101"))
    request.addfinalizer(cleanup_container)

    worker = PrefixCaller(manage, "crossbar.node.functestee.worker.container101")

    # restart non-existing component
    try:
        x = yield worker.restart_container_component("should_fail")
        assert False, "Should get exception"
    except ApplicationError as e:
        assert 'no component with ID' in e.message

    # stop non-existing component (could maybe be separate test, but ...)
    try:
        x = yield worker.stop_container_component("should_fail")
        assert False, "Should get exception"
    except ApplicationError as e:
        assert 'no component with ID' in e.message


@inlineCallbacks
def test_container_invalid_config(crossbar, request):
    """
    invalid config is rejected
    """
    raise pytest.skip("Needs old-style management API to work")

    manage = yield functest_management_session(debug=False)

    node = PrefixCaller(manage, "crossbar.node.functestee")

    container_id = "container{}".format(random.randint(1, 1000))
    x = yield node.start_container(container_id)

    def cleanup_container():
        pytest.blockon(node.stop_container(container_id))
    request.addfinalizer(cleanup_container)

    worker = PrefixCaller(manage, "crossbar.node.functestee.worker.{}".format(container_id))

    # trivially-invalid config
    config = {}
    try:
        yield worker.start_container_component("component42", config)
    except ApplicationError as e:
        assert 'invalid' in e.message


@inlineCallbacks
def test_container_init_error(crossbar, request):
    """
    component fails to be instantiated
    """
    raise pytest.skip("Needs old-style management API to work")

    manage = yield functest_management_session(debug=False)

    node = PrefixCaller(manage, "crossbar.node.functestee")

    container_id = "container{}".format(random.randint(1, 1000))
    x = yield node.start_container(container_id)

    def cleanup_container():
        pytest.blockon(node.stop_container(container_id))
    request.addfinalizer(cleanup_container)

    worker = PrefixCaller(manage, "crossbar.node.functestee.worker.{}".format(container_id))

    config = {
        "type": u"class",
        "classname": u"functests.components.ErrorComponent",
        "realm": u"testee_realm1",
        "transport": {
            "type": u"websocket",
            "id": u"testcase",
            "endpoint": {
                "type": u"tcp",
                "host": u"127.0.0.1",
                "port": 6565,
            },
            "url": u"ws://localhost:6565/ws"
        }
    }

    start_d = Deferred()
    stop_d = Deferred()

    def started(info, options=None):
        start_d.callback(info)

    def stopped(info, options=None):
        stop_d.callback(info)

    yield manage.subscribe(
        started,
        'crossbar.node.functestee.worker.{}.container.on_component_start'.format(container_id)
    )
    yield manage.subscribe(
        stopped,
        'crossbar.node.functestee.worker.{}.container.on_component_stop'.format(container_id)
    )

    yield worker.start_container_component(
        "component1234", config,
    )
    # note: we don't get an error immediately, as we successfully
    # connect before the component is instantiated.

    # XXX would be nice to have a better way to know how long stuff takes to
    # start up on "our" platform...
    yield sleep(5)

    comps = yield worker.get_container_components()
    assert 'component1234' not in comps
    assert comps == []
    assert start_d.called
    assert stop_d.called
