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
                key_filepath = abspath(join(cbdir, config['tls']['key']))
                cert_filepath = abspath(join(cbdir, config['tls']['certificate']))

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
                            # or do "whatever tlxctx was doing"
                            dh_params = None
                            log.warn("OpenSSL DH modes not active (no 'dhparam')")

                        # create a TLS context factory
                        #
                        key = key_file.read()
                        cert = cert_file.read()
                        ca_certs = None
                        if 'ca_certificates' in config['tls']:
                            ca_certs = []
                            for fname in config['tls']['ca_certificates']:
                                with open(fname, 'r') as f:
                                    ca_certs.append(Certificate.loadPEM(f.read()).original)

                        crossbar_ciphers = AcceptableCiphers.fromOpenSSLCipherString(
                            'ECDHE-RSA-AES128-GCM-SHA256:'
                            'DHE-RSA-AES128-GCM-SHA256:'
                            'ECDHE-RSA-AES128-SHA256:'
                            'DHE-RSA-AES128-SHA256:'
                            'ECDHE-RSA-AES128-SHA:'
                            'DHE-RSA-AES128-SHA'
                        )

                        ctx = CertificateOptions(
                            privateKey=KeyPair.load(key, crypto.FILETYPE_PEM).original,
                            certificate=Certificate.loadPEM(cert).original,
                            verify=(ca_certs is not None),
                            caCerts=ca_certs,
                            dhParameters=dh_params,
                            acceptableCiphers=crossbar_ciphers,
                        )
                        if ctx._ecCurve is None:
                            log.warn("OpenSSL failed to set ECDH default curve")
                        else:
                            log.info(
                                "Ok, OpenSSL is using ECDH elliptic curve {curve}",
                                curve=ctx._ecCurve.snName,
                            )

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
