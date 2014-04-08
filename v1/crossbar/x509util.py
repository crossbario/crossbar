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


import hashlib, datetime
from OpenSSL import crypto
from Crypto.PublicKey import RSA


ZERODIGEST = ('00:' * (160/8))[:-1]


def dotted(s):
   """
   Dotted hex from hex string.
   """
   ss = ':'.join(s[pos:pos+2] for pos in range(0, len(s), 2))
   return ss.upper() # do NOT change to lower() !


def fingerprint(key):
   """
   Compute SHA1 fingerprint from key in DER format.

   :param key: Key in DER format.
   :type key: str
   :returns str -- Fingerprint of key in dotted hex format.
   """
   digest = hashlib.sha1(key).hexdigest()
   return dotted(digest)


def fill_x509name_from_info(name, info):
   """
   Fill X509 name object from info dictionary.

   :param name: The X509 name object to be filled.
   :type name: crypto.X509Name instance
   :param info: An info dictionary.
   :type info: dict
   """
   if info.has_key("common-name") and type(info["common-name"]) in [str, unicode]:
      name.CN = info["common-name"].encode("utf8")
   if info.has_key("country-name") and type(info["country-name"]) in [str, unicode]:
      name.C = info["country-name"].encode("utf8")
   if info.has_key("state-or-province-name") and type(info["state-or-province-name"]) in [str, unicode]:
      name.ST = info["state-or-province-name"].encode("utf8")
   if info.has_key("locality-name") and type(info["locality-name"]) in [str, unicode]:
      name.L = info["locality-name"].encode("utf8")
   if info.has_key("organization-name") and type(info["organization-name"]) in [str, unicode]:
      name.O = info["organization-name"].encode("utf8")
   if info.has_key("organization-unit-name") and type(info["organization-unit-name"]) in [str, unicode]:
      name.OU = info["organization-unit-name"].encode("utf8")
   if info.has_key("email-address") and type(info["email-address"]) in [str, unicode]:
      name.emailAddress = info["email-address"].encode("utf8")


def extract_info_from_x509name(name):
   """
   Create info dictionary from X509 name object.

   :param name: The X509 name object from which to extract info.
   :type name: crypto.X509Name instance
   :returns dict -- Info dictionary for X509 entity.
   """
   info = {}
   if name.CN:
      info["common-name"] = name.CN
   else:
      info["common-name"] = ""
   if name.C:
      info["country-name"] = name.C
   else:
      info["country-name"] = ""
   if name.ST:
      info["state-or-province-name"] = name.ST
   else:
      info["state-or-province-name"] = ""
   if name.L:
      info["locality-name"] = name.L
   else:
      info["locality-name"] = ""
   if name.O:
      info["organization-name"] = name.O
   else:
      info["organization-name"] = ""
   if name.OU:
      info["organization-unit-name"] = name.OU
   else:
      info["organization-unit-name"] = ""
   if name.emailAddress:
      info["email-address"] = name.emailAddress
   else:
      info["email-address"] = ""
   return info


def generate_rsa_key(length = 1024):
   """
   Generate new RSA key pair.

   :param length: Length of key, must be one of 1024, 2048 or 4096.
   :type length: int
   :returns tuple -- (Key PEM, Public Key PEM, Key Fingerprint).
   """
   pkey = crypto.PKey()
   pkey.generate_key(crypto.TYPE_RSA, length)

   keypem = crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey)

   # FIXME: pyOpenSSL lacks a dump_publickey method, so we use pyCrypto for that
   pkey2 = RSA.importKey(keypem).publickey()
   pub_keypem = pkey2.exportKey()

   # FIXME: pyOpenSSL lacks a fingerprint method, so we use pyCrypto for that
   fp = fingerprint(pkey2.exportKey(format = 'DER'))

   return (keypem, pub_keypem, fp)


