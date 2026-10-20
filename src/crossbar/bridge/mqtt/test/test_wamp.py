#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import datetime
import json
import os

from twisted.trial.unittest import TestCase

from crossbar.router.test.helpers import add_realm_to_router, connect_application_session, make_router

try:
    from twisted.test.proto_helpers import Clock
except ImportError:
    from twisted.internet.task import Clock
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import ComponentConfig
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from twisted.internet import reactor as global_reactor
from twisted.internet.defer import Deferred, inlineCallbacks, succeed
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.task import LoopingCall
from twisted.test.iosim import FakeTransport, connect
from twisted.test.proto_helpers import AccumulatingProtocol
from txaio.tx import make_logger

from crossbar._logging import LogCapturer
from crossbar._util import get_free_tcp_port
from crossbar.bridge.mqtt._events import (
    ConnACK,
    Connect,
    ConnectFlags,
    Disconnect,
    PubACK,
    Publish,
    SubACK,
    Subscribe,
    SubscriptionTopicRequest,
)
from crossbar.bridge.mqtt.wamp import WampMQTTServerFactory
from crossbar.common.twisted.endpoint import (
    create_connecting_endpoint_from_config,
    create_listening_endpoint_from_config,
)
from crossbar.personality import Personality
from crossbar.router.role import RouterRoleStaticAuth

# import txaio
# txaio.start_logging(level='info')


class MockContainer(object):
    def has_realm(self, realm):
        return realm == "realm"

    def has_role(self, realm, role):
        return realm == "realm" and role == "anonymous"


class RouterRealmContainer(object):
    """
    The realm container (the router worker in production) authentication queries
    about the realms and roles of the routers in a router factory.
    """

    personality = Personality

    def __init__(self, router_factory):
        self._router_factory = router_factory

    def has_realm(self, realm):
        return realm in self._router_factory

    def has_role(self, realm, role):
        return realm in self._router_factory and self._router_factory[realm].has_role(role)

    def get_service_session(self, realm, role):
        return succeed(self._router_factory[realm]._realm.session)


class ObservingSession(ApplicationSession):
    _topic = "test"

    @inlineCallbacks
    def onJoin(self, details):
        self.events = []

        def on_event(*a, **kw):
            evt = {"args": a, "kwargs": kw}
            self.events.append(evt)
            print(evt)
            self.log.info("event on {topic}: {evt}", topic=self._topic, evt=evt)

        self.s = yield self.subscribe(on_event, self._topic)


