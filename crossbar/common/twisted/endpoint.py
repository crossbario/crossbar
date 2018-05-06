#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
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
import os
from os import environ
from os.path import join, abspath, isabs, exists

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
    UNIXClientEndpoint, \
    serverFromString,   \
    clientFromString
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.python.filepath import FilePath
from zope.interface import implementer

import txtorcon

from crossbar.common.twisted.sharedport import SharedPort, SharedTLSPort

try:
    from twisted.internet.endpoints import SSL4ServerEndpoint, \
        SSL4ClientEndpoint
    # import OpenSSL
    from OpenSSL import crypto
    # from OpenSSL.SSL import OP_NO_SSLv3, OP_NO_TLSv1
    from twisted.internet._sslverify import TLSVersion
    from twisted.internet.interfaces import ISSLTransport

    _HAS_TLS = True
    _LACKS_TLS_MSG = None
except ImportError as e:
    _HAS_TLS = False
    _LACKS_TLS_MSG = "{}".format(e)

__all__ = ('create_listening_endpoint_from_config',
           'create_listening_port_from_config',
           'create_connecting_endpoint_from_config',
           'create_connecting_port_from_config',
           'extract_peer_certificate')


def extract_peer_certificate(transport):
    """
    Extract TLS x509 client certificate information from a Twisted stream transport.
    """
    if not _HAS_TLS:
        raise Exception("cannot extract certificate - TLS support packages not installed")

    # check if the Twisted transport is a TLSMemoryBIOProtocol
    if not (hasattr(transport, 'getPeerCertificate') and ISSLTransport.providedBy(transport)):
        return None

    cert = transport.getPeerCertificate()
    if cert:
        # Extract x509 name components from an OpenSSL X509Name object.
        # pkey = cert.get_pubkey()
        def maybe_bytes(value):
            if type(value) == six.binary_type:
                return value.decode('utf8')
            else:
                return value

        result = {
            u'md5': u'{}'.format(maybe_bytes(cert.digest('md5'))).upper(),
            u'sha1': u'{}'.format(maybe_bytes(cert.digest('sha1'))).upper(),
            u'sha256': u'{}'.format(maybe_bytes(cert.digest('sha256'))).upper(),
            u'expired': bool(cert.has_expired()),
            u'hash': maybe_bytes(cert.subject_name_hash()),
            u'serial': int(cert.get_serial_number()),
            u'signature_algorithm': maybe_bytes(cert.get_signature_algorithm()),
            u'version': int(cert.get_version()),
            u'not_before': maybe_bytes(cert.get_notBefore()),
            u'not_after': maybe_bytes(cert.get_notAfter()),
            u'extensions': []
        }

        for i in range(cert.get_extension_count()):
            ext = cert.get_extension(i)
            ext_info = {
                u'name': u'{}'.format(maybe_bytes(ext.get_short_name())),
                u'value': u'{}'.format(maybe_bytes(ext)),
                u'criticial': ext.get_critical() != 0
            }
            result[u'extensions'].append(ext_info)

        for entity, name in [(u'subject', cert.get_subject()), (u'issuer', cert.get_issuer())]:
            result[entity] = {}
            for key, value in name.get_components():
                key = maybe_bytes(key)
                value = maybe_bytes(value)
                result[entity][u'{}'.format(key).lower()] = u'{}'.format(value)

        return result


