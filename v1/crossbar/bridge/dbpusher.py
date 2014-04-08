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
from twisted.application import service

from twisted.python import log
from twisted.internet import threads
from twisted.application import service
from twisted.enterprise import adbapi
from twisted.internet.defer import Deferred, \
                                   returnValue, \
                                   inlineCallbacks, \
                                   CancelledError

from pusher import Pusher


class PushStats:

   def __init__(self, id):
      self.stats = {'uri': id,
                    'publish-allowed': 0,
                    'publish-denied': 0,
                    'dispatch-success': 0,
                    'dispatch-failed': 0}
      self.statsChanged = False

   def updateDispatches(self, receiver_count, requested_count):
      if receiver_count > 0:
         self.stats['dispatch-success'] += receiver_count

      error_count = requested_count - receiver_count
      if error_count > 0:
         self.stats['dispatch-failed'] += error_count

      if receiver_count > 0 or error_count > 0:
         self.statsChanged = True

   def updatePublications(self, allowed_count, denied_count):
      if allowed_count > 0:
         self.stats['publish-allowed'] += 1

      if denied_count > 0:
         self.stats['publish-denied'] += 1

      if allowed_count > 0 or denied_count > 0:
         self.statsChanged = True

   def get(self, changedonly = True, reset = True):
      if not changedonly or self.statsChanged:
         if reset:
            self.statsChanged = False
         return self.stats
      else:
         return None


from collections import deque