def _write_self_signed(certdir, name, cn):
    """
    Write a self-signed certificate for cn and its key to certdir, and return the
    SHA1 fingerprint of the certificate (formatted as in the TLS transport details).
    """
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(cn)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(os.path.join(certdir, name + ".key"), "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
    with open(os.path.join(certdir, name + ".crt"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return ":".join("{:02X}".format(b) for b in cert.fingerprint(hashes.SHA1()))  # nosec B303 - certificate ID


# The MQTT bridge reads the client certificate after the TLS handshake, with autobahn's
# extract_peer_certificate(), which fails on pyOpenSSL >= 26.2.0 (X509.get_extension removed)
_SKIP_TLS = "autobahn extract_peer_certificate() fails with pyOpenSSL >= 26.2.0 (crossbar #2048)"


def write_test_certs(certdir):
    """
    Write the server certificate and two client certificates the server trusts at
    the TLS level, and return the SHA1 fingerprint of the first client certificate.
    """
    os.makedirs(certdir)
    _write_self_signed(certdir, "server", "localhost")
    _write_self_signed(certdir, "client_1", "client_1")
    return _write_self_signed(certdir, "client", "client_0")


def build_mqtt_server(accepted_certs=()):
    reactor = Clock()
    router_factory, server_factory, session_factory = make_router()
    router_factory._worker = RouterRealmContainer(router_factory)

    default_router = add_realm_to_router(router_factory, session_factory)
    router = add_realm_to_router(router_factory, session_factory, realm_name="mqtt", realm_options={})

    # allow everything
    default_permissions = {
        "uri": "",
        "match": "prefix",
        "allow": {"call": True, "register": True, "publish": True, "subscribe": True},
    }

    router.add_role(RouterRoleStaticAuth(router, "mqttrole", default_permissions=default_permissions))

    class AuthenticatorSession(ApplicationSession):
        @inlineCallbacks
        def onJoin(self, details):
            def authenticate(realm, authid, details):
                if authid == "test123":
                    if details["ticket"] != "password":
                        raise ApplicationError("com.example.invalid_ticket", "nope")

                    res = {"realm": "mqtt", "role": "mqttrole", "extra": {}}
                    return res

                else:
                    raise ApplicationError("com.example.no_such_user", "nah")

            yield self.register(authenticate, "com.example.auth")

            def tls(realm, authid, details):
                if "client_cert" not in details["transport"] or not details["transport"]["client_cert"]:
                    raise ApplicationError("com.example.no_cert", "no client certificate presented")

                client_cert = details["transport"]["client_cert"]
                sha1 = client_cert["sha1"]
                subject_cn = client_cert["subject"]["cn"]

                if sha1 not in accepted_certs:
                    raise ApplicationError("com.example.invalid_cert", "certificate with SHA1 {} denied".format(sha1))
                else:
                    return {"authid": subject_cn, "role": "mqttrole", "realm": "mqtt"}

            yield self.register(tls, "com.example.tls")

    config = ComponentConfig("default", {})
    authsession = AuthenticatorSession(config)
    session_factory.add(authsession, default_router, authrole="trusted")

    options = {
        "options": {
            "realm": "mqtt",
            "role": "mqttrole",
            "payload_mapping": {"": {"type": "native", "serializer": "json"}},
            "auth": {
                "ticket": {
                    "type": "dynamic",
                    "authenticator": "com.example.auth",
                    "authenticator-realm": "default",
                    "authenticator-role": "trusted",
                },
                "tls": {
                    "type": "dynamic",
                    "authenticator": "com.example.tls",
                    "authenticator-realm": "default",
                    "authenticator-role": "trusted",
                },
            },
        }
    }

    mqtt_factory = WampMQTTServerFactory(session_factory, options, reactor)

    server_factory._mqtt_factory = mqtt_factory

    return reactor, router, server_factory, session_factory


def connect_mqtt_server(server_factory):
    server_protocol = server_factory.buildProtocol(None)
    server_transport = FakeTransport(server_protocol, True)

    client_protocol = AccumulatingProtocol()
    client_transport = FakeTransport(client_protocol, False)

    mqtt_pump = connect(server_protocol, server_transport, client_protocol, client_transport, debug=False)

    return client_transport, client_protocol, mqtt_pump


class MQTTAdapterTests(TestCase):
    def setUp(self):
        self.logs = LogCapturer()
        self.logs.__enter__()
        self.addCleanup(lambda: self.logs.__exit__(None, None, None))

    def test_basic_publish(self):
        reactor, router, server_factory, session_factory = build_mqtt_server()

        session, pump = connect_application_session(
            server_factory,
            ObservingSession,
            component_config=ComponentConfig(realm="mqtt", controller=MockContainer()),
        )
        client_transport, client_protocol, mqtt_pump = connect_mqtt_server(server_factory)

        client_transport.write(
            Connect(
                client_id="testclient",
                username="test123",
                password="password",
                flags=ConnectFlags(clean_session=True, username=True, password=True),
            ).serialise()
        )
        mqtt_pump.flush()

        # We get a CONNECT
        self.assertEqual(client_protocol.data, ConnACK(session_present=False, return_code=0).serialise())
        client_protocol.data = b""

        client_transport.write(
            Publish(
                duplicate=False, qos_level=0, retain=False, topic_name="test", payload=b'{"kwargs": {"bar": "baz"}}'
            ).serialise()
        )
        mqtt_pump.flush()
        pump.flush()

        # This needs to be replaced with the real deal, see https://github.com/crossbario/crossbar/issues/885
        self.assertEqual(len(session.events), 1)
        self.assertEqual(session.events, [{"args": tuple(), "kwargs": {"bar": "baz"}}])

    @inlineCallbacks
    def _tls_connect(self, client_name, expected):
        """
        Connect a MQTT client over TLS with the client certificate client_name, send a
        Connect and a Publish, and check the server answers with exactly expected.

        This runs on the global reactor: the TLS handshake does not complete on a
        reactor of its own.
        """
        certdir = self.mktemp()
        client_sha1 = write_test_certs(certdir)
        port = get_free_tcp_port()
        reactor, router, server_factory, session_factory = build_mqtt_server(accepted_certs={client_sha1})
        logger = make_logger()

        session, pump = connect_application_session(
            server_factory,
            ObservingSession,
            component_config=ComponentConfig(realm="mqtt", controller=MockContainer()),
        )

        endpoint = create_listening_endpoint_from_config(
            {
                "type": "tcp",
                "port": port,
                "interface": "127.0.0.1",
                "tls": {
                    "certificate": "server.crt",
                    "key": "server.key",
                    "ca_certificates": ["client.crt", "client_1.crt"],
                },
            },
            certdir,
            global_reactor,
            logger,
        )

        client_endpoint = create_connecting_endpoint_from_config(
            {
                "type": "tcp",
                "host": "127.0.0.1",
                "port": port,
                "tls": {
                    "certificate": client_name + ".crt",
                    "hostname": "localhost",
                    "key": client_name + ".key",
                    "ca_certificates": ["server.crt"],
                },
            },
            certdir,
            global_reactor,
            logger,
        )

        received = Deferred()

        class TestProtocol(Protocol):
            data = b""

            def dataReceived(self_, data):
                self_.data = self_.data + data
                if len(self_.data) >= len(expected) and not received.called:
                    received.callback(self_.data)

        listening_port = yield endpoint.listen(server_factory)
        self.addCleanup(listening_port.stopListening)

        lc = LoopingCall(pump.flush)
        lc.start(0.01)
        self.addCleanup(lc.stop)

        client_protocol = yield client_endpoint.connect(Factory.forProtocol(TestProtocol))
        self.addCleanup(client_protocol.transport.loseConnection)

        client_protocol.transport.write(
            Connect(client_id="test123", flags=ConnectFlags(clean_session=True)).serialise()
        )
        client_protocol.transport.write(
            Publish(
                duplicate=False,
                qos_level=1,
                retain=False,
                topic_name="test",
                payload=b"{}",
                packet_identifier=1,
            ).serialise()
        )

        data = yield received
        self.assertEqual(data, expected)

        pump.flush()
        return session

    @inlineCallbacks
    def test_tls_auth(self):
        """
        A MQTT client can connect using mutually authenticated TLS
        authentication.
        """
        session = yield self._tls_connect(
            "client",
            ConnACK(session_present=False, return_code=0).serialise() + PubACK(packet_identifier=1).serialise(),
        )

        # This needs to be replaced with the real deal, see https://github.com/crossbario/crossbar/issues/885
        self.assertEqual(len(session.events), 1)
        self.assertEqual(session.events, [{"args": tuple(), "kwargs": {}}])

    test_tls_auth.timeout = 10  # type: ignore[attr-defined]
    test_tls_auth.skip = _SKIP_TLS  # type: ignore[attr-defined]

    @inlineCallbacks
    def test_tls_auth_denied(self):
        """
        A MQTT client offering the wrong certificate won't be authenticated.
        """
        # BAD key: trusted at the TLS level, but wrong ID
        session = yield self._tls_connect("client_1", ConnACK(session_present=False, return_code=1).serialise())

        # No events!
        self.assertEqual(session.events, [])

    test_tls_auth_denied.timeout = 10  # type: ignore[attr-defined]
    test_tls_auth_denied.skip = _SKIP_TLS  # type: ignore[attr-defined]

    def test_basic_subscribe(self):
        """
        The MQTT client can subscribe to a WAMP topic and get messages.
        """
        reactor, router, server_factory, session_factory = build_mqtt_server()
        client_transport, client_protocol, mqtt_pump = connect_mqtt_server(server_factory)

        session, pump = connect_application_session(
            server_factory,
            ApplicationSession,
            component_config=ComponentConfig(realm="mqtt", controller=MockContainer()),
        )

        client_transport.write(
            Connect(
                client_id="testclient",
                username="test123",
                password="password",
                flags=ConnectFlags(clean_session=True, username=True, password=True),
            ).serialise()
        )
        client_transport.write(
            Subscribe(
                packet_identifier=1, topic_requests=[SubscriptionTopicRequest(topic_filter="com/test/wamp", max_qos=0)]
            ).serialise()
        )

        mqtt_pump.flush()

        self.assertEqual(
            client_protocol.data,
            (
                ConnACK(session_present=False, return_code=0).serialise()
                + SubACK(packet_identifier=1, return_codes=[0]).serialise()
            ),
        )
        client_protocol.data = b""

        session.publish("com.test.wamp", "bar")
        pump.flush()

        reactor.advance(0.1)
        mqtt_pump.flush()

        self.assertEqual(
            client_protocol.data,
            Publish(
                duplicate=False, qos_level=0, retain=False, topic_name="com/test/wamp", payload=b'{"args":["bar"]}'
            ).serialise(),
        )

    def test_retained(self):
        """
        The MQTT client can set and receive retained messages.
        """
        reactor, router, server_factory, session_factory = build_mqtt_server()
        client_transport, client_protocol, mqtt_pump = connect_mqtt_server(server_factory)

        client_transport.write(
            Connect(
                client_id="testclient",
                username="test123",
                password="password",
                flags=ConnectFlags(clean_session=True, username=True, password=True),
            ).serialise()
        )

        client_transport.write(
            Publish(
                duplicate=False,
                qos_level=1,
                retain=True,
                topic_name="com/test/wamp",
                packet_identifier=123,
                payload=b"{}",
            ).serialise()
        )

        mqtt_pump.flush()

        self.assertEqual(
            client_protocol.data,
            (ConnACK(session_present=False, return_code=0).serialise() + PubACK(packet_identifier=123).serialise()),
        )
        client_protocol.data = b""

        client_transport.write(
            Subscribe(
                packet_identifier=1, topic_requests=[SubscriptionTopicRequest(topic_filter="com/test/wamp", max_qos=0)]
            ).serialise()
        )

        mqtt_pump.flush()

        self.assertEqual(client_protocol.data, SubACK(packet_identifier=1, return_codes=[0]).serialise())
        client_protocol.data = b""

        reactor.advance(0.1)
        mqtt_pump.flush()

        # This needs to be replaced with the real deal, see https://github.com/crossbario/crossbar/issues/885
        self.assertEqual(
            client_protocol.data,
            Publish(
                duplicate=False,
                qos_level=0,
                retain=True,
                topic_name="com/test/wamp",
                payload=json.dumps({}).encode("utf8"),
            ).serialise(),
        )

    def test_lastwill(self):
        """
        FIXME: reactivate this test.

        The MQTT client can set a last will message which will be published
        when it disconnects.
        """
        reactor, router, server_factory, session_factory = build_mqtt_server()
        session, pump = connect_application_session(
            server_factory,
            ObservingSession,
            component_config=ComponentConfig(realm="mqtt", controller=MockContainer()),
        )
        client_transport, client_protocol, mqtt_pump = connect_mqtt_server(server_factory)

        client_transport.write(
            Connect(
                client_id="testclient",
                username="test123",
                password="password",
                will_topic="test",
                will_message=b'{"args":["foobar"]}',
                flags=ConnectFlags(clean_session=True, username=True, password=True, will=True),
            ).serialise()
        )

        mqtt_pump.flush()

        # We get a CONNECT
        self.assertEqual(client_protocol.data, ConnACK(session_present=False, return_code=0).serialise())
        client_protocol.data = b""

        client_transport.write(Disconnect().serialise())

        mqtt_pump.flush()
        pump.flush()

        self.assertEqual(client_transport.disconnected, True)

        # This needs to be replaced with the real deal, see https://github.com/crossbario/crossbar/issues/885
        self.assertEqual(len(session.events), 1)
        self.assertEqual(session.events, [{"args": ("foobar",), "kwargs": {}}])
