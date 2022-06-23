#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import treq

from twisted.internet import reactor, defer
from twisted.internet.selectreactor import SelectReactor

from crossbar.test import TestCase
from crossbar.router.role import RouterRoleStaticAuth, RouterPermissions
from crossbar.worker import router

from txaio import make_logger

from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.message import Publish, Published, Subscribe, Subscribed
from autobahn.wamp.message import Register, Registered, Hello, Welcome
from autobahn.wamp.role import RoleBrokerFeatures, RoleDealerFeatures
from autobahn.wamp.types import ComponentConfig

from .examples.goodclass import _

try:
    from twisted.web.wsgi import WSGIResource  # noqa
except (ImportError, SyntaxError):
    WSGI_TESTS = "Twisted WSGI support is not available."
else:
    WSGI_TESTS = False

WSGI_TESTS = True


class DottableDict(dict):
    def __getattr__(self, name):
        return self[name]


class FakeWAMPTransport(object):
    """
    A fake WAMP transport that responds to all messages with successes.
    """
    def __init__(self, session):
        self._messages = []
        self._session = session

    def send(self, message):
        """
        Send the message, respond with it's success message synchronously.
        Append it to C{self._messages} for later analysis.
        """
        self._messages.append(message)

        if isinstance(message, Hello):
            self._session.onMessage(
                Welcome(1, {
                    "broker": RoleBrokerFeatures(),
                    "dealer": RoleDealerFeatures()
                }, authrole="anonymous"))
        elif isinstance(message, Register):
            self._session.onMessage(Registered(message.request, message.request))
        elif isinstance(message, Publish):
            if message.acknowledge:
                self._session.onMessage(Published(message.request, message.request))
        elif isinstance(message, Subscribe):
            self._session.onMessage(Subscribed(message.request, message.request))
        else:
            assert False, message

    def _get(self, klass):
        return list(filter(lambda x: isinstance(x, klass), self._messages))


class RouterWorkerSessionTests(TestCase):

    skip = True

    def setUp(self):
        """
        Set up the common component config.
        """
        self.realm = "realm1"
        config_extras = DottableDict({"worker": "worker1", "cbdir": self.mktemp()})
        self.config = ComponentConfig(self.realm, extra=config_extras)

    def test_basic(self):
        """
        We can instantiate a RouterController.
        """
        log_list = []

        r = router.RouterController(config=self.config, reactor=reactor)
        r.log = make_logger(observer=log_list.append, log_level="debug")

        # Open the transport
        transport = FakeWAMPTransport(r)
        r.onOpen(transport)

        # XXX depends on log-text; perhaps a little flaky...
        self.assertIn("running as", log_list[-1]["log_format"])

    def test_start_router_component(self):
        """
        Starting a class-based router component works.
        """
        r = router.RouterController(config=self.config, reactor=reactor)

        # Open the transport
        transport = FakeWAMPTransport(r)
        r.onOpen(transport)

        realm_config = {
            "name":
            "realm1",
            'roles': [{
                'name': 'anonymous',
                'permissions': [{
                    'subscribe': True,
                    'register': True,
                    'call': True,
                    'uri': '*',
                    'publish': True
                }]
            }]
        }

        r.start_router_realm("realm1", realm_config)

        permissions = RouterPermissions('', True, True, True, True, True)
        routera = r._router_factory.get('realm1')
        routera.add_role(RouterRoleStaticAuth(router, 'anonymous', default_permissions=permissions))

        component_config = {
            "type": "class",
            "classname": "crossbar.worker.test.examples.goodclass.AppSession",
            "realm": "realm1"
        }

        r.start_router_component("newcomponent", component_config)

        self.assertEqual(len(r.get_router_components()), 1)
        self.assertEqual(r.get_router_components()[0]["id"], "newcomponent")

        self.assertEqual(len(_), 1)
        _.pop()  # clear this global state

    def test_start_router_component_fails(self):
        """
        Trying to start a class-based router component that gets an error on
        importing fails.
        """
        log_list = []

        r = router.RouterController(config=self.config, reactor=reactor)
        r.log = make_logger(observer=log_list.append, log_level="debug")

        # Open the transport
        transport = FakeWAMPTransport(r)
        r.onOpen(transport)

        realm_config = {
            "name":
            "realm1",
            'roles': [{
                'name': 'anonymous',
                'permissions': [{
                    'subscribe': True,
                    'register': True,
                    'call': True,
                    'uri': '*',
                    'publish': True
                }]
            }]
        }

        r.start_router_realm("realm1", realm_config)

        component_config = {"type": "class", "classname": "thisisathing.thatdoesnot.exist", "realm": "realm1"}

        with self.assertRaises(ApplicationError) as e:
            r.start_router_component("newcomponent", component_config)

        self.assertIn("Failed to import class 'thisisathing.thatdoesnot.exist'", str(e.exception.args[0]))

        self.assertEqual(len(r.get_router_components()), 0)

    def test_start_router_component_invalid_type(self):
        """
        Trying to start a component with an invalid type fails.
        """
        log_list = []

        r = router.RouterController(config=self.config, reactor=reactor)
        r.log = make_logger(observer=log_list.append, log_level="debug")

        # Open the transport
        transport = FakeWAMPTransport(r)
        r.onOpen(transport)

        realm_config = {"name": "realm1", 'roles': []}

        r.start_router_realm("realm1", realm_config)

        component_config = {"type": "notathingcrossbarsupports", "realm": "realm1"}

        with self.assertRaises(ApplicationError) as e:
            r.start_router_component("newcomponent", component_config)

        self.assertEqual(e.exception.error, "crossbar.error.invalid_configuration")

        self.assertEqual(len(r.get_router_components()), 0)

    def test_start_router_component_wrong_baseclass(self):
        """
        Starting a class-based router component fails when the application
        session isn't derived from ApplicationSession.
        """
        r = router.RouterController(config=self.config, reactor=reactor)

        # Open the transport
        transport = FakeWAMPTransport(r)
        r.onOpen(transport)

        realm_config = {"name": "realm1", 'roles': []}

        r.start_router_realm("realm1", realm_config)

        component_config = {
            "type": "class",
            "classname": "crossbar.worker.test.examples.badclass.AppSession",
            "realm": "realm1"
        }

        with self.assertRaises(ApplicationError) as e:
            r.start_router_component("newcomponent", component_config)

        self.assertIn(("session not derived of ApplicationSession"), str(e.exception.args[0]))

        self.assertEqual(len(r.get_router_components()), 0)