def check_rsa_key(keyPem):
   """
   Load and checks a private RSA key.

   :param keyPem: Subject private RSA key in PEM format.
   :type keyPem: str
   :returns tuple -- (key length, key fingerprint).
   """
   key = crypto.load_privatekey(crypto.FILETYPE_PEM, keyPem)
   key.check()

   # FIXME: pyOpenSSL lacks a dump_publickey method, so we use pyCrypto for that
   pkey2 = RSA.importKey(keyPem).publickey()
   pub_keypem = pkey2.exportKey()

   # FIXME: pyOpenSSL lacks a fingerprint method, so we use pyCrypto for that
   fp = fingerprint(pkey2.exportKey(format = 'DER'))

   return (pub_keypem, key.bits(), fp)


def create_certificate_signing_request(subjectKey,
                                       subjectInfo,
                                       version = 0,
                                       hash = 'sha1'):
   """
   Create a certificate signing request (CSR) and return CSR
   in PEM and text formats.

   :param subjectKey: Subject private RSA key in PEM format.
   :type subjectKey: str
   :param subjectInfo: Subject information.
   :type subjectInfo: dict
   :returns tuple -- (CSR in PEM format, CSR as Text).
   """
   skey = crypto.load_privatekey(crypto.FILETYPE_PEM, subjectKey)

   req = crypto.X509Req()
   subj = req.get_subject()
   fill_x509name_from_info(subj, subjectInfo)
   req.set_pubkey(skey)
   req.set_version(version)
   req.sign(skey, hash)

   csr_pem = crypto.dump_certificate_request(crypto.FILETYPE_PEM, req)

   # FIXME: needs crypto.FILETYPE_TEXT
   csr_text = '???'
   return (csr_pem, csr_text)


def create_certificate(issuerKeyPem,
                       issuerCertPem,
                       csrPem,
                       validForDays,
                       serial,
                       version = 0,
                       digest = 'sha1'):
   """
   Create a certificate and return certificate (PEM, text, fingerprint).

   :param subjectPrivKey: Subject private RSA key in PEM format.
   :type subjectPrivKey: str
   :param subjectInfo: Subject information.
   :type subjectInfo: dict
   :returns tuple -- (CSR in PEM format, CSR as text).
   """
   issuerKey = crypto.load_privatekey(crypto.FILETYPE_PEM, issuerKeyPem)
   issuerCert = crypto.load_certificate(crypto.FILETYPE_PEM, issuerCertPem)
   csr = crypto.load_certificate_request(crypto.FILETYPE_PEM, csrPem)

   cert = crypto.X509()
   cert.set_serial_number(serial)
   cert.set_version(version)
   cert.gmtime_adj_notBefore(0)
   cert.gmtime_adj_notAfter(60 * 60 * 24 * validForDays)
   cert.set_issuer(issuerCert.get_subject())
   cert.set_subject(csr.get_subject())
   cert.set_pubkey(csr.get_pubkey())
   cert.sign(issuerKey, digest)

   certPem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
   certText = '???'
   certFingerprint = cert.digest(digest)

   return (certPem, certText, certFingerprint)


def create_selfsigned_certificate(entityPrivKey,
                                  entityInfo,
                                  validForDays,
                                  serial = 0,
                                  version = 0,
                                  digest = 'sha1'):
   """
   Create a self-signed certificate and return certificate (PEM, text, fingerprint).
   """
   ekey = crypto.load_privatekey(crypto.FILETYPE_PEM, entityPrivKey)

   req = crypto.X509Req()
   subj = req.get_subject()
   fill_x509name_from_info(subj, entityInfo)
   req.set_pubkey(ekey)
   req.sign(ekey, digest)

   cert = crypto.X509()
   cert.set_serial_number(serial)
   cert.set_version(version)
   cert.gmtime_adj_notBefore(0)
   cert.gmtime_adj_notAfter(60 * 60 * 24 * validForDays)
   cert.set_issuer(req.get_subject())
   cert.set_subject(req.get_subject())
   cert.set_pubkey(req.get_pubkey())
   cert.sign(ekey, digest)

   certPem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
   certText = '???'
   certFingerprint = cert.digest(digest)

   return (certPem, certText, certFingerprint)


