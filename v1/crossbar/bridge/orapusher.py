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

from crossbar.adminwebmodule.uris import URI_EVENT, URI_ORACONNECT
from oraclient import OraConnect
from dbpusher import DbPusher, DbPushClient
from pusher import validateUri


class OraPushRule:
   """
   Oracle Push Rule.

   User:
      Oracle: Session User => sys_context('USERENV', 'SESSION_USER')
   """
   def __init__(self,
                id,
                connectId,
                user,
                topicUri,
                matchByPrefix):
      self.id = str(id)
      self.connectId = str(connectId)
      self.user = set([x.strip().upper() for x in str(user).split(',')]) if user is not None else None
      self.topicUri = str(topicUri)
      self.matchByPrefix = matchByPrefix != 0



class OraPushClient(DbPushClient):
   """
   Oracle Push Client.
   """

   LOGID = "OraPushClient"

   def loop(self):

      ## use DBMS_PIPE based notification
      self.usePipe = True

      ## DBMS_PIPE.receive_message timeout in secs
      self.pipeTimeout = int(1)

      ## Iff true, recheck event table on every pipe timeout
      self.recheckOnPipeTimeout = False

      import time, json

      import os
      os.environ["NLS_LANG"] = "AMERICAN_AMERICA.UTF8"

      import cx_Oracle

      try:
         dsn = cx_Oracle.makedsn(self.connect.host,
                                 self.connect.port,
                                 self.connect.sid)
         self.conn = cx_Oracle.connect(self.connect.user,
                                       self.connect.password,
                                       dsn,
                                       threaded = False)
         self.conn.autocommit = True
         log.msg("pusher Oracle connection established")
      except Exception, e:
         #log.msg(str(e))
         raise e


      ## verify that we are the only pusher connected to this DB
      ## by allocating an X-lock.
      ## FIXME:
      ##   - the lock is not schema-wise, but instance wise
      ##   - we should cover the whole crossbar.io/Oracle integration (not only the pusher)
      cur = self.conn.cursor()
      cur.prepare("""
         DECLARE
            l_lockhandle VARCHAR2(128);
         BEGIN
           DBMS_LOCK.ALLOCATE_UNIQUE('crossbar', l_lockhandle);
           :retval := DBMS_LOCK.REQUEST(l_lockhandle, DBMS_LOCK.X_MODE, 0, FALSE);
         END;
      """)
      curVars = cur.setinputsizes(retval = cx_Oracle.NUMBER)
      cur.execute(None)
      retval = int(curVars["retval"].getvalue())
      if retval != 0:
         rmap = {0: "Success",
                 1: "Timeout",
                 2: "Deadlock",
                 3: "Parameter error",
                 4: "Don't own lock specified by id or lockhandle",
                 5: "Illegal lock handle"}
         raise Exception("There seems to be another pusher connected [lock result %d - %s]" % (retval, rmap.get(retval, "??")))
      else:
         log.msg("Ok, we are the only pusher connected to the Oracle instance")


      self.isConnected = True
      self.pusher.publishPusherStateChange(self.connect.id, True, True)

      cur = self.conn.cursor()

      cur.execute("SELECT sys_context('USERENV', 'SESSION_USER') FROM dual")
      session_user = cur.fetchone()[0].upper()

      cur.execute("""
                  BEGIN
                     DBMS_SESSION.SET_IDENTIFIER(:1);
                  END;
                  """, ['CROSSBAR_%s_PUSHER_%s' % (session_user, self.connect.id)])

      ## when using DBMS_PIPE, the name of the event pipe
      PIPENAME = 'CROSSBAR_%s_ONPUBLISH' % session_user
      print "using pipe", PIPENAME

      ## if using pipe mode, prepare for that
      ##
      if self.usePipe:
         cur.execute("""
                     BEGIN
                        SYS.DBMS_PIPE.purge(:pipename);
                     END;
                     """, pipename = PIPENAME)

         curWaitPipe = self.conn.cursor()
         curWaitPipe.prepare("""
                             BEGIN
                                :retval := SYS.DBMS_PIPE.receive_message(:pipename, :timeout);
                                IF :retval = 0 THEN
                                   SYS.DBMS_PIPE.unpack_message(:event_id);
                                   SYS.DBMS_PIPE.purge(:pipename);
                                END IF;
                             END;
                             """)
         curWaitPipeVars = curWaitPipe.setinputsizes(retval = cx_Oracle.NUMBER,
                                                     pipename = cx_Oracle.STRING,
                                                     timeout = cx_Oracle.NUMBER,
                                                     event_id = cx_Oracle.NUMBER)
         pipePipename = curWaitPipeVars["pipename"]
         pipePipename.setvalue(0, PIPENAME)

         pipeTimeout = curWaitPipeVars["timeout"]
         pipeTimeout.setvalue(0, self.pipeTimeout)

         pipeRetVal = curWaitPipeVars["retval"]
         pipeEventId = curWaitPipeVars["event_id"]


      ## setup stuff for getting unprocessed events
      ##
      curGetEvents = self.conn.cursor()
      curGetEvents.prepare("""
                           SELECT id,
                                  published_by,
                                  topic,
                                  qos,
                                  payload_type,
                                  payload_str,
                                  payload_lob,
                                  exclude_sids,
                                  eligible_sids
                            FROM
                               event WHERE id > :id AND processed_at IS NULL
                            ORDER BY id ASC
                            """)
      curGetEventsVars = curGetEvents.setinputsizes(id = cx_Oracle.NUMBER)
      getFromEventId = curGetEventsVars["id"]


      ## setup stuff for purging/marking processed events
      ##
      if self.purge:
         curDeleteEvents = self.conn.cursor()
         curDeleteEvents.prepare("""DELETE FROM event WHERE id = :id""")
         curDeleteEventsVars = curDeleteEvents.setinputsizes(id = cx_Oracle.NUMBER)
         deleteEventId = curDeleteEventsVars["id"]
      else:
         curMarkEvents = self.conn.cursor()
         curMarkEvents.prepare("""
                               UPDATE event SET processed_at = systimestamp at time zone 'utc',
                                                processed_status = :processed_status,
                                                processed_errmsg = :processed_errmsg,
                                                processed_len = :processed_len
                                 WHERE id = :id""")
         curMarkEventsVars = curMarkEvents.setinputsizes(id = cx_Oracle.NUMBER,
                                                         processed_status = cx_Oracle.NUMBER,
                                                         processed_errmsg = cx_Oracle.STRING,
                                                         processed_len = cx_Oracle.NUMBER)
         markEventId = curMarkEventsVars["id"]
         markEventProcessedStatus = curMarkEventsVars["processed_status"]
         markEventProcessedErrMsg = curMarkEventsVars["processed_errmsg"]
         markEventProcessedLen = curMarkEventsVars["processed_len"]


      ## setup stuff for tracking stats of processed events
      ##
      if self._trackDispatched:
         curTrackEvents = self.conn.cursor()
         curTrackEvents.prepare("""
                               UPDATE event SET dispatch_status = :dispatch_status,
                                                dispatch_success = :dispatch_success,
                                                dispatch_failed = :dispatch_failed
                                 WHERE id = :id""")
         curTrackEventsVars = curTrackEvents.setinputsizes(id = cx_Oracle.NUMBER,
                                                           dispatch_status = cx_Oracle.NUMBER,
                                                           dispatch_success = cx_Oracle.NUMBER,
                                                           dispatch_failed = cx_Oracle.NUMBER)
         trackEventId = curTrackEventsVars["id"]
         trackDispatchStatus = curTrackEventsVars["dispatch_status"]
         trackDispatchSuccess = curTrackEventsVars["dispatch_success"]
         trackDispatchFailed = curTrackEventsVars["dispatch_failed"]


      ## check current contents of event table
      ##
      cur.execute("SELECT NVL(MIN(id), 0), NVL(MAX(id), 0), COUNT(*) FROM event WHERE processed_at IS NULL")
      (minId, maxId, evtCnt) = cur.fetchone()

      ## event ID after we will start processing events ..
      ##
      id = None

      ## purge or mark events left over since we were offline
      ##
      if evtCnt > 0:
         if not self.processOldEvents:
            log.msg("skipping %d events accumulated since we were offline [purge = %s]" % (evtCnt, self.purge))
            if self.purge:
               cur.execute("""
                           DELETE FROM event
                              WHERE id >= :1 AND
                                    id <= :2 AND
                                    processed_at IS NULL""",
                                    [minId,
                                     maxId])
               #self.conn.commit()
            else:
               processed_status = 5
               processed_errmsg = None
               cur.execute("""
                           UPDATE event
                              SET processed_at = systimestamp at time zone 'utc',
                                  processed_status = :1,
                                  processed_errmsg = :2
                              WHERE
                                  id >= :3 AND
                                  id <= :4 AND
                                  processed_at IS NULL""",
                                  [processed_status,
                                   processed_errmsg[:4000] if processed_errmsg is not None else None,
                                   minId,
                                   maxId])
               #self.conn.commit()

            ## start processing only with new events (skipping events that accumulated while we were offline)
            id = maxId
         else:
            log.msg("%d events accumulated since we were offline - will process those now" % evtCnt)

            ## start processing at events that accumulated while we were offline
            id = minId - 1
      else:
         log.msg("no events accumulated since we were offline")

         ## start processing with new events
         id = maxId

      ## inner loop, will run until we get stop()'ed
      ##
      while not self.stopped:

         checkAgain = True
         while checkAgain:

            if self.trackDispatched:
               while self.dispatched and len(self.dispatched) > 0:
                  trackedEventId, dispatch_status, dispatch_success, dispatch_failed = self.dispatched.popleft()
                  trackEventId.setvalue(0, trackedEventId)
                  trackDispatchStatus.setvalue(0, dispatch_status)
                  trackDispatchSuccess.setvalue(0, dispatch_success)
                  trackDispatchFailed.setvalue(0, dispatch_failed)
                  curTrackEvents.execute(None)
                  #self.conn.commit()


            ## we do this rather low-level with a cursor loop, since
            ## we process CLOB columns
            ##
            gotRows = 0

            #cur.execute("""SELECT id,
            #                      published_by,
            #                      topic,
            #                      qos,
            #                      payload_type,
            #                      payload_str,
            #                      payload_lob,
            #                      exclude_sids,
            #                      eligible_sids
            #                FROM
            #                   event WHERE id > :1 AND processed_at IS NULL
            #                ORDER BY id ASC""", [id])

            getFromEventId.setvalue(0, id)
            curGetEvents.execute(None)

            doFetch = True
            while doFetch:
               #r = cur.fetchone()
               r = curGetEvents.fetchone()
               if r is not None:
                  gotRows += 1

                  ## processed_status:
                  ##
                  ##     0 - ok
                  ##     1 - invalid event topic URI
                  ##     2 - illegal event payload type
                  ##     3 - invalid event payload
                  ##     4 - illegal event qos type
                  ##     5 - unprocessed old event (got published as we were offline)
                  ##
                  processed_status = 0 # default to valid processing
                  processed_errmsg = None # filled when processed_status != 0

                  id = r[0]
                  pushedBy = r[1]
                  topic = r[2]
                  qos = r[3]
                  payload_type = r[4]

                  if r[6] is not None:
                     ## cx_Oracle.LOB object
                     payload_raw_len = r[6].size()
                     payload_raw = r[6].read()
                  else:
                     ## cx_Oracle.STRING
                     if r[5] is not None:
                        payload_raw_len = len(r[5])
                        payload_raw = r[5]
                     else:
                        payload_raw_len = 0
                        payload_raw = None

                  payload = None
                  exclude = r[7] if r[7] is not None else []
                  eligible = r[8] if r[8] is not None else None

                  ## validate/parse event
                  ##
                  if processed_status == 0:
                     uriValid, result = validateUri(topic)
                     if not uriValid:
                        processed_status = 1
                        processed_errmsg = result

                  if processed_status == 0:
                     if payload_type == 1:
                        ## plain string
                        ##
                        payload = payload_raw
                     elif payload_type == 2:
                        ## JSON
                        ##
                        try:
                           if payload_raw is not None:
                              payload = json_loads(payload_raw)
                           else:
                              payload = None
                        except Exception, e:
                           ## this should not happen, since we have serialized the
                           ## payload from a JSON typed object within Oracle!
                           ##
                           processed_status = 3 # invalid payload
                           processed_errmsg = "invalid JSON payload ('%s')" % str(e)
                     else:
                        ## this should not happen, since we have a CHECK constraint
                        ## on the underlying event table!
                        ##
                        processed_status = 2
                        processed_errmsg = "illegal event payload type %d" % payload_type

                  if processed_status == 0:
                     if qos == 1:
                        pass
                     else:
                        processed_status = 4
                        processed_errmsg = "illegal event qos type %d" % qos

                  ## let the events be dispatched on the reactor thread
                  ##
                  if processed_status == 0:
                     self.reactor.callFromThread(self.pusher.push,
                                                id,
                                                self.connect.id,
                                                pushedBy,
                                                topic,
                                                payload,
                                                exclude,
                                                eligible)

                  ## purge or mark processed event
                  ##
                  if self.purge:
                     #cur.execute("DELETE FROM event WHERE id = :1", [id])
                     deleteEventId.setvalue(0, id)
                     curDeleteEvents.execute(None)
                     #self.conn.commit()
                  else:
                     #cur.execute("UPDATE event SET processed_at = systimestamp at time zone 'utc', processed_status = :1, processed_errmsg = :2 WHERE id = :3", [processed_status, processed_errmsg[:4000] if processed_errmsg is not None else None, id])
                     markEventId.setvalue(0, id)
                     markEventProcessedStatus.setvalue(0, processed_status)
                     markEventProcessedErrMsg.setvalue(0, processed_errmsg)
                     markEventProcessedLen.setvalue(0, payload_raw_len)
                     curMarkEvents.execute(None)
                     #self.conn.commit()
               else:
                  doFetch = False

            ## immediately check again if we got rows.
            ## otherwise go to sleep / wait on pipe notification
            ##
            if gotRows > 0:
               #log.msg("got %d events, checking again .." % gotRows)
               checkAgain = True
            else:
               #log.msg("no new events")
               checkAgain = False

         ## wait for new events ..
         ##
         if not self.usePipe:
            ## when in polling mode, just sleep a little and recheck for events ..
            ##
            if self.pollThrottle > 0:
               time.sleep(self.pollThrottle)
         else:
            ## when using DBMS_PIPE, block in pipe receive for new events ..
            ##
            waitForPipe = True
            debugPipe = False

            while waitForPipe:

               ## the following will block in pipe receive ..
               ##
               curWaitPipe.execute(None)
               retval = int(pipeRetVal.getvalue())

               if retval == 1:

                  ## pipe timeout
                  ##
                  if debugPipe:
                     log.msg("DBMS_PIPE timeout")

               elif retval == 0:

                  ## the pipe got a new event ID ..
                  ##
                  notifiedId = int(pipeEventId.getvalue())
                  waitForPipe = False

                  if debugPipe:
                     log.msg("DBMS_PIPE data available [event %s]" % notifiedId)

               else:
                  ## could not receive from pipe .. something bad happened.
                  ## exit and rely on automatic pusher restart
                  ##
                  raise Exception("error while doing DBMS_PIPE.receive_message - return value %d" % retval)

               if self.recheckOnPipeTimeout:
                  waitForPipe = False



