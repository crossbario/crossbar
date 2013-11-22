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

from crossbar.adminwebmodule.uris import URI_EVENT, URI_PGCONNECT
from pgclient import PgConnect
from dbpusher import PushStats, DbPusher, DbPushClient


class PgPushRule:
   """
   PostgreSQL Push Rule.

   User:
      PostgreSQL: current_user
      http://www.postgresql.org/docs/9.1/static/functions-info.html
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



class PgPushClient(DbPushClient):
   """
   PostgreSQL Push Client.
   """

   LOGID = "PgPushClient"

   def loop(self):
      import time, json
      import select
      import psycopg2
      import psycopg2.extensions

      ## establish database connection
      ##
      try:
         self.conn = psycopg2.connect(user = self.connect.user,
                                      password = self.connect.password,
                                      database = self.connect.database,
                                      host = self.connect.host,
                                      port = self.connect.port)
      except Exception, e:
         log.msg(str(e))
         raise Exception(str(e))

      self.conn.autocommit = True

      ## note state change and trigger event
      ##
      self.isConnected = True
      self.pusher.publishPusherStateChange(self.connect.id, True, True)

      cur1 = self.conn.cursor()
      cur2 = self.conn.cursor()
      cur3 = self.conn.cursor()
      cur4 = self.conn.cursor()

      useNotify = True

      cur1.execute("SELECT COALESCE(MAX(id), 0), COALESCE(MIN(id), 0), COUNT(*) FROM event WHERE dispatched_at IS NULL")
      (id, minid, evtcnt) = cur1.fetchone()

      while not self.stopped:
         cur1.execute("SELECT id, published_by, topic, payload_type, payload_str, payload_json, exclude_sids, eligible_sids FROM event WHERE id > %s AND dispatched_at IS NULL ORDER BY id ASC", [id])
         oldid = id
         for r in cur1.fetchall():

            id = r[0]
            pushedBy = r[1]
            topic = r[2]
            payload_type = r[3]
            exclude = r[6] if r[6] is not None else []
            eligible = r[7]

            ## Psycopg2 does automatic typecasting from PG JSON to Python object
            ##
            if payload_type == 1:
               ## string
               payload = r[4]
            elif payload_type == 2:
               ## JSON
               payload = r[5] # Psycopg2 already did automatic typecasting from PG JSON to Python object

               ## manual typecasting from PG JSON to Python object
               #try:
               #   payload = json.loads(r[5])
               #except Exception, e:
               #   ## should not arrive here, since event table column is of type JSON already!
               #   log.msg("%s - INVALID JSON PAYLOAD - %s" % (r[4], str(e)))
            else:
               raise Exception("unknown payload type %d" % payload_type)

            reactor.callFromThread(self.pusher.push, id, self.connect.id, pushedBy, topic, payload, exclude, eligible)

         if self.purge and id > oldid:
            cur2.execute("DELETE FROM event WHERE id <= %s", [id])
            self.conn.commit()
         else:
            cur3.execute("UPDATE event SET dispatched_at = NOW () AT TIME ZONE 'UTC' WHERE id <= %s AND dispatched_at IS NULL", [id])
            self.conn.commit()

         if not useNotify:
            if self.throttle > 0:
               time.sleep(self.throttle)
         else:
            cur4.execute("LISTEN onpublish")
            if select.select([self.conn], [], [], 5) == ([], [], []):
               pass
               #print "timeout"
            else:
               self.conn.poll()
               while self.conn.notifies:
                  notify = self.conn.notifies.pop()
                  #print "Got NOTIFY:", notify.pid, notify.channel, notify.payload



class PgPusher(DbPusher):
   """
   PostgreSQL Pusher Service.

   For each PostgreSQL Connect with >0 push rules, spawn 1 background pusher thread.
   """

   SERVICENAME = "PostgreSQL Pusher"

   LOGID = "PgPusher"

   CONNECT_ID_BASEURI = URI_PGCONNECT

   PUSHER_STATE_CHANGE_EVENT_URI = URI_EVENT + "on-pgpusher-statechange"
   STATS_EVENT_URI = URI_EVENT + "on-pgpusherstat"

   def makeConnect(self, r):
      ## called from DbPusher base class to create database connect instances
      return PgConnect(r[0], r[1], r[2], r[3], r[4], r[5], r[6])

   def makeRule(self, r):
      ## called from DbPusher base class to create push rule instances
      return PgPushRule(r[0], r[1], r[2], r[3], r[4])

   def makeClient(self, connect):
      ## called from DbPusher base class to create background push client instances
      return PgPushClient(self, connect, False)

   def recache(self, txn):
      log.msg("PgPusher.recache")

      txn.execute("SELECT id, host, port, database, user, password, connection_timeout FROM pgconnect ORDER BY id")
      connects = txn.fetchall()

      txn.execute("SELECT id, pgconnect_id, user, topic_uri, match_by_prefix FROM pgpushrule ORDER BY pgconnect_id, id")
      rules = txn.fetchall()

      self._cache(connects, rules)

      #log.msg("PostgreSQL Connects cached: %s" % self.connects)
