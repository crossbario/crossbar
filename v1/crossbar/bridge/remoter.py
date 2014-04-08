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



class RemoteStats:

   def __init__(self, id):
      self.stats = {'uri': id,
                    'call-allowed': 0,
                    'call-denied': 0,
                    'forward-success': 0,
                    'forward-failed': 0}
      self.statsChanged = False

   def updateForwards(self, success_count, failed_count):
      if success_count > 0:
         self.stats['forward-success'] += success_count

      if failed_count > 0:
         self.stats['forward-failed'] += failed_count

      if success_count > 0 or failed_count > 0:
         self.statsChanged = True

   def updateCalls(self, allowed_count, denied_count):
      if allowed_count > 0:
         self.stats['call-allowed'] += 1

      if denied_count > 0:
         self.stats['call-denied'] += 1

      if allowed_count > 0 or denied_count > 0:
         self.statsChanged = True

   def get(self, changedonly = True, reset = True):
      if not changedonly or self.statsChanged:
         if reset:
            self.statsChanged = False
         return self.stats
      else:
         return None


class Remoter(service.Service):

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)
      self.stopped = False

      ## current statistics
      self.stats = {}
      self.stats[None] = self._createRemoteStat(None)
      self.publishRemoterStats()

      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      self.stopped = True
      self.isRunning = False


   def _createRemoteStat(self, id):
      return RemoteStats(self.REMOTE_ID_BASEURI + id if id is not None else None)


   def getRemoterStats(self):
      res = []
      for s in self.stats.values():
         res.append(s.get(changedonly = False, reset = False))
      return res


   def publishRemoterStats(self):
      if not self.stopped:
         res = []
         for s in self.stats.values():
            v = s.get()
            if v:
               res.append(v)
         if len(res) > 0:
            self.services["adminws"].dispatchAdminEvent(self.STATS_EVENT_URI, res)
         self.reactor.callLater(0.2, self.publishRemoterStats)


   def onAfterRemoteCallSuccess(self, result, remoteId):
      if not self.stats.has_key(remoteId):
         self.stats[remoteId] = self._createRemoteStat(remoteId)
      self.stats[None].updateForwards(1, 0)
      return result


   def onAfterRemoteCallError(self, error, remoteId):
      if not self.stats.has_key(remoteId):
         self.stats[remoteId] = self._createRemoteStat(remoteId)
      self.stats[None].updateForwards(0, 1)
      raise error
