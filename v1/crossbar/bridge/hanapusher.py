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


from twisted.python import log

from autobahn.wamp import json_loads

from crossbar.adminwebmodule.uris import URI_EVENT, URI_HANACONNECT
from hanaclient import HanaConnect
from dbpusher import DbPusher, DbPushClient


class HanaPushRule:
   """
   SAP HANA Push Rule.

   User:
      SAP HANA: current_user
      http://help.sap.com/hana/html/_esql_functions_misc.html
   """
   def __init__(self,
                id,
                connectId,
                user,
                topicUri,
                matchByPrefix):
      self.id = str(id)
      self.connectId = str(connectId)
      self.user = str(user) if user is not None else None
      self.topicUri = str(topicUri)
      self.matchByPrefix = matchByPrefix != 0



class HanaPushClient(DbPushClient):
   """
   SAP HANA Push Client.
   """

   LOGID = "HanaPushClient"


   def loop(self):
      import time
      import pyodbc

      conn = pyodbc.connect(self.connectstr)
      cur1 = conn.cursor()
      cur2 = conn.cursor()

      cur1.execute("SELECT COALESCE(MAX(id), 0), COALESCE(MIN(id), 0), COUNT(*) FROM crossbar.event")
      (id, minid, evtcnt) = cur1.fetchone()

      while not self.stopped:
         cur1.execute("SELECT id, pushed_by, topic, payload_type, payload FROM crossbar.event WHERE id > ? ORDER BY id ASC", [id])
         oldid = id
         for r in cur1.fetchall():

            id = r[0]
            pushedBy = r[1]
            topic = r[2]
            payload = None

            if r[4] is not None:

               ## JSON payload
               if r[3] == 2:
                  try:
                     payload = json_loads(r[4])
                  except Exception, e:
                     log.msg("%s - INVALID JSON PAYLOAD - %s" % (r[4], str(e)))

               ## plain string payload
               elif r[3] == 1:
                  payload = r[4]

               else:
                  log.msg("INVALID PAYLOAD TYPE %s" % r[4])

            reactor.callFromThread(self.pusher, self.hanaconnectId, pushedBy, topic, payload)

         if self.purge and id > oldid:
            cur2.execute("DELETE FROM crossbar.event WHERE id <= ?", id)
            conn.commit()

         if self.throttle > 0:
            time.sleep(self.throttle)




class HanaPusher(DbPusher):
   """
   SAP HANA Pusher Service.

   For each SAP HANA Connect with >0 push rules, spawn 1 background pusher thread.
   """

   SERVICENAME = "SAP HANA Pusher"

   LOGID = "HanaPusher"

   CONNECT_ID_BASEURI = URI_HANACONNECT

   PUSHER_STATE_CHANGE_EVENT_URI = URI_EVENT + "on-hanapusher-statechange"
   STATS_EVENT_URI = URI_EVENT + "on-hanapusherstat"

   def makeConnect(self, r):
      ## called from DbPusher base class to create database connect instances
      return HanaConnect(r[0], r[1], r[2], r[3], r[4], r[5], r[6])

   def makeRule(self, r):
      ## called from DbPusher base class to create push rule instances
      return HanaPushRule(r[0], r[1], r[2], r[3], r[4])

   def makeClient(self, connect):
      ## called from DbPusher base class to create background push client instances
      return HanaPushClient(self, connect, False)

   def recache(self, txn):
      log.msg("HanaPusher.recache")

      txn.execute("SELECT id, driver, host, port, database, user, password FROM hanaconnect")
      connects = txn.fetchall()

      txn.execute("SELECT id, hanaconnect_id, user, topic_uri, match_by_prefix FROM hanapushrule")
      rules = txn.fetchall()

      self._cache(connects, rules)

      #log.msg("SAP HANA Connects cached: %s" % self.connects)
