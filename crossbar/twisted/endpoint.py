#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import, division

import six
from os import environ
from os.path import join, abspath

from twisted.internet import defer
from twisted.internet._sslverify import OpenSSLCertificateAuthorities
from twisted.internet.ssl import CertificateOptions, PrivateCertificate, Certificate, KeyPair
from twisted.internet.ssl import optionsForClientTLS, DiffieHellmanParameters
from twisted.internet.ssl import AcceptableCiphers
from twisted.internet.endpoints import TCP4ServerEndpoint, \
    TCP6ServerEndpoint, \
    TCP4ClientEndpoint, \
    TCP6ClientEndpoint, \
    UNIXServerEndpoint, \
    UNIXClientEndpoint
from twisted.python.filepath import FilePath

from crossbar._logging import make_logger
from crossbar.twisted.sharedport import SharedPort

try:
    from twisted.internet.endpoints import SSL4ServerEndpoint, \
        SSL4ClientEndpoint
    from OpenSSL import crypto
    _HAS_TLS = True
    _LACKS_TLS_MSG = None
except ImportError as e:
    _HAS_TLS = False
    _LACKS_TLS_MSG = "{}".format(e)

__all__ = ('create_listening_endpoint_from_config',
           'create_listening_port_from_config',
           'create_connecting_endpoint_from_config',
           'create_connecting_port_from_config')


