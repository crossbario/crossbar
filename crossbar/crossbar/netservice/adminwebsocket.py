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


import hmac, hashlib, binascii, random, datetime, re, urlparse, urllib

from twisted.application import service
from twisted.python import log
from twisted.python.failure import Failure

from autobahn.util import utcnow, parseutc
from autobahn.websocket import WebSocketProtocol, listenWS
from autobahn.wamp import WampServerFactory, WampCraServerProtocol
from autobahn.wamp import exportRpc
from autobahn.wamp import json_loads, json_dumps

import crossbar

from crossbar.cryptoutil import encrypt_and_sign
from crossbar.tlsctx import TlsContextFactory

from crossbar.adminwebmodule.uris import *
from crossbar.adminwebmodule.appcreds import AppCreds

from crossbar.adminwebmodule.hanaconnects import HanaConnects
from crossbar.adminwebmodule.hanapushrules import HanaPushRules
from crossbar.adminwebmodule.hanaremotes import HanaRemotes

from crossbar.adminwebmodule.pgconnects import PgConnects
from crossbar.adminwebmodule.pgpushrules import PgPushRules
from crossbar.adminwebmodule.pgremotes import PgRemotes

from crossbar.adminwebmodule.oraconnects import OraConnects
from crossbar.adminwebmodule.orapushrules import OraPushRules
from crossbar.adminwebmodule.oraremotes import OraRemotes

from crossbar.adminwebmodule.postrules import PostRules
from crossbar.adminwebmodule.ftpusers import FtpUsers
from crossbar.adminwebmodule.servicekeys import ServiceKeys
from crossbar.adminwebmodule.clientperms import ClientPerms
from crossbar.adminwebmodule.extdirectremotes import ExtDirectRemotes
from crossbar.adminwebmodule.restremotes import RestRemotes
from crossbar.adminwebmodule.serviceconfig import ServiceConfig
from crossbar.adminwebmodule.servicestatus import ServiceStatus
from crossbar.adminwebmodule.servicecontrol import ServiceControl
from crossbar.database import Database

import json
from crossbar.customjson import CustomJsonEncoder


