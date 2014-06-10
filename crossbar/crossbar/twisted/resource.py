###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
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

import os
import json

from twisted.python import log
from twisted.web.resource import Resource, NoResource
from twisted.web import server


try:
   ## triggers module level reactor import
   ## https://twistedmatrix.com/trac/ticket/6849#comment:4  
   from twisted.web.static import File
   _HAS_STATIC = True
except ImportError:
   ## Twisted hasn't ported this to Python 3 yet
   _HAS_STATIC = False


try:
   ## trigers module level reactor import
   ## https://twistedmatrix.com/trac/ticket/6849#comment:5
   from twisted.web.twcgi import CGIScript, CGIProcessProtocol
   _HAS_CGI = True
except ImportError:
   ## Twisted hasn't ported this to Python 3 yet
   _HAS_CGI = False


import crossbar



class JsonResource(Resource):
   """
   Static Twisted Web resource that renders to a JSON document.
   """

   def __init__(self, value):
      Resource.__init__(self)
      self._data = json.dumps(value, sort_keys = True, indent = 3)

   def render_GET(self, request):
      request.setHeader('content-type', 'application/json; charset=UTF-8')
      return self._data



class Resource404(Resource):
   """
   Custom error page (404).
   """
   def __init__(self, templates, directory):
      Resource.__init__(self)
      self._page = templates.get_template('cb_web_404.html')
      self._directory = directory

   def render_GET(self, request):
      s = self._page.render(cbVersion = crossbar.__version__,
                            directory = self._directory)
      return s.encode('utf8')



class RedirectResource(Resource):

   isLeaf = True

   def __init__(self, redirect_url):
      Resource.__init__(self)
      self._redirect_url = redirect_url

   def render_GET(self, request):
      request.redirect(self._redirect_url)
      request.finish()
      return server.NOT_DONE_YET



if _HAS_STATIC:

   class FileNoListing(File):
      """
      A file hierarchy resource with directory listing disabled.
      """
      def directoryListing(self):
         return self.childNotFound



if _HAS_CGI:

   from twisted.python.filepath import FilePath

   class CgiScript(CGIScript):

      def __init__(self, filename, filter):
         CGIScript.__init__(self, filename)
         self.filter = filter

      def runProcess(self, env, request, qargs = []):
         p = CGIProcessProtocol(request)
         from twisted.internet import reactor
         reactor.spawnProcess(p, self.filter, [self.filter, self.filename], env, os.path.dirname(self.filename))


   class CgiDirectory(Resource, FilePath):

      cgiscript = CgiScript

      def __init__(self, pathname, filter, childNotFound = None):
         Resource.__init__(self)
         FilePath.__init__(self, pathname)
         self.filter = filter
         if childNotFound:
            self.childNotFound = childNotFound
         else:
            self.childNotFound = NoResource("CGI directories do not support directory listing.")

      def getChild(self, path, request):
         fnp = self.child(path)
         if not fnp.exists():
            return File.childNotFound
         elif fnp.isdir():
            return CgiDirectory(fnp.path, self.filter, self.childNotFound)
         else:
            return self.cgiscript(fnp.path, self.filter)
         return NoResource()

      def render(self, request):
         return self.childNotFound.render(request)



import json
from autobahn.util import utcnow, parseutc

from autobahn.wamp.types import PublishOptions



