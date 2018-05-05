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

import tempfile

from OpenSSL import crypto, SSL
from twisted.internet.ssl import DefaultOpenSSLContextFactory, ClientContextFactory

from txaio import make_logger

# Monkey patch missing constants
#
# See:
# - https://bugs.launchpad.net/pyopenssl/+bug/1244201
# - https://www.openssl.org/docs/ssl/SSL_CTX_set_options.html
#
SSL.OP_NO_COMPRESSION = 0x00020000
SSL.OP_CIPHER_SERVER_PREFERENCE = 0x00400000
SSL.OP_SINGLE_ECDH_USE = 0x00080000
SSL.OP_SINGLE_DH_USE = 0x00100000
SSL.OP_DONT_INSERT_EMPTY_FRAGMENTS = 0x00000800
SSL.OP_NO_TLSv1 = 0x04000000
SSL.OP_NO_SESSION_RESUMPTION_ON_RENEGOTIATION = 0x00010000
SSL.OP_NO_TICKET = 0x00004000

SSL_DEFAULT_OPTIONS = SSL.OP_NO_SSLv2 | \
    SSL.OP_NO_SSLv3 | \
    SSL.OP_NO_COMPRESSION | \
    SSL.OP_CIPHER_SERVER_PREFERENCE | \
    SSL.OP_SINGLE_ECDH_USE | \
    SSL.OP_SINGLE_DH_USE | \
    SSL.OP_DONT_INSERT_EMPTY_FRAGMENTS | \
    SSL.OP_NO_SESSION_RESUMPTION_ON_RENEGOTIATION | \
    SSL.OP_NO_TICKET

# List of available ciphers
#
# Check via: https://www.ssllabs.com/ssltest/analyze.html?d=myserver.com
#
# http://www.openssl.org/docs/apps/ciphers.html#CIPHER_LIST_FORMAT
#

# http://hynek.me/articles/hardening-your-web-servers-ssl-ciphers/
# SSL_DEFAULT_CIPHERS = 'ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+3DES:DH+3DES:RSA+AES:RSA+3DES:!ADH:!AECDH:!MD5:!DSS'

# We prefer to make every single cipher (6 in total) _explicit_ (to reduce chances either we or the pattern-matching
# language inside OpenSSL messes up) and drop support for Windows XP (we do WebSocket anyway).
# We don't use AES256 and SHA384, to reduce number of ciphers and since the additional security gain seems
# to worth the additional performance drain.
#
SSL_DEFAULT_CIPHERS = 'ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:DHE-RSA-AES128-SHA'
# SSL_DEFAULT_CIPHERS = 'AES128-GCM-SHA256'

# Resorted to prioritize ECDH (hence favor performance over cipher strength) - no gain in practice, that doesn't
# change the effectively accepted cipher with common browsers/clients
# SSL_DEFAULT_CIPHERS = 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA'


# Named curves built into OpenSSL .. can be listed using:
#
# openssl ecparam -list_curves
#
# Only some of those are exposed in pyOpenSSL
#
# http://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.186-4.pdf

# curves over binary fields
#
SSL.SN_X9_62_c2pnb163v1 = "c2pnb163v1"
SSL.NID_X9_62_c2pnb163v1 = 684

SSL.SN_X9_62_c2pnb163v2 = "c2pnb163v2"
SSL.NID_X9_62_c2pnb163v2 = 685

SSL.SN_X9_62_c2pnb163v3 = "c2pnb163v3"
SSL.NID_X9_62_c2pnb163v3 = 686

SSL.SN_X9_62_c2pnb176v1 = "c2pnb176v1"
SSL.NID_X9_62_c2pnb176v1 = 687

SSL.SN_X9_62_c2tnb191v1 = "c2tnb191v1"
SSL.NID_X9_62_c2tnb191v1 = 688

SSL.SN_X9_62_c2tnb191v2 = "c2tnb191v2"
SSL.NID_X9_62_c2tnb191v2 = 689

SSL.SN_X9_62_c2tnb191v3 = "c2tnb191v3"
SSL.NID_X9_62_c2tnb191v3 = 690

SSL.SN_X9_62_c2onb191v4 = "c2onb191v4"
SSL.NID_X9_62_c2onb191v4 = 691

SSL.SN_X9_62_c2onb191v5 = "c2onb191v5"
SSL.NID_X9_62_c2onb191v5 = 692

SSL.SN_X9_62_c2pnb208w1 = "c2pnb208w1"
SSL.NID_X9_62_c2pnb208w1 = 693

SSL.SN_X9_62_c2tnb239v1 = "c2tnb239v1"
SSL.NID_X9_62_c2tnb239v1 = 694

SSL.SN_X9_62_c2tnb239v2 = "c2tnb239v2"
SSL.NID_X9_62_c2tnb239v2 = 695

SSL.SN_X9_62_c2tnb239v3 = "c2tnb239v3"
SSL.NID_X9_62_c2tnb239v3 = 696

SSL.SN_X9_62_c2onb239v4 = "c2onb239v4"
SSL.NID_X9_62_c2onb239v4 = 697

