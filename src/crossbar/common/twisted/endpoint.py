#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
from os import environ
from os.path import abspath, exists, isabs, join

import txtorcon
from twisted.internet import defer
from twisted.internet._sslverify import OpenSSLCertificateAuthorities
from twisted.internet.endpoints import (
    TCP4ClientEndpoint,
    TCP4ServerEndpoint,
    TCP6ClientEndpoint,
    TCP6ServerEndpoint,
    UNIXClientEndpoint,
    UNIXServerEndpoint,
    clientFromString,
    serverFromString,
)
from twisted.internet.interfaces import ILoggingContext, IStreamServerEndpoint
from twisted.internet.protocol import Protocol
from twisted.internet.ssl import (
    Certificate,
    CertificateOptions,
    KeyPair,
    PrivateCertificate,
    optionsForClientTLS,
)
from twisted.protocols.policies import ProtocolWrapper, WrappingFactory
from twisted.python.filepath import FilePath
from zope.interface import implementer

from crossbar._util import first_free_tcp_port, get_free_tcp_port
from crossbar.common.twisted.sharedport import CustomTCPPort, CustomTCPTLSPort

try:
    # import OpenSSL
    from OpenSSL import crypto

    # from OpenSSL.SSL import OP_NO_SSLv3, OP_NO_TLSv1
    from twisted.internet._sslverify import TLSVersion
    from twisted.internet.endpoints import SSL4ClientEndpoint, SSL4ServerEndpoint
    from twisted.internet.interfaces import ISSLTransport  # noqa
    from twisted.protocols.tls import TLSMemoryBIOFactory

    _HAS_TLS = True
    _LACKS_TLS_MSG = None
except ImportError as e:
    _HAS_TLS = False
    _LACKS_TLS_MSG = "{}".format(e)

__all__ = (
    "create_listening_endpoint_from_config",
    "create_listening_port_from_config",
    "create_connecting_endpoint_from_config",
    "create_connecting_port_from_config",
)


def _unwrapped_log_prefix(obj):
    """
    The log prefix of ``obj``, the same as Twisted computes it for a port or connection.
    """
    if ILoggingContext.providedBy(obj):
        return obj.logPrefix()
    return obj.__class__.__name__


class _CountedConnection(ProtocolWrapper):
    """
    Counts a connection on a :class:`MaxConnectionsFactory`.

    It hands the real transport to the wrapped protocol, so that protocol sees the same transport
    as without a connection cap (e.g. the TLS transport for TLS channel binding). Protocols that
    take over a connection (WebSocket upgrade on a Web transport) replace ``wrappedProtocol``,
    so the connection stays counted until it is closed.
    """

    def makeConnection(self, transport):
        Protocol.makeConnection(self, transport)
        self.factory.registerProtocol(self)
        self.wrappedProtocol.makeConnection(transport)

    def logPrefix(self):
        return _unwrapped_log_prefix(self.wrappedProtocol)


class _RefusedConnection(Protocol):
    """
    Closes a connection refused because the listening port is at its connection cap.
    """

    def connectionMade(self):
        self.transport.abortConnection()


class MaxConnectionsFactory(WrappingFactory):
    """
    The outermost factory of a listening port: refuses new connections while ``max_connections``
    connections are open (#2324). A refused connection is closed right after accept, before any
    TLS, WebSocket or RawSocket handshake.
    """

    protocol = _CountedConnection

    # log refusals at most every LOG_INTERVAL seconds
    LOG_INTERVAL = 10.0

    def __init__(self, wrappedFactory, max_connections, name, reactor, log):
        WrappingFactory.__init__(self, wrappedFactory)
        self.max_connections = max_connections
        self._name = name
        self._reactor = reactor
        self._log = log
        self._refused = 0
        self._last_logged = None

    def logPrefix(self):
        # log as the wrapped factory, so that log lines such as "<factory> starting on <port>"
        # are the same as without the connection cap
        return _unwrapped_log_prefix(self.wrappedFactory)

    def buildProtocol(self, addr):
        if len(self.protocols) < self.max_connections:
            return WrappingFactory.buildProtocol(self, addr)

        self._refused += 1
        now = self._reactor.seconds()
        if self._last_logged is None or now - self._last_logged >= self.LOG_INTERVAL:
            self._log.warn(
                "Listening port {name} refused {refused} connection(s): max_connections={max_connections} reached",
                name=self._name,
                refused=self._refused,
                max_connections=self.max_connections,
            )
            self._refused = 0
            self._last_logged = now
        protocol = _RefusedConnection()
        protocol.factory = self
        return protocol


