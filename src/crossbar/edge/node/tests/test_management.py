#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""
The node management uplink authenticates with WAMP-cryptosign: it requests TLS channel
binding only on a transport with a TLS channel ID, and signs with that channel ID (#2360).
"""

import os
from unittest.mock import Mock

from autobahn.wamp.types import Challenge, ComponentConfig, TransportDetails
from twisted.trial.unittest import TestCase

from crossbar.edge.node.management import NodeManagementSession


class NodeManagementChannelBindingTests(TestCase):
    def _session(self, channel_id):
        key = Mock()
        key.public_key.return_value = "ab" * 32
        key.sign_challenge.return_value = "signature"
        node = Mock(secmod={1: key})

        session = NodeManagementSession(None, ComponentConfig(None, extra={"node": node}))
        session._transport = Mock(transport_details=TransportDetails(channel_id=channel_id))
        session.join = Mock()
        return session, key

    def test_tls_channel_binding(self):
        channel_id = os.urandom(32)
        session, key = self._session({"tls-unique": channel_id})
        session.onConnect()
        self.assertEqual(session.join.call_args.kwargs["authextra"]["channel_binding"], "tls-unique")

        challenge = Challenge("cryptosign", {"challenge": "00" * 32, "channel_binding": "tls-unique"})
        self.assertEqual(session.onChallenge(challenge), "signature")
        key.sign_challenge.assert_called_once_with(challenge, channel_id=channel_id, channel_id_type="tls-unique")

    def test_no_tls_no_channel_binding(self):
        session, key = self._session({})
        session.onConnect()
        self.assertIsNone(session.join.call_args.kwargs["authextra"].get("channel_binding", None))

        challenge = Challenge("cryptosign", {"challenge": "00" * 32, "channel_binding": None})
        session.onChallenge(challenge)
        key.sign_challenge.assert_called_once_with(challenge, channel_id=None, channel_id_type=None)
