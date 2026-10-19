#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import datetime
import os

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID
from OpenSSL import SSL
from twisted.trial import unittest
from txaio import make_logger

from crossbar.common.twisted.endpoint import _create_tls_server_context


def _write_self_signed(cbdir, key):
    """
    Write a self-signed server certificate for "localhost" and its key to cbdir.
    """
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    with open(os.path.join(cbdir, "server.key"), "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
    with open(os.path.join(cbdir, "server.crt"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def _handshake(server_ctx, max_version=None):
    """
    Run a TLS handshake in memory between a server using server_ctx and a client
    limited to max_version. Returns the negotiated protocol version name, or raises
    OpenSSL.SSL.Error when the handshake fails.
    """
    client_ctx = SSL.Context(SSL.TLS_CLIENT_METHOD)
    if max_version is not None:
        client_ctx.set_max_proto_version(max_version)
    server = SSL.Connection(server_ctx, None)
    server.set_accept_state()
    client = SSL.Connection(client_ctx, None)
    client.set_connect_state()

    done = {server: False, client: False}
    for _ in range(10):
        for conn in (client, server):
            if not done[conn]:
                try:
                    conn.do_handshake()
                    done[conn] = True
                except SSL.WantReadError:
                    pass
        for src, dst in ((client, server), (server, client)):
            try:
                dst.bio_write(src.bio_read(65536))
            except SSL.WantReadError:
                pass
        if all(done.values()):
            return client.get_protocol_version_name()
    raise RuntimeError("TLS handshake did not complete")


class TlsListenerTests(unittest.TestCase):
    """
    TLS listening endpoints accept TLS 1.3 only (#2325).
    """

    log = make_logger()

    def setUp(self):
        self.cbdir = self.mktemp()
        os.makedirs(self.cbdir)
        self.config = {"key": "server.key", "certificate": "server.crt"}

    def _server_ctx(self, config):
        return _create_tls_server_context(config, self.cbdir, self.log).getContext()

    def test_tls13_client_accepted_ecdsa(self):
        _write_self_signed(self.cbdir, ec.generate_private_key(ec.SECP256R1()))
        self.assertEqual(_handshake(self._server_ctx(self.config)), "TLSv1.3")

    def test_tls13_client_accepted_rsa(self):
        _write_self_signed(self.cbdir, rsa.generate_private_key(public_exponent=65537, key_size=2048))
        self.assertEqual(_handshake(self._server_ctx(self.config)), "TLSv1.3")

    def test_tls12_client_refused(self):
        _write_self_signed(self.cbdir, rsa.generate_private_key(public_exponent=65537, key_size=2048))
        self.assertRaises(SSL.Error, _handshake, self._server_ctx(self.config), SSL.TLS1_2_VERSION)

    def test_tls11_client_refused(self):
        _write_self_signed(self.cbdir, rsa.generate_private_key(public_exponent=65537, key_size=2048))
        self.assertRaises(SSL.Error, _handshake, self._server_ctx(self.config), SSL.TLS1_1_VERSION)

    def test_ciphers_do_not_enable_tls12(self):
        """
        An explicit "ciphers" setting (a TLS 1.2 cipher list) is still accepted, but does not
        re-enable TLS 1.2.
        """
        _write_self_signed(self.cbdir, rsa.generate_private_key(public_exponent=65537, key_size=2048))
        self.config["ciphers"] = "ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA"
        server_ctx = self._server_ctx(self.config)
        self.assertRaises(SSL.Error, _handshake, server_ctx, SSL.TLS1_2_VERSION)
        self.assertEqual(_handshake(server_ctx), "TLSv1.3")

    def test_dhparam_unused(self):
        """
        A "dhparam" setting is still accepted, but the file is not loaded: TLS 1.3 does not use it.
        """
        _write_self_signed(self.cbdir, rsa.generate_private_key(public_exponent=65537, key_size=2048))
        self.config["dhparam"] = "does-not-exist.pem"
        self.assertEqual(_handshake(self._server_ctx(self.config)), "TLSv1.3")