def _create_tls_server_context(config, cbdir, log):
    """
    Create a CertificateOptions object for use with TLS listening endpoints.
    """
    # server private key
    key_filepath = abspath(join(cbdir, config['key']))
    log.info("Loading server TLS key from {key_filepath}", key_filepath=key_filepath)
    with open(key_filepath) as key_file:
        # server certificate (but only the server cert, no chain certs)
        cert_filepath = abspath(join(cbdir, config['certificate']))
        log.info("Loading server TLS certificate from {cert_filepath}", cert_filepath=cert_filepath)
        with open(cert_filepath) as cert_file:
            key = KeyPair.load(key_file.read(), crypto.FILETYPE_PEM).original
            cert = Certificate.loadPEM(cert_file.read()).original

    # list of certificates that complete your verification chain
    extra_certs = None
    if 'chain_certificates' in config:
        extra_certs = []
        for fname in config['chain_certificates']:
            extra_cert_filepath = abspath(join(cbdir, fname))
            with open(extra_cert_filepath, 'r') as f:
                extra_certs.append(Certificate.loadPEM(f.read()).original)
            log.info("Loading server TLS chain certificate from {extra_cert_filepath}", extra_cert_filepath=extra_cert_filepath)

    # list of certificate authority certificate objects to use to verify the peer's certificate
    ca_certs = None
    if 'ca_certificates' in config:
        ca_certs = []
        for fname in config['ca_certificates']:
            ca_cert_filepath = abspath(join(cbdir, fname))
            with open(ca_cert_filepath, 'r') as f:
                ca_certs.append(Certificate.loadPEM(f.read()).original)
            log.info("Loading server TLS CA certificate from {ca_cert_filepath}", ca_cert_filepath=ca_cert_filepath)

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
    # The effective list of ciphers determined from an OpenSSL cipher string:
    #
    #   openssl ciphers -v 'ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA256:'
    #
    # References:
    #
    #  * https://www.ssllabs.com/ssltest/analyze.html?d=myserver.com
    #  * http://hynek.me/articles/hardening-your-web-servers-ssl-ciphers/
    #  * http://www.openssl.org/docs/apps/ciphers.html#CIPHER_LIST_FORMAT
    #  * https://wiki.mozilla.org/Talk:Security/Server_Side_TLS
    #
    if 'ciphers' in config:
        log.info("Using explicit TLS ciphers from config")
        crossbar_ciphers = AcceptableCiphers.fromOpenSSLCipherString(config['ciphers'])
    else:
        log.info("Using secure default TLS ciphers")
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

    # DH modes require a parameter file
    if 'dhparam' in config:
        dhpath = FilePath(abspath(join(cbdir, config['dhparam'])))
        dh_params = DiffieHellmanParameters.fromFile(dhpath)
    else:
        dh_params = None
        log.warn("No OpenSSL DH parameter file set - DH cipher modes will be deactive!")

    ctx = CertificateOptions(
        privateKey=key,
        certificate=cert,
        extraCertChain=extra_certs,
        verify=(ca_certs is not None),
        caCerts=ca_certs,
        dhParameters=dh_params,
        acceptableCiphers=crossbar_ciphers,

        # Disable SSLv3 and TLSv1 -- only allow TLSv1.1 or higher
        #
        # We are using Twisted private stuff (from twisted.internet._sslverify import TLSVersion),
        # as OpenSSL.SSL.TLSv1_1_METHOD wont work:
        #
        # [ERROR] File "../twisted/internet/_sslverify.py", line 1530, in __init__
        #    if raiseMinimumTo > self._defaultMinimumTLSVersion:
        #       builtins.TypeError: '>' not supported between instances of 'int' and 'NamedConstant'
        #
        raiseMinimumTo=TLSVersion.TLSv1_1,

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
    Create a CertificateOptions object for use with TLS listening endpoints.
    """
    # server hostname: The expected name of the remote host.
    hostname = config['hostname']

    # explicit trust (certificate) root
    ca_certs = None
    if 'ca_certificates' in config:
        log.info("TLS client using explicit trust ({cnt_certs} certificates)", cnt_certs=len(config['ca_certificates']))
        ca_certs = []
        for cert_fname in [os.path.abspath(os.path.join(cbdir, x)) for x in (config['ca_certificates'])]:
            cert = crypto.load_certificate(
                crypto.FILETYPE_PEM,
                six.u(open(cert_fname, 'r').read())
            )
            log.info("TLS client trust root CA certificate loaded from '{fname}'", fname=cert_fname)
            ca_certs.append(cert)
        ca_certs = OpenSSLCertificateAuthorities(ca_certs)
    else:
        log.info("TLS client using platform trust")

    # client key/cert to use
    client_cert = None
    if 'key' in config:
        if 'certificate' not in config:
            raise Exception('TLS client key present, but certificate missing')

        key_fname = os.path.abspath(os.path.join(cbdir, config['key']))
        with open(key_fname, 'r') as f:
            private_key = KeyPair.load(f.read(), format=crypto.FILETYPE_PEM)
            log.info("Loaded client TLS key from '{key_fname}'", key_fname=key_fname)

        cert_fname = os.path.abspath(os.path.join(cbdir, config['certificate']))
        with open(cert_fname, 'r') as f:
            cert = Certificate.loadPEM(f.read(),)
            log.info("Loaded client TLS certificate from '{cert_fname}' (cn='{cert_cn}', sha256={cert_sha256}..)",
                     cert_fname=cert_fname,
                     cert_cn=cert.getSubject().CN,
                     cert_sha256=cert.digest('sha256')[:12])

        client_cert = PrivateCertificate.fromCertificateAndKeyPair(cert, private_key)
    else:
        if 'certificate' in config:
            log.warn('TLS client certificate present, but key is missing')

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
    if config['type'] == 'tcp':

        # the TCP protocol version (v4 or v6)
        #
        version = int(config.get('version', 4))

        # the listening port
        if type(config['port']) is six.text_type:
            # read port from environment variable ..
            try:
                port = int(environ[config['port'][1:]])
            except Exception as e:
                log.warn("Could not read listening port from env var: {e}", e=e)
                raise
        else:
            port = config['port']

        # the listening interface
        #
        interface = str(config.get('interface', '').strip())

        # the TCP accept queue depth
        #
        backlog = int(config.get('backlog', 50))

        if 'tls' in config:
            # create a TLS server endpoint
            #
            if _HAS_TLS:
                # TLS server context
                context = _create_tls_server_context(config['tls'], cbdir, log)

                if version == 4:
                    endpoint = SSL4ServerEndpoint(reactor,
                                                  port,
                                                  context,
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

    # twisted endpoint-string
    elif config['type'] == 'twisted':
        endpoint = serverFromString(reactor, config['server_string'])

    # tor endpoint
    elif config['type'] == 'onion':  # or "tor"? r "tor_onion"?
        port = config['port']
        private_key_fname = _ensure_absolute(config[u'private_key_file'], cbdir)
        tor_control_ep = create_connecting_endpoint_from_config(
            config[u'tor_control_endpoint'], cbdir, reactor, log
        )

        try:
            with open(private_key_fname, 'r') as f:
                private_key = f.read().strip()
        except (IOError, OSError):
            private_key = None

        @implementer(IStreamServerEndpoint)
        class _EphemeralOnion(object):

            @defer.inlineCallbacks
            def listen(self, proto_factory):
                # we don't care which local TCP port we listen on, but
                # we do need to know it
                local_ep = TCP4ServerEndpoint(reactor, 0, interface=u"127.0.0.1")
                target_port = yield local_ep.listen(proto_factory)
                tor = yield txtorcon.connect(
                    reactor,
                    tor_control_ep,
                )

                # create and add the service
                hs = txtorcon.EphemeralHiddenService(
                    ports=["{} 127.0.0.1:{}".format(port, target_port.getHost().port)],
                    key_blob_or_type=private_key if private_key else "NEW:BEST",
                )
                log.info("Uploading descriptors can take more than 30s")
                yield hs.add_to_tor(tor.protocol)

                # if it's new, store our private key
                # XXX better "if private_key is None"?
                if not exists(private_key_fname):
                    with open(private_key_fname, 'w') as f:
                        f.write(hs.private_key)
                    log.info("Wrote private key to '{fname}'", fname=private_key_fname)

                addr = txtorcon.TorOnionAddress(hs.hostname, port)
                log.info(
                    "Listening on Tor onion service {addr.onion_uri}:{addr.onion_port}"
                    " with local port {local_port}",
                    addr=addr,
                    local_port=target_port.getHost().port,
                )
                defer.returnValue(addr)
        endpoint = _EphemeralOnion()

    else:
        raise Exception("invalid endpoint type '{}'".format(config['type']))

    return endpoint


def create_listening_port_from_config(config, cbdir, factory, reactor, log):
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
        #
        version = int(config.get('version', 4))

        # the listening port
        #
        port = int(config['port'])

        # the listening interface
        #
        interface = str(config.get('interface', '').strip())

        # the TCP accept queue depth
        #
        backlog = int(config.get('backlog', 50))

        # the TCP socket sharing option
        #
        shared = config.get('shared', False)

        # create a listening port
        #
        if 'tls' in config:
            if _HAS_TLS:
                # TLS server context
                context = _create_tls_server_context(config['tls'], cbdir, log)

                if version == 4:
                    listening_port = SharedTLSPort(port, factory, context, backlog, interface, reactor, shared=shared)
                elif version == 6:
                    raise Exception("TLS on IPv6 not implemented")
                else:
                    raise Exception("invalid TCP protocol version {}".format(version))
            else:
                raise Exception("TLS transport requested, but TLS packages not available:\n{}".format(_LACKS_TLS_MSG))
        else:
            listening_port = SharedPort(port, factory, backlog, interface, reactor, shared=shared)

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
            # create a TLS client endpoint
            #
            if _HAS_TLS:
                # TLS client context
                context = _create_tls_client_context(config['tls'], cbdir, log)

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

    elif config['type'] == 'twisted':
        endpoint = clientFromString(reactor, config['client_string'])

    elif config['type'] == 'tor':
        host = config['host']
        port = config['port']
        socks_port = config['tor_socks_port']
        tls = config.get('tls', False)
        if not tls and not host.endswith(u'.onion'):
            log.warn("Non-TLS connection traversing Tor network; end-to-end encryption advised")

        socks_endpoint = TCP4ClientEndpoint(
            reactor, "127.0.0.1", socks_port,
        )
        endpoint = txtorcon.TorClientEndpoint(
            host, port,
            socks_endpoint=socks_endpoint,
            reactor=reactor,
            use_tls=tls,
        )

    else:
        raise Exception("invalid endpoint type '{}'".format(config['type']))

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
