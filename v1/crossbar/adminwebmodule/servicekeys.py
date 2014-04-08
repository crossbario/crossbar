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


import os, re, datetime

from twisted.python import log

from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

from crossbar.adminwebmodule.uris import *

from crossbar.x509util import generate_rsa_key, \
                           check_rsa_key, \
                           create_selfsigned_certificate, \
                           create_certificate_signing_request, \
                           unpack_certificate

from crossbar.database import Database


class ServiceKeys:
   """
   Service keys model.
   """

   SERVICEKEY_LABEL_MIN_LENGTH = 3
   SERVICEKEY_LABEL_MAX_LENGTH = 40

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _importServiceKeys(self, txn, removeImported):

      ## filled with imported keys
      ##
      svckeys = []

      ## look in keys/certs import directory
      ##
      import_dir = str(self.proto.factory.services["config"].get("import-dir"))
      if os.path.isdir(import_dir):
         log.msg("service key/cert import: walking import directory %s" % import_dir)

         for root, dirs, files in os.walk(import_dir):
            for f in files:

               filename = os.path.join(root, f)
               ext = os.path.splitext(filename)[1][1:]
               basename = os.path.splitext(os.path.basename(filename))[0]

               if ext == 'key':

                  keyFile = filename
                  log.msg("service key/cert import: considering key file %s" % keyFile)

                  ## verify file actually is a RSA key
                  ##
                  try:
                     key_pem = open(keyFile).read()
                     (key_pub_pem, key_length, key_fingerprint) = check_rsa_key(key_pem)
                  except Exception, e:
                     log.msg("skipping key from file %s - invalid RSA key (%s)" % (keyFile, e))
                  else:

                     ## skip keys we already have
                     ##
                     txn.execute("SELECT id FROM servicekey WHERE key_fingerprint = ?", [key_fingerprint])
                     res = txn.fetchone()
                     if res is not None:
                        log.msg("skipping key from file %s already imported (fingerprint %s)" % (keyFile, key_fingerprint))

                     else:

                        ## check if we have a corresponding cert file
                        ##
                        certFile = os.path.join(os.path.dirname(filename), basename + '.crt')

                        if not os.path.isfile(certFile):
                           log.msg("skipping key from file %s because cert file %s does not exist" % (keyFile, certFile))
                        else:
                           try:
                              certPem = open(certFile).read()
                              (cert, cert_text) = unpack_certificate(certPem)
                           except Exception, e:
                              log.msg("skipping cert from file %s - invalid RSA cert (%s)" % (certFile, e))
                           else:

                              log.msg("importing key from file %s (fingerprint %s) and cert from file %s" % (keyFile, key_fingerprint, certFile))

                              id = newid()
                              svckey_uri = URI_SERVICEKEY + id
                              now = utcnow()

                              ## Auto-generate label
                              ##
                              key_label = basename + datetime.datetime.utcnow().strftime("_%Y%m%d_%H%M%S")
                              #key_label = basename

                              txn.execute("INSERT INTO servicekey (id, created, label, key_priv, key_pub, key_length, key_fingerprint, cert, cert_fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                          [id,
                                           now,
                                           key_label,
                                           key_pem,
                                           key_pub_pem,
                                           key_length,
                                           key_fingerprint,
                                           certPem,
                                           cert['fingerprint'],
                                           ])

                              svckey = {"uri": svckey_uri,
                                        "created": now,
                                        "label": key_label,
                                        "length": key_length,
                                        "fingerprint": key_fingerprint,
                                        "public": key_pub_pem,
                                        "certificate": cert,
                                        "certificate-text": cert_text}

                              self.proto.dispatch(URI_EVENT + "on-servicekey-created", svckey, [])

                              svckey["uri"] = self.proto.shrink(svckey_uri)

                              svckeys.append(svckey)

                              if removeImported:
                                 os.remove(keyFile)
                                 os.remove(certFile)
                                 log.msg("removed imported key file %s and cert file %s" % (keyFile, certFile))

               else:
                  #log.msg("skipping file %s" % filename)
                  pass
      else:
         raise Exception("keys/certs import directory does not exist")

      return svckeys


   @exportRpc("import-servicekeys")
   def importServiceKeys(self, removeImported = True):
      """
      Import pairs of service keys/certs from import directory.
      """
      return self.proto.dbpool.runInteraction(self._importServiceKeys, removeImported)


   def _getServiceKeys(self, txn):
      txn.execute("SELECT id, created, modified, label, key_pub, key_length, key_fingerprint, cert FROM servicekey ORDER BY label ASC, key_fingerprint ASC")
      sks = []
      res = txn.fetchall()
      for r in res:
         try:
            (cert, cert_text) = unpack_certificate(str(r[7]))
         except:
            (cert, cert_text) = (None, "")
         sk = {"uri": self.proto.shrink(URI_SERVICEKEY + r[0]),
               "created": r[1],
               "modified": r[2],
               "label": r[3],
               "public": r[4],
               "length": r[5],
               "fingerprint": r[6],
               "certificate": cert,
               "certificate-text": cert_text}
         sks.append(sk)
      return sks


   @exportRpc("get-servicekeys")
   def getServiceKeys(self):
      """
      Return list of service keys.

      Parameters:

         -

      Errors:

         -

      Events:

         -

      Result:

         object[]:

         created:       Creation timestamp of service key.
         modified:      Last modification timestamp for service key.
         label:         Service key label
         public:        Service key RSA public key (PEM format)
         length:        Service key length in bits (1024, 2048 or 4096)
         fingerprint:   Service key public key fingerprint.
         certificate:   Subobject containing the current x509 certificate set for the
                        service key or null when no certificate is set.
      """
      return self.proto.dbpool.runInteraction(self._getServiceKeys)


   def _createSelfSignedCertForServiceKey(self, txn, serviceKeyUri, subjectInfo, validForDays):

      try:
         validForDays = int(validForDays)
         if validForDays < 1 or validForDays > 10000:
            raise Exception(URI_ERROR + "out-of-range", "validForDays must be between 1 and 10000", 1, 10000)
      except:
         raise Exception(URI_ERROR + "illegal-argument-type", "validForDays must be integer (was '%s')" % validForDays)

      if type(serviceKeyUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument serviceKeyUri, but got %s" % str(type(serviceKeyUri)))

      uri = self.proto.resolveOrPass(serviceKeyUri)
      id = self.proto.uriToId(uri)

      txn.execute("SELECT key_priv, selfsigned_cert_serial FROM servicekey WHERE id = ?", [id])
      res = txn.fetchone()

      if res is not None:

         if res[1] is None:
            serial = 1
         else:
            serial = res[1] + 1

         try:
            (cert_pem, cert_text, cert_fingerprint) = create_selfsigned_certificate(str(res[0]),
                                                                                    subjectInfo,
                                                                                    validForDays,
                                                                                    serial)
         except:
            raise Exception(URI_ERROR + "x509-error", "Could not create Self-Signed Certificate (%s)" % str(e), str(e))

         txn.execute("UPDATE servicekey SET selfsigned_cert_serial = ? WHERE id = ?", [serial,
                                             id])

         return {"pem": cert_pem, "text": cert_text}

      else:
         raise Exception(URI_ERROR + "no-such-object", "No service key with URI %s" % uri)


   @exportRpc("create-ssc-for-servicekey")
   def createSelfSignedCertForServiceKey(self, serviceKeyUri, subjectInfo, validForDays = 360):
      """
      Create a new self-signed certificate for an existing PKI service key.

      Parameters:

         serviceKeyUri:          URI or CURIE of existing service key.
         subjectInfo:            Certificate subject detail object[]:

            common-name:         x509 CN field - Subject common name, in case of server certificates
                                 this should be the server's fully qualified hostname, i.e.
                                 "wshub.tavendo.de" - MANDATORY.

            country-name:              x509 C field - Subject ISO country code, i.e. "DE" - OPTIONAL.
            state-or-province-name:    x509 ST field - i.e. "Bayern" - OPTIONAL
            locality-name:             x509 L field - i.e. "Erlangen" - OPTIONAL
            organization-name:         x509 O field - i.e. "Tavendo GmbH" - OPTIONAL
            organization-unit-name:    x509 OU field - i.e. "Network Services" - OPTIONAL
            email-address:             x509 Email field - i.e. "x509@tavendo.de" - OPTIONAL

         validForDays:           Certificate validity in days (from now), i.e. 360.

      Events:

         -

      Errors:

         illegal-argument-type,
         out-of-range,
         no-such-object,
         x509-error

      Result:

         Self-signed x509 certificate object[]:

            pem:     Certificate PEM-encoded.
            text:    Certificate as human-readable text.
      """
      return self.proto.dbpool.runInteraction(self._createSelfSignedCertForServiceKey, serviceKeyUri, subjectInfo, validForDays)


   def _createCsrForServiceKey(self, txn, serviceKeyUri, subjectInfo):

      if type(serviceKeyUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument serviceKeyUri, but got %s" % str(type(serviceKeyUri)))

      uri = self.proto.resolveOrPass(serviceKeyUri)
      id = self.proto.uriToId(uri)

      txn.execute("SELECT key_priv, key_pub FROM servicekey WHERE id = ?", [id])
      res = txn.fetchone()

      if res is not None:

         try:
            (csr_pem, csr_text) = create_certificate_signing_request(str(res[0]), subjectInfo)
         except Exception, e:
            raise Exception(URI_ERROR + "x509-error", "Could not create CSR (%s)" % str(e), str(e))

         return {"pem": csr_pem, "text": csr_text}

      else:
         raise Exception(URI_ERROR + "no-such-object", "No service key with URI %s" % uri)


   @exportRpc("create-csr-for-servicekey")
   def createCsrForServiceKey(self, serviceKeyUri, subjectInfo):
      """
      Create a CSR for a service key.

      Parameters:

         serviceKeyUri:          URI or CURIE of existing service key.
         subjectInfo:            Certificate subject detail object[]:

            common-name:         x509 CN field - Subject common name, in case of server certificates
                                 this should be the server's fully qualified hostname, i.e.
                                 "wshub.tavendo.de" - MANDATORY.

            country-name:              x509 C field - Subject ISO country code, i.e. "DE" - OPTIONAL.
            state-or-province-name:    x509 ST field - i.e. "Bayern" - OPTIONAL
            locality-name:             x509 L field - i.e. "Erlangen" - OPTIONAL
            organization-name:         x509 O field - i.e. "Tavendo GmbH" - OPTIONAL
            organization-unit-name:    x509 OU field - i.e. "Network Services" - OPTIONAL
            email-address:             x509 Email field - i.e. "x509@tavendo.de" - OPTIONAL

      Events:

         -

      Errors:

         illegal-argument-type,
         no-such-object,
         x509-error

      Result:

         x509 certificate signing request (CSR) object[]:

            pem:     CSR PEM-encoded.
            text:    CSR as human-readable text.
      """
      return self.proto.dbpool.runInteraction(self._createCsrForServiceKey, serviceKeyUri, subjectInfo)


   def _checkCertificate(self, txn, certPem):

      if type(certPem) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument certPem, but got %s" % str(type(certPem)))

      try:
         (cert, cert_text) = unpack_certificate(str(certPem))
      except Exception, e:
         raise Exception(URI_ERROR + "invalid-certificate", "Could not analyze X509 certificate (%s)" % str(e), str(e))
      else:
         ret = {}
         ret["certificate"] = cert

         fp = cert["public-key"]["fingerprint"]
         txn.execute("SELECT id, cert_fingerprint FROM servicekey WHERE key_fingerprint = ?", [fp])

         ## we can only have 1 servicekey here, since there is a unique key on key_fingerprint
         ##
         res = txn.fetchone()
         if res is not None:
            ret["servicekey-uri"] = self.proto.shrink(URI_SERVICEKEY + res[0])
            is_changed = res[1] != cert["fingerprint"]
            ret["is-certificate-changed"] = is_changed
            if is_changed:
               (etls, ctls) = self._getAffectedServices(res[0])
               ret["changed-services"] = ctls
               ret["affected-services"] = etls
            else:
               ret["changed-services"] = []
               ret["affected-services"] = []
            ret["restart-required"] = True if len(etls) > 0 else False
         else:
            ret["servicekey-uri"] = None
            ret["is-certificate-changed"] = False
            ret["changed-services"] = []
            ret["affected-services"] = []
            ret["restart-required"] = False

         return ret


   @exportRpc("check-certificate")
   def checkCertificate(self, certPem):
      """
      Parses a x509 certificate in PEM format and returns detail information.
      This should be called before setting a certificate on a service key.

      Parameters:

         certPem:          x509 certificate in PEM format (as string).

      Events:

         -

      Errors:

         illegal-argument:       Argument was not a string.
         invalid-certificate:    Given string could not be parsed as x509 PEM-encoded certificate.

      Result:

         object[]:

         certificate:      Subobject with certificate detail information.
         servicekey-uri:   Either the URI of the servicekey the certificate matches for
                           or null. In the latter case the certificate cannot be imported.
         is-certificate-changed:    Boolean indicating whether the certificate has changed
                                    w.r.t. any certificate already set for the matching
                                    service key (if any).
         restart-required: Indicates whether a restart of services would be done when
                           the certificate would be set on the matching service key (if any).
         changed-services: List of services that would have their certificate changed, but
                           for which TLS is currently disabled.
         affected-services:   List of services that would have their certificate changed and
                              for which TLS is currently enabled (and thus triggered a restart).
      """
      return self.proto.dbpool.runInteraction(self._checkCertificate, certPem)


   def _setServiceKeyCertificate(self, txn, serviceKeyUri, certPem):

      if type(serviceKeyUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument serviceKeyUri, but got %s" % str(type(serviceKeyUri)))

      uri = self.proto.resolveOrPass(serviceKeyUri)
      id = self.proto.uriToId(uri)

      txn.execute("SELECT key_fingerprint, cert_fingerprint FROM servicekey WHERE id = ?", [id])
      res = txn.fetchone()

      if res is not None:

         try:
            (cert, cert_text) = unpack_certificate(str(certPem))
         except Exception, e:
            raise Exception(URI_ERROR + "invalid-certificate", "Could analyze X509 certificate (%s)" % str(e), str(e))
         else:
            ## check that certificate matches service key
            ##
            fp = cert["public-key"]["fingerprint"]
            if res[0] != fp:
               raise Exception(URI_ERROR + "certificate-does-not-match", "Certificate subject public key does not match service key.")

            ## certificate unchanged
            ##
            if res[1] == cert["fingerprint"]:
               return {}

            ## determine changed/effected services
            ##
            (etls, ctls) = self._getAffectedServices(id)
            restartRequired = True if len(etls) > 0 else False

            now = utcnow()
            txn.execute("UPDATE servicekey SET modified = ?, cert = ?, cert_text = ?, cert_fingerprint = ?, is_cert_selfsigned = ? WHERE id = ?",
                        [now,
                         certPem,
                         cert["text"],
                         cert["fingerprint"],
                         cert["is-selfsigned"],
                         id])

            if restartRequired:
               reactor.callLater(1, self.proto.restartHub)

            delta = {}
            delta["modified"] = now
            delta["uri"] = uri
            delta["certificate"] = cert

            self.proto.dispatch(URI_EVENT + "on-servicekey-modified", delta, [self.proto])

            delta["uri"] = self.proto.shrink(uri)
            return delta

      else:
         raise Exception(URI_ERROR + "no-such-object", "No service key with URI %s" % uri)


   @exportRpc("set-servicekey-certificate")
   def setServiceKeyCertificate(self, serviceKeyUri, certPem):
      """
      Set a X509 certificate for a service key.
      """
      return self.proto.dbpool.runInteraction(self._setServiceKeyCertificate, serviceKeyUri, certPem)


   def _createServiceKey(self, txn, label, keylength):

      attrs = {"label": (True,
                         [str, unicode],
                         ServiceKeys.SERVICEKEY_LABEL_MIN_LENGTH,
                         ServiceKeys.SERVICEKEY_LABEL_MAX_LENGTH,
                         None),
               "keylength": (True,
                             [int],
                             [1024, 2048, 4096])}

      values = {"label": label, "keylength": keylength}

      errcnt, errs = self.proto.checkDictArg("appcred spec", values, attrs)

      if errcnt:
         raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)

      ## generate new RSA key
      ##
      log.msg("generating new service key (length %d) .." % values["keylength"])

      (key_pem, key_pub_pem, key_fingerprint) = generate_rsa_key(values["keylength"])

      log.msg("new service key generated (length %d)" % values["keylength"])

      ## store new key
      ##
      id = newid()
      svckey_uri = URI_SERVICEKEY + id
      now = utcnow()

      txn.execute("INSERT INTO servicekey (id, created, label, key_priv, key_pub, key_length, key_fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  [id,
                   now,
                   values["label"],
                   key_pem,
                   key_pub_pem,
                   values["keylength"],
                   key_fingerprint])

      svckey = {"uri": svckey_uri,
                "created": now,
                "label": values["label"],
                "length": values["keylength"],
                "fingerprint": key_fingerprint,
                "public": key_pub_pem}

      self.proto.dispatch(URI_EVENT + "on-servicekey-created", svckey, [self.proto])

      svckey["uri"] = self.proto.shrink(svckey_uri)
      return svckey


   @exportRpc("create-servicekey")
   def createServiceKey(self, label, keylength = 2048):
      """
      Create a new RSA service key.

      Parameters:

         label:      Label, a string, not necessarily unique.
         length:     Key length, one of 1024, 2048 or 4096.

      Result:

         {"uri":           <service key URI>,
          "created":       <service key creation timestamp>,
          "label":         <service key label>,
          "length":        <service key length>,
          "fingerprint":   <service key fingerprint>}

      Events:

         on-servicekey-created

      Errors:
      """
      return self.proto.dbpool.runInteraction(self._createServiceKey, label, keylength)


   def _modifyServiceKey(self, txn, serviceKeyUri, specDelta):

      if type(serviceKeyUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument serviceKeyUri, but got %s" % str(type(serviceKeyUri)))

      uri = self.proto.resolveOrPass(serviceKeyUri)
      id = self.proto.uriToId(uri)

      txn.execute("SELECT label FROM servicekey WHERE id = ?", [id])
      res = txn.fetchone()

      if res is not None:

         attrs = {"label": (False,
                            [str, unicode],
                            ServiceKeys.SERVICEKEY_LABEL_MIN_LENGTH,
                            ServiceKeys.SERVICEKEY_LABEL_MAX_LENGTH,
                            None)}

         errcnt, errs = self.proto.checkDictArg("servicekey delta spec", specDelta, attrs)

         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         if specDelta.has_key("label"):
            newval = specDelta["label"].strip()
            if newval != res[0]:
               delta["label"] = newval
               sql += ", label = ?"
               sql_vars.append(newval)

         if errcnt:
            raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)

         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE servicekey SET %s WHERE id = ?" % sql, sql_vars)

            self.proto.dispatch(URI_EVENT + "on-servicekey-modified", delta, [self.proto])

            delta["uri"] = self.proto.shrink(uri)
            return delta
         else:
            return {}

      else:
         raise Exception(URI_ERROR + "no-such-object", "No service key with URI %s" % uri)


   @exportRpc("modify-servicekey")
   def modifyServiceKey(self, serviceKeyUri, specDelta):
      """
      Modify service key.
      """
      return self.proto.dbpool.runInteraction(self._modifyServiceKey, serviceKeyUri, specDelta)


   def _getAffectedServices(self, serviceKeyId):
      """
      Given servicekey ID, determine which services would be
      changed and effected by a change to the RSA key and/or cert of
      the servicekey. Returns (effected, changed). If effected is a
      non-empty list, the hub will need a restart.
      """
      etls = []
      ctls = []
      for t in Database.NETPORTS_TLS_PREFIXES:
         s_tls = self.proto.factory.services["config"].get(t + "-tls")
         s_tlskey = self.proto.factory.services["config"].get(t + "-tlskey")
         if s_tlskey == serviceKeyId:
            if s_tls:
               etls.append(t)
            else:
               ctls.append(t)
      return (etls, ctls)


   def _deleteServiceKey(self, txn, serviceKeyUri):

      if type(serviceKeyUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument serviceKeyUri, but got %s" % str(type(serviceKeyUri)))

      uri = self.proto.resolveOrPass(serviceKeyUri)
      id = self.proto.uriToId(uri)

      txn.execute("SELECT created FROM servicekey WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         (etls, ctls) = self._getAffectedServices(id)

         if len(etls) > 0:
            raise Exception(URI_ERROR + "depending-service", "One or more services have TLS activated using this service key.", etls)

         if len(ctls) > 0:
            delta = {}
            for t in ctls:
               delta[t + "-tlskey"] = None
            self.proto.serviceConfig._modifyConfig(txn, delta)

         txn.execute("DELETE FROM servicekey WHERE id = ?", [id])

         self.proto.dispatch(URI_EVENT + "on-servicekey-deleted", uri, [self.proto])

         return self.proto.shrink(uri)

      else:
         raise Exception(URI_ERROR + "no-such-object", "No service key with URI %s" % uri)


   @exportRpc("delete-servicekey")
   def deleteServiceKey(self, serviceKeyUri):
      return self.proto.dbpool.runInteraction(self._deleteServiceKey, serviceKeyUri)