def unpack_certificate(certificatePem):
   """
   Unpack X509 PEM-encoded certificate.

   :param certificatePem: PEM encoded X509 certificate.
   :type certificatePem: str
   :returns tuple -- (Dict of detailed information from the certificate, Certificate Text).
   """
   cert = crypto.load_certificate(crypto.FILETYPE_PEM, certificatePem)

   res = {}

   ## we include the reserialized PEM encoding (which in principle
   ## should be identical to certificatePem .. but who knows .. this
   ## is x509 crap)
   res["pem"] = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
   res["fingerprint"] = cert.digest('sha1')

   ## we convert this to dotted hex, since the version
   ## might be a unsigned long (8 bytes) which i.e. JavaScript
   ## can't consume
   serial = "0x%x" % cert.get_serial_number()
   res["serial"] = dotted(serial[2:])

   res["version"] = cert.get_version()
   res["issuer"] = extract_info_from_x509name(cert.get_issuer())
   res["subject"] = extract_info_from_x509name(cert.get_subject())

   # ASN1 GENERALIZEDTIME : YYYYMMDDhhmmssZ
   ASN1_TIMESTAMP_FORMAT = "%Y%m%d%H%M%SZ"
   not_before = datetime.datetime.strptime(cert.get_notBefore(), ASN1_TIMESTAMP_FORMAT)
   not_after = datetime.datetime.strptime(cert.get_notAfter(), ASN1_TIMESTAMP_FORMAT)

   UTC_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
   res["not-valid-before"] = not_before.strftime(UTC_TIMESTAMP_FORMAT)
   res["not-valid-after"] = not_after.strftime(UTC_TIMESTAMP_FORMAT)

   now = datetime.datetime.utcnow()
   res["expired"] = not (not_before <= now and now <= not_after)

   pubkey = cert.get_pubkey()

   res["public-key"] = {"length": pubkey.bits(),
                        "fingerprint": ZERODIGEST} # FIXME

   # FIXME
   #res["is-selfsigned"] = True if cert.verify(pubkey) == 1 else False

   text = """Version: %(version)s
Serial: %(serial)s
Fingerprint: %(fingerprint)s
Validity: %(not-valid-before)s - %(not-valid-after)s
Expired: %(expired)s
""" % res

   for k in [("Issuer", "issuer"), ("Subject", "subject")]:
      text += "\n" + k[0] + "\n"
      text += """   Common Name: %(common-name)s
   Country: %(country-name)s
   State/Province: %(state-or-province-name)s
   Locality: %(locality-name)s
   Organization: %(organization-name)s
   Organization Unit: %(organization-unit-name)s
   Email: %(email-address)s
""" % res[k[1]]

   return res, text


if __name__ == '__main__':

   ## create self-signed CA key/cert
   ##
   ca_info = {'common-name': 'Certificate Authority',
              'organization-name': 'Tavendo GmbH',
              'country-name': 'DE'}

   (ca_key, ca_keypub, ca_fingerprint) = generate_rsa_key(1024)
   (ca_cert, ca_cert_text, ca_cert_fingperint) = create_selfsigned_certificate(ca_key, ca_info, 365)

   ## create server key/CSR
   ##
   s1_info = {'common-name': 'www.tavendo.de',
              'organization-name': 'Tavendo GmbH',
              'country-name': 'DE'}

   (s1_key, s1_keypub, s1_fingerprint) = generate_rsa_key(1024)
   (s1_csr, s1_csr_text) = create_certificate_signing_request(s1_key, s1_info)

   ## create server cert
   ##
   (s1_cert, s1_cert_text, s1_cert_fingperint) = create_certificate(ca_key, ca_cert, s1_csr, 365, 1)
   print unpack_certificate(s1_cert)