class OraPusher(DbPusher):
   """
   Oracle Pusher Service.

   For each OraConnect with >0 push rules, spawn 1 background pusher thread.
   """

   SERVICENAME = "Oracle Pusher"

   LOGID = "OraPusher"

   CONNECT_ID_BASEURI = URI_ORACONNECT

   PUSHER_STATE_CHANGE_EVENT_URI = URI_EVENT + "on-orapusher-statechange"
   STATS_EVENT_URI = URI_EVENT + "on-orapusherstat"

   def makeConnect(self, r):
      ## called from DbPusher base class to create database connect instances
      return OraConnect(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8])

   def makeRule(self, r):
      ## called from DbPusher base class to create push rule instances
      return OraPushRule(r[0], r[1], r[2], r[3], r[4])

   def makeClient(self, connect):
      ## called from DbPusher base class to create background push client instances
      return OraPushClient(self, connect, False)

   def recache(self, txn):
      log.msg("OraPusher.recache")

      txn.execute("SELECT id, host, port, sid, user, password, demo_user, demo_password, connection_timeout FROM oraconnect ORDER BY id")
      connects = txn.fetchall()

      txn.execute("SELECT id, oraconnect_id, user, topic_uri, match_by_prefix FROM orapushrule ORDER BY oraconnect_id, id")
      rules = txn.fetchall()

      self._cache(connects, rules)