SSL.SN_X9_62_c2onb239v5 = "c2onb239v5"
SSL.NID_X9_62_c2onb239v5 = 698

SSL.SN_X9_62_c2pnb272w1 = "c2pnb272w1"
SSL.NID_X9_62_c2pnb272w1 = 699

SSL.SN_X9_62_c2pnb304w1 = "c2pnb304w1"
SSL.NID_X9_62_c2pnb304w1 = 700

SSL.SN_X9_62_c2tnb359v1 = "c2tnb359v1"
SSL.NID_X9_62_c2tnb359v1 = 701

SSL.SN_X9_62_c2pnb368w1 = "c2pnb368w1"
SSL.NID_X9_62_c2pnb368w1 = 702

SSL.SN_X9_62_c2tnb431r1 = "c2tnb431r1"
SSL.NID_X9_62_c2tnb431r1 = 703

# curves over prime fields
#
SSL.SN_X9_62_prime192v1 = "prime192v1"
SSL.NID_X9_62_prime192v1 = 409
SSL.SN_X9_62_prime192v2 = "prime192v2"
SSL.NID_X9_62_prime192v2 = 410
SSL.SN_X9_62_prime192v3 = "prime192v3"
SSL.NID_X9_62_prime192v3 = 411
SSL.SN_X9_62_prime239v1 = "prime239v1"
SSL.NID_X9_62_prime239v1 = 412
SSL.SN_X9_62_prime239v2 = "prime239v2"
SSL.NID_X9_62_prime239v2 = 413
SSL.SN_X9_62_prime239v3 = "prime239v3"
SSL.NID_X9_62_prime239v3 = 414
SSL.SN_X9_62_prime256v1 = "prime256v1"
SSL.NID_X9_62_prime256v1 = 415

# map of curve name to curve NID
#
ELLIPTIC_CURVES = {
    SSL.SN_X9_62_c2pnb163v1: SSL.NID_X9_62_c2pnb163v1,
    SSL.SN_X9_62_c2pnb163v2: SSL.NID_X9_62_c2pnb163v2,
    SSL.SN_X9_62_c2pnb163v3: SSL.NID_X9_62_c2pnb163v3,
    SSL.SN_X9_62_c2pnb176v1: SSL.NID_X9_62_c2pnb176v1,
    SSL.SN_X9_62_c2tnb191v1: SSL.NID_X9_62_c2tnb191v1,
    SSL.SN_X9_62_c2tnb191v2: SSL.NID_X9_62_c2tnb191v2,
    SSL.SN_X9_62_c2tnb191v3: SSL.NID_X9_62_c2tnb191v3,
    SSL.SN_X9_62_c2onb191v4: SSL.NID_X9_62_c2onb191v4,
    SSL.SN_X9_62_c2onb191v5: SSL.NID_X9_62_c2onb191v5,
    SSL.SN_X9_62_c2pnb208w1: SSL.NID_X9_62_c2pnb208w1,
    SSL.SN_X9_62_c2tnb239v1: SSL.NID_X9_62_c2tnb239v1,
    SSL.SN_X9_62_c2tnb239v2: SSL.NID_X9_62_c2tnb239v2,
    SSL.SN_X9_62_c2tnb239v3: SSL.NID_X9_62_c2tnb239v3,
    SSL.SN_X9_62_c2onb239v4: SSL.NID_X9_62_c2onb239v4,
    SSL.SN_X9_62_c2onb239v5: SSL.NID_X9_62_c2onb239v5,
    SSL.SN_X9_62_c2pnb272w1: SSL.NID_X9_62_c2pnb272w1,
    SSL.SN_X9_62_c2pnb304w1: SSL.NID_X9_62_c2pnb304w1,
    SSL.SN_X9_62_c2tnb359v1: SSL.NID_X9_62_c2tnb359v1,
    SSL.SN_X9_62_c2pnb368w1: SSL.NID_X9_62_c2pnb368w1,
    SSL.SN_X9_62_c2tnb431r1: SSL.NID_X9_62_c2tnb431r1,

    SSL.SN_X9_62_prime192v1: SSL.NID_X9_62_prime192v1,
    SSL.SN_X9_62_prime192v2: SSL.NID_X9_62_prime192v2,
    SSL.SN_X9_62_prime192v3: SSL.NID_X9_62_prime192v3,
    SSL.SN_X9_62_prime239v1: SSL.NID_X9_62_prime239v1,
    SSL.SN_X9_62_prime239v2: SSL.NID_X9_62_prime239v2,
    SSL.SN_X9_62_prime239v3: SSL.NID_X9_62_prime239v3,
    SSL.SN_X9_62_prime256v1: SSL.NID_X9_62_prime256v1
}

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
ECDH_DEFAULT_CURVE_NAME = "prime256v1"
ECDH_DEFAULT_CURVE = ELLIPTIC_CURVES[ECDH_DEFAULT_CURVE_NAME]


