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


import types

from netaddr import IPAddress

from autobahn.wamp import exportRpc, json_loads, json_dumps

from crossbar.adminwebmodule.uris import *
from crossbar.database import Database


class ServiceConfig:
   """
   Service config model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def _getSingleConfig(self, txn, key):
      txn.execute("SELECT value FROM config WHERE key = ?", [key,])
      res = txn.fetchone()
      if res:
         val = json_loads(res[0])
         if key in Database.NETPORTS_TLS_KEYS and val is not None:
            val = self.proto.shrink(URI_SERVICEKEY + val)
         return val
      else:
         raise Exception(URI_ERROR + "invalid-config-parameter", "No configuration parameter '%s'" % key)


   def _getAllConfig(self, txn):
      txn.execute("SELECT key, value FROM config ORDER BY key")
      res = {}
      for r in txn.fetchall():
         key = r[0]
         val = json_loads(r[1])
         if key in Database.NETPORTS_TLS_KEYS and val is not None:
            val = self.proto.shrink(URI_SERVICEKEY + val)
         res[key] = val
      return res


   def _getMultipleConfig(self, txn, keys):
      all = self._getAllConfig(txn)
      res = {}
      for r in all:
         if r in keys:
            res[r] = all[r]
      return res


   @exportRpc("get-config")
   def getConfig(self, key = None):
      """
      Get configuration, either all or single parameter.
      """
      if type(key) == types.NoneType:
         return self.proto.dbpool.runInteraction(self._getAllConfig)
      elif type(key) in [str, unicode]:
         return self.proto.dbpool.runInteraction(self._getSingleConfig, str(key))
      elif type(key) == list:
         return self.proto.dbpool.runInteraction(self._getMultipleConfig, key)
      else:
         raise Exception(URI_ERROR + "illegal-argument-type",
                         "Expected argument of type str, unicode, None or list for %s, got %s" % (key, str(type(key))))


   def _getConfigChangeset(self, txn, attrs, delta):
      all = delta.copy()
      changed = {}
      ss = ""
      for p in attrs:
         ss += "'%s'," % p
      ss = ss[:-1]
      txn.execute("SELECT key, value FROM config WHERE key IN (" + ss + ")")
      for r in txn.fetchall():
         val = json_loads(r[1])
         if not all.has_key(r[0]):
            all[r[0]] = val
         else:
            if all[r[0]] != val:
               changed[r[0]] = all[r[0]]
      return (all, changed)


   def _setServicePorts(self, txn, ports, dryRun):

      ## check entry argument types
      ##
      if type(ports) != dict:
         raise Exception(URI_ERROR + "invalid-argument", "Invalid argument of type '%s' [expected dict]" % str(type(ports)))

      ## errors will be accumulated here (per port-key)
      ##
      errs = {}

      ## convenience handling in JS
      for u in Database.NETPORTS_TLS_PREFIXES:
         o = u + "-tlskey"
         if ports.has_key(o):
            if ports[o] == "null" or ports[o] == "":
               ports[o] = None

      ## check each port in change for itself
      ##
      uports = {}
      c_tls_flags = {}
      c_tls_keys = {}
      for k in ports.keys():
         if k in Database.NETPORTS:
            try:
               port = int(ports[k])
            except:
               errs[k] = (self.proto.shrink(URI_ERROR + "not-an-integer"), "Invalid value '%s' for port '%s' (not an integer)" % (ports[k], k))
            else:
               if port < 1 or port > 65535:
                  errs[k] = (self.proto.shrink(URI_ERROR + "out-of-range"), "Invalid value %d for port '%s' (out of valid range [1, 65535])" % (port, k))
               else:
                  if k in Database.NETPORTS_READONLY:
                     errs[k] = (self.proto.shrink(URI_ERROR + "read-only"), "Port '%s' is read-only." % k)
                  else:
                     uports[k] = port
         elif k in Database.NETPORTS_TLS_FLAGS:
            if type(ports[k]) != bool:
               errs[k] = (self.proto.shrink(URI_ERROR + "invalid-attribute-type"), "Expected bool for attribute %s, got %s" % (k, str(type(ports[k]))))
            else:
               c_tls_flags[k] = ports[k]
         elif k in Database.NETPORTS_TLS_KEYS:
            if type(ports[k]) not in [str, unicode, types.NoneType]:
               errs[k] = (self.proto.shrink(URI_ERROR + "invalid-attribute-type"), "Expected str/unicode for attribute %s, got %s" % (k, str(type(ports[k]))))
            else:
               c_tls_keys[k] = None
               if ports[k] is not None:
                  ruri = str(ports[k]).strip()
                  if ruri != "":
                     uri = self.proto.resolveOrPass(ruri)
                     id = self.proto.uriToId(uri)
                     c_tls_keys[k] = id
         else:
            errs[str(k)] = (self.proto.shrink(URI_ERROR + "unknown-attribute"), "Illegal attribute '%s'" % k)

      ## determine all TLS flags/keys (changed+existing) and change set
      (all_tls_flags, changed_tls_flags) = self._getConfigChangeset(txn, Database.NETPORTS_TLS_FLAGS, c_tls_flags)
      (all_tls_keys, changed_tls_keys) = self._getConfigChangeset(txn, Database.NETPORTS_TLS_KEYS, c_tls_keys)

      for u in Database.NETPORTS_TLS_PREFIXES:

         o = u + "-tlskey"
         if changed_tls_keys.has_key(o):
            id = changed_tls_keys[o]
            if id is not None:
               txn.execute("SELECT cert FROM servicekey WHERE ID = ?", [id])
               res = txn.fetchone()
               if res:
                  if res[0] is None:
                     errs[o] = (self.proto.shrink(URI_ERROR + "servicekey-without-certificate"), "Service key with URI %s has no certificate" % URI_SERVICEKEY + id)
               else:
                  errs[o] = (self.proto.shrink(URI_ERROR + "no-such-object"), "No service key with URI %s" % URI_SERVICEKEY + id)
            else:
               if all_tls_flags[u + "-tls"]:
                  errs[o] = (self.proto.shrink(URI_ERROR + "tls-enabled-without-servicekey"), "TLS set to enabled, but no service key given.")

         o = u + "-tls"
         if changed_tls_flags.has_key(o):
            if changed_tls_flags[o] and all_tls_keys[u + "-tlskey"] is None:
               errs[o] = (self.proto.shrink(URI_ERROR + "missing-servicekey"), "TLS enabled, but service key missing.")

      ## For Admin Web/WebSocket pair, disallow running Web via TLS, but WebSocket non-TLS
      ## i.e. Firefox throws a "security-exception" when we try that ..
      ## For Hub Web/WebSocket we allow this, since both are "independent" services (that is Hub Web
      ## does not serve the HTML/JS that connects to Hub WebSocket)
      ##
      if all_tls_flags["admin-web-tls"] and not all_tls_flags["admin-websocket-tls"]:
         errs["admin-websocket-tls"] = (self.proto.shrink(URI_ERROR + "non-tls-websocket-from-tls-web"), "TLS on WebSocket port set to enabled, but corresponding Web serving port running non-TLS.")
         errs["admin-web-tls"] = (self.proto.shrink(URI_ERROR + "non-tls-websocket-from-tls-web"), "TLS on WebSocket port set to enabled, but corresponding Web serving port running non-TLS.")

      ## determine all ports (changed+existing) and change set
      ##
      (aports, cports) = self._getConfigChangeset(txn, Database.NETPORTS, uports)

      ## duplicate check
      ##
      if len(set(aports.values())) != len(aports):
         dups = {}
         for d in aports:
            if not dups.has_key(aports[d]):
               dups[aports[d]] = []
            dups[aports[d]].append(d)
         for d in dups:
            if len(dups[d]) > 1:
               for k in dups[d]:
                  errs[k] = (self.proto.shrink(URI_ERROR + "duplicate-value"), "Duplicate port %d for %s" % (d, str(dups[d])))

      ## valid passive FTP port range
      ##
      if aports["ftp-passive-port-start"] > aports["ftp-passive-port-end"]:
         e = (self.proto.shrink(URI_ERROR + "invalid-range"), "Start port must be <= end port")
         errs["ftp-passive-port-start"] = e
         errs["ftp-passive-port-end"] = e

      ## check collisions of service ports with passive FTP port range
      ##
      passive_port_range = xrange(aports["ftp-passive-port-start"], aports["ftp-passive-port-end"] + 1)
      for p in Database.NETPORTS:
         if aports[p] in passive_port_range and p not in ["ftp-passive-port-start", "ftp-passive-port-end"]:
            e = (self.proto.shrink(URI_ERROR + "duplicate-value"),
                 "Duplicate port %d for %s collides with passive FTP port range %d-%d" % (aports[p],
                                                                                          p,
                                                                                          aports["ftp-passive-port-start"],
                                                                                          aports["ftp-passive-port-end"])
                 )
            errs[p] = e

      ## bail out on any errors accumulated
      ##
      if len(errs) > 0:
         raise Exception(URI_ERROR + "invalid-argument", "One or more invalid attributes (see errorDetails).", errs)

      ## now do the actual database update (if there is any change left)
      ##
      delta = {}
      delta.update(cports)
      delta.update(changed_tls_flags)
      delta.update(changed_tls_keys)

      if len(delta) > 0:
         if not dryRun:
            for p in delta:
               txn.execute("UPDATE config SET value = ? WHERE key = ?", [json_dumps(delta[p]), p])

            ## recache config
            services = self.proto.factory.services
            if services.has_key("config"):
              services["config"].recache(txn)

         ## automatically restart services when required
         restartRequired = len(cports) > 0 or len(changed_tls_flags) > 0
         for t in Database.NETPORTS_TLS_PREFIXES:
            if delta.has_key(t + "-tlskey") and all_tls_flags[t + "-tls"]:
               restartRequired = True
               break

         for t in Database.NETPORTS_TLS_KEYS:
            if delta.has_key(t) and delta[t]:
               delta[t] = URI_SERVICEKEY + delta[t]

         if not dryRun:
            self.proto.dispatch(URI_EVENT + "on-service-ports-set", delta, [self.proto])

         for t in Database.NETPORTS_TLS_KEYS:
            if delta.has_key(t) and delta[t]:
               delta[t] = self.proto.shrink(delta[t])

         if restartRequired and not dryRun:
            from twisted.internet import reactor
            reactor.callLater(1, self.proto.serviceControl.restartHub)

      else:
         restartRequired = False

      ## return change set
      ##
      return [delta, restartRequired]


   @exportRpc("set-service-ports")
   def setServicePorts(self, ports, dryRun = False):
      """
      Set service ports. When this leads to an actual change of at least
      one port, the application is automatically restarted!

      Errors:

         ports:         invalid-argument

         ports[]:

            ssh-port,
            hub-web-port,
            hub-websocket-port,
            admin-web-port,
            admin-websocket-port,
            echo-websocket-port,
            ftp-port,
            ftp-passive-port-start,
            ftp-passive-port-end:         not-an-integer,
                                          out-of-range,
                                          invalid-range,
                                          read-only,
                                          duplicate-value

            hub-web-tls,
            hub-websocket-tls,
            admin-web-tls,
            admin-websocket-tls,
            echo-websocket-tls:           illegal-attribute-type

            hub-web-tlskey,
            hub-websocket-tlskey,
            admin-web-tlskey,
            admin-websocket-tlskey,
            echo-websocket-tlskey:        illegal-attribute-type,
                                          no-such-object

            ?:                            unknown-attribute
      """
      return self.proto.dbpool.runInteraction(self._setServicePorts, ports, dryRun)


   def _modifyConfig(self, txn, configDelta):
      ## determine actual set of modified stuff
      ##
      modified = {}
      for c in configDelta:
         txn.execute("SELECT value FROM config WHERE key = ?", [c,])
         res = txn.fetchone()
         if res:
            cval = json_loads(res[0])
            if cval != configDelta[c]:
               modified[c] = configDelta[c]
               txn.execute("UPDATE config SET value = ? WHERE key = ?", [json_dumps(configDelta[c]), c])

      ## only something to do when there was an actual change
      ##
      if len(modified) > 0:
         ## recache config
         ##
         services = self.proto.factory.services
         if services.has_key("config"):
           services["config"].recache(txn)

         ## check if WebSocket option changed .. if so, notify WS factory
         ##
         wsOptionChanged = False
         for k in modified:
            if k[:2] == 'ws':
               wsOptionChanged = True
               break
         if wsOptionChanged:
            if self.proto.factory.services.has_key("appws"):
               self.proto.factory.services["appws"].setOptionsFromConfig()
            if self.proto.factory.services.has_key("echows"):
               self.proto.factory.services["echows"].setOptionsFromConfig()

         ## check for restart required
         ##
         for k in modified:
            if k in Database.SERVICES:
               self.proto.factory.issueRestartRequired()

         ## notify subscribers
         ##
         self.proto.dispatch(URI_EVENT + "on-config-modified", modified, [self.proto])

         ## return modified set to caller
         ##
         return modified
      else:
         ## nothing changed
         ##
         return {}


   @exportRpc("modify-config")
   def modifyConfig(self, configDelta):
      """
      Modify service configuration

      Parameters:

         configDelta:         Configuration change specification.

      Events:

         on-config-modified

      Errors:

         configDelta:                  illegal-argument

         configDelta[]:

            postrule-default-action,
            log-write-interval,
            post-body-limit,
            sig-timestamp-delta-limit,
            update-check-interval,
            auth-cookie-lifetime,
            client-auth-timeout,
            client-auth-allow-anonymous: illegal-attribute-type,
                                         out-of-range

            ?:                         unknown-attribute
      """
      attrs = {"postrule-default-action": (False, [str, unicode], ["ALLOW", "DENY"]),
               "post-body-limit": (False, [int], 0, 1000000),
               "sig-timestamp-delta-limit": (False, [int], 1, 3600),

               "client-auth-timeout": (False, [int], 0, 120),
               "client-auth-allow-anonymous": (False, [bool]),

               "log-retention-time": (False, [int], 0, 24*90),
               "log-write-interval": (False, [int], 1, 600),

               "update-url": (False, [str, unicode], 0, 1000),
               "update-check-interval": (False, [int], 0, 60 * 60 * 24),

               "auth-cookie-lifetime": (False, [int], 0, 60 * 60 * 24 * 30),
               "ftp-passive-public-ip": (False, [str, unicode, types.NoneType], 0, 20),

               "ws-allow-version-0": (False, [bool]),
               "ws-allow-version-8": (False, [bool]),
               "ws-allow-version-13": (False, [bool]),
               "ws-max-connections": (False, [int], 0, 200000),
               "ws-max-frame-size": (False, [int], 0, 16*2**20),
               "ws-max-message-size": (False, [int], 0, 16*2**20),
               "ws-auto-fragment-size": (False, [int], 0, 16*2**20),
               "ws-fail-by-drop": (False, [bool]),
               "ws-echo-close-codereason": (False, [bool]),
               "ws-open-handshake-timeout": (False, [int], 0, 120),
               "ws-close-handshake-timeout": (False, [int], 0, 120),
               "ws-tcp-nodelay": (False, [bool]),
               "ws-mask-server-frames": (False, [bool]),
               "ws-require-masked-client-frames": (False, [bool]),
               "ws-apply-mask": (False, [bool]),
               "ws-validate-utf8": (False, [bool]),
               "ws-enable-webstatus": (False, [bool]),
               "ws-accept-queue-size": (False, [int], 10, 10000),
               "ws-enable-webserver": (False, [bool]),
               "ws-websocket-path": (False, [str, unicode], 2, 100, "^[a-zA-Z0-9_-]*$"),

               "ws-enable-permessage-deflate": (False, [bool]),
               "ws-permessage-deflate-window-size": (False, [int], [0, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]),
               "ws-permessage-deflate-require-window-size": (False, [bool]),

               "appweb-cgi-enable": (False, [bool]),
               "appweb-cgi-path": (False, [str, unicode], 3, 100, r"^[a-zA-Z0-9_\-]*$"),
               "appweb-cgi-processor": (False, [str, unicode], 3, 100, r"^[a-zA-Z0-9_/\-\.\\]*$"),
               }

      for s in Database.SERVICES:
         attrs[s] = (False, [bool])

      errcnt, errs = self.proto.checkDictArg("config modification delta", configDelta, attrs)

      attr = "ftp-passive-public-ip"
      if configDelta.has_key(attr):
         ## normalize
         if configDelta[attr].strip() == "":
            configDelta[attr] = None

         ## check
         if configDelta[attr]:
            try:
               ## normalize
               ip = IPAddress(str(configDelta[attr]))
               configDelta[attr] = str(ip)
               if ip.version != 4:
                  errcnt += 1
                  errs[attr].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"), "Not an IP version 4 address"))
            except:
               errcnt += 1
               errs[attr].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"), "Not an IP address"))

      if configDelta.has_key("update-url") and not errs["update-url"]:
         update_url, errs2 = self.proto.validateUri(configDelta["update-url"])
         errs["update-url"].extend(errs2)
         errcnt += len(errs2)
         configDelta["update-url"] = update_url

      ## bail out if any errors were accumulated
      ##
      if errcnt:
         raise Exception(URI_ERROR + "illegal-argument", "one or more illegal arguments (%d errors)" % errcnt, errs)
      else:
         return self.proto.dbpool.runInteraction(self._modifyConfig, configDelta)


   def _storeObject(self, txn, uri, obj):
      ## check arguments
      ##
      if type(uri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument uri, but got %s" % str(type(uri)))

      ## resolve URI
      ##
      uri = self.proto.resolveOrPass(uri)
      modified = True

      txn.execute("SELECT obj FROM objstore WHERE uri = ?", [uri])
      res = txn.fetchone()
      if res is not None:
         oldobj = json_loads(res[0])
         if obj is not None:
            objser = json_dumps(obj)
            if objser != res[0]:
               txn.execute("UPDATE objstore SET obj = ? WHERE uri = ?", [objser, uri])
            else:
               modified = False
         else:
            txn.execute("DELETE FROM objstore WHERE uri = ?", [uri])
      else:
         oldobj = None
         if obj is not None:
            objser = json_dumps(obj)
            txn.execute("INSERT INTO objstore (uri, obj) VALUES (?, ?)", [uri, objser])
         else:
            modified = False

      if modified:
         event = {'uri': uri, 'old': oldobj, 'new': obj}
         self.proto.dispatch(URI_EVENT + "on-store-modified", event, [self.proto])
         event["uri"] = self.proto.shrink(uri)
         return event
      else:
         return None


   @exportRpc("store-obj")
   def storeObj(self, uri, obj):
      return self.proto.dbpool.runInteraction(self._storeObject, uri, obj)


   def _loadObject(self, txn, uri):
      ## check arguments
      ##
      if type(uri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for argument uri, but got %s" % str(type(uri)))

      ## resolve URI
      ##
      uri = self.proto.resolveOrPass(uri)

      txn.execute("SELECT obj FROM objstore WHERE uri = ?", [uri])
      res = txn.fetchone()
      if res is not None:
         obj = json_loads(res[0])
         return obj
      else:
         return None


   @exportRpc("load-obj")
   def loadObj(self, uri):
      return self.proto.dbpool.runInteraction(self._loadObject, uri)