def create_listening_endpoint_from_config(config, cbdir, reactor):
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
    log = make_logger()
    endpoint = None

    # a TCP endpoint
    #
    if config['type'] == 'tcp':

        # the TCP protocol version (v4 or v6)
        #
        version = int(config.get('version', 4))

        # the listening port
        #
        if type(config['port']) is six.text_type:
            # read port from environment variable ..
            try:
                port = int(environ[config['port'][1:]])
            except Exception as e:
                print("Could not read listening port from env var: {}".format(e))
                raise e
        else:
            port = config['port']

        # the listening interface
        #
        interface = str(config.get('interface', '').strip())

        # the TCP accept queue depth
        #
        backlog = int(config.get('backlog', 50))

        if 'tls' in config:
            if _HAS_TLS:
                # server private key
                key_filepath = abspath(join(cbdir, config['tls']['key']))
                log.info("Loading server TLS key from {key_filepath}", key_filepath=key_filepath)

                # server certificate (but only the server cert, no chain certs)
                cert_filepath = abspath(join(cbdir, config['tls']['certificate']))
                log.info("Loading server TLS certificate from {cert_filepath}", cert_filepath=cert_filepath)

                with open(key_filepath) as key_file:
                    with open(cert_filepath) as cert_file:

                        if 'dhparam' in config['tls']:
                            dhpath = FilePath(
                                abspath(join(cbdir, config['tls']['dhparam']))
                            )
                            dh_params = DiffieHellmanParameters.fromFile(dhpath)
                        else:
                            # XXX won't be doing ANY EDH
                            # curves... maybe make dhparam required?
                            # or do "whatever tlsctx was doing"
                            dh_params = None
                            log.warn("OpenSSL DH modes not active (no 'dhparam')")

                        # create a TLS context factory
                        # see: https://twistedmatrix.com/documents/current/api/twisted.internet.ssl.CertificateOptions.html

                        # server key/cert
                        key = KeyPair.load(key_file.read(), crypto.FILETYPE_PEM).original
                        cert = Certificate.loadPEM(cert_file.read()).original

                        # list of certificates that complete your verification chain
                        extra_certs = None
                        if 'chain_certificates' in config['tls']:
                            extra_certs = []
                            for fname in config['tls']['chain_certificates']:
                                extra_cert_filepath = abspath(join(cbdir, fname))
                                with open(extra_cert_filepath, 'r') as f:
                                    extra_certs.append(Certificate.loadPEM(f.read()).original)
                                log.info("Loading server TLS chain certificate from {extra_cert_filepath}", extra_cert_filepath=extra_cert_filepath)

                        # list of certificate authority certificate objects to use to verify the peer's certificate
                        ca_certs = None
                        if 'ca_certificates' in config['tls']:
                            ca_certs = []
                            for fname in config['tls']['ca_certificates']:
                                ca_cert_filepath = abspath(join(cbdir, fname))
                                with open(ca_cert_filepath, 'r') as f:
                                    ca_certs.append(Certificate.loadPEM(f.read()).original)
                                log.info("Loading server TLS CA certificate from {extra_cert_filepath}", extra_cert_filepath=extra_cert_filepath)

                        # ciphers we accept
                        #
                        # We prefer to make every single cipher (6 in total) _explicit_ (to reduce chances either we or the pattern-matching
                        # language inside OpenSSL messes up) and drop support for Windows XP (we do WebSocket anyway).
                        #
                        # We don't use AES256 and SHA384, to reduce number of ciphers and since the additional
                        # security gain seems not worth the additional performance drain.
                        #
                        # We also don't use ECDSA, since EC certificates a rare in the wild.
                        #
                        # References:
                        #  * https://www.ssllabs.com/ssltest/analyze.html?d=myserver.com
                        #  * http://hynek.me/articles/hardening-your-web-servers-ssl-ciphers/
                        #  * http://www.openssl.org/docs/apps/ciphers.html#CIPHER_LIST_FORMAT
                        #  * https://wiki.mozilla.org/Talk:Security/Server_Side_TLS
                        #
                        if 'ciphers' in config['tls']:
                            crossbar_ciphers = AcceptableCiphers.fromOpenSSLCipherString(config['tls']['ciphers'])
                        else:
                            crossbar_ciphers = AcceptableCiphers.fromOpenSSLCipherString(
                                # AEAD modes (GCM)
                                # 'ECDHE-ECDSA-AES128-GCM-SHA256:'
                                'ECDHE-RSA-AES128-GCM-SHA256:'
                                # 'ECDHE-ECDSA-AES256-GCM-SHA384:'
                                # 'ECDHE-RSA-AES256-GCM-SHA384:'
                                'DHE-RSA-AES128-GCM-SHA256:'
                                # 'DHE-RSA-AES256-GCM-SHA384:'

                                # CBC modes
                                'ECDHE-RSA-AES128-SHA256:'
                                'DHE-RSA-AES128-SHA256:'
                                'ECDHE-RSA-AES128-SHA:'
                                'DHE-RSA-AES128-SHA:'
                            )

                        ctx = CertificateOptions(
                            privateKey=key,
                            certificate=cert,
                            extraCertChain=extra_certs,
                            verify=(ca_certs is not None),
                            caCerts=ca_certs,
                            dhParameters=dh_params,
                            acceptableCiphers=crossbar_ciphers,
                        )

                        # Without a curve being set, ECDH won't be available even if listed
                        # in acceptable ciphers!
                        #
                        # The curves available in OpenSSL can be listed: openssl ecparam -list_curves
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
                        if ctx._ecCurve is None:
                            log.warn("OpenSSL failed to set default elliptic curve - EC-modes will be unavailable!")
                        else:
                            if ctx._ecCurve.snName != "prime256v1":
                                log.info("OpenSSL is using elliptic curve {curve}", curve=ctx._ecCurve.snName)
                            else:
                                log.info("OpenSSL is using most common elliptic curve (prime256v1 / NIST P-256)")

                # create a TLS server endpoint
                #
                if version == 4:
                    endpoint = SSL4ServerEndpoint(reactor,
                                                  port,
                                                  ctx,
                                                  backlog=backlog,
                                                  interface=interface)
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
                endpoint = TCP4ServerEndpoint(reactor,
                                              port,
                                              backlog=backlog,
                                              interface=interface)
            elif version == 6:
                endpoint = TCP6ServerEndpoint(reactor,
                                              port,
                                              backlog=backlog,
                                              interface=interface)
            else:
                raise Exception("invalid TCP protocol version {}".format(version))

    # a Unix Domain Socket endpoint
    #
    elif config['type'] == 'unix':

        # the accept queue depth
        #
        backlog = int(config.get('backlog', 50))

        # the path
        #
        path = FilePath(join(cbdir, config['path']))

        # if there is already something there, delete it.
        #
        if path.exists():
            log.info(("{path} exists, attempting to remove before using as a "
                     "UNIX socket"), path=path)
            path.remove()

        # create the endpoint
        #
        endpoint = UNIXServerEndpoint(reactor, path.path, backlog=backlog)

    else:
        raise Exception("invalid endpoint type '{}'".format(config['type']))

    return endpoint