def _create_tls_server_context(config, cbdir, log):
    """
    Create a CertificateOptions object for use with TLS listening endpoints.
    """
    # server private key
    key_filepath = abspath(join(cbdir, config["key"]))
    log.info("Loading server TLS key from {key_filepath}", key_filepath=key_filepath)
    with open(key_filepath) as key_file:
        # server certificate (but only the server cert, no chain certs)
        cert_filepath = abspath(join(cbdir, config["certificate"]))
        log.info("Loading server TLS certificate from {cert_filepath}", cert_filepath=cert_filepath)
        with open(cert_filepath) as cert_file:
            key = KeyPair.load(key_file.read(), crypto.FILETYPE_PEM).original
            cert = Certificate.loadPEM(cert_file.read()).original

    # list of certificates that complete your verification chain
    extra_certs = None
    if "chain_certificates" in config:
        extra_certs = []
        for fname in config["chain_certificates"]:
            extra_cert_filepath = abspath(join(cbdir, fname))
            with open(extra_cert_filepath, "r") as f:
                extra_certs.append(Certificate.loadPEM(f.read()).original)
            log.info(
                "Loading server TLS chain certificate from {extra_cert_filepath}",
                extra_cert_filepath=extra_cert_filepath,
            )

    # list of certificate authority certificate objects to use to verify the peer's certificate
    ca_certs = None
    if "ca_certificates" in config:
        ca_certs = []
        for fname in config["ca_certificates"]:
            ca_cert_filepath = abspath(join(cbdir, fname))
            with open(ca_cert_filepath, "r") as f:
                ca_certs.append(Certificate.loadPEM(f.read()).original)
            log.info("Loading server TLS CA certificate from {ca_cert_filepath}", ca_cert_filepath=ca_cert_filepath)

    # TLS 1.3 only (#2325): TLS 1.3 has only AEAD cipher suites with forward secrecy and no
    # DH parameters, so the TLS 1.2 settings "ciphers" and "dhparam" have no effect. They are
    # still accepted in the configuration, so existing node configurations keep working.
    for unused in ("ciphers", "dhparam"):
        if unused in config:
            log.info("TLS 1.3 only listener: ignoring TLS 1.2 setting '{unused}'", unused=unused)

    ctx = CertificateOptions(
        privateKey=key,
        certificate=cert,
        extraCertChain=extra_certs,
        verify=(ca_certs is not None),
        caCerts=ca_certs,
        # Only allow TLS 1.3 (#2325)
        #
        # We are using Twisted private stuff (from twisted.internet._sslverify import TLSVersion),
        # as the OpenSSL.SSL method constants wont work:
        #
        # [ERROR] File "../twisted/internet/_sslverify.py", line 1530, in __init__
        #    if raiseMinimumTo > self._defaultMinimumTLSVersion:
        #       builtins.TypeError: '>' not supported between instances of 'int' and 'NamedConstant'
        #
        raiseMinimumTo=TLSVersion.TLSv1_3,
        # TLS hardening
        enableSingleUseKeys=True,
        enableSessions=False,
        enableSessionTickets=False,
        fixBrokenPeers=False,
    )

    # Without a curve being set, ECDH won't be available even if listed
    # in acceptable ciphers!
    #
    # The curves available in OpenSSL can be listed:
    #
    #   openssl ecparam -list_curves
    #
    # prime256v1: X9.62/SECG curve over a 256 bit prime field
    #
    # This is elliptic curve "NIST P-256" from here
    # http://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.186-4.pdf
    #
    # This seems to be the most widely used curve
    #
    # http://crypto.stackexchange.com/questions/11310/with-openssl-and-ecdhe-how-to-show-the-actual-curve-being-used
    #
    # and researchers think it is "ok" (other than wrt timing attacks etc)
    #
    # https://twitter.com/hyperelliptic/status/394258454342148096
    #
    if False:
        # FIXME: this doesn't work anymore with Twisted 18.4. (there now seems more complex machinery
        # in self._ecChooser)
        if ctx._ecCurve is None:
            log.warn("No OpenSSL elliptic curve set - EC cipher modes will be deactive!")
        else:
            if ctx._ecCurve.snName != "prime256v1":
                log.info("OpenSSL is using elliptic curve {curve}", curve=ctx._ecCurve.snName)
            else:
                log.info("OpenSSL is using elliptic curve prime256v1 (NIST P-256)")

    return ctx


