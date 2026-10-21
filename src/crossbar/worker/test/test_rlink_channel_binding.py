#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""
The remote leg of a router-to-router link authenticates with WAMP-cryptosign: it requests
TLS channel binding only on a transport with a TLS channel ID, and signs with the channel
ID of its own connection to the remote router (#2360).
"""

import os
from unittest.mock import Mock

from autobahn.wamp.types import Challenge, ComponentConfig, TransportDetails
from twisted.internet.defer import succeed
from twisted.trial.unittest import TestCase

from crossbar.worker.rlink import RLinkRemoteSession

_CHALLENGE = Challenge("cryptosign", {"challenge": "00" * 32, "channel_binding": "tls-unique"})


class RLinkChannelBindingTests(TestCase):
    def _session(self, channel_id):
        controller = Mock()
        # the router worker's own connection, to the node controller: never TLS
        controller._transport.transport_details = TransportDetails(channel_id={})
        controller.get_public_key.return_value = succeed("ab" * 32)
        controller.sign_challenge.return_value = "signature"
        manager = Mock(controller=controller, _controller=controller)

        session = RLinkRemoteSession(ComponentConfig("realm1", extra={"rlink_manager": manager}))
        # the rlink's connection to the remote router
        session._transport = Mock(transport_details=TransportDetails(channel_id=channel_id))
        session.join = Mock()
        return session, controller

    def test_tls_requests_channel_binding(self):
        session, _ = self._session({"tls-unique": os.urandom(32)})
        session.onConnect()
        authextra = session.join.call_args.kwargs["authextra"]
        self.assertEqual(authextra.get("channel_binding"), "tls-unique")

    def test_tls_signs_with_own_channel_id(self):
        channel_id = os.urandom(32)
        session, controller = self._session({"tls-unique": channel_id})
        session.onConnect()
        self.assertEqual(session.onChallenge(_CHALLENGE), "signature")
        controller.sign_challenge.assert_called_once_with(_CHALLENGE, channel_id, "tls-unique")

    def test_no_tls_no_channel_binding(self):
        session, controller = self._session({})
        session.onConnect()
        authextra = session.join.call_args.kwargs["authextra"]
        self.assertIsNone(authextra.get("channel_binding", None))

        challenge = Challenge("cryptosign", {"challenge": "00" * 32, "channel_binding": None})
        session.onChallenge(challenge)
        controller.sign_challenge.assert_called_once_with(challenge, None, None)