class DbPushClient:
   """
   Database Push Client. Base class for specific pushers.
   """

   def __init__(self, pusher, connect, purge = True, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.pusher = pusher
      self.connect = connect
      self.stopped = False
      self.isRunning = False
      self.isConnected = False
      self.autoReconnect = True
      self.conn = None
      self.failure = None

      ## purge processed events by DELETE, instead of marking with UPDATE
      self.purge = purge

      ## process events that have accumulated since we were offline
      self.processOldEvents = False

      ## when running in poll-mode, seconds to sleep for throttling the poll loop
      self.pollThrottle = float(0.2)

      ## track dispatched
      self._trackDispatched = True

      if self._trackDispatched:
         self.dispatched = deque()
      else:
         self.dispatched = None


   def trackDispatched(self, eventId, dispatchStatus, dispatchSuccess, dispatchFailed):
      """
      Track dispatched events.
      """
      if self._trackDispatched:
         self.dispatched.append((eventId, dispatchStatus, dispatchSuccess, dispatchFailed))


   def stop(self):
      """
      Stop the background pusher. This is safe to call directly from the
      reactor thread.
      """
      log.msg("%s stopping .." % self.LOGID)

      self.stopped = True
      self.failure = CancelledError()

      ## try cancel any query running ..
      if self.conn:
         try:
            self.conn.cancel()
         except:
            pass


   def run(self):

      if self.isRunning:
         raise Exception("%s already running" % self.LOGID)

      log.msg("%s starting .." % self.LOGID)

      self.stopped = False
      self.failure = None

      self.isRunning = True
      self.retries = 0

      try:
         self.loop()

         if self.failure:
            raise self.failure

         if self.conn:
            try:
               self.conn.close()
            except:
               pass
         self.conn = None
         self.isConnected = False
         self.isRunning = False

         if self._trackDispatched:
            self.dispatched = deque()
         else:
            self.dispatched = None

         log.msg("%s stopped" % self.LOGID)

      except Exception, e:

         if self.conn:
            try:
               self.conn.close()
            except:
               pass

         self.conn = None
         self.isConnected = False
         self.isRunning = False

         self.pusher.publishPusherStateChange(self.connect.id, False, True, str(e))

         if self._trackDispatched:
            self.dispatched = deque()
         else:
            self.dispatched = None

         log.msg("%s failed [%s]" % (self.LOGID, e))

         raise e



class DbPusher(Pusher):
   """
   Database pusher service. Base class for specific pusher services.
   """

   def __init__(self, dbpool, services, reactor = None):
      Pusher.__init__(self, dbpool, services, reactor)


   def publishPusherStateChange(self, connectId, isConnected, shouldBeConnected, lastErrMessage = None):
      evt = {"uri": self.CONNECT_ID_BASEURI + connectId,
             "is-connected": isConnected,
             "should-be-connected": shouldBeConnected,
             "last-error": lastErrMessage}
      if self.connects.has_key(connectId):
         self.connects[connectId].pushclientLastStateEvent = evt
      self.services["adminws"].dispatchAdminEvent(self.PUSHER_STATE_CHANGE_EVENT_URI, evt)


   def getPusherState(self, connectId):
      state = {'is-connected': False, 'should-be-connected': False, 'last-error': None}
      try:
         e = self.connects[connectId].pushclientLastStateEvent
         state['is-connected'] = e['is-connected']
         state['should-be-connected'] = e['should-be-connected']
         state['last-error'] = e['last-error']
      except:
         pass
      return state


   def _createPushStat(self, id):
      return PushStats(self.CONNECT_ID_BASEURI + id if id is not None else None)


   def getPusherStats(self):
      res = []
      for s in self.stats.values():
         res.append(s.get(changedonly = False, reset = False))
      return res


   def publishPusherStats(self):
      if not self.stopped:
         res = []
         for s in self.stats.values():
            v = s.get()
            if v:
               res.append(v)
         if len(res) > 0:
            self.services["adminws"].dispatchAdminEvent(self.STATS_EVENT_URI, res)
         self.reactor.callLater(0.2, self.publishPusherStats)


   def push(self, eventId, connectId, pushedBy, topicUri, payload, exclude = [], eligible = None):
      ## Called from background database pusher thread
      #print "OraPusher", connectId, allowed, pushedBy, topic, payload, type(payload), exclude, eligible
      allowed = False
      dbc = self.connects.get(connectId, None)
      if dbc:
         for pushrule in dbc.pushrules:
            if pushrule.user is None or pushedBy in pushrule.user:
               if pushrule.topicUri == topicUri or (pushrule.matchByPrefix and pushrule.topicUri == topicUri[:len(pushrule.topicUri)]):
                  allowed = True
                  break
      if allowed:
         d = self.services["appws"].dispatchHubEvent(topicUri, payload, exclude, eligible)

         if not self.stats.has_key(connectId):
            self.stats[connectId] = self._createPushStat(connectId)

         def onpushed(res):
            (receiver_count, requested_count) = res
            self.stats[None].updateDispatches(receiver_count, requested_count)
            self.stats[connectId].updateDispatches(receiver_count, requested_count)

            ## track event dispatch stats in database
            ##
            if dbc.pushclient:
               dbc.pushclient.trackDispatched(eventId, 0, receiver_count, requested_count - receiver_count)

         d.addCallback(onpushed)

         self.stats[None].updatePublications(1, 0)
         self.stats[connectId].updatePublications(1, 0)
      else:
         self.stats[None].updatePublications(0, 1)
         self.stats[connectId].updatePublications(0, 1)

         ## track event dispatch stats in database
         ##
         if dbc.pushclient:
            dbc.pushclient.trackDispatched(eventId, 1, 0, 0)


   def startService(self):
      Pusher.startService(self)

      self.stopped = False
      self.connects = {}
      self.dbpool.runInteraction(self.recache)

      ## current statistics
      self.stats = {}
      self.stats[None] = self._createPushStat(None)
      self.publishPusherStats()


   def stopService(self):
      self.stopped = True
      for k in self.connects:
         c = self.connects[k]
         if c.pushclient is not None:
            c.pushclient.stop()
            c.pushclient = None

      Pusher.stopService(self)


   def _cache(self, connectRows, ruleRows):

      ## map of rules by connect ID
      ##
      rules = {}
      for ruleRow in ruleRows:
         rule = self.makeRule(ruleRow)
         if not rules.has_key(rule.connectId):
            rules[rule.connectId] = []
         rules[rule.connectId].append(rule)

      ## map of connects by connect ID
      ##
      connects = {}
      for connectRow in connectRows:
         connect = self.makeConnect(connectRow)
         if rules.has_key(connect.id):
            connect.pushrules = rules[connect.id]
         else:
            connect.pushrules = []
         connect.pushruleCount = len(connect.pushrules)
         connect.pushclient = None
         connect.pushclientIsConnected = False
         connects[connect.id] = connect

      ## check for dropped connects
      ##
      for id in self.connects.keys():
         if not connects.has_key(id):
            ## stop push client
            if self.connects[id].pushclient is not None:
               log.msg("%s pushclient : stopping - connect dropped .. [connect ID %s]" % (self.LOGID, id))
               self.publishPusherStateChange(id, self.connects[id].pushclientIsConnected, False)
               self.connects[id].pushclient.autoReconnect = False
               self.connects[id].pushclient.stop()
               self.connects[id].pushclient = None

            ## remove dropped connect
            del self.connects[id]

      ## check for new/changed connects
      ##
      nConnects = 0
      nRules = 0
      for id in connects:

         dbc = connects[id]

         nConnects += 1
         nRules += len(dbc.pushrules)

         ## reuse existing pushclient (if any) by copying the reference
         ##
         if self.connects.has_key(id):
            dbc.pushclient = self.connects[id].pushclient

         ## start/stop pushclient as needed
         ##
         if len(dbc.pushrules) == 0:

            ## no pushrules, so no pushclient needed ..
            ##
            if dbc.pushclient is not None:
               log.msg("%s pushclient : stopping - pushrule count dropped to zero .. [connect ID %s]" % (self.LOGID, id))

               self.publishPusherStateChange(id, dbc.pushclient.isConnected, False)

               ## we need to prohibit a pushclient that has not yet connected from
               ## trying to reconnect when it again fails to connect
               dbc.pushclient.autoReconnect = False

               ## we try to immediately stop a connected pushclient. we also provide
               ## a CancelledError() that the pushclient will raise when exiting
               dbc.pushclient.stop()

               ## we immediately delete our reference so that it gets GCed soon
               dbc.pushclient = None
            else:
               log.msg("%s pushclient : skipped, since no push rules configured [connect ID %s]" % (self.LOGID, id))
         else:

            ## at least 1 pushrules, hence we need a pushclient ..
            ##
            if dbc.pushclient is None:

               ## create new push client
               ##
               dbc.pushclient = self.makeClient(dbc)
               dbc.cancelCall = None
               dbc.retries = 0
               self.publishPusherStateChange(id, dbc.pushclient.isConnected, True)

               ## create a startup function to start/retrystart the pushclient ..
               ##
               def connectPushClient():

                  log.msg("%s pushclient : starting .. [connect ID %s]" % (self.LOGID, id))
                  d = threads.deferToThread(dbc.pushclient.run)

                  ## not all DBI implementations allow to specify a connect timeout, so
                  ## we try the best we can do by manually setting up a timeout which will
                  ## stop-cancel ..
                  if dbc.connectionTimeout > 0 and dbc.cancelCall is None:
                     def cancelIfNotConnected():
                        if dbc and dbc.pushclient and not dbc.pushclient.isConnected:
                           log.msg("%s pushclient : database connection timeout fired [connect ID %s]" % (self.LOGID, id))
                           ## stop-cancel the pushclient. note that we can't just d.cancel(),
                           ## since when the pushclient later actually exits, the deferred
                           ## was already consumed
                           dbc.pushclient.stop()
                        else:
                           log.msg("%s pushclient : database connection timeout skipped, since already connected [connect ID %s]" % (self.LOGID, id))

                     dbc.cancelCall = self.reactor.callLater(dbc.connectionTimeout, cancelIfNotConnected)

                  def onstop(_):
                     if dbc and dbc.cancelCall:
                        dbc.cancelCall.cancel()
                        dbc.cancelCall = None
                     ## pushclient has exited cleanly
                     log.msg("%s pushclient : stopped [connect ID %s]" % (self.LOGID, id))
                     self.publishPusherStateChange(id, dbc.pushclient.isConnected, False)

                  def onerror(failure):
                     try:
                        if dbc and dbc.cancelCall:
                           dbc.cancelCall.cancel()
                           dbc.cancelCall = None
                     except Exception, e:
                        log.msg("Could not cancel Oracle connection - %s" % e)

                     if failure.check(CancelledError):
                        m = "connection timeout - retries %d" % dbc.retries
                        log.msg("%s pushclient : database connection timeout [connect ID %s]" % (self.LOGID, id))
                     else:
                        m = "%s - retries %d" % (failure.getErrorMessage(), dbc.retries)
                        log.msg("%s pushclient : database error %s [connect ID %s]" % (self.LOGID, m, id))

                     ## only try to restart if not yet running and set to autoconnect ..
                     if dbc.pushclient and not dbc.pushclient.isRunning and dbc.pushclient.autoReconnect:
                        dbc.retries += 1
                        self.publishPusherStateChange(id, dbc.pushclient.isConnected, True, m)
                        self.reactor.callLater(2, connectPushClient)

                  d.addCallbacks(onstop, onerror)

               ## start/retrystart the pushclient. this will
               connectPushClient()
            else:
               ## reuse existing pushclient
               ##
               log.msg("%s pushclient : reusing already running [connect ID %s]" % (self.LOGID, id))

         ## store
         ##
         self.connects[id] = dbc

      log.msg("%s._cacheConnects (%d, %d)" % (self.LOGID, nConnects, nRules))
