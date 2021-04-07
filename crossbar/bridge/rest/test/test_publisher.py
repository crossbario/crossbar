#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import json

from twisted.internet.defer import inlineCallbacks, maybeDeferred

from autobahn.wamp.exception import ApplicationError

from crossbar.test import TestCase
from crossbar._compat import native_string
from crossbar._logging import LogCapturer
from crossbar._log_categories import log_categories
from crossbar.bridge.rest import PublisherResource
from crossbar.bridge.rest.test import MockPublisherSession, renderResource


class PublisherTestCase(TestCase):
    """
    Unit tests for L{PublisherResource}. These tests publish no real WAMP
    messages, but test the interation of the HTTP request and the resource.
    """
    @inlineCallbacks
    def test_basic_publish(self):
        """
        Test a very basic publish to a topic.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer() as l:
            request = yield renderResource(resource,
                                           b"/",
                                           method=b"POST",
                                           headers={b"Content-Type": [b"application/json"]},
                                           body=b'{"topic": "com.test.messages", "args": [1]}')

        self.assertEqual(len(session._published_messages), 1)
        self.assertEqual(session._published_messages[0]["args"], (1, ))

        self.assertEqual(request.code, 200)

        logs = l.get_category("AR200")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["code"], 200)

        self.assertEqual(json.loads(native_string(request.get_written_data())),
                         {"id": session._published_messages[0]["id"]})
        # ensure we have all the format-keys AR200 asks for (can we
        # extract these from the _log_categories string instead?)
        self.assertIn('code', logs[0])
        self.assertIn('reason', logs[0])

    @inlineCallbacks
    def test_publish_error(self):
        """
        A publish that errors will return the error to the client.
        """
        class RejectingPublisherSession(object):
            """
            A mock WAMP session.
            """
            def publish(self, topic, *args, **kwargs):
                return maybeDeferred(self._publish, topic, *args, **kwargs)

            def _publish(self, topic, *args, **kwargs):
                raise ApplicationError('wamp.error.not_authorized', foo="bar")

        session = RejectingPublisherSession()
        resource = PublisherResource({}, session)

        with LogCapturer() as l:
            request = yield renderResource(resource,
                                           b"/",
                                           method=b"POST",
                                           headers={b"Content-Type": [b"application/json"]},
                                           body=b'{"topic": "com.test.messages", "args": [1]}')

        self.assertEqual(request.code, 200)

        logs = l.get_category("AR456")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["code"], 200)

        self.assertEqual(json.loads(native_string(request.get_written_data())), {
            "error": "wamp.error.not_authorized",
            "args": [],
            "kwargs": {
                "foo": "bar"
            }
        })

    @inlineCallbacks
    def test_publish_cberror(self):
        """
        A publish that errors with a Crossbar failure will return a generic
        error to the client and log the exception.
        """
        class RejectingPublisherSession(object):
            """
            A mock WAMP session.
            """
            def publish(self, topic, *args, **kwargs):
                return maybeDeferred(self._publish, topic, *args, **kwargs)

            def _publish(self, topic, *args, **kwargs):
                raise ValueError("ono")

        session = RejectingPublisherSession()
        resource = PublisherResource({}, session)

        with LogCapturer() as l:
            request = yield renderResource(resource,
                                           b"/",
                                           method=b"POST",
                                           headers={b"Content-Type": [b"application/json"]},
                                           body=b'{"topic": "com.test.messages", "args": [1]}')

        self.assertEqual(request.code, 500)

        logs = l.get_category("AR456")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["code"], 500)

        logs = l.get_category("AR500")
        self.assertEqual(len(logs), 1)

        self.assertEqual(json.loads(native_string(request.get_written_data())), {
            "error": "wamp.error.runtime_error",
            "args": ["Sorry, Crossbar.io has encountered a problem."],
            "kwargs": {}
        })

        # We manually logged it, so this one is OK
        self.flushLoggedErrors(ValueError)

    @inlineCallbacks
    def test_publish_needs_topic(self):
        """
        Test that attempted publishes without a topic will be rejected.
        """
        session = MockPublisherSession(self)
        resource = PublisherResource({}, session)

        with LogCapturer() as l:
            request = yield renderResource(resource,
                                           b"/",
                                           method=b"POST",
                                           headers={b"Content-Type": [b"application/json"]},
                                           body=b'{}')

        self.assertEqual(len(session._published_messages), 0)

        self.assertEqual(request.code, 400)
        errors = l.get_category("AR455")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], 400)

        self.assertEqual(json.loads(native_string(request.get_written_data())), {
            "error": log_categories["AR455"].format(key="topic"),
            "args": [],
            "kwargs": {}
        })