class AdminWebSocketProtocol(WampCraServerProtocol):

   USER_PASSWORD_PATTERN = """^[a-zA-Z0-9_\-!$%&/=()"?+*#,;.:\[\]<>|~{}']*$"""
   USER_PASSWORD_MIN_LENGTH = 6
   USER_PASSWORD_MAX_LENGTH = 20

   def onSessionOpen(self):
      """
      Entry point when admin UI is connected.
      """
      self.dbpool = self.factory.dbpool

      self.registerForRpc(self, URI_API, [AdminWebSocketProtocol.isActivated,
                                          AdminWebSocketProtocol.createActivationRequest,
                                          AdminWebSocketProtocol.getPasswordSet,
                                          AdminWebSocketProtocol.setPassword])

      self.serviceConfig = ServiceConfig(self)

      ## override global client auth options
      self.clientAuthTimeout = 120
      self.clientAuthAllowAnonymous = False

      self.authUser = None

      ## call base class method
      WampCraServerProtocol.onSessionOpen(self)


   def _getPasswordSet(self, txn):
      txn.execute("SELECT value FROM config WHERE key = ?", ["admin-password"])
      res = txn.fetchone()
      if res:
         password = json_loads(res[0])
         return password is not None
      else:
         raise Exception(URI_ERROR + "internal-error", "admin-password key not found.")

   @exportRpc("get-password-set")
   def getPasswordSet(self):
      return self.dbpool.runInteraction(self._getPasswordSet)


   def _getEulaAccepted(self, txn):
      txn.execute("SELECT value FROM config WHERE key = ?", ["eula-accepted"])
      res = txn.fetchone()
      if res:
         eula_accepted = json_loads(res[0])
         return eula_accepted
      else:
         raise Exception(URI_ERROR + "internal-error", "eula-accepted key not found.")

   @exportRpc("get-eula-accepted")
   def getEulaAccepted(self):
      return self.dbpool.runInteraction(self._getEulaAccepted)


   def _acceptEula(self, txn):
      txn.execute("SELECT value FROM config WHERE key = ?", ["eula-accepted"])
      res = txn.fetchone()
      if res:
         eula_accepted = json_loads(res[0])
         if eula_accepted:
            raise Exception(URI_ERROR + "illegal-invocation", "EULA already accepted.")
         else:
            now = utcnow()
            txn.execute("UPDATE config SET value = ? WHERE key = ?", [json_dumps(now), "eula-accepted"])
            self.factory.services["config"].recache(txn)
            return now
      else:
         raise Exception(URI_ERROR + "internal-error", "EULA key not found.")

   @exportRpc("accept-eula")
   def acceptEula(self):
      return self.dbpool.runInteraction(self._acceptEula)


   def _isActivated(self, txn):
      if True:
         return {'license-id': '',
                 'type': 'BETA',
                 'connected-cap': 0,
                 'tls-enabled': True,
                 'valid-from': '1970-01-01T00:00:00:00Z',
                 'valid-to': '2020-01-01T00:00:00:00Z'}
      else:
         now = utcnow()
         txn.execute("SELECT license_id, license_type, connection_cap, tls_enabled, valid_from, valid_to FROM license WHERE enabled = 1 AND valid_from <= ? AND valid_to > ?", [now, now])
         res = txn.fetchone()
         if res:
            return {'license-id': res[0],
                    'type': res[1],
                    'connected-cap': res[2],
                    'tls-enabled': True if res[3] != 0 else False,
                    'valid-from': res[4],
                    'valid-to': res[5]}
         else:
            return None

   @exportRpc("is-activated")
   def isActivated(self):
      #return True
      return self.dbpool.runInteraction(self._isActivated)


   def _createActivationRequest(self, txn, origin, licenseType, extra):

      LICENSE_TYPES = ['BETA']

      if licenseType not in LICENSE_TYPES:
         raise Exception(URI_ERROR + "illegal-argument", "Unknown license type '%s'" % str(licenseType), LICENSE_TYPES)

      ## construct license activation request
      ##
      hostid = self.factory.services['platform'].getHostId()
      instanceid = self.serviceConfig._getSingleConfig(txn, "instance-id")
      msg = {'type': licenseType,
             'host-id': hostid,
             'instance-id': instanceid}

      dbcreated = self.serviceConfig._getSingleConfig(txn, "database-created")
      platform = self.factory.services['platform'].getPlatformInfo()
      network = self.factory.services['platform'].getNetworkConfig()

      msg['info'] = {'request-time': utcnow(),
                     'database-created': dbcreated,
                     'platform': platform,
                     'network': network}

      if extra is not None:
         msg['extra'] = extra

      log.msg("created license activation request: %s" % msg)

      rmsg = json_dumps(msg)

      ## load instance key pair
      ##
      pubkey = str(self.serviceConfig._getSingleConfig(txn, "instance-pub-key"))
      privkey = str(self.serviceConfig._getSingleConfig(txn, "instance-priv-key"))

      ## encrypt activation request for Tavendo public key
      ## and sign encrypted message using instance private key
      ##
      (emsg, skey, dig, sig) = encrypt_and_sign(rmsg,
                                                privkey,
                                                Database.WEBMQ_LICENSE_CA_PUBKEY)

      payload = "%s,%s,%s,%s,%s,%s" % (emsg,
                                       skey,
                                       dig,
                                       sig,
                                       urllib.quote_plus(pubkey),
                                       urllib.quote_plus(origin + "/doactivate"))

      #print payload

      return {'request': msg,
              'url': self.factory.services['master'].licenseserver,
              'payload': payload}


   @exportRpc("create-activation-request")
   def createActivationRequest(self, origin, licenseType, extra = None):
      """
      Create activation request for appliance.

      :param origin: Must be filled with "window.location.origin". This will be used to direct the license activation POST back to this instance.
      :type origin: str
      :param licenseType: Type of license: currently, only "BETA" is allowed.
      :type licenseType: str
      :param extra: User provided extra information like name or email.
      :type extra: dict

      Example:

         session.call("api:create-activation-request",
                      window.location.origin,
                      "BETA",
                      {name: "Foobar Corp.", email: "bob.ross@foobar.com"}).then(ab.log, ab.log);
      """
      return self.dbpool.runInteraction(self._createActivationRequest, origin, licenseType, extra)


   @exportRpc("get-license-options")
   def getLicenseOptions(self):
      return self.factory.services['database'].getLicenseOptions()


   @exportRpc("get-installed-options")
   def getInstalledOptions(self):
      return self.factory.services['database'].getInstalledOptions()


   @exportRpc("login-request")
   def loginRequest(self, username):
      """
      Challenge-response authentication request.
      """
      if type(username) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument username, but got %s" % str(type(username)))

      username = username.encode("utf-8")
      if username != "admin":
         raise Exception(URI_ERROR + "invalid-user", "User %s not known" % str(username))

      self.authChallenge = ''.join([random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_") for i in xrange(16)])
      self.authChallengeUser = username
      return self.authChallenge


   def _login(self, txn, authResponse, stayLoggedIn):

      if self.authChallenge is None:
         raise Exception(URI_ERROR + "login-without-previous-request", "Login attempt without previous login request.")

      txn.execute("SELECT value FROM config WHERE key = ?", ['admin-password'])
      res = txn.fetchone()
      if res:
         pw = str(json_loads(res[0]))
         h = hmac.new(pw, self.authChallenge, hashlib.sha256)
         v = binascii.b2a_base64(h.digest()).strip()
         if v == str(authResponse):
            self.authUser = self.authChallengeUser
            if stayLoggedIn:
               cookie = ''.join([random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_") for i in xrange(64)])
               now = utcnow()
               txn.execute("INSERT INTO cookie (created, username, value) VALUES (?, ?, ?)", [now, "admin", cookie])
               self.authCookie = cookie
               res = cookie
            else:
               res = None
            self.onLogin()
            return res
         else:
            raise Exception(URI_ERROR + "login-failed", "Login failed.")
      else:
         raise Exception(URI_ERROR + "internal-error", "Could not retrieve admin password from database.")


   @exportRpc("login")
   def login(self, authResponse, stayLoggedIn = False):
      """
      Login the user via a response to a previous authentication challenge.
      """
      if self.authUser is not None:
         raise Exception(URI_ERROR + "already-authenticated", "Connection is already authenticated")
      return self.dbpool.runInteraction(self._login, authResponse, stayLoggedIn)


   def _cookieLogin(self, txn, cookie):
      if type(cookie) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument cookie, but got %s" % str(type(cookie)))

      txn.execute("SELECT created, username FROM cookie WHERE value = ?", [cookie])
      res = txn.fetchone()
      if res is not None:
         created = parseutc(res[0])
         now = datetime.datetime.utcnow()
         lifetime = (now - created).total_seconds()
         expiration = self.factory.services["config"].get("auth-cookie-lifetime", 600)
         if expiration > 0 and lifetime > expiration:
            txn.execute("DELETE FROM cookie WHERE value = ?", [cookie])
            raise Exception(URI_ERROR + "expired-cookie", "Authentication cookie expired.")
         self.authUser = str(res[1])
         self.authCookie = cookie
         self.onLogin()
      else:
         raise Exception(URI_ERROR + "bad-cookie", "Invalid authentication cookie.")


   @exportRpc("cookie-login")
   def cookieLogin(self, cookie):
      """
      Login the user via a cookie.
      """
      if self.authUser is not None:
         raise Exception(URI_ERROR + "already-authenticated", "Connection is already authenticated")
      return self.dbpool.runInteraction(self._cookieLogin, cookie)


   def getAuthPermissions(self, authKey, authExtra):
      ## return permissions which will be granted for the auth key
      ## when the authentication succeeds
      return {'permissions': {}}


   def _getAuthSecret(self, txn):
      txn.execute("SELECT value FROM config WHERE key = ?", ['admin-password'])
      res = txn.fetchone()
      if res:
         pw = str(json_loads(res[0]))
         return pw
      else:
         raise Exception(URI_ERROR + "internal-error", "Could not retrieve admin password from database.")


   def getAuthSecret(self, authKey):
      ## return the auth secret for the given auth key or None when the auth key
      ## does not exist
      if authKey != "admin":
         return None
      else:
         return self.dbpool.runInteraction(self._getAuthSecret)


   def onAuthenticated(self, authKey, perms):
      """
      Called when user was logged in. Register the full set of
      RPCs and PubSub topics.
      """
      self.authUser = authKey

      licenseOpts = self.factory.services["database"].getLicenseOptions()

      #self.serviceConfig = ServiceConfig(self)
      self.registerForRpc(self.serviceConfig, URI_API)

      self.appCreds = AppCreds(self)
      self.registerForRpc(self.appCreds, URI_API)

      if licenseOpts["hana"]:
         self.hanaConnects = HanaConnects(self)
         self.registerForRpc(self.hanaConnects, URI_API)

         self.hanaPushRules = HanaPushRules(self)
         self.registerForRpc(self.hanaPushRules, URI_API)

         self.hanaRemotes = HanaRemotes(self)
         self.registerForRpc(self.hanaRemotes, URI_API)

      if licenseOpts["postgresql"]:
         self.pgConnects = PgConnects(self)
         self.registerForRpc(self.pgConnects, URI_API)

         self.pgPushRules = PgPushRules(self)
         self.registerForRpc(self.pgPushRules, URI_API)

         self.pgRemotes = PgRemotes(self)
         self.registerForRpc(self.pgRemotes, URI_API)

      if licenseOpts["oracle"]:
         self.oraConnects = OraConnects(self)
         self.registerForRpc(self.oraConnects, URI_API)

         self.oraPushRules = OraPushRules(self)
         self.registerForRpc(self.oraPushRules, URI_API)

         self.oraRemotes = OraRemotes(self)
         self.registerForRpc(self.oraRemotes, URI_API)

      self.postRules = PostRules(self)
      self.registerForRpc(self.postRules, URI_API)

      self.ftpUsers = FtpUsers(self)
      self.registerForRpc(self.ftpUsers, URI_API)

      self.serviceKeys = ServiceKeys(self)
      self.registerForRpc(self.serviceKeys, URI_API)

      self.clientPerms = ClientPerms(self)
      self.registerForRpc(self.clientPerms, URI_API)

      self.extDirectRemotes = ExtDirectRemotes(self)
      self.registerForRpc(self.extDirectRemotes, URI_API)

      self.restRemotes = RestRemotes(self)
      self.registerForRpc(self.restRemotes, URI_API)

      self.serviceStatus = ServiceStatus(self)
      self.registerForRpc(self.serviceStatus, URI_API)

      self.serviceControl = ServiceControl(self)
      self.registerForRpc(self.serviceControl, URI_API)

      self.registerForRpc(self, URI_API)

      ## register prefix URI_EVENT for topics
      self.registerForPubSub(URI_EVENT, True)

      ## register prefix URI_WIRETAP_EVENT for topics
      self.registerForPubSub(URI_WIRETAP_EVENT, True)


   def onLogout(self):
      """
      Called when user is logged out. Automatically close WebSocket connection.
      """
      self.sendClose(WebSocketProtocol.CLOSE_STATUS_CODE_NORMAL, "logged out")


   def _logout(self, txn):
      if self.authCookie is not None:
         txn.execute("DELETE FROM cookie WHERE value = ?", [self.authCookie])
      self.dispatch(URI_EVENT + "on-logout", self.authCookie, eligible = [self])
      self.authUser = None
      self.authCookie = None
      self.onLogout()


   @exportRpc("logout")
   def logout(self):
      """
      Logout the user. If the user was authenticated via a cookie, the cookie
      is expired/deleted.
      """
      self.raiseIfNotAuthenticated()
      return self.dbpool.runInteraction(self._logout)


   def _setPassword(self, txn, password1, password2):
      txn.execute("SELECT value FROM config WHERE key = ?", ['admin-password'])
      res = txn.fetchone()
      if res:
         pw = json_loads(res[0])
         if pw is not None:
            raise Exception((URI_ERROR + "invalid-invocation", "Initial password already set."))
      else:
         raise Exception(URI_ERROR + "internal-error", "Could not retrieve admin password from database.")

      attrs = {"password1": (True,
                             [str, unicode],
                             AdminWebSocketProtocol.USER_PASSWORD_MIN_LENGTH,
                             AdminWebSocketProtocol.USER_PASSWORD_MAX_LENGTH,
                             AdminWebSocketProtocol.USER_PASSWORD_PATTERN),
               "password2": (True,
                             [str, unicode],
                             AdminWebSocketProtocol.USER_PASSWORD_MIN_LENGTH,
                             AdminWebSocketProtocol.USER_PASSWORD_MAX_LENGTH,
                             AdminWebSocketProtocol.USER_PASSWORD_PATTERN)}

      errcnt, errs = self.checkDictArg("user password", {"password1": password1, "password2": password2}, attrs)

      if password1 != password2:
         errcnt += 1
         if not errs.has_key('password1') or errs.has_key('password2'):
            p = 'password1'
         else:
            p = 'password2'
         if not errs.has_key(p):
            errs[p] = []
         errs[p].append((self.shrink(URI_ERROR + "invalid-attribute-value"), "Passwords do not match"))

      if errcnt:
         raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)

      txn.execute("UPDATE config SET value = ? WHERE key = ?", [json_dumps(password1), "admin-password"])


   @exportRpc("set-password")
   def setPassword(self, password1, password2):
      """
      Set initial password.
      """
      return self.dbpool.runInteraction(self._setPassword, password1, password2)


   def _changePassword(self, txn, oldpassword, newpassword1, newpassword2):
      attrs = {"oldpassword": (True,
                               [str, unicode],
                               AdminWebSocketProtocol.USER_PASSWORD_MIN_LENGTH,
                               AdminWebSocketProtocol.USER_PASSWORD_MAX_LENGTH,
                               AdminWebSocketProtocol.USER_PASSWORD_PATTERN),
               "newpassword1": (True,
                                [str, unicode],
                                AdminWebSocketProtocol.USER_PASSWORD_MIN_LENGTH,
                                AdminWebSocketProtocol.USER_PASSWORD_MAX_LENGTH,
                                AdminWebSocketProtocol.USER_PASSWORD_PATTERN),
               "newpassword2": (True,
                                [str, unicode],
                                AdminWebSocketProtocol.USER_PASSWORD_MIN_LENGTH,
                                AdminWebSocketProtocol.USER_PASSWORD_MAX_LENGTH,
                                AdminWebSocketProtocol.USER_PASSWORD_PATTERN)}

      errcnt, errs = self.checkDictArg("user password",
                                       {"oldpassword": oldpassword,
                                        "newpassword1": newpassword1,
                                        "newpassword2": newpassword2},
                                       attrs)

      if newpassword1 != newpassword2:
         errcnt += 1
         if not errs.has_key('newpassword1') or errs.has_key('newpassword2'):
            p = 'newpassword1'
         else:
            p = 'newpassword2'
         if not errs.has_key(p):
            errs[p] = []
         errs[p].append((self.shrink(URI_ERROR + "invalid-attribute-value"), "New password values do not match"))

      if errcnt:
         raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)

      txn.execute("SELECT value FROM config WHERE key = ?", ['admin-password'])
      res = txn.fetchone()
      if res:
         pw = str(json_loads(res[0]))
         if pw == oldpassword:
            if newpassword1 != oldpassword:
               txn.execute("UPDATE config SET value = ? WHERE key = ?", [json_dumps(newpassword1), "admin-password"])
            else:
               raise Exception(URI_ERROR + "illegal-argument",
                               "one or more illegal arguments (%d errors)" % 2,
                               {'newpassword1': [(self.shrink(URI_ERROR + "attribute-value-unchanged"), "Password unchanged")],
                                'newpassword2': [(self.shrink(URI_ERROR + "attribute-value-unchanged"), "Password unchanged")]})
         else:
            raise Exception(URI_ERROR + "illegal-argument",
                            "one or more illegal arguments (%d errors)" % 1,
                            {'oldpassword': [(self.shrink(URI_ERROR + "invalid-attribute-value"), "Old password is invalid")]})
      else:
         raise Exception(URI_ERROR + "internal-error", "Could not retrieve admin password from database.")


   @exportRpc("change-password")
   def changePassword(self, oldpassword, newpassword1, newpassword2):
      """
      Change the password of the currently logged in user.
      """
      self.raiseIfNotAuthenticated()
      return self.dbpool.runInteraction(self._changePassword, oldpassword, newpassword1, newpassword2)


   def raiseIfNotAuthenticated(self):
      if self.authUser is None:
         raise Exception(URI_ERROR + "not-authenticated", "Connection is not authenticated")



   ##################################################################################################
   ## FIXME: REFACTOR THE FOLLOWING


   def uriToId(self, uri):
      """
      Create object ID within database (which is a UUID) from a object URI.
      """
      return uri[uri.rfind("/") + 1:]


   def validateUri(self, uri, allowEmptyNetworkLocation = True):

      ## valid URI: absolute URI from http(s) scheme, no query component
      ##
      errs = []
      normalizedUri = None
      try:
         p = urlparse.urlparse(uri)

         if p.scheme == "":
            errs.append((self.shrink(URI_ERROR + "missing-uri-scheme"),
                         "URI '%s' does not contain a scheme." % uri))
         else:
            if p.scheme not in ['http', 'https']:
               errs.append((self.shrink(URI_ERROR + "invalid-uri-scheme"),
                            "URI '%s' scheme '%s' is invalid (only 'http' or 'https' allowed." % (uri, p.scheme)))

         if p.netloc == "" and not allowEmptyNetworkLocation:
            errs.append((self.shrink(URI_ERROR + "missing-uri-network-location"),
                         "URI '%s' does not contain a network location." % uri))

         if p.query != "":
            errs.append((self.shrink(URI_ERROR + "uri-contains-query-component"),
                         "URI '%s' contains a query component '%s'." % (uri, p.query)))

         normalizedUri = urlparse.urlunparse(p)

      except Exception, e:
         errs.append((self.shrink(URI_ERROR + "invalid-uri"),
                      "Invalid URI '%s' - could not parse URI (%s)" % (uri, str(e))))

      return (normalizedUri, errs)


   def cleanErrs(self, errs):
      acnt = 0
      tcnt = 0
      cerrs = {}
      for e in errs:
         l = len(errs[e])
         if l > 0:
            cerrs[e] = errs[e]
            tcnt += l
            acnt += 1
      return (cerrs, acnt, tcnt)


   def raiseDictArgException(self, errs):
      cerrs, acnt, tcnt = self.cleanErrs(errs)
      if tcnt:
         raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors in %d attributes)" % (tcnt, acnt), cerrs)


   def checkDictArg(self, argname, arg, attrs):
      """
      Check a dict of attributes "arg" for attribute spec "attrs".
      Return errorDetails = {errorLocUri: [(errorTypeUri, errorDesc)]}
      """
      if type(arg) != dict:
         raise Exception(URI_ERROR + "illegal-argument-type",
                         "Expected argument of type dict for %s, got %s" % (argname, str(type(arg))))
      errs = {}
      errcnt = 0
      for a in attrs.keys():
         errs[a] = []
         if attrs[a][0] and not arg.has_key(a):
            errs[a].append((self.shrink(URI_ERROR + "missing-attribute"),
                            "Missing mandatory attribute '%s' in %s" % (a, argname)))
            errcnt += 1
         if arg.has_key(a):

            ## check value type and do graceful conversion where possible
            ##
            go = False
            if type(arg[a]) not in attrs[a][1]:
               try:
                  ## graceful conversion to first accepted value type of spec
                  val = attrs[a][1][0](arg[a])
                  arg[a] = val
                  go = True
               except:
                  errs[a].append((self.shrink(URI_ERROR + "illegal-attribute-type"),
                                  "Expected type %s for %s attribute '%s', got %s" % (" or ".join([str(x) for x in attrs[a][1]]), argname, a, str(type(arg[a])))))
                  errcnt += 1
            else:
               go = True

            ## check value
            ##
            if go:
               if type(arg[a]) in [str, unicode]:
                  if len(attrs[a]) == 3 and type(attrs[a][2]) == list:
                     if str(arg[a]) not in attrs[a][2]:
                        errs[a].append((self.shrink(URI_ERROR + "invalid-attribute-value"),
                                        "Attribute '%s' value invalid (must be one of %s, was %s)" % (a, str(sorted(attrs[a][2])), str(arg[a])),
                                        sorted(attrs[a][2])))
                        errcnt += 1
                  elif len(attrs[a]) >= 4:
                     l = len(arg[a])
                     if l < attrs[a][2]:
                        errs[a].append((self.shrink(URI_ERROR + "attribute-value-too-short"),
                                        "Attribute '%s' value too short (must be at least %d, was %d)" % (a, attrs[a][2], l),
                                        attrs[a][2],
                                        attrs[a][3]))
                        errcnt += 1
                     elif l > attrs[a][3]:
                        errs[a].append((self.shrink(URI_ERROR + "attribute-value-too-long"),
                                        "Attribute '%s' value too long (must be at most %d, was %d)" % (a, attrs[a][3], l),
                                        attrs[a][2],
                                        attrs[a][3]))
                        errcnt += 1
                  if len(attrs[a]) >= 5:
                     if attrs[a][4]:
                        pat = re.compile(attrs[a][4])
                        if not pat.match(arg[a]):
                           errs[a].append((self.shrink(URI_ERROR + "attribute-value-invalid-characters"),
                                           "Attribute '%s' value contains invalid characters (must only contain characters from %s)" % (a, attrs[a][4]),
                                           attrs[a][4]))
                           errcnt += 1
               elif type(arg[a]) in [int, long, float]:
                  if len(attrs[a]) >= 4:
                     l = arg[a]
                     if l < attrs[a][2]:
                        errs[a].append((self.shrink(URI_ERROR + "out-of-range"),
                                        "Attribute '%s' value too small (must be at least %s, was %s)" % (a, attrs[a][2], l),
                                        attrs[a][2],
                                        attrs[a][3]))
                        errcnt += 1
                     elif l > attrs[a][3]:
                        errs[a].append((self.shrink(URI_ERROR + "out-of-range"),
                                        "Attribute '%s' value too large (must be at most %s, was %s)" % (a, attrs[a][3], l),
                                        attrs[a][2],
                                        attrs[a][3]))
                        errcnt += 1
                  elif len(attrs[a]) == 3 and type(attrs[a][2]) == list:
                     if arg[a] not in attrs[a][2]:
                        errs[a].append((self.shrink(URI_ERROR + "invalid-attribute-value"),
                                        "Attribute '%s' value invalid (must be one of %s, was %s)" % (a, str(sorted(attrs[a][2])), arg[a]),
                                        sorted(attrs[a][2])))
                        errcnt += 1
      for a in arg.keys():
         if not attrs.has_key(a):
            errs[a] = [(self.shrink(URI_ERROR + "unknown-attribute"),
                        "Unknown attribute '%s' in %s" % (a, argname))]
            errcnt += 1
      return errcnt, errs


   def cleanStripDictArg(self, arg, attrs):
      for a in attrs:
         if arg.has_key(a):
            s = arg[a].strip()
            if s!= "":
               arg[a] = s
            else:
               arg[a] = None



class AdminWebSocketFactory(WampServerFactory):

   protocol = AdminWebSocketProtocol

   def __init__(self, url, dbpool, services):
      WampServerFactory.__init__(self, url, debugApp = False)
      self.dbpool = dbpool
      self.services = services
      self.restartRequired = False


   #def _serialize(self, obj):
   #   return json_dumps(obj, cls = CustomJsonEncoder)


   def startFactory(self):
      WampServerFactory.startFactory(self)
      log.msg("AdminWebSocketFactory started [speaking %s]" % self.protocols)

      log.msg("debugWamp: %s" % self.debugWamp)
      log.msg("debugApp: %s" % self.debugApp)

      self.updateAvailable = {"update-available": False}
      self.autocheckForUpdates()

      #self.debugWamp = True


   def stopFactory(self):
      log.msg("AdminWebSocketFactory stopped")
      WampServerFactory.stopFactory(self)


   def dispatchAdminEvent(self, topicuri, event):
      return self.dispatch(topicuri, event)


   def issueRestartRequired(self):
      if not self.restartRequired:
         self.restartRequired = True
         self.dispatch(URI_EVENT + "on-restart-required", True, [])


   def getRestartRequired(self):
      return self.restartRequired


   def _autocheckForUpdates(self, result, delay):
      if isinstance(result, Failure):
         log.err("update check: failed! (%s)" % result)
      else:
         self.updateAvailable = result
         self.updateAvailable["checked"] = utcnow()
         if result["update-available"]:
            log.msg("update check: updates found! [%s]" % self.updateAvailable)
            self.dispatch(URI_EVENT + "on-update-available", self.updateAvailable, [])
         else:
            log.msg("update check: ok, no updates found.")
      if delay > 0:
         self.reactor.callLater(delay, self.autocheckForUpdates)
      return self.updateAvailable


   def autocheckForUpdates(self):
      delay = self.services["config"].get("update-check-interval", 600)
      if delay > 0:
         d = self._checkForUpdates()
         d.addBoth(self._autocheckForUpdates, delay)


   def checkForUpdatesNow(self):
      d = self._checkForUpdates()
      d.addBoth(self._autocheckForUpdates, 0)
      return d


   def _checkForUpdatesSuccess(self, index):
      p = re.compile(r'href="(crossbar.*?\.egg)"')
      ab_eggs = p.findall(index)
      versions = sorted([tuple([int(x) for x in s.split("-")[1].split(".")]) for s in ab_eggs])
      if len(versions) > 0:
         latest = versions[-1]
      else:
         latest = []
      installed = tuple([int(x) for x in crossbar.version.split('.')])
      return {"installed": '.'.join([str(x) for x in installed]),
              "latest": '.'.join([str(x) for x in latest]),
              "update-available": installed < latest}


   def _checkForUpdatesFailed(self, error):
      log.msg("check for software updates failed (%s)" % error.value)
      return {"update-available": False}


   def _checkForUpdates(self):

      ## avoid module-level reactor import
      from twisted.web.client import getPage

      update_url = str(self.services["config"].get("update-url"))
      d = getPage(url = update_url,
                  method = 'GET',
                  timeout = 5,
                  followRedirect = False)
      d.addCallbacks(self._checkForUpdatesSuccess, self._checkForUpdatesFailed)
      return d


class AdminWebSocketService(service.Service):

   SERVICENAME = "Admin WebSocket"

   def __init__(self, dbpool, services):
      self.dbpool = dbpool
      self.services = services
      self.isRunning = False
      self.factory = None
      self.listener = None


   def dispatchAdminEvent(self, topic, event):
      if self.factory:
         self.factory.dispatchAdminEvent(topic, event)


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)

      if self.services["config"]["admin-websocket-tls"]:
         contextFactory = TlsContextFactory(self.services["config"]["admin-websocket-tlskey-pem"],
                                            self.services["config"]["admin-websocket-tlscert-pem"],
                                            dhParamFilename = self.services['master'].dhParamFilename)

         uri = "wss://localhost:%d" % self.services["config"]["admin-websocket-port"]
      else:
         contextFactory = None

         uri = "ws://localhost:%d" % self.services["config"]["admin-websocket-port"]

      self.factory = AdminWebSocketFactory(uri, self.dbpool, self.services)
      self.listener = listenWS(self.factory,
                               contextFactory,
                               backlog = self.services["config"]["ws-accept-queue-size"])

      if self.services.has_key("logger"):
         self.services["logger"].setDispatch(self.dispatchAdminEvent)
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      if self.listener:
         self.listener.stopListening()
         self.listener = None
         self.factory = None
      self.isRunning = False