def _create_tls_client_context(config, cbdir, log):
    """
    Create a CertificateOptions object for use with TLS connecting endpoints.
    """
    # server hostname: The expected name of the remote host.
    hostname = config["hostname"]

    # explicit trust (certificate) root
    ca_certs = None
    if "ca_certificates" in config:
        log.debug(
            "TLS client using explicit trust ({cnt_certs} certificates)", cnt_certs=len(config["ca_certificates"])
        )
        ca_certs = []
        for cert_fname in [os.path.abspath(os.path.join(cbdir, x)) for x in (config["ca_certificates"])]:
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(cert_fname, "rb").read())
            log.debug("TLS client trust root CA certificate loaded from '{fname}'", fname=cert_fname)
            ca_certs.append(cert)
        ca_certs = OpenSSLCertificateAuthorities(ca_certs)
    else:
        log.debug("TLS client using platform trust")

    # client key/cert to use
    client_cert = None
    if "key" in config:
        if "certificate" not in config:
            raise Exception("TLS client key present, but certificate missing")

        key_fname = os.path.abspath(os.path.join(cbdir, config["key"]))
        with open(key_fname, "r") as f:
            private_key = KeyPair.load(f.read(), format=crypto.FILETYPE_PEM)
            log.debug("Loaded client TLS key from '{key_fname}'", key_fname=key_fname)

        cert_fname = os.path.abspath(os.path.join(cbdir, config["certificate"]))
        with open(cert_fname, "r") as f:
            cert = Certificate.loadPEM(
                f.read(),
            )
            log.debug(
                "Loaded client TLS certificate from '{cert_fname}' (cn='{cert_cn}', sha256={cert_sha256}..)",
                cert_fname=cert_fname,
                cert_cn=cert.getSubject().CN,
                cert_sha256=cert.digest("sha256")[:12],
            )

        client_cert = PrivateCertificate.fromCertificateAndKeyPair(cert, private_key)
    else:
        if "certificate" in config:
            log.warn("TLS client certificate present, but key is missing")

    # create TLS client context
    ctx = optionsForClientTLS(hostname, trustRoot=ca_certs, clientCertificate=client_cert)

    return ctx


def _ensure_absolute(fname, cbdir):
    if isabs(fname):
        return fname
    return abspath(join(cbdir, fname))


