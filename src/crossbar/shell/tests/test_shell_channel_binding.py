#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""
The management shell clients authenticate with WAMP-cryptosign and request TLS channel
binding by the negotiated TLS version: "tls-exporter" (RFC 9266) on TLS 1.3, "tls-unique"
(RFC 5929) on TLS <= 1.2, and none on a transport without a TLS channel ID (#2037).
"""

import os
from unittest.mock import Mock

from autobahn.wamp.types import Challenge, ComponentConfig, TransportDetails
from twisted.trial.unittest import TestCase

from crossbar.shell.client import ManagementClientSession, ShellClient


class _ShellChannelBindingBase:
    SESSION = None

    def _session(self, channel_id):
        key = Mock()
        key.public_key.return_value = "ab" * 32
        key.sign_challenge.return_value = "signature"
        session = self.SESSION(ComponentConfig("realm1", extra={"key": key}))
        session._transport = Mock(transport_details=TransportDetails(channel_id=channel_id))
        session.join = Mock()
        return session, key

    def test_tls13_requests_tls_exporter(self):
        session, _ = self._session({"tls-exporter": os.urandom(32)})
        session.onConnect()
        authextra = session.join.call_args.kwargs["authextra"]
        self.assertEqual(authextra.get("channel_binding"), "tls-exporter")

    def test_tls13_signs_with_tls_exporter(self):
        channel_id = os.urandom(32)
        session, key = self._session({"tls-exporter": channel_id})
        session.onConnect()
        challenge = Challenge("cryptosign", {"challenge": "00" * 32, "channel_binding": "tls-exporter"})
        self.assertEqual(session.onChallenge(challenge), "signature")
        key.sign_challenge.assert_called_once_with(challenge, channel_id=channel_id, channel_id_type="tls-exporter")

    def test_tls12_requests_tls_unique(self):
        session, _ = self._session({"tls-unique": os.urandom(32)})
        session.onConnect()
        authextra = session.join.call_args.kwargs["authextra"]
        self.assertEqual(authextra.get("channel_binding"), "tls-unique")

    def test_no_tls_no_channel_binding(self):
        session, _ = self._session({})
        session.onConnect()
        authextra = session.join.call_args.kwargs["authextra"]
        self.assertIsNone(authextra.get("channel_binding", None))


class ShellClientChannelBindingTests(_ShellChannelBindingBase, TestCase):
    SESSION = ShellClient


class ManagementClientChannelBindingTests(_ShellChannelBindingBase, TestCase):
    SESSION = ManagementClientSession