class WebTests(TestCase):

    # FIXME: test_root_not_required is broken:
    #
    #       [ERROR]
    #
    #       Traceback (most recent call last):
    #
    #       Failure: twisted.trial.util.DirtyReactorAggregateError: Reactor was unclean.
    #
    #       DelayedCalls: (set twisted.internet.base.DelayedCall.debug = True to debug)
    #
    #       <DelayedCall 0x7f9128dfd638 [59.9999029636s] called=0 cancelled=0 HTTPChannel.__timedOut()>
    #
    #       crossbar.worker.test.test_router.WebTests.test_root_not_required
    #
    #       ===============================================================================
    #
    #       [ERROR]
    #
    #       Traceback (most recent call last):
    #
    #       Failure: twisted.web._newclient.ResponseNeverReceived: [<twisted.python.failure.Failure twisted.internet.error.ConnectionLost: Connection to the other side was lost in a non-clean fashion: Connection lost.>]
    #
    #       crossbar.worker.test.test_router.WebTests.test_root_not_required
    #
    #       -------------------------------------------------------------------------------
    #
    #       Ran 280 tests in 3.191s
    skip = True

    def setUp(self):
        self.cbdir = self.mktemp()
        os.makedirs(self.cbdir)
        config_extras = DottableDict({
            "worker":
            "worker1",
            "cbdir":
            self.cbdir.decode('utf8') if not isinstance(self.cbdir, str) else self.cbdir
        })
        self.config = ComponentConfig("realm1", extra=config_extras)

    def test_root_not_required(self):
        """
        Not including a '/' path will mean that path has a 404, but children
        will still be routed correctly.
        """
        temp_reactor = SelectReactor()
        r = router.RouterController(config=self.config, reactor=temp_reactor)

        # Open the transport
        transport = FakeWAMPTransport(r)
        r.onOpen(transport)

        realm_config = {"name": "realm1", 'roles': []}

        # Make a file
        with open(os.path.join(self.cbdir, 'file.txt'), "wb") as f:
            f.write(b"hello!")

        r.start_router_realm("realm1", realm_config)
        r.start_router_transport(
            "component1", {
                "type": "web",
                "endpoint": {
                    "type": "tcp",
                    "port": 8080
                },
                "paths": {
                    "static": {
                        "directory": ".",
                        "type": "static"
                    }
                }
            })

        d1 = treq.get("http://localhost:8080/", reactor=temp_reactor)
        d1.addCallback(lambda resp: self.assertEqual(resp.code, 404))

        d2 = treq.get("http://localhost:8080/static/file.txt", reactor=temp_reactor)
        d2.addCallback(treq.content)
        d2.addCallback(self.assertEqual, b"hello!")

        def done(results):
            for item in results:
                if not item[0]:
                    return item[1]

        d = defer.DeferredList([d1, d2])
        d.addCallback(done)
        d.addCallback(lambda _: temp_reactor.stop())

        def escape():
            if temp_reactor.running:
                temp_reactor.stop()

        temp_reactor.callLater(1, escape)
        temp_reactor.run()