def create_listening_endpoint_from_config(config, cbdir, reactor, log):
    """
    Create a Twisted stream server endpoint from a Crossbar.io transport configuration.

    See: https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IStreamServerEndpoint.html

    :param config: The transport configuration.
    :type config: dict
    :param cbdir: Crossbar.io node directory (we need this for TLS key/certificates).
    :type cbdir: str
    :param reactor: The reactor to use for endpoint creation.
    :type reactor: obj

    :returns obj -- An instance implementing IStreamServerEndpoint
    """
    endpoint = None

    # a TCP endpoint
    #
    if config["type"] == "tcp":
        # the TCP protocol version (v4 or v6)
        #
        version = int(config.get("version", 4))

        # the listening port
        if isinstance(config["port"], str):
            # read port from environment variable ..
            try:
                port = int(environ[config["port"][1:]])
            except Exception as e:
                log.warn("Could not read listening port from env var: {e}", e=e)
                raise
        else:
            port = config["port"]

        # the listening interface
        #
        interface = str(config.get("interface", "").strip())

        # the TCP accept queue depth
        #
        backlog = int(config.get("backlog", 50))

        if "tls" in config:
            # create a TLS server endpoint
            #
            if _HAS_TLS:
                # TLS server context
                context = _create_tls_server_context(config["tls"], cbdir, log)

                if version == 4:
                    endpoint = SSL4ServerEndpoint(reactor, port, context, backlog=backlog, interface=interface)
                elif version == 6:
                    raise Exception("TLS on IPv6 not implemented")
                else:
                    raise Exception("invalid TCP protocol version {}".format(version))
            else:
                raise Exception("TLS transport requested, but TLS packages not available:\n{}".format(_LACKS_TLS_MSG))

        else:
            # create a non-TLS server endpoint
            #
            if version == 4:
                endpoint = TCP4ServerEndpoint(reactor, port, backlog=backlog, interface=interface)
            elif version == 6:
                endpoint = TCP6ServerEndpoint(reactor, port, backlog=backlog, interface=interface)
            else:
                raise Exception("invalid TCP protocol version {}".format(version))

    # a Unix Domain Socket endpoint
    #
    elif config["type"] == "unix":
        # the accept queue depth
        #
        backlog = int(config.get("backlog", 50))

        # the path
        #
        path = FilePath(join(cbdir, os.path.expandvars(config["path"])))

        # if there is already something there, delete it.
        #
        if path.exists():
            log.info(("{path} exists, attempting to remove before using as a UNIX socket"), path=path)
            path.remove()

        # create the endpoint
        #
        endpoint = UNIXServerEndpoint(reactor, path.path, backlog=backlog)

    # twisted endpoint-string
    elif config["type"] == "twisted":
        endpoint = serverFromString(reactor, config["server_string"])

    # tor endpoint
    elif config["type"] == "onion":  # or "tor"? r "tor_onion"?
        port = config["port"]
        private_key_fname = _ensure_absolute(config["private_key_file"], cbdir)
        tor_control_ep = create_connecting_endpoint_from_config(config["tor_control_endpoint"], cbdir, reactor, log)
        version = config.get("version", 3)  # default to modern version 3

        try:
            with open(private_key_fname, "r") as f:
                private_key = f.read().strip()
            log.info(
                "Onion private key from '{private_key_fname}'",
                private_key_fname=private_key_fname,
            )
        except (IOError, OSError):
            private_key = None

        @implementer(IStreamServerEndpoint)
        class _EphemeralOnion(object):
            @defer.inlineCallbacks
            def listen(self, proto_factory):
                # we don't care which local TCP port we listen on, but
                # we do need to know it
                local_ep = TCP4ServerEndpoint(reactor, 0, interface="127.0.0.1")
                target_port = yield local_ep.listen(proto_factory)
                tor = yield txtorcon.connect(
                    reactor,
                    tor_control_ep,
                )

                log.info("Creating onion service (descriptor upload can take 30s or more)")
                hs = yield tor.create_onion_service(
                    ports=[
                        (port, target_port.getHost().port),
                    ],
                    private_key=private_key,
                    version=version,
                )

                # if it's new, store our private key
                # XXX better "if private_key is None"?
                if not exists(private_key_fname):
                    with open(private_key_fname, "w") as f:
                        f.write(hs.private_key)
                    log.info("Wrote private key to '{fname}'", fname=private_key_fname)

                log.info(
                    "Listening on Tor onion service {hs.hostname}  with ports: {ports}",
                    hs=hs,
                    ports=" ".join(hs.ports),
                )
                defer.returnValue(target_port)

        endpoint = _EphemeralOnion()

    else:
        raise Exception("invalid endpoint type '{}'".format(config["type"]))

    return endpoint


