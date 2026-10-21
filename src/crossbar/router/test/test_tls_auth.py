#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""
WAMP over TLS on the router (#2360): TLS client certificate authentication (authmethod
"tls", static and dynamic) and WAMP-cryptosign with TLS channel binding ("tls-unique"),
over WebSocket and RawSocket, on real TLS connections on the loopback interface.
"""

import hashlib
import os

from autobahn.twisted.rawsocket import WampRawSocketClientFactory
from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.websocket import WampWebSocketClientFactory
from autobahn.wamp import cryptosign
from autobahn.wamp.types import ComponentConfig
from twisted.internet import reactor as global_reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.trial.unittest import TestCase
from txaio.tx import make_logger

from crossbar._util import get_free_tcp_port
from crossbar.common.twisted.endpoint import (
    create_connecting_endpoint_from_config,
    create_listening_endpoint_from_config,
)
from crossbar.router.protocol import WampRawSocketServerFactory, WampWebSocketServerFactory
from crossbar.router.role import RouterRoleStaticAuth
from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.test.helpers import RouterRealmContainer, add_realm_to_router, write_self_signed_cert

_PRIVKEY = b"\x01" * 32

_ALLOW_ALL = {
    "uri": "",
    "match": "prefix",
    "allow": {"call": True, "register": True, "publish": True, "subscribe": True},
}


class _Client(ApplicationSession):
    """
    A WAMP client that joins with one authmethod and reports the outcome.
    """

    def __init__(self, config, authmethod, authextra, sign, done):
        ApplicationSession.__init__(self, config)
        self._authmethod = authmethod
        self._authextra = authextra
        self._sign = sign
        self._done = done

    def onConnect(self):
        self.join(self.config.realm, authmethods=[self._authmethod], authextra=self._authextra)

    def onChallenge(self, challenge):
        return self._sign(self, challenge)

    def onJoin(self, details):
        if not self._done.called:
            self._done.callback(("joined", details))
        self.leave()

    def onLeave(self, details):
        if not self._done.called:
            self._done.callback(("left", details))
        self.disconnect()

    def onDisconnect(self):
        if not self._done.called:
            self._done.callback(("disconnected", None))


def _sign_cryptosign(channel_id=None):
    """
    Return a challenge handler signing with _PRIVKEY: with the client's own TLS channel ID
    (if it has one), or with ``channel_id`` when given.
    """
    key = cryptosign.CryptosignKey.from_bytes(_PRIVKEY)

    def sign(session, challenge):
        if challenge.extra.get("channel_binding") != "tls-unique":
            return key.sign_challenge(challenge)
        cid = channel_id
        if cid is None:
            cid = (session._transport.transport_details.channel_id or {}).get("tls-unique", None)
        if cid is None:
            return key.sign_challenge(challenge)
        return key.sign_challenge(challenge, channel_id=cid, channel_id_type="tls-unique")

    return sign


class _TlsAuthTests(object):
    """
    The tests, for a router transport (WebSocket or RawSocket) given by the subclass.
    """

    transport = None
    timeout = 20

    def setUp(self):
        self.certdir = os.path.abspath(self.mktemp())
        os.makedirs(self.certdir)
        write_self_signed_cert(self.certdir, "server", "localhost")
        self.sha1 = {
            "client_0": write_self_signed_cert(self.certdir, "client_0", "client_0"),
            "client_1": write_self_signed_cert(self.certdir, "client_1", "client_1"),
        }
        self.pubkey = cryptosign.CryptosignKey.from_bytes(_PRIVKEY).public_key()
        self.authenticator_details = []

    def _auth_config(self):
        return {
            "tls": {
                "type": "static",
                "principals": {"client_0": {"certificate-sha1": self.sha1["client_0"], "role": "backend"}},
            },
            "cryptosign": {
                "type": "static",
                "principals": {"alice": {"realm": "realm1", "role": "backend", "authorized_keys": [self.pubkey]}},
            },
        }

    def _dynamic_tls_config(self):
        return {
            "tls": {
                "type": "dynamic",
                "authenticator": "com.example.tls",
                "authenticator-realm": "default",
                "authenticator-role": "trusted",
            }
        }

    def _make_router(self, auth_config):
        router_factory = RouterFactory("node1", "worker1", None)
        session_factory = RouterSessionFactory(router_factory)
        router_factory._worker = RouterRealmContainer(router_factory)

        default_router = add_realm_to_router(router_factory, session_factory)
        router = add_realm_to_router(router_factory, session_factory, realm_name="realm1")
        router.add_role(RouterRoleStaticAuth(router, "backend", default_permissions=_ALLOW_ALL))

        details_seen = self.authenticator_details

        class AuthenticatorSession(ApplicationSession):
            """
            A dynamic TLS authenticator, as in crossbar-examples authentication/tls/dynamic,
            that reads the client certificate from the key given in its call.
            """

            @inlineCallbacks
            def onJoin(self, details):
                def authenticate(key):
                    def tls(realm, authid, details):
                        details_seen.append(details)
                        client_cert = details["transport"].get(key, None)
                        if not client_cert:
                            return {"authid": "nobody", "role": "nobody"}
                        return {"authid": client_cert["subject"]["cn"], "role": "backend", "realm": "realm1"}

                    return tls

                yield self.register(authenticate(self.config.extra["key"]), "com.example.tls")

        return router_factory, session_factory, default_router, AuthenticatorSession

    def _server_factory(self, session_factory, auth_config):
        if self.transport == "websocket":
            return WampWebSocketServerFactory(session_factory, self.certdir, {"auth": auth_config}, None)
        return WampRawSocketServerFactory(session_factory, {"auth": auth_config})

    @inlineCallbacks
    def _join(
        self,
        client,
        authmethod,
        authextra=None,
        sign=None,
        tls=True,
        request_client_cert=True,
        auth_config=None,
        authenticator_key=None,
    ):
        """
        Start a router listening on the loopback interface (TLS or plain TCP), connect a
        client with the TLS client certificate ``client`` (or none), join with ``authmethod``,
        and return ``(outcome, details, router side protocol)``.
        """
        logger = make_logger()
        if auth_config is None:
            auth_config = self._auth_config()
        router_factory, session_factory, default_router, AuthenticatorSession = self._make_router(auth_config)
        if authenticator_key:
            authsession = AuthenticatorSession(ComponentConfig("default", {"key": authenticator_key}))
            session_factory.add(authsession, default_router, authrole="trusted")

        server_factory = self._server_factory(session_factory, auth_config)
        server_protocols = []
        build_protocol = server_factory.buildProtocol

        def record_protocol(addr):
            p = build_protocol(addr)
            server_protocols.append(p)
            return p

        server_factory.buildProtocol = record_protocol

        port = get_free_tcp_port()
        listen_config = {"type": "tcp", "port": port, "interface": "127.0.0.1"}
        connect_config = {"type": "tcp", "host": "127.0.0.1", "port": port}
        if tls:
            listen_config["tls"] = {"certificate": "server.crt", "key": "server.key"}
            if request_client_cert:
                listen_config["tls"]["ca_certificates"] = ["client_0.crt", "client_1.crt"]
            connect_config["tls"] = {"hostname": "localhost", "ca_certificates": ["server.crt"]}
            if client:
                connect_config["tls"].update({"certificate": client + ".crt", "key": client + ".key"})

        endpoint = create_listening_endpoint_from_config(listen_config, self.certdir, global_reactor, logger)
        listening_port = yield endpoint.listen(server_factory)
        self.addCleanup(listening_port.stopListening)

        done = Deferred()

        def client_session():
            return _Client(ComponentConfig("realm1"), authmethod, authextra, sign, done)

        if self.transport == "websocket":
            url = "{}://localhost:{}".format("wss" if tls else "ws", port)
            client_factory = WampWebSocketClientFactory(client_session, url=url)
        else:
            client_factory = WampRawSocketClientFactory(client_session)

        client_endpoint = create_connecting_endpoint_from_config(connect_config, self.certdir, global_reactor, logger)
        client_protocol = yield client_endpoint.connect(client_factory)

        outcome, details = yield done
        # the client just joined (or failed to), and the connection is still open: remember
        # the router side TLS Finished message from the client and the channel ID
        for p in server_protocols:
            handle = p.transport.getHandle() if tls else None
            p.observed_tls = (
                handle.get_peer_finished() if handle else None,
                (p.transport_details.channel_id or {}).get("tls-unique", None),
            )
        # wait until both sides closed the connection
        yield client_protocol.is_closed
        for p in server_protocols:
            yield p.is_closed
        return outcome, details, server_protocols[0]

    # TLS client certificate authentication (authmethod "tls")

    @inlineCallbacks
    def test_tls_static_accepted(self):
        outcome, details, _ = yield self._join("client_0", "tls")
        self.assertEqual(outcome, "joined", details)
        self.assertEqual((details.authid, details.authrole, details.authmethod), ("client_0", "backend", "tls"))

    @inlineCallbacks
    def test_tls_static_unknown_certificate(self):
        """
        A client certificate the router trusts at the TLS level, but that is no principal:
        denied, for that reason.
        """
        outcome, details, _ = yield self._join("client_1", "tls")
        self.assertEqual(outcome, "left")
        self.assertEqual(details.message, 'no principal with authid "{}" exists'.format(self.sha1["client_1"]))

    @inlineCallbacks
    def test_tls_no_certificate(self):
        outcome, details, _ = yield self._join(None, "tls", request_client_cert=False)
        self.assertEqual(outcome, "left")
        self.assertEqual(details.message, "client did not send a TLS client certificate")

    @inlineCallbacks
    def test_tls_dynamic_peer_cert(self):
        """
        A dynamic authenticator gets the client certificate as ``details["transport"]["peer_cert"]``.
        """
        outcome, details, _ = yield self._join(
            "client_0", "tls", auth_config=self._dynamic_tls_config(), authenticator_key="peer_cert"
        )
        self.assertEqual(outcome, "joined", details)
        self.assertEqual((details.authid, details.authrole), ("client_0", "backend"))
        peer_cert = self.authenticator_details[0]["transport"]["peer_cert"]
        self.assertEqual(peer_cert["sha1"], self.sha1["client_0"])

    @inlineCallbacks
    def test_tls_dynamic_client_cert(self):
        """
        ... and also as ``details["transport"]["client_cert"]``, the key crossbar used before
        2022 and that the crossbar-examples authenticator reads.
        """
        outcome, details, _ = yield self._join(
            "client_0", "tls", auth_config=self._dynamic_tls_config(), authenticator_key="client_cert"
        )
        self.assertEqual(outcome, "joined", details)
        self.assertEqual((details.authid, details.authrole), ("client_0", "backend"))
        transport = self.authenticator_details[0]["transport"]
        self.assertEqual(transport["client_cert"], transport["peer_cert"])

    # WAMP-cryptosign with TLS channel binding

    def _check_channel_id(self, server_protocol):
        """
        The router's tls-unique channel ID is the SHA256 of the first TLS Finished message
        of the handshake, the client's (RFC 5929, as Python's ssl module computes it).
        """
        client_finished, channel_id = server_protocol.observed_tls
        self.assertEqual(channel_id, hashlib.sha256(client_finished).digest())

    @inlineCallbacks
    def test_cryptosign_channel_binding(self):
        outcome, details, server_protocol = yield self._join(
            None,
            "cryptosign",
            {"pubkey": self.pubkey, "channel_binding": "tls-unique"},
            _sign_cryptosign(),
            request_client_cert=False,
        )
        self.assertEqual(outcome, "joined", details)
        self.assertEqual((details.authid, details.authmethod), ("alice", "cryptosign"))
        self._check_channel_id(server_protocol)

    @inlineCallbacks
    def test_cryptosign_channel_binding_with_client_certificate(self):
        outcome, details, server_protocol = yield self._join(
            "client_0", "cryptosign", {"pubkey": self.pubkey, "channel_binding": "tls-unique"}, _sign_cryptosign()
        )
        self.assertEqual(outcome, "joined", details)
        self._check_channel_id(server_protocol)

    @inlineCallbacks
    def test_cryptosign_channel_binding_wrong_channel_id(self):
        outcome, details, _ = yield self._join(
            None,
            "cryptosign",
            {"pubkey": self.pubkey, "channel_binding": "tls-unique"},
            _sign_cryptosign(channel_id=os.urandom(32)),
            request_client_cert=False,
        )
        self.assertEqual(outcome, "left")
        self.assertTrue(details.message.startswith("message signed is bogus"), details.message)

    @inlineCallbacks
    def test_cryptosign_without_channel_binding(self):
        outcome, details, _ = yield self._join(
            None, "cryptosign", {"pubkey": self.pubkey}, _sign_cryptosign(), request_client_cert=False
        )
        self.assertEqual(outcome, "joined", details)

    @inlineCallbacks
    def test_cryptosign_channel_binding_without_tls(self):
        """
        A client requesting channel binding on a transport without a TLS channel ID is denied,
        not authenticated without channel binding.
        """
        outcome, details, _ = yield self._join(
            None,
            "cryptosign",
            {"pubkey": self.pubkey, "channel_binding": "tls-unique"},
            _sign_cryptosign(),
            tls=False,
        )
        self.assertEqual(outcome, "left")
        self.assertEqual(
            details.message, 'channel binding "tls-unique" requested, but the transport has no TLS channel ID'
        )


class TlsAuthWebSocketTests(_TlsAuthTests, TestCase):
    transport = "websocket"


class TlsAuthRawSocketTests(_TlsAuthTests, TestCase):
    transport = "rawsocket"
