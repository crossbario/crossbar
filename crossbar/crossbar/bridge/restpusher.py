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


import hmac, hashlib, base64

from twisted.python import log
from twisted.application import service
from twisted.enterprise import adbapi

from netaddr.ip import IPAddress, IPNetwork


class PostFilterRule:

   def __init__(self,
                id,
                topicUri,
                matchByPrefix,
                filterIp,
                filterIpNetwork,
                requireSignature,
                appCredKey,
                action):

      self.id = str(id)
      self.topicUri = str(topicUri)
      self.matchByPrefix = matchByPrefix
      self.filterIp = filterIp
      self.filterIpNetwork = filterIpNetwork
      self.requireSignature = requireSignature
      self.appCredKey = appCredKey
      self.action = action

      self.definition = "{'topicUri': %s, 'matchByPrefix': %s, 'filterIp': %s, 'filterIpNetwork': %s, 'requireSignature': %s, 'appCredKey': %s, 'action': %s}" % \
                        (self.topicUri, self.matchByPrefix, self.filterIp, self.filterIpNetwork, self.requireSignature, self.appCredKey, self.action)


class RestPusher(service.Service):

   SERVICENAME = "REST Pusher"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False


   def startService(self):
      log.msg("Starting %s service .." % self.SERVICENAME)
      self.dbpool.runInteraction(self.recache)
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service .." % self.SERVICENAME)
      self.isRunning = False


   def signature(self, topicUri, appkey, timestamp, body):
      """
      Computes the signature a signed HTTP/POST is expected to have.
      If appkey is unknown, returns None. Else, return Base64 ("url-safe")
      encoded signature.

      HMAC[SHA1]_{appsecret}(topicuri | appkey | timestamp | body) => appsig
      """
      if self.appcreds.has_key(appkey):
         secret = str(self.appcreds[appkey]) # this needs to be str, not unicode!
         hm = hmac.new(secret, None, hashlib.sha256)
         hm.update(topicUri)
         hm.update(appkey)
         hm.update(timestamp)
         hm.update(body)
         return base64.urlsafe_b64encode(hm.digest())
      else:
         return None


   def authorize(self, topicUri, clientIp, appkey):
      """
      Authorizes a HTTP/POST request. Returns a pair (authorized, ruleId), where
      authorized = True|False, and ruleId = ID of rule that was triggered, or None
      if default (deny) rule applied.
      """

      ## check ordered list of rules for request matching rule
      ##
      for r in self.rules:

         ## check if POST request matches rule
         ##

         ## match topic URI completely or by prefix if matchByPrefix set
         if r.topicUri == topicUri or (r.matchByPrefix and r.topicUri == topicUri[:len(r.topicUri)]):

            ## match any client or client IP in network if filterIpNetwork set
            if not r.filterIp or (r.filterIp and IPAddress(clientIp) in r.filterIpNetwork):

               ## match any signed/unsigned or signed/arbitrary appCredKey or signed/specific appCredKey
               if not r.requireSignature or (r.requireSignature and not r.appCredKey and appkey) or (r.requireSignature and r.appCredKey and r.appCredKey == appkey):
                  ## ok, POST request matches rule .. now apply action
                  ##
                  if r.action == "ALLOW":
                     return (True, r.id, r.definition)
                  else:
                     return (False, r.id, r.definition)

      ## no rule matched, apply default rule action
      ##
      defaultAction = self.services["config"].get("postrule-default-action", "DENY")
      if defaultAction == "ALLOW":
         return (True, None, "global default")
      else:
         return (False, None, "global default")


   def _cacheRules(self, res):
      self.rules = [PostFilterRule(id = r[0],
                                   topicUri = r[1],
                                   matchByPrefix = r[2] != 0,
                                   filterIp = r[3] != 0,
                                   filterIpNetwork = IPNetwork(r[4]) if r[4] else None,
                                   requireSignature = r[5] != 0,
                                   appCredKey = r[6],
                                   action = r[7]) for r in res]

      log.msg("RestPusher._cacheRules (%d)" % len(self.rules))


   def _cacheAppCreds(self, res):
      self.appcreds = {}
      for r in res:
         self.appcreds[r[0]] = r[1]
      log.msg("RestPusher._cacheAppCreds (%d)" % len(self.appcreds))


   def recache(self, txn):
      log.msg("RestPusher.recache")

      txn.execute("SELECT r.id, r.topic_uri, r.match_by_prefix, r.filter_ip, r.filter_ip_network, r.require_signature, a.key, r.action FROM postrule r LEFT OUTER JOIN appcredential a ON r.require_appcred_id = a.id ORDER BY r.position ASC")
      self._cacheRules(txn.fetchall())

      txn.execute("SELECT key, secret FROM appcredential ORDER BY key")
      self._cacheAppCreds(txn.fetchall())