def create_listening_port_from_config(config, cbdir, factory, reactor, log, max_connections=None, name=None):
    """
    Create a Twisted listening port from a Crossbar.io transport configuration.

    See: https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IListeningPort.html

    :param config: The transport configuration.
    :type config: dict
    :param factory: The transport factory to use (a provider of IProtocolFactory).
    :type factory: obj
    :param cbdir: Crossbar.io node directory (we need this for TLS key/certificates).
    :type cbdir: str
    :param reactor: The reactor to use for endpoint creation.
    :type reactor: obj
    :param max_connections: When set, the port refuses connections while this many are open.
    :type max_connections: int or None
    :param name: The name of the listening port in log messages.
    :type name: str or None

    :returns obj -- A Deferred that results in an IListeningPort or an CannotListenError
    """

    if "portrange" in config:
        # first free port in given range
        config["port"] = first_free_tcp_port(host=config.get("interface", ""), portrange=config["portrange"])
    else:
        if "port" not in config or config["port"] is None:
            # random free port
            config["port"] = get_free_tcp_port(host=config.get("interface", ""))

    # the connection cap is the outermost layer of the listening port (#2324), so TLS is
    # layered inside it here (the same as Twisted's listenSSL), and the port is a plain TCP port
    if max_connections is not None:
        if "tls" in config:
            if not _HAS_TLS:
                raise Exception("TLS transport requested, but TLS packages not available:\n{}".format(_LACKS_TLS_MSG))
            context = _create_tls_server_context(config["tls"], cbdir, log)
            factory = TLSMemoryBIOFactory(context, False, factory)
            config = {k: v for k, v in config.items() if k != "tls"}
        factory = MaxConnectionsFactory(factory, max_connections, name, reactor, log)

    # the TCP socket sharing option
    #
    shared = config.get("shared", False)

    # the TCP socket user timeout option
    #
    user_timeout = config.get("user_timeout", None)

    if config["type"] == "tcp" and (shared or user_timeout is not None):
        # the TCP protocol version (v4 or v6)
        #
        version = int(config.get("version", 4))

        # the listening interface
        #
        interface = str(config.get("interface", "").strip())

        # the listening port
        #
        port = int(config["port"])

        # the TCP accept queue depth
        #
        backlog = int(config.get("backlog", 50))

        # create a listening port
        #
        if "tls" in config:
            if _HAS_TLS:
                # TLS server context
                context = _create_tls_server_context(config["tls"], cbdir, log)

                if version == 4:
                    listening_port = CustomTCPTLSPort(
                        port, factory, context, backlog, interface, reactor, shared=shared, user_timeout=user_timeout
                    )
                elif version == 6:
                    raise Exception("TLS on IPv6 not implemented")
                else:
                    raise Exception("invalid TCP protocol version {}".format(version))
            else:
                raise Exception("TLS transport requested, but TLS packages not available:\n{}".format(_LACKS_TLS_MSG))
        else:
            listening_port = CustomTCPPort(
                port, factory, backlog, interface, reactor, shared=shared, user_timeout=user_timeout
            )

        try:
            listening_port.startListening()
            return defer.succeed(listening_port)
        except Exception as e:
            return defer.fail(e)

    else:
        try:
            endpoint = create_listening_endpoint_from_config(config, cbdir, reactor, log)
            return endpoint.listen(factory)
        except Exception:
            return defer.fail()


