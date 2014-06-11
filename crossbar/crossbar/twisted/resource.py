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
import datetime
import hmac
import hashlib
import base64

import six

from autobahn.util import utcnow, parseutc

from autobahn.wamp.types import PublishOptions
from twisted.web.server import NOT_DONE_YET


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

      self._debug = False

      options = config.get('options', {})

      self._key = None
      if 'key' in options:
         self._key = options['key'].encode('utf8')

      self._secret = None
      if 'secret' in options:
         self._secret = options['secret'].encode('utf8')

      self._post_body_limit = int(options.get('post_body_limit', 0))
      self._timestamp_delta_limit = int(options.get('timestamp_delta_limit', 300))



   def _deny_request(self, request, code, reason):
      """
      Called when client request is denied.
      """
      request.setResponseCode(code)
      return "{}\n".format(reason)



   def render(self, request):
      if self._debug:
         log.msg("PusherResource.render", request.method, request.path, request.args)

      if request.method != "POST":
         return self._deny_request(request, 405, "HTTP/{0} not allowed".format(request.method))
      else:
         return self.render_POST(request)



   def render_POST(self, request):
      """
      Receives an HTTP/POST request to forward a WAMP event.
      """
      try:
         path = request.path
         args = request.args
         headers = request.getAllHeaders()

         ## check content type
         ##
         if headers.get("content-type", None) != 'application/x-www-form-urlencoded':
            return self._deny_request(request, 400, "bad or missing content type ('{0}')".format(headers.get("content-type", None)))

         ## enforce "post_body_limit"
         ##
         content_length = int(headers.get("content-length", 0))
         if self._post_body_limit and content_length > self._post_body_limit:  
            return self._deny_request(request, 400, "HTTP/POST body length ({0}) exceeds maximum ({1})".format(content_length, self._post_body_limit))

         ##
         ## parse/check HTTP/POST query parameters
         ##

         ## key
         ##
         if 'key' in args:
            key_str = args["key"][0]
         else:
            if self._secret:
               return self._deny_request(request, 400, "signed request required, but mandatory 'key' field missing")

         ## timestamp
         ##
         if 'timestamp' in args:
            timestamp_str = args["timestamp"][0]
            try:
               ts = datetime.datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
               delta = abs((ts - datetime.datetime.utcnow()).total_seconds())
               if self._timestamp_delta_limit and delta > self._timestamp_delta_limit:
                  return self._deny_request(request, 400, "request expired (delta {0} seconds)".format(delta))
            except:
               return self._deny_request(request, 400, "invalid timestamp '{0}' (must be UTC/ISO-8601, e.g. '2011-10-14T16:59:51.123Z')".format(timestamp_str))
         else:
            if self._secret:
               return self._deny_request(request, 400, "signed request required, but mandatory 'timestamp' field missing")

         ## seq
         ##
         if 'seq' in args:
            seq_str = args["seq"][0]
            try:
               seq = int(seq_str)
            except:
               return self._deny_request(request, 400, "invalid sequence number '{0}' (must be an integer)".format(seq_str))
         else:
            if self._secret:
               return self._deny_request(request, 400, "signed request required, but mandatory 'seq' field missing")

         ## nonce
         ##
         if 'nonce' in args:
            nonce_str = args["nonce"][0]
            try:
               nonce = int(nonce_str)
            except:
               return self._deny_request(request, 400, "invalid nonce '{0}' (must be an integer)".format(nonce_str))
         else:
            if self._secret:
               return self._deny_request(request, 400, "signed request required, but mandatory 'nonce' field missing")

         ## signature
         ##
         if 'signature' in args:
            signature_str = args["signature"][0]
         else:
            if self._secret:
               return self._deny_request(request, 400, "signed request required, but mandatory 'signature' field missing")


         ## read HTTP/POST body
         ##
         body = request.content.read()


         ## do more checks if signed requests are required
         ##
         if self._secret:

            if key_str != self._key:
               return self._deny_request(request, 400, "unknown key '{0}' in signed request".format(key_str))

            ## Compute signature: HMAC[SHA256]_{secret} (key | timestamp | seq | nonce | body) => signature
            hm = hmac.new(self._secret, None, hashlib.sha256)
            hm.update(key_str)
            hm.update(timestamp_str)
            hm.update(seq_str)
            hm.update(nonce_str)
            hm.update(body)
            signature_recomputed = base64.urlsafe_b64encode(hm.digest())

            if signature_str != signature_recomputed:
               return self._deny_request(request, 401, "invalid request signature")
            else:
               if self._debug:
                  log.msg("request signature ok!")


         user_agent = headers.get("user-agent", "unknown")
         client_ip = request.getClientIP()
         is_secure = request.isSecure()

         ## FIXME: authorize request
         authorized = True

         if authorized:

            try:
               event = json.loads(body)
            except Exception as e:
               return self._deny_request(request, 400, "invalid request event - HTTP/POST body must be valid JSON: {0}".format(e))

            if type(event) != dict:
               return self._deny_request(request, 400, "invalid request event - HTTP/POST body must be JSON dict")

            if not 'topic' in event:
               return self._deny_request(request, 400, "invalid request event - missing 'topic' in HTTP/POST body")

            topic = event.pop('topic')

            args = event.pop('args', [])
            kwargs = event.pop('kwargs', {})
            options = event.pop('options', {})

            publish_options = PublishOptions(acknowledge = True,
               exclude = options.get('exclude', None),
               eligible = options.get('eligible', None))

            kwargs['options'] = publish_options

            ## http://twistedmatrix.com/documents/current/web/howto/web-in-60/asynchronous-deferred.html

            d = self._session.publish(topic, *args, **kwargs)

            def on_publish_ok(pub):
               res = {'id': pub.id}
               if self._debug:
                  log.msg("request succeeded: {0}".format(res))
               body = json.dumps(res, separators = (',',':'))
               if six.PY3:
                  body = body.encode('utf8')

               request.setHeader('content-type', 'application/json; charset=UTF-8')
               request.setResponseCode(202)
               request.write(body)
               request.finish()

            def on_publish_error(err):
               emsg = "request failed: {0}\n".format(err.value)
               if self._debug:
                  log.msg(emsg)
               request.setResponseCode(400)
               request.write(emsg)
               request.finish()

            d.addCallbacks(on_publish_ok, on_publish_error)

            return NOT_DONE_YET

         else:
            return self._deny_request(request, 401, "not authorized")

      except Exception as e:
         ## catch all .. should not happen (usually)
         return self._deny_request(request, 500, "internal server error ('{0}')".format(e))
