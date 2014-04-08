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


import datetime, os
from collections import deque

from twisted.python import log
from twisted.application import service
from twisted.web.resource import Resource

from autobahn.util import utcnow, parseutc
from autobahn.wamp import json_loads

from crossbar.adminwebmodule.uris import URI_EVENT
from crossbar.tlsctx import TlsContextFactory


class HubWebResource(Resource):
   """
   A Twisted/Web resource that receives events via HTTP/POSTs and
   dispatches to subscribed WebSockets clients.
   """

   def __init__(self, dbpool, services, reactor = None):
      Resource.__init__(self)

      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services

      logdir = self.services["config"].get("log-dir")

      ## create log dir when not there
      if not os.path.isdir(logdir):
         os.mkdir(logdir)

      ## create/open log files
      self.dispatch_log_file = open(os.path.join(logdir, "dispatch.log"), 'ab')
      self.error_log_file = open(os.path.join(logdir, "error.log"), 'ab')

      ## in-memory log queues
      self.dispatch_log = deque()
      self.error_log = deque()

      ## current statistics
      self.stats = {'uri': None,
                    'publish-allowed': 0,
                    'publish-denied': 0,
                    'dispatch-success': 0,
                    'dispatch-failed': 0}
      self.statsChanged = False

      ## the config is not yet load at this point
      #self.writeLog()
      self.reactor.callLater(10, self.writeLog)

      self.publishStats()


   def getStats(self):
      return [self.stats]


   def publishStats(self):
      if self.statsChanged:
         self.services["adminws"].dispatchAdminEvent(URI_EVENT + "on-restpusherstat", [self.stats])
         self.statsChanged = False
      self.reactor.callLater(0.2, self.publishStats)


   def writeLog(self):
      """
      Write buffered log records to database.
      """
      n = 0
      while True:
         try:
            rec = self.error_log.popleft()
            s = ','.join([str(x) for x in rec]) + '\n'
            self.error_log_file.write(s)
            n += 1
         except IndexError:
            break
      if n > 0:
         self.error_log_file.flush()
         log.msg("%d buffered records written to error log" % n)

      n = 0
      while True:
         try:
            rec = self.dispatch_log.popleft()
            s = ','.join([str(x) for x in rec]) + '\n'
            self.dispatch_log_file.write(s)
            n += 1
         except IndexError:
            break
      if n > 0:
         self.dispatch_log_file.flush()
         log.msg("%d buffered records written to dispatch log" % n)

      self.reactor.callLater(self.services["config"].get("log-write-interval", 60), self.writeLog)


   def _getContentLengthLimit(self):
      return self.services["config"].get("post-body-limit", 4096)


   def _getTimestampDeltaLimit(self):
      return self.services["config"].get("sig-timestamp-delta-limit", 300)


   def deny(self, request, code, reason):
      """
      Called when HTTP/POST is denied.
      """
      headers = request.getAllHeaders()
      user_agent = headers.get("user-agent", "unknown")
      client_ip = request.getClientIP()
      is_secure = request.isSecure()

      self.error_log.append([utcnow(), user_agent, client_ip, is_secure, code, reason])
      self.stats['publish-denied'] += 1
      self.statsChanged = True

      request.setResponseCode(code)
      return "%s\n" % str(reason)


   def log(self, user_agent, client_ip, is_secure, topic, content_length, postrule_id, receiver_count, requested_count):
      """
      Log successful HTTP/POST to WebSockets PubSub event dispatch.
      """
      logrec = [utcnow(), user_agent, client_ip, is_secure, topic, content_length, receiver_count]
      self.dispatch_log.append(logrec)
      self.stats['dispatch-success'] += receiver_count
      error_count = requested_count - receiver_count
      if error_count > 0:
         self.stats['dispatch-failed'] += error_count
      self.statsChanged = True


   def render(self, request):
      if request.method != "POST":
         return self.deny(request, 405, "HTTP/%s not allowed" % request.method)
      else:
         return self.render_POST(request)


   def render_POST(self, request):
      """
      The HTTP/POST to WebSockets hub Twisted/Web resource main method.
      """
      try:
         path = request.path
         args = request.args
         headers = request.getAllHeaders()

         if headers.get("content-type", "missing") != 'application/x-www-form-urlencoded':
            return self.deny(request, 400, "bad or missing content type ('%s')" % headers.get("content-type", "missing"))

         ## FIXME: post-body-limit
         ##
         content_length = int(headers.get("content-length", 0))
         if content_length > self._getContentLengthLimit():
            return self.deny(request, 400, "content length (%d) exceeds maximum (%d)" % (content_length, self._getContentLengthLimit()))

         if not args.has_key("topic"):
            return self.deny(request, 400, "missing query parameter 'topic'")
         topic = args["topic"][0]

         appkey = args.get("appkey", [False])[0]
         signature = args.get("signature", [False])[0]
         timestamp_str = args.get("timestamp", [False])[0]
         if appkey or signature or timestamp_str:
            if not (appkey and signature and timestamp_str):
               return self.deny(request, 400, "either all or none of parameters 'appkey', 'signature' and 'timestamp' must be present")

         if timestamp_str:
            # '2011-10-14T12:59:51Z'
            timestamp = parseutc(timestamp_str)
            if timestamp is None:
               return self.deny(request, 400, "invalid timestamp '%s' (must be i.e. '2011-10-14T16:59:51Z'" % timestamp_str)
            delta = int(round(abs(timestamp - datetime.datetime.utcnow()).total_seconds()))
            if delta > self._getTimestampDeltaLimit():
               return self.deny(request, 400, "timestamp expired (delta %d seconds)" % delta)
         else:
            timestamp = None

         if args.has_key('event'):
            json_str = args['event'][0]
         else:
            json_str = request.content.read()

         if appkey:
            sig = self.services["restpusher"].signature(topic, appkey, timestamp_str, json_str)
            if sig is None:
               return self.deny(request, 400, "unknown application key '%s'" % appkey)
            if sig != signature:
               return self.deny(request, 401, "invalid request signature (expected %s, got %s)" % (sig, signature))

         user_agent = headers.get("user-agent", "unknown")
         client_ip = request.getClientIP()
         is_secure = request.isSecure()

         auth = self.services["restpusher"].authorize(topic, client_ip, appkey)
         if auth[0]:

            try:
               event = json_loads(json_str)
            except:
               return self.deny(request, 400, "invalid JSON in request body")

            if args.has_key("exclude"):
               exclude = [x.strip() for x in args["exclude"][0].split(",")]
            else:
               exclude = []

            if args.has_key("eligible"):
               eligible = [x.strip() for x in args["eligible"][0].split(",")]
            else:
               eligible = None

            ## dispatch & log event
            d = self.services["appws"].dispatchHubEvent(topic, event, exclude, eligible)
            d.addCallback(lambda res: self.log(user_agent,
                                               client_ip,
                                               is_secure,
                                               topic,
                                               content_length,
                                               postrule_id = auth[1],
                                               receiver_count = res[0],
                                               requested_count = res[1]))
            self.stats['publish-allowed'] += 1
            self.statsChanged = True

            ## signal success to submitter
            request.setResponseCode(202)
            return ""
         else:
            return self.deny(request, 401, "not authorized (denied by post rule %s: %s)" % (auth[1], auth[2]))

      except Exception, e:
         ## catch all .. should not happen (usually)
         return self.deny(request, 500, "internal server error ('%s')" % str(e))



class HubWebService(service.Service):

   SERVICENAME = "Hub Web"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False
      self.factory = None
      self.root = None
      self.listener = None


   def getStats(self):
      if self.isRunning and self.root:
         return self.root.children[""].getStats()


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)

      ## avoid module level reactor import
      from twisted.web.static import File
      from twisted.web.server import Site

      self.root = Resource()
      self.root.putChild("", HubWebResource(self.dbpool, self.services))

      self.factory = Site(self.root)
      self.factory.log = lambda _: None # disable any logging

      cfg = self.services["config"]

      port = cfg["hub-web-port"]
      if cfg["hub-web-tls"]:
         contextFactory = TlsContextFactory(cfg["hub-web-tlskey-pem"],
                                            cfg["hub-web-tlscert-pem"],
                                            dhParamFilename = self.services['master'].dhParamFilename)
         self.listener = self.reactor.listenSSL(port, self.factory, contextFactory)
      else:
         self.listener = self.reactor.listenTCP(port, self.factory)

      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      if self.listener:
         self.listener.stopListening()
         self.listener = None
         self.factory = None
         self.root = None
      self.isRunning = False
