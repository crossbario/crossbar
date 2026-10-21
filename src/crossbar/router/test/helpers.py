#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import datetime
import os

from autobahn.twisted.wamp import ApplicationSessionFactory, WampRawSocketClientFactory

# from autobahn.twisted.wamp import WampWebSocketClientFactory
from autobahn.wamp.types import ComponentConfig
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from twisted.internet.defer import succeed
from twisted.test.iosim import FakeTransport, connect

from crossbar.personality import Personality
from crossbar.router.protocol import WampRawSocketServerFactory, WampWebSocketServerFactory
from crossbar.router.role import RouterRoleStaticAuth
from crossbar.router.router import RouterFactory
from crossbar.router.service import RouterServiceAgent
from crossbar.router.session import RouterSessionFactory
from crossbar.router.unisocket import UniSocketServerFactory
from crossbar.worker.types import RouterRealm


def make_router():
    """
    Make a router, and return it and a RawSocket factory.
    """
    # create a router factory
    router_factory = RouterFactory("node1", "worker1", None)

    # create a router session factory
    session_factory = RouterSessionFactory(router_factory)

    # Create a new WebSocket factory
    websocket_server_factory = WampWebSocketServerFactory(session_factory, ".", {}, None)

    # Create a new RawSocket factory
    rawsocket_server_factory = WampRawSocketServerFactory(session_factory, {})

    # Create a new UniSocket factory
    server_factory = UniSocketServerFactory(
        websocket_factory_map={"/": websocket_server_factory}, rawsocket_factory=rawsocket_server_factory
    )

    return router_factory, server_factory, session_factory


def add_realm_to_router(router_factory, session_factory, realm_name="default", realm_options={}):
    opts = dict(realm_options)
    opts.update({"name": realm_name})

    # start a realm
    realm = RouterRealm(None, None, opts)
    router = router_factory.start_realm(realm)

    extra = {}
    session_config = ComponentConfig(realm_name, extra)
    realm.session = RouterServiceAgent(session_config, router)

    # allow everything
    default_permissions = {
        "uri": "",
        "match": "prefix",
        "allow": {"call": True, "register": True, "publish": True, "subscribe": True},
    }

    router = router_factory.get(realm_name)
    router.add_role(RouterRoleStaticAuth(router, "anonymous", default_permissions=default_permissions))

    session_factory.add(realm.session, router, authrole="trusted")

    return router


def make_router_and_realm(realm_name="default"):
    router_factory, server_factory, session_factory = make_router()
    router = add_realm_to_router(router_factory, session_factory, realm_name)
    return router, server_factory, session_factory


def connect_application_session(server_factory, MyApplicationSession, component_config=None):
    """
    Connect an ApplicationSession class to the given server factory.
    """
    application_session_factory = ApplicationSessionFactory(component_config)
    application_session_factory.session = MyApplicationSession

    client_factory = WampRawSocketClientFactory(application_session_factory)
    # client_factory = WampWebSocketClientFactory(application_session_factory)

    server_protocol = server_factory.buildProtocol(None)
    client_protocol = client_factory.buildProtocol(None)

    server_transport = FakeTransport(server_protocol, True)
    client_transport = FakeTransport(client_protocol, False)

    pump = connect(server_protocol, server_transport, client_protocol, client_transport, debug=False)

    return client_protocol._session, pump


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


def write_self_signed_cert(certdir, name, cn):
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