class WSGITests(TestCase):

    skip = WSGI_TESTS

    def setUp(self):
        self.cbdir = self.mktemp()
        os.makedirs(self.cbdir)
        config_extras = DottableDict({"worker": "worker1", "cbdir": self.cbdir})
        self.config = ComponentConfig("realm1", extra=config_extras)

    def test_basic(self):
        """
        A basic WSGI app can be ran.
        """
        temp_reactor = SelectReactor()
        r = router.RouterController(config=self.config, reactor=temp_reactor)

        # Open the transport
        transport = FakeWAMPTransport(r)
        r.onOpen(transport)

        realm_config = {"name": "realm1", 'roles': []}

        r.start_router_realm("realm1", realm_config)
        r.start_router_transport(
            "component1", {
                "type": "web",
                "endpoint": {
                    "type": "tcp",
                    "port": 8080
                },
                "paths": {
                    "/": {
                        "module": "crossbar.worker.test.test_router",
                        "object": "hello",
                        "type": "wsgi"
                    }
                }
            })

        # Make a request to the WSGI app.
        d = treq.get("http://localhost:8080/", reactor=temp_reactor)
        d.addCallback(treq.content)
        d.addCallback(self.assertEqual, b"hello!")
        d.addCallback(lambda _: temp_reactor.stop())

        def escape():
            if temp_reactor.running:
                temp_reactor.stop()

        temp_reactor.callLater(1, escape)
        temp_reactor.run()

        return d

    def test_basic_subresources(self):
        """
        A basic WSGI app can be ran, with subresources
        """
        temp_reactor = SelectReactor()
        r = router.RouterController(config=self.config, reactor=temp_reactor)

        # Open the transport
        transport = FakeWAMPTransport(r)
        r.onOpen(transport)

        realm_config = {"name": "realm1", 'roles': []}

        r.start_router_realm("realm1", realm_config)
        r.start_router_transport(
            "component1", {
                "type": "web",
                "endpoint": {
                    "type": "tcp",
                    "port": 8080
                },
                "paths": {
                    "/": {
                        "module": "crossbar.worker.test.test_router",
                        "object": "hello",
                        "type": "wsgi"
                    },
                    "json": {
                        "type": "json",
                        "value": {}
                    }
                }
            })

        # Make a request to the /json endpoint, which is technically a child of
        # the WSGI app, but is not served by WSGI.
        d = treq.get("http://localhost:8080/json", reactor=temp_reactor)
        d.addCallback(treq.content)
        d.addCallback(self.assertEqual, b"{}")
        d.addCallback(lambda _: temp_reactor.stop())

        def escape():
            if temp_reactor.running:
                temp_reactor.stop()

        temp_reactor.callLater(1, escape)
        temp_reactor.run()

        return d

    # This test relies on timing artifacts (read: it's unstable, eg https://travis-ci.org/crossbario/crossbar/jobs/96633875)
    # def test_threads(self):
    #     """
    #     A basic WSGI app can be ran, with subresources
    #     """
    #     temp_reactor = SelectReactor()
    #     r = router.RouterController(config=self.config,
    #                                    reactor=temp_reactor)

    #     # Open the transport
    #     transport = FakeWAMPTransport(r)
    #     r.onOpen(transport)

    #     realm_config = {
    #         "name": "realm1",
    #         'roles': []
    #     }

    #     threads = 20

    #     r.start_router_realm("realm1", realm_config)
    #     r.start_router_transport(
    #         "component1",
    #         {
    #             "type": "web",
    #             "endpoint": {
    #                 "type": "tcp",
    #                 "port": 8080
    #             },
    #             "paths": {
    #                 "/": {
    #                     "module": "crossbar.worker.test.test_router",
    #                     "object": "sleep",
    #                     "type": "wsgi",
    #                     "maxthreads": threads,
    #                 }
    #             }
    #         })

    #     deferreds = []
    #     results = []

    #     for i in range(threads):
    #         d = treq.get("http://localhost:8080/", reactor=temp_reactor)
    #         d.addCallback(treq.content)
    #         d.addCallback(results.append)
    #         deferreds.append(d)

    #     def done(_):
    #         max_concurrency = max([int(x) for x in results])

    #         assert max_concurrency == threads, "Maximum concurrency was %s, not %s" % (max_concurrency, threads)
    #         temp_reactor.stop()

    #     defer.DeferredList(deferreds).addCallback(done)

    #     def escape():
    #         if temp_reactor.running:
    #             temp_reactor.stop()

    #     temp_reactor.callLater(1, escape)
    #     temp_reactor.run()


def hello(environ, start_response):
    """
    A super dumb WSGI app for testing.
    """
    start_response('200 OK', [('Content-Type', 'text/html')])
    return [b'hello!']


# Ugh global state, but it's just for a test...
count = []


def sleep(environ, start_response):
    """
    A super dumb WSGI app for testing.
    """
    from time import sleep
    start_response('200 OK', [('Content-Type', 'text/html')])
    # Count how many concurrent responses there are.
    count.append(None)
    res = len(count)
    sleep(0.1)
    count.pop(0)
    return [str(res).encode('ascii')]