def create_connecting_endpoint_from_config(config, cbdir, reactor, log):
    """
    Create a Twisted stream client endpoint from a Crossbar.io transport configuration.

    See: https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IStreamClientEndpoint.html

    :param config: The transport configuration.
    :type config: dict
    :param cbdir: Crossbar.io node directory (we need this for Unix domain socket paths and TLS key/certificates).
    :type cbdir: str
    :param reactor: The reactor to use for endpoint creation.
    :type reactor: obj

    :returns obj -- An instance implementing IStreamClientEndpoint
    """
    endpoint = None

    # a TCP endpoint
    #
    if config["type"] == "tcp":
        # the TCP protocol version (v4 or v6)
        #
        version = int(config.get("version", 4))

        # the host to connect to
        #
        host = str(config["host"])

        # the port to connect to
        #
        port = int(config["port"])

        # connection timeout in seconds
        #
        timeout = int(config.get("timeout", 10))

        if "tls" in config:
            # create a TLS client endpoint
            #
            if _HAS_TLS:
                # TLS client context
                context = _create_tls_client_context(config["tls"], cbdir, log)

                if version == 4:
                    endpoint = SSL4ClientEndpoint(
                        reactor,
                        host,
                        port,
                        context,
                        timeout=timeout,
                    )
                elif version == 6:
                    raise Exception("TLS on IPv6 not implemented")
                else:
                    raise Exception("invalid TCP protocol version {}".format(version))

            else:
                raise Exception("TLS transport requested, but TLS packages not available:\n{}".format(_LACKS_TLS_MSG))

        else:
            # create a non-TLS client endpoint
            #
            if version == 4:
                endpoint = TCP4ClientEndpoint(reactor, host, port, timeout=timeout)
            elif version == 6:
                endpoint = TCP6ClientEndpoint(reactor, host, port, timeout=timeout)
            else:
                raise Exception("invalid TCP protocol version {}".format(version))

    # a Unix Domain Socket endpoint
    #
    elif config["type"] == "unix":
        # the path
        #
        path = abspath(join(cbdir, config["path"]))

        # connection timeout in seconds
        #
        timeout = int(config.get("timeout", 10))

        # create the endpoint
        #
        endpoint = UNIXClientEndpoint(reactor, path, timeout=timeout)

    elif config["type"] == "twisted":
        endpoint = clientFromString(reactor, config["client_string"])

    elif config["type"] == "tor":
        host = config["host"]
        port = config["port"]
        socks_port = config["tor_socks_port"]
        tls = config.get("tls", False)
        if not tls and not host.endswith(".onion"):
            log.warn("Non-TLS connection traversing Tor network; end-to-end encryption advised")

        socks_endpoint = TCP4ClientEndpoint(
            reactor,
            "127.0.0.1",
            socks_port,
        )
        endpoint = txtorcon.TorClientEndpoint(
            host,
            port,
            socks_endpoint=socks_endpoint,
            reactor=reactor,
            use_tls=tls,
        )

    else:
        raise Exception("invalid endpoint type '{}'".format(config["type"]))

    return endpoint


def create_connecting_port_from_config(config, cbdir, factory, reactor, log):
    """
    Create a Twisted connecting port from a Crossbar.io transport configuration.

    See: https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IListeningPort.html

    :param config: The transport configuration.
    :type config: dict
    :param factory: The transport factory to use (a provider of IProtocolFactory).
    :type factory: obj
    :param cbdir: Crossbar.io node directory (we need this for Unix domain socket paths and TLS key/certificates).
    :type cbdir: str
    :param reactor: The reactor to use for endpoint creation.
    :type reactor: obj

    :returns obj -- A Deferred that results in an IProtocol upon successful connection otherwise a ConnectError
    """
    endpoint = create_connecting_endpoint_from_config(config, cbdir, reactor, log)
    return endpoint.connect(factory)