def create_listening_port_from_config(config, factory, cbdir, reactor):
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

    :returns obj -- A Deferred that results in an IListeningPort or an CannotListenError
    """
    if config['type'] == 'tcp' and config.get('shared', False):

        # the TCP protocol version (v4 or v6)
        # FIXME: handle v6
        # version = int(config.get('version', 4))

        # the listening port
        #
        port = int(config['port'])

        # the listening interface
        #
        interface = str(config.get('interface', '').strip())

        # the TCP accept queue depth
        #
        backlog = int(config.get('backlog', 50))

        listening_port = SharedPort(port, factory, backlog, interface, reactor, shared=True)
        try:
            listening_port.startListening()
            return defer.succeed(listening_port)
        except Exception as e:
            return defer.fail(e)

    else:
        try:
            endpoint = create_listening_endpoint_from_config(config, cbdir, reactor)
            return endpoint.listen(factory)
        except Exception:
            return defer.fail()


def create_connecting_endpoint_from_config(config, cbdir, reactor):
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
    log = make_logger()

    # a TCP endpoint
    #
    if config['type'] == 'tcp':

        # the TCP protocol version (v4 or v6)
        #
        version = int(config.get('version', 4))

        # the host to connect to
        #
        host = str(config['host'])

        # the port to connect to
        #
        port = int(config['port'])

        # connection timeout in seconds
        #
        timeout = int(config.get('timeout', 10))

        if 'tls' in config:
            if _HAS_TLS:
                # if the config specified any CA certificates, we use those (only!)
                if 'ca_certificates' in config['tls']:
                    ca_certs = []
                    for cert_fname in config['tls']['ca_certificates']:
                        cert = crypto.load_certificate(
                            crypto.FILETYPE_PEM,
                            six.u(open(cert_fname, 'r').read())
                        )
                        log.info("Loaded CA certificate '{fname}'", fname=cert_fname)
                        ca_certs.append(cert)

                    client_cert = None
                    if 'key' in config['tls']:
                        with open(config['tls']['certificate'], 'r') as f:
                            cert = Certificate.loadPEM(
                                f.read(),
                            )
                            log.info(
                                "{fname}: CN={subj.CN}, sha={sha}",
                                fname=config['tls']['certificate'],
                                subj=cert.getSubject(),
                                sha=cert.digest('sha'),
                            )

                        with open(config['tls']['key'], 'r') as f:
                            private_key = KeyPair.load(
                                f.read(),
                                format=crypto.FILETYPE_PEM,
                            )

                            log.info(
                                "{fname}: {key}",
                                fname=config['tls']['key'],
                                key=private_key.inspect(),
                            )

                        client_cert = PrivateCertificate.fromCertificateAndKeyPair(
                            cert, private_key)

                    # XXX OpenSSLCertificateAuthorities is a "private"
                    # class, in _sslverify, so we shouldn't really be
                    # using it. However, while you can pass a single
                    # Certificate as trustRoot= there's no way to pass
                    # multiple ones.
                    # XXX ...but maybe the config should only allow
                    # the user to configure a single cert to trust
                    # here anyway?
                    options = optionsForClientTLS(
                        config['tls']['hostname'],
                        trustRoot=OpenSSLCertificateAuthorities(ca_certs),
                        clientCertificate=client_cert,
                    )
                else:
                    options = optionsForClientTLS(config['tls']['hostname'])

                # create a TLS client endpoint
                #
                if version == 4:
                    endpoint = SSL4ClientEndpoint(
                        reactor,
                        host,
                        port,
                        options,
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
                endpoint = TCP4ClientEndpoint(reactor,
                                              host,
                                              port,
                                              timeout=timeout)
            elif version == 6:
                endpoint = TCP6ClientEndpoint(reactor,
                                              host,
                                              port,
                                              timeout=timeout)
            else:
                raise Exception("invalid TCP protocol version {}".format(version))

    # a Unix Domain Socket endpoint
    #
    elif config['type'] == 'unix':

        # the path
        #
        path = abspath(join(cbdir, config['path']))

        # connection timeout in seconds
        #
        timeout = int(config.get('timeout', 10))

        # create the endpoint
        #
        endpoint = UNIXClientEndpoint(reactor, path, timeout=timeout)

    else:
        raise Exception("invalid endpoint type '{}'".format(config['type']))

    return endpoint


def create_connecting_port_from_config(config, factory, cbdir, reactor):
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
    endpoint = create_connecting_endpoint_from_config(config, cbdir, reactor)
    return endpoint.connect(factory)