class PusherResource(Resource):
   """
   A HTTP/POST to WAMP PubSub bridge.

   {
      post_body_limit: 10000
   }

   curl -d 'topic=com.myapp.topic1&event="123"' http://127.0.0.1:8080/push
   """

   def __init__(self, config, session):
      Resource.__init__(self)
      self._config = config
      self._session = session

      self._config_post_body_limit = int(self._config.get('post_body_limit', 0))


   def _deny_request(self, request, code, reason):
      """
      Called when client request is denied.
      """
      request.setResponseCode(code)
      return "%s\n" % str(reason)


   def render(self, request):
      if request.method != "POST":
         return self._deny_request(request, 405, "HTTP/{0} not allowed".format(request.method))
      else:
         return self.render_POST(request)


   def render_POST(self, request):
      """
      The HTTP/POST to WebSockets hub Twisted/Web resource main method.
      """
      print "GOT POST", request.path, request.args
      try:
         path = request.path
         args = request.args
         headers = request.getAllHeaders()

         if headers.get("content-type", None) != 'application/x-www-form-urlencoded':
            return self._deny_request(request, 400, "bad or missing content type ('{0}')".format(headers.get("content-type", None)))

         ## enforce "post_body_limit"
         ##
         content_length = int(headers.get("content-length", 0))
         if self._config_post_body_limit and content_length > self._config_post_body_limit:  
            return self._deny_request(request, 400, "content length ({0}) exceeds maximum ({1})".format(content_length, self._config_post_body_limit))

         ## "topic" parameter
         ##
         if not args.has_key("topic"):
            return self._deny_request(request, 400, "missing mandatory parameter 'topic'")
         topic = args["topic"][0]

         ## FIXME: check topic

         appkey = args.get("appkey", [False])[0]
         signature = args.get("signature", [False])[0]
         timestamp_str = args.get("timestamp", [False])[0]
         if appkey or signature or timestamp_str:
            if not (appkey and signature and timestamp_str):
               return self._deny_request(request, 400, "either all or none of parameters 'appkey', 'signature' and 'timestamp' must be present")

         if timestamp_str:
            # '2011-10-14T12:59:51Z'
            timestamp = parseutc(timestamp_str)
            if timestamp is None:
               return self._deny_request(request, 400, "invalid timestamp '{0}' (must be i.e. '2011-10-14T16:59:51Z'".format(timestamp_str))
            delta = int(round(abs(timestamp - datetime.datetime.utcnow()).total_seconds()))
            if delta > self._getTimestampDeltaLimit():
               return self._deny_request(request, 400, "timestamp expired (delta {0} seconds)".format(delta))
         else:
            timestamp = None

         if args.has_key('event'):
            json_str = args['event'][0]
         else:
            json_str = request.content.read()

         print "$$$", json_str

         if appkey:
            sig = self.services["restpusher"].signature(topic, appkey, timestamp_str, json_str)
            if sig is None:
               return self._deny_request(request, 400, "unknown application key '%s'" % appkey)
            if sig != signature:
               return self._deny_request(request, 401, "invalid request signature (expected %s, got %s)" % (sig, signature))

         user_agent = headers.get("user-agent", "unknown")
         client_ip = request.getClientIP()
         is_secure = request.isSecure()

         #auth = self.services["restpusher"].authorize(topic, client_ip, appkey)
         auth = (True, None, "global default")

         if auth[0]:

            try:
               event = json.loads(json_str)
            except Exception as e:
               return self._deny_request(request, 400, "invalid JSON in request body - {}".format(e))

            if args.has_key("exclude"):
               exclude = [x.strip() for x in args["exclude"][0].split(",")]
            else:
               exclude = []

            if args.has_key("eligible"):
               eligible = [x.strip() for x in args["eligible"][0].split(",")]
            else:
               eligible = None

            ## dispatch & log event
            #d = self.services["appws"].dispatchHubEvent(topic, event, exclude, eligible)

            print "DISPATCH", topic, event
            #self._session.publish(topic, event, options = PublishOptions(acknowledge = True))
            self._session.publish(topic, event)

            # d.addCallback(lambda res: self.log(user_agent,
            #                                    client_ip,
            #                                    is_secure,
            #                                    topic,
            #                                    content_length,
            #                                    postrule_id = auth[1],
            #                                    receiver_count = res[0],
            #                                    requested_count = res[1]))
            ## signal success to submitter
            request.setResponseCode(202)
            return ""
         else:
            return self._deny_request(request, 401, "not authorized (denied by post rule %s: %s)" % (auth[1], auth[2]))

      except Exception as e:
         ## catch all .. should not happen (usually)
         return self._deny_request(request, 500, "internal server error ('{0}')".format(e))
