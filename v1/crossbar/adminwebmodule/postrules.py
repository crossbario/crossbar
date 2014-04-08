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
from netaddr.ip import IPAddress, IPNetwork

from autobahn.wamp import exportRpc
from autobahn.util import utcstr, utcnow, parseutc, newid

from crossbar.adminwebmodule.uris import *


class PostRules:
   """
   Post rules model.
   """

   def __init__(self, proto):
      """
      :param proto: WAMP protocol class this model is exposed from.
      :type proto: Instance of AdminWebSocketProtocol.
      """
      self.proto = proto


   def checkPostRuleSpec(self, spec, specDelta, errs):

      errcnt = 0

      ## check rule action
      ##
      if not errs["action"]:
         if specDelta.has_key("action"):
            valid_actions = ['ALLOW', 'DENY']
            if specDelta["action"] not in valid_actions:
               errs["action"].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"), "Illegal value '%s' for action [must be one of %s]." % (specDelta["action"], ", ".join(valid_actions))))
               errcnt += 1

      ## check IP network filter
      ##
      network = spec.get("filter-ip-network", None)
      if not errs["filter-ip-network"]:
         if specDelta.has_key("filter-ip-network"):
            if specDelta["filter-ip-network"] is not None and specDelta["filter-ip-network"].strip() != "":
               nw = specDelta["filter-ip-network"].strip()
               try:
                  network = IPNetwork(nw)
                  if network.version != 4:
                     network = None
                     errs["filter-ip-network"].append((self.proto.shrink(URI_ERROR + "non-ipv4-network"),
                                                       "Illegal value '%s' for filter IP network - only IPv4 supported." % nw))
                     errcnt += 1
                  specDelta["filter-ip-network"] = str(network)
               except Exception, e:
                  errs["filter-ip-network"].append((self.proto.shrink(URI_ERROR + "invalid-attribute-value"),
                                                    "Illegal value '%s' for filter IP network (%s)." % (nw, str(e))))
                  errcnt += 1
            else:
               specDelta["filter-ip-network"] = None

      if not errs["filter-ip"]:
         if specDelta.has_key("filter-ip") and specDelta["filter-ip"] and network is None:
            errs["filter-ip-network"].append((self.proto.shrink(URI_ERROR + "missing-attribute"), "Filter IP = true, but no IP network specified."))
            errcnt += 1

      return errcnt


   def _createPostRule(self, txn, spec, insertAtPostRuleUri, insertAfter):

      if type(insertAtPostRuleUri) not in [str, unicode, types.NoneType]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode/null for agument insertAtPostRuleUri, but got %s" % str(type(insertAtPostRuleUri)))

      if type(insertAfter) != bool:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type bool for agument insertAfter, but got %s" % str(type(insertAfter)))

      attrs = {"topic-uri": (True, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (True, [bool]),
               "filter-ip": (True, [bool]),
               "filter-ip-network": (False, [str, unicode, types.NoneType]),
               "require-signature": (True, [bool]),
               "require-appcred-uri": (False, [str, unicode, types.NoneType]),
               "action": (True, [str, unicode])}

      errcnt, errs = self.proto.checkDictArg("postrule spec", spec, attrs)

      if not errs["topic-uri"]:
         normalizedUri, errs2 = self.proto.validateUri(spec["topic-uri"])
         errs["topic-uri"].extend(errs2)
         errcnt += len(errs2)

      errcnt += self.checkPostRuleSpec({}, spec, errs)

      ## convenience handling in JS
      if not errs["require-appcred-uri"] and spec.has_key("require-appcred-uri"):
         if spec["require-appcred-uri"] == "null" or spec["require-appcred-uri"] == "":
            spec["require-appcred-uri"] = None

      appcred_id = None
      appcred_uri = None
      if spec.has_key("require-appcred-uri") and spec["require-appcred-uri"] is not None and spec["require-appcred-uri"].strip() != "":
         appcred_uri = self.proto.resolveOrPass(spec["require-appcred-uri"].strip())
         appcred_id = self.proto.uriToId(appcred_uri)
         txn.execute("SELECT created FROM appcredential WHERE id = ?", [appcred_id])
         if txn.fetchone() is None:
            errs["require-appcred-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No application credentials with URI %s" % appcred_uri))

      self.proto.raiseDictArgException(errs)


      ## determine new position
      ##
      if insertAtPostRuleUri is not None and insertAtPostRuleUri.strip() != "":

         at_uri = self.proto.resolveOrPass(insertAtPostRuleUri.strip())
         at_id = self.proto.uriToId(at_uri)
         txn.execute("SELECT position FROM postrule WHERE id = ?", [at_id])
         res = txn.fetchone()
         if res is None:
            raise Exception(URI_ERROR + "no-such-object", "No post rule with URI %s" % at_uri)

         at_pos = float(res[0])
         if insertAfter:
            txn.execute("SELECT position FROM postrule WHERE position > ? ORDER BY position ASC", [at_pos])
            res = txn.fetchone()
            if res is not None:
               new_pos = at_pos + abs(float(res[0]) - at_pos) / 2.
            else:
               new_pos = at_pos + 1.
         else:
            txn.execute("SELECT position FROM postrule WHERE position < ? ORDER BY position DESC", [at_pos])
            res = txn.fetchone()
            if res is not None:
               new_pos = at_pos - abs(float(res[0]) - at_pos) / 2.
            else:
               new_pos = at_pos - 1.
      else:
         txn.execute("SELECT MAX(position) FROM postrule")
         res = txn.fetchone()
         if res is not None and res[0] is not None:
            new_pos = float(res[0]) + 1.
         else:
            new_pos = 1.


      id = newid()
      postrule_uri = URI_POSTRULE + id
      now = utcnow()
      #topic_uri = self.proto.resolveOrPass(spec["topic-uri"].strip())
      topic_uri = normalizedUri
      network = spec.get("filter-ip-network", None)

      txn.execute("INSERT INTO postrule (id, created, modified, position, topic_uri, match_by_prefix, filter_ip, filter_ip_network, require_signature, require_appcred_id, action) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                          [id,
                                           now,
                                           None,
                                           new_pos,
                                           topic_uri,
                                           int(spec["match-by-prefix"]),
                                           int(spec["filter-ip"]),
                                           network,
                                           int(spec["require-signature"]),
                                           appcred_id,
                                           spec["action"]
                                           ])

      services = self.proto.factory.services
      if services.has_key("restpusher"):
         services["restpusher"].recache(txn)

      postrule = {"uri": postrule_uri,
                  "created": now,
                  "modified": None,
                  "position": new_pos,
                  "topic-uri": topic_uri,
                  "match-by-prefix": spec["match-by-prefix"],
                  "filter-ip": spec["filter-ip"],
                  "filter-ip-network": network,
                  "require-signature": spec["require-signature"],
                  "require-appcred-uri": appcred_uri,
                  "action": spec["action"]}

      if insertAtPostRuleUri:
         postrule["inserted-at-uri"] = self.proto.shrink(URI_POSTRULE + at_id)
         postrule["inserted-after"] = insertAfter

      self.proto.dispatch(URI_EVENT + "on-postrule-created", postrule, [self.proto])

      postrule["uri"] = self.proto.shrink(postrule_uri)
      if postrule["require-appcred-uri"] is not None:
         postrule["require-appcred-uri"] = self.proto.shrink(appcred_uri)
      return postrule


   @exportRpc("create-postrule")
   def createPostRule(self, spec, insertAtPostRuleUri = None, insertAfter = True):
      """
      Create new postrule.

      Parameters:

         spec:                         Postrule specification.
         spec[]:
            topic-uri:                 Topic URI.
            match-by-prefix:           Match topic URI by prefix?
            filter-ip:                 Match only for specific IPs?
            filter-ip-network:         Specify IPs as IP network when filtering by IP.
            require-signature:         Require signed POSTs?
            require-appcred:           Require signing with specific application credential.
            require-appcred-uri:       Require signing with this application credential.
            action:                    Action: 'ALLOW' or 'DENY'.

         insertAtPostRuleUri:          None or URI or CURIE of existing postrule the
                                       new one is to be created after/before.
         insertAfter:                  None or True/False

      Events:

         on-postrule-created

      Errors:

         spec,
         insertAtPostRuleUri,
         insertAfter:               illegal-argument-type

         insertAtPostRuleUri:       no-such-object

         spec[]:

            *:                      illegal-attribute-type,
                                    missing-attribute

            topic-uri:              attribute-value-too-long,
                                    invalid-uri,
                                    missing-uri-scheme,
                                    invalid-uri-scheme,
                                    missing-uri-network-location,
                                    uri-contains-query-component

            require-appcred-uri:    no-such-object

            action:                 invalid-attribute-value

            require-signature:      invalid-attribute-value

            filter-ip-network:      invalid-attribute-value,
                                    non-ipv4-network

            ?:                      unknown-attribute
      """
      return self.proto.dbpool.runInteraction(self._createPostRule, spec, insertAtPostRuleUri, insertAfter)


   def _deletePostRule(self, txn, postRuleUri):

      if type(postRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument postRuleUri, but got %s" % str(type(postRuleUri)))

      uri = self.proto.resolveOrPass(postRuleUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT created FROM postrule WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         txn.execute("DELETE FROM postrule WHERE id = ?", [id])

         services = self.proto.factory.services
         if services.has_key("restpusher"):
            services["restpusher"].recache(txn)

         self.proto.dispatch(URI_EVENT + "on-postrule-deleted", uri, [self.proto])

         return self.proto.shrink(uri)
      else:
         raise Exception(URI_ERROR + "no-such-object", "No post rule with URI %s" % uri)


   @exportRpc("delete-postrule")
   def deletePostRule(self, postRuleUri):
      """
      Delete existing postrule.

      Parameters:

         postRuleUri:         URI or CURIE of postrule to delete

      Result:

         <postrule URI>

      Events:

         on-postrule-deleted

      Errors:

         postRuleUri:               illegal-argument-type,
                                    no-such-object
      """
      return self.proto.dbpool.runInteraction(self._deletePostRule, postRuleUri)


   def _movePostRule(self, txn, postRuleUri, moveAtPostRuleUri, moveAfter):

      if type(postRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument postRuleUri, but got %s" % str(type(postRuleUri)))

      if type(moveAtPostRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type str/unicode for agument moveAtPostRuleUri, but got %s" % str(type(moveAtPostRuleUri)))

      if type(moveAfter) != bool:
         raise Exception(URI_ERROR + "illegal-argument-type", "Expected type bool for agument moveAfter, but got %s" % str(type(moveAfter)))

      uri = self.proto.resolveOrPass(postRuleUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT position FROM postrule WHERE id = ?", [id])
      res = txn.fetchone()
      if res is None:
         raise Exception(URI_ERROR + "no-such-object", "No post rule with URI %s to move." % uri)
      pos = res[0]

      to_uri = self.proto.resolveOrPass(moveAtPostRuleUri)
      to_id = self.proto.uriToId(to_uri)
      txn.execute("SELECT position FROM postrule WHERE id = ?", [to_id])
      res = txn.fetchone()
      if res is None:
         raise Exception(URI_ERROR + "no-such-object", "No post rule with URI %s to move after/before." % uri)
      to_pos = float(res[0])

      if moveAfter:
         txn.execute("SELECT position FROM postrule WHERE position > ? ORDER BY position ASC", [to_pos])
         res = txn.fetchone()
         if res is not None:
            new_pos = to_pos + abs(float(res[0]) - to_pos) / 2.
         else:
            new_pos = to_pos + 1.
      else:
         txn.execute("SELECT position FROM postrule WHERE position < ? ORDER BY position DESC", [to_pos])
         res = txn.fetchone()
         if res is not None:
            new_pos = to_pos - abs(float(res[0]) - to_pos) / 2.
         else:
            new_pos = to_pos - 1.

      now = utcnow()
      txn.execute("UPDATE postrule SET position = ?, modified = ? WHERE id = ?", [new_pos, now, id])

      services = self.proto.factory.services
      if services.has_key("restpusher"):
         services["restpusher"].recache(txn)

      moved = {"uri": uri,
               "modified": now,
               "position": new_pos,
               "moved-at-uri": URI_POSTRULE + to_id,
               "moved-after": moveAfter}

      self.proto.dispatch(URI_EVENT + "on-postrule-moved", moved, [self.proto])

      moved["uri"] = self.proto.shrink(uri)
      moved["moved-at-uri"] = self.proto.shrink(URI_POSTRULE + to_id)

      return moved


   @exportRpc("move-postrule")
   def movePostRule(self, postRuleUri, moveAtPostRuleUri, moveAfter = True):
      """
      Move existing postrule within filter list.

      Parameters:

         postRuleUri:         URI or CURIE of postrule to move
         moveAtPostRuleUri:   URI or CURIE of move anchor postrule anchor
         moveAfter:           True/False => move after/before move anchor

      Result:

         {"uri":           <URI of moved postrule>,
          "modified":      <timestamp of modification>,
          "position":      <new postrule position>,
          "moved-at-uri":  <URI of move anchor postrule>,
          "moved-after":   <true/false => moved after/before}

      Events:

         on-postrule-moved

      Errors:

         postRuleUri,
         moveAtPostRuleUri,
         moveAfter:                 illegal-argument-type

         postRuleUri,
         moveAtPostRuleUri:         no-such-object
      """
      return self.proto.dbpool.runInteraction(self._movePostRule, postRuleUri, moveAtPostRuleUri, moveAfter)


   def _modifyPostRule(self, txn, postRuleUri, specDelta):

      if type(postRuleUri) not in [str, unicode]:
         raise Exception(URI_ERROR + "illegal-argument", "Expected type str/unicode for agument postRuleUri, but got %s" % str(type(postRuleUri)))

      attrs = {"topic-uri": (False, [str, unicode], 0, URI_MAXLEN),
               "match-by-prefix": (False, [bool]),
               "filter-ip": (False, [bool]),
               "filter-ip-network": (False, [str, unicode, types.NoneType]),
               "require-signature": (False, [bool]),
               "require-appcred-uri": (False, [str, unicode, types.NoneType]),
               "action": (False, [str, unicode])}

      errcnt, errs = self.proto.checkDictArg("postrule delta spec", specDelta, attrs)

      if not errs["topic-uri"] and specDelta.has_key("topic-uri"):
         normalizedUri, errs2 = self.proto.validateUri(specDelta["topic-uri"])
         errs["topic-uri"].extend(errs2)
         errcnt += len(errs2)

      ## convenience handling in JS
      if not errs["require-appcred-uri"] and specDelta.has_key("require-appcred-uri"):
         if specDelta["require-appcred-uri"] == "null" or specDelta["require-appcred-uri"] == "":
            specDelta["require-appcred-uri"] = None

      appcred_id = None
      appcred_uri = None
      if specDelta.has_key("require-appcred-uri") and specDelta["require-appcred-uri"] is not None and specDelta["require-appcred-uri"].strip() != "":
         appcred_uri = self.proto.resolveOrPass(specDelta["require-appcred-uri"].strip())
         appcred_id = self.proto.uriToId(appcred_uri)
         txn.execute("SELECT created FROM appcredential WHERE id = ?", [appcred_id])
         if txn.fetchone() is None:
            errs["require-appcred-uri"].append((self.proto.shrink(URI_ERROR + "no-such-object"), "No application credentials with URI %s" % appcred_uri))


      uri = self.proto.resolveOrPass(postRuleUri)
      id = self.proto.uriToId(uri)
      txn.execute("SELECT topic_uri, match_by_prefix, filter_ip, filter_ip_network, require_signature, require_appcred_id, action FROM postrule WHERE id = ?", [id])
      res = txn.fetchone()
      if res is not None:

         spec = {}
         spec["topic-uri"] = res[0]
         spec["match-by-prefix"] = res[1] != 0
         spec["filter-ip"] = res[2] != 0
         spec["filter-ip-network"] = str(res[3]) if res[3] is not None else None
         spec["require-signature"] = res[4] != 0
         spec["require-appcred-uri"] = self.proto.shrink(URI_APPCRED + res[5]) if res[5] else None
         spec["action"] = str(res[6])

         errcnt += self.checkPostRuleSpec(spec, specDelta, errs)

         self.proto.raiseDictArgException(errs)

         now = utcnow()
         delta = {}
         sql = "modified = ?"
         sql_vars = [now]

         if specDelta.has_key("topic-uri"): # and specDelta["topic-uri"] is not None:
            #newval = self.proto.resolveOrPass(specDelta["topic-uri"].strip())
            newval = normalizedUri
            if newval != "" and newval != res[0]:
               delta["topic-uri"] = newval
               sql += ", topic_uri = ?"
               sql_vars.append(newval)

         if specDelta.has_key("match-by-prefix"): # and specDelta["match-by-prefix"] is not None:
            newval = specDelta["match-by-prefix"]
            if newval != (res[1] != 0):
               delta["match-by-prefix"] = newval
               sql += ", match_by_prefix = ?"
               sql_vars.append(newval)

         if specDelta.has_key("filter-ip"): # and specDelta["filter-ip"] is not None:
            newval = specDelta["filter-ip"]
            if newval != (res[2] != 0):
               delta["filter-ip"] = newval
               sql += ", filter_ip = ?"
               sql_vars.append(newval)

         if specDelta.has_key("filter-ip-network"): # and specDelta["filter-ip-network"] is not None:
            newval = specDelta["filter-ip-network"]
            if newval != res[3]:
               delta["filter-ip-network"] = newval
               sql += ", filter_ip_network = ?"
               sql_vars.append(newval)

         if specDelta.has_key("require-signature"): # and specDelta["require-signature"] is not None:
            newval = specDelta["require-signature"]
            if newval != (res[4] != 0):
               delta["require-signature"] = newval
               sql += ", require_signature = ?"
               sql_vars.append(newval)

#         if specDelta.has_key("require-appcred-uri") and specDelta["require-appcred-uri"] is not None and specDelta["require-appcred-uri"].strip() != "":
         if specDelta.has_key("require-appcred-uri"):
            if appcred_id != res[5]:
               delta["require-appcred-uri"] = appcred_uri
               sql += ", require_appcred_id = ?"
               sql_vars.append(appcred_id)

         if specDelta.has_key("action"): # and specDelta["action"] is not None:
            newval = specDelta["action"]
            if newval != res[6]:
               delta["action"] = newval
               sql += ", action = ?"
               sql_vars.append(newval)

         if len(delta) > 0:
            delta["modified"] = now
            delta["uri"] = uri

            sql_vars.append(id)
            txn.execute("UPDATE postrule SET %s WHERE id = ?" % sql, sql_vars)

            services = self.proto.factory.services
            if services.has_key("restpusher"):
               services["restpusher"].recache(txn)

            self.proto.dispatch(URI_EVENT + "on-postrule-modified", delta, [self.proto])

            delta["uri"] = self.proto.shrink(uri)
            if delta.has_key("require-appcred-uri") and delta["require-appcred-uri"] is not None:
               delta["require-appcred-uri"] = self.proto.shrink(appcred_uri)
            return delta
         else:
            return {}
      else:
         raise Exception(URI_ERROR + "no-such-object", "No post rule with URI %s" % uri)


   @exportRpc("modify-postrule")
   def modifyPostRule(self, postRuleUri, specDelta):
      """
      Modify existing postrule's attributes (other than position).

      Parameters:

         postRuleUri:               URI or CURIE of existing postrule.
         specDelta:                 Change spec for postrule.
         specDelta[]:
            topic-uri:                 Topic URI.
            match-by-prefix:           Match topic URI by prefix?
            filter-ip:                 Match only for specific IPs?
            filter-ip-network:         Specify IPs as IP network when filtering by IP.
            require-signature:         Require signed POSTs?
            require-appcred-uri:       Require signing with this application credential.
            action:                    Action: 'ALLOW' or 'DENY'.

      Events:

         on-postrule-modified

      Errors:

         postRuleUri,
         specDelta:                 illegal-argument-type

         postRuleUri:               no-such-object

         specDelta[]:

            *:                      illegal-attribute-type,
                                    missing-attribute

            topic-uri:              attribute-value-too-long,
                                    invalid-uri,
                                    missing-uri-scheme,
                                    invalid-uri-scheme,
                                    missing-uri-network-location,
                                    uri-contains-query-component

            require-appcred-uri:    no-such-object

            action:                 invalid-attribute-value

            require-signature:      invalid-attribute-value

            filter-ip-network:      invalid-attribute-value,
                                    non-ipv4-network

            ?:                      unknown-attribute
      """
      return self.proto.dbpool.runInteraction(self._modifyPostRule, postRuleUri, specDelta)


   @exportRpc("get-postrules")
   def getPostRules(self):
      """
      Return postrule filter list (ordered by postrule position ascending).
      """
      d = self.proto.dbpool.runQuery("SELECT id, created, modified, position, topic_uri, match_by_prefix, filter_ip, filter_ip_network, require_signature, require_appcred_id, action FROM postrule ORDER BY position ASC")
      d.addCallback(lambda res: [{"uri": self.proto.shrink(URI_POSTRULE + r[0]),
                                  "created": r[1],
                                  "modified": r[2],
                                  "position": r[3],
                                  "topic-uri": r[4],
                                  "match-by-prefix": r[5] != 0,
                                  "filter-ip": r[6] != 0,
                                  "filter-ip-network": r[7],
                                  "require-signature": r[8] != 0,
                                  "require-appcred-uri": self.proto.shrink(URI_APPCRED + r[9]) if r[9] else None,
                                  "action": r[10]} for r in res])
      return d
