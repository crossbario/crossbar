#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""
WAMP-cryptosign mutual authentication: the router signs a client-supplied "challenge" with
the node key. That value must be exactly 32 bytes (hex encoded), a random nonce - otherwise
the node key becomes a signing oracle over attacker-chosen or oversized data. The router
rejects a challenge that is not 32 bytes or not valid hex (#2037; defense in depth for the
pre-authentication signing oracle, wamp-proto#585).
"""

from unittest import mock

from autobahn.wamp.types import Deny, HelloDetails, TransportDetails
from twisted.trial import unittest

from crossbar.router.auth import cryptosign


class CryptosignChallengeLengthTests(unittest.TestCase):
    def _pending(self):
        return cryptosign.PendingAuthCryptosign(
            1, TransportDetails(), mock.Mock(), {"type": "static", "principals": {}}
        )

    def _hello(self, authextra):
        return self._pending().hello("realm1", HelloDetails(authmethods=["cryptosign"], authextra=authextra))

    def test_oversized_challenge_denied(self):
        res = self._hello({"challenge": "00" * 64})
        self.assertIsInstance(res, Deny)
        self.assertIn("32 bytes", res.message)

    def test_undersized_challenge_denied(self):
        res = self._hello({"challenge": "00" * 16})
        self.assertIsInstance(res, Deny)
        self.assertIn("32 bytes", res.message)

    def test_malformed_hex_challenge_denied(self):
        res = self._hello({"challenge": "not-hex"})
        self.assertIsInstance(res, Deny)
        self.assertIn("hex", res.message)

    def test_valid_32byte_challenge_passes_length_check(self):
        # a valid 32-byte challenge passes the length check; the session is then denied for other
        # reasons (no principal), but never for the challenge
        res = self._hello({"challenge": "00" * 32})
        self.assertNotIn("challenge", getattr(res, "message", ""))

    def test_no_challenge_passes_length_check(self):
        # no client challenge at all: the length check does not fire
        res = self._hello({})
        self.assertNotIn("challenge", getattr(res, "message", ""))
