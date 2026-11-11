#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""
Regression tests for crossbar#2396: failures the typing round found.
"""

from unittest import mock

from autobahn.wamp import message, role
from autobahn.wamp.types import Deny, HelloDetails, TransportDetails
from twisted.internet import defer, task
from twisted.trial import unittest

from crossbar.router.auth.scram import PendingAuthScram
from crossbar.router.role import RouterRoleStaticAuth
from crossbar.router.router import RouterFactory
from crossbar.worker.types import RouterRealm


class TestStopRealmWithoutSessions(unittest.TestCase):
    def test_stop_realm_without_sessions(self):
        # Router.detach() of all sessions logged the auth details of the loop's
        # last session, and so raised AttributeError when the realm had none.
        router_factory = RouterFactory("node1", "router1", None)
        router_factory.start_realm(RouterRealm(None, "realm-001", {"name": "realm1"}))
        self.assertEqual(router_factory.stop_realm("realm1"), [])


class TestRemoveCallee(unittest.TestCase):
    def setUp(self):
        self.router_factory = RouterFactory("node1", "router1", None)
        self.realm = RouterRealm(None, "realm-001", {"name": "realm1"})
        self.router_factory.start_realm(self.realm)
        self.router = self.router_factory.get("realm1")
        self.router.add_role(
            RouterRoleStaticAuth(
                self.router,
                "test_role",
                default_permissions={
                    "uri": "com.example.",
                    "match": "prefix",
                    "allow": {"call": True, "register": True, "publish": True, "subscribe": True},
                },
            )
        )

    def test_remove_callee_with_service_session(self):
        # removeCallee() (wamp.registration.remove_callee) unregisters without an
        # UNREGISTER message: with a service session on the realm (as every
        # crossbar realm has), _unregister() raised AttributeError on None.
        messages = []
        session = mock.Mock()
        session._transport.send = messages.append
        session._session_roles = {"callee": role.RoleCalleeFeatures(registration_revocation=True)}

        self.router.authorize = mock.Mock(return_value=defer.succeed({"allow": True, "disclose": False}))
        dealer = self.router._dealer
        dealer._reactor = task.Clock()
        dealer.attach(session)
        dealer.processRegister(
            session, message.Register(1, "com.example.my.proc", "exact", message.Register.INVOKE_SINGLE, 1)
        )
        registered = messages[-1]
        self.assertIsInstance(registered, message.Registered)

        service_session = mock.Mock()
        self.router._realm.session = service_session
        registration = dealer._registration_map.get_observation_by_id(registered.registration)

        dealer.removeCallee(registration, session, reason="wamp.close.testing")

        # the callee is told, and the meta events go out on the next reactor turn
        self.assertIsInstance(messages[-1], message.Unregistered)
        dealer._reactor.advance(0)
        topics = [c.args[0] for c in service_session.publish.call_args_list]
        self.assertIn("wamp.registration.on_unregister", topics)


class TestScramHelloWithoutAuthextra(unittest.TestCase):
    def test_hello_without_authextra(self):
        # a HELLO without authextra: Deny (no nonce), not AttributeError on None
        pending = PendingAuthScram(1, TransportDetails(), mock.Mock(), {"type": "static", "principals": {}})
        res = pending.hello("realm1", HelloDetails(authmethods=["scram"], authid="alice", authextra=None))
        self.assertIsInstance(res, Deny)
        self.assertIn("nonce", res.message)


class TestCryptosignCertificateChainShape(unittest.TestCase):
    def test_chain_not_delegate_then_authority_is_denied(self):
        # The trustroot check reads the delegate certificate (first) and the root CA
        # certificate (last) of the client's chain. A chain of another shape failed
        # with AttributeError; it is now denied explicitly.
        from xbr import EIP712AuthorityCertificate, EIP712DelegateCertificate

        from crossbar.router.auth import cryptosign

        root_ca_address = "0xf766Dc789CF04CD18aE75af2c5fAf2DA6650Ff57"
        root_ca = mock.Mock(spec=EIP712AuthorityCertificate)
        root_ca.issuer = bytes.fromhex(root_ca_address[2:])

        pending = cryptosign.PendingAuthCryptosign(
            1, TransportDetails(), mock.Mock(), {"type": "static", "principals": {}}
        )
        pending._realms_to_trustroots = {"realm1": root_ca}

        # reversed: an authority certificate first, a delegate certificate last
        chain = [mock.Mock(spec=EIP712AuthorityCertificate), mock.Mock(spec=EIP712DelegateCertificate)]
        authextra = {"trustroot": root_ca_address, "certificates": [("hash", {}, "sig"), ("hash", {}, "sig")]}
        with mock.patch.object(cryptosign, "parse_certificate_chain", return_value=chain):
            res = pending.hello("realm1", HelloDetails(authmethods=["cryptosign"], authextra=authextra))
        self.assertIsInstance(res, Deny)
        self.assertIn("certificate chain", res.message)
