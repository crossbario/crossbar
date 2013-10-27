###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################


import tempfile

from OpenSSL import crypto, SSL
from twisted.internet.ssl import DefaultOpenSSLContextFactory

from twisted.python import log

## Monkey patch missing constants
##
## See:
##   - https://bugs.launchpad.net/pyopenssl/+bug/1244201
##   - https://www.openssl.org/docs/ssl/SSL_CTX_set_options.html
##
SSL.OP_NO_COMPRESSION                         = 0x00020000L
SSL.OP_CIPHER_SERVER_PREFERENCE               = 0x00400000L
SSL.OP_SINGLE_ECDH_USE                        = 0x00080000L
SSL.OP_SINGLE_DH_USE                          = 0x00100000L
SSL.OP_DONT_INSERT_EMPTY_FRAGMENTS            = 0x00000800L
SSL.OP_NO_TLSv1                               = 0x04000000L
SSL.OP_NO_SESSION_RESUMPTION_ON_RENEGOTIATION = 0x00010000L
SSL.OP_NO_TICKET                              = 0x00004000L

SSL_DEFAULT_OPTIONS = SSL.OP_NO_SSLv2 | \
                      SSL.OP_NO_SSLv3 | \
                      #SSL.OP_NO_TLSv1 | \
                      SSL.OP_NO_COMPRESSION | \
                      SSL.OP_CIPHER_SERVER_PREFERENCE | \
                      SSL.OP_SINGLE_ECDH_USE | \
                      SSL.OP_SINGLE_DH_USE | \
                      SSL.OP_DONT_INSERT_EMPTY_FRAGMENTS | \
                      SSL.OP_NO_SESSION_RESUMPTION_ON_RENEGOTIATION | \
                      SSL.OP_NO_TICKET

## List of available ciphers
##
## Check via: https://www.ssllabs.com/ssltest/analyze.html?d=myserver.com
##
## http://www.openssl.org/docs/apps/ciphers.html#CIPHER_LIST_FORMAT
##

# http://hynek.me/articles/hardening-your-web-servers-ssl-ciphers/
#SSL_DEFAULT_CIPHERS = 'ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+3DES:DH+3DES:RSA+AES:RSA+3DES:!ADH:!AECDH:!MD5:!DSS'

## We prefer to make every single cipher (6 in total) _explicit_ (to reduce chances either we or the pattern-matching
## language inside OpenSSL messes up) and drop support for Windows XP (we do WebSocket anyway).
## We don't use AES256 and SHA384, to reduce number of ciphers and since the additional security gain seems
## to worth the additional performance drain.
##
SSL_DEFAULT_CIPHERS = 'ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:DHE-RSA-AES128-SHA'


## Named curves built into OpenSSL .. can be listed using:
##
##  openssl ecparam -list_curves
##
## Only some of those are exposed in pyOpenSSL
##
# SSL.NID_X9_62_prime192v1
# SSL.NID_X9_62_prime192v2
# SSL.NID_X9_62_prime192v3
# SSL.NID_X9_62_prime239v1
# SSL.NID_X9_62_prime239v2
# SSL.NID_X9_62_prime239v3
# SSL.NID_X9_62_prime256v1

SSL.SN_X9_62_prime192v1 = "prime192v1"
SSL.SN_X9_62_prime192v2 = "prime192v2"
SSL.SN_X9_62_prime192v3 = "prime192v3"
SSL.SN_X9_62_prime239v1 = "prime239v1"
SSL.SN_X9_62_prime239v2 = "prime239v2"
SSL.SN_X9_62_prime239v3 = "prime239v3"
SSL.SN_X9_62_prime256v1 = "prime256v1"

ELLIPTIC_CURVES = {
   SSL.SN_X9_62_prime192v1: SSL.NID_X9_62_prime192v1,
   SSL.SN_X9_62_prime192v2: SSL.NID_X9_62_prime192v2,
   SSL.SN_X9_62_prime192v3: SSL.NID_X9_62_prime192v3,
   SSL.SN_X9_62_prime239v1: SSL.NID_X9_62_prime239v1,
   SSL.SN_X9_62_prime239v2: SSL.NID_X9_62_prime239v2,
   SSL.SN_X9_62_prime239v3: SSL.NID_X9_62_prime239v3,
   SSL.SN_X9_62_prime256v1: SSL.NID_X9_62_prime256v1
}

## prime256v1: X9.62/SECG curve over a 256 bit prime field
##
## This is elliptic curve "NIST P-256" from here
## http://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.186-4.pdf
##
## This seems to be the most widely used curve
##
##   http://crypto.stackexchange.com/questions/11310/with-openssl-and-ecdhe-how-to-show-the-actual-curve-being-used
##
## and researchers think it is "ok" (other than wrt timing attacks etc)
##
##   https://twitter.com/hyperelliptic/status/394258454342148096
##
ECDH_DEFAULT_CURVE = ELLIPTIC_CURVES["prime256v1"]


class TlsContextFactory(DefaultOpenSSLContextFactory):
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

   def __init__(self, privateKeyString, certificateString, chainedCertificate = True, dhParamFilename = None):
      self.privateKeyString = str(privateKeyString)
      self.certificateString = str(certificateString)
      self.chainedCertificate = chainedCertificate
      self.dhParamFilename = dhParamFilename

      ## do a SSLv2-compatible handshake even for TLS
      ##
      self.sslmethod = SSL.SSLv23_METHOD

      self._contextFactory = SSL.Context
      self.cacheContext()

   def cacheContext(self):
      if self._context is None:
         ctx = self._contextFactory(self.sslmethod)

         ## SSL hardening
         ##
         ctx.set_options(SSL_DEFAULT_OPTIONS)
         ctx.set_cipher_list(SSL_DEFAULT_CIPHERS)


         ## Activate DH(E)
         ##
         ## http://linux.die.net/man/3/ssl_ctx_set_tmp_dh
         ## http://linux.die.net/man/1/dhparam
         ##
         if self.dhParamFilename:
            try:
               ctx.load_tmp_dh(self.dhParamFilename)
            except Exception, e:
               log.msg("Error: OpenSSL DH modes not active - failed to load DH parameter file [%s]" % e)
         else:
            log.msg("Warning: OpenSSL DH modes not active - missing DH param file")


         ## Activate ECDH(E)
         ##
         ## This needs pyOpenSSL with patch applied from
         ## https://bugs.launchpad.net/pyopenssl/+bug/1233810
         ##
         try:
            ## without setting a curve, ECDH won't be available even if listed
            ## in SSL_DEFAULT_CIPHERS!
            ##
            ctx.set_tmp_ecdh_by_curve_name(ECDH_DEFAULT_CURVE)
         except Exception, e:
            log.msg("Failed to set ECDH default curve [%s]" % e)


         ## load certificate (chain) into context
         ##
         if not self.chainedCertificate:
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, self.certificateString)
            ctx.use_certificate(cert)
         else:
            # http://pyopenssl.sourceforge.net/pyOpenSSL.html/openssl-context.html
            # there is no "use_certificate_chain" function, so we need to create
            # a temporary file writing the certificate chain file
            f = tempfile.NamedTemporaryFile(delete = False)
            f.write(self.certificateString)
            f.close()
            ctx.use_certificate_chain_file(f.name)


         ## load private key into context
         ##
         key = crypto.load_privatekey(crypto.FILETYPE_PEM, self.privateKeyString)
         ctx.use_privatekey(key)
         ctx.check_privatekey()


         ## set cached context
         ##
         self._context = ctx