class TlsServerContextFactory(DefaultOpenSSLContextFactory):
    """
    TLS context factory for use with Twisted.

    Like the default

       http://twistedmatrix.com/trac/browser/tags/releases/twisted-11.1.0/twisted/internet/ssl.py#L42

    but loads key/cert from string, not file and supports chained certificates.

    See also:

       http://pyopenssl.sourceforge.net/pyOpenSSL.html/openssl-context.html
       http://www.openssl.org/docs/ssl/SSL_CTX_use_certificate.html

    Chained certificates:
       The certificates must be in PEM format and must be sorted starting with
       the subject's certificate (actual client or server certificate), followed
       by intermediate CA certificates if applicable, and ending at the
       highest level (root) CA.

    Hardening:
       http://hynek.me/articles/hardening-your-web-servers-ssl-ciphers/
       https://www.ssllabs.com/ssltest/analyze.html?d=www.example.com
    """

    log = make_logger()

    def __init__(self,
                 privateKeyString,
                 certificateString,
                 chainedCertificate=True,
                 dhParamFilename=None,
                 ciphers=None,
                 ca_certs=[]):
        self._privateKeyString = str(privateKeyString).encode('utf8')
        self._certificateString = str(certificateString).encode('utf8')
        self._chainedCertificate = chainedCertificate
        self._dhParamFilename = str(dhParamFilename) if dhParamFilename else None
        self._ciphers = str(ciphers) if ciphers else None
        self._ca_certs = ca_certs  # additional CA certificates to trust

        # do a SSLv2-compatible handshake even for TLS
        #
        self.sslmethod = SSL.SSLv23_METHOD

        self._contextFactory = SSL.Context
        self.cacheContext()

    def _verify_peer(self, conn, cert, errno, depth, preverify_ok):
        if not preverify_ok:
            self.log.info(
                "TLS verification failing at depth {depth}; err={err}",
                depth=depth,
                err=errno,  # can we convert this to string/symbolic code?
            )
            # X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN		19
            # X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY	20
            if errno in [19, 20]:
                self.log.debug(
                    "Can't find CA certificate to verify against or self-signed "
                    "certificate."
                )
                self.log.debug(
                    "Is 'ca_certificates' endpoint configuration missing a cert?"
                )
        return preverify_ok

    def cacheContext(self):
        if self._context is None:
            ctx = self._contextFactory(self.sslmethod)

            # SSL hardening
            #
            ctx.set_options(SSL_DEFAULT_OPTIONS)

            if self._ciphers:
                ctx.set_cipher_list(self._ciphers)
                self.log.info("Using explicit cipher list.")
            else:
                ctx.set_cipher_list(SSL_DEFAULT_CIPHERS)
                self.log.info("Using default cipher list.")

            # Activate DH(E)
            #
            # http://linux.die.net/man/3/ssl_ctx_set_tmp_dh
            # http://linux.die.net/man/1/dhparam
            #
            if self._dhParamFilename:
                try:
                    ctx.load_tmp_dh(self._dhParamFilename)
                except Exception:
                    self.log.failure("Error: OpenSSL DH modes not active - failed to load DH parameter file [{log_failure}]")
                else:
                    self.log.info("Ok, OpenSSL Diffie-Hellman ciphers parameter file loaded.")
            else:
                self.log.warn("OpenSSL DH modes not active - missing DH param file")

            # Activate ECDH(E)
            #
            # This needs pyOpenSSL 0.15
            #
            try:
                # without setting a curve, ECDH won't be available even if listed
                # in SSL_DEFAULT_CIPHERS!
                # curve must be one of OpenSSL.crypto.get_elliptic_curves()
                #
                curve = crypto.get_elliptic_curve(ECDH_DEFAULT_CURVE_NAME)
                ctx.set_tmp_ecdh(curve)
            except Exception:
                self.log.failure("Warning: OpenSSL failed to set ECDH default curve [{log_failure}]")
            else:
                self.log.info("Ok, OpenSSL is using ECDH elliptic curve {curve}",
                              curve=ECDH_DEFAULT_CURVE_NAME)

            # load certificate (chain) into context
            #
            if not self._chainedCertificate:
                cert = crypto.load_certificate(crypto.FILETYPE_PEM, self._certificateString)
                ctx.use_certificate(cert)
            else:
                # http://pyopenssl.sourceforge.net/pyOpenSSL.html/openssl-context.html
                # there is no "use_certificate_chain" function, so we need to create
                # a temporary file writing the certificate chain file
                f = tempfile.NamedTemporaryFile(delete=False)
                f.write(self._certificateString)
                f.close()
                ctx.use_certificate_chain_file(f.name)

            store = ctx.get_cert_store()
            for cert in self._ca_certs:
                store.add_cert(cert.original)
            ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT, self._verify_peer)

            # load private key into context
            #
            key = crypto.load_privatekey(crypto.FILETYPE_PEM, self._privateKeyString)
            ctx.use_privatekey(key)
            ctx.check_privatekey()

            # set cached context
            #
            self._context = ctx


class TlsClientContextFactory(ClientContextFactory):
    pass
