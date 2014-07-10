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

from __future__ import absolute_import

__all__ = ['CrossbarWampWebSocketServerFactory',
           'CrossbarWampRawSocketServerFactory']

import datetime

from twisted.python import log
from autobahn.twisted.websocket import WampWebSocketServerProtocol, \
                                       WampWebSocketServerFactory, \
                                       WampWebSocketClientProtocol, \
                                       WampWebSocketClientFactory

from autobahn.twisted.rawsocket import WampRawSocketServerProtocol, \
                                       WampRawSocketServerFactory, \
                                       WampRawSocketClientProtocol, \
                                       WampRawSocketClientFactory

from twisted.internet.defer import Deferred

import json
from six.moves import urllib
from six.moves import http_cookies

import os
import sqlite3

try:
   from twisted.enterprise import adbapi
   _HAS_ADBAPI = True
except ImportError:
   ## Twisted hasn't ported this to Python 3 yet
   _HAS_ADBAPI = False



from autobahn import util
from autobahn.websocket import http
from autobahn.websocket.compress import *

from autobahn.wamp import types
from autobahn.wamp import message
from autobahn.wamp.router import RouterFactory
from autobahn.twisted.wamp import RouterSession, RouterSessionFactory

import crossbar



def set_websocket_options(factory, options):
   """
   Set WebSocket options on a WebSocket or WAMP-WebSocket factory.

   :param factory: The WebSocket or WAMP-WebSocket factory to set options on.
   :type factory:  Instance of :class:`autobahn.twisted.websocket.WampWebSocketServerFactory`
                   or :class:`autobahn.twisted.websocket.WebSocketServerFactory`.
   :param options: Options from Crossbar.io transport configuration.
   :type options: dict
   """
   c = options

   versions = []
   if c.get("enable_hixie76", True):
      versions.append(0)
   if c.get("enable_hybi10", True):
      versions.append(8)
   if c.get("enable_rfc6455", True):
      versions.append(13)

   ## FIXME: enforce!!
   ##
   #self.connectionCap = c.get("max_connections")

   ## convert to seconds
   ##
   openHandshakeTimeout = float(c.get("open_handshake_timeout", 0))
   if openHandshakeTimeout:
      openHandshakeTimeout = openHandshakeTimeout / 1000.

   closeHandshakeTimeout = float(c.get("close_handshake_timeout", 0))
   if closeHandshakeTimeout:
      closeHandshakeTimeout = closeHandshakeTimeout / 1000.

   factory.setProtocolOptions(versions = versions,
                              allowHixie76 = c.get("enable_hixie76", True),
                              webStatus = c.get("enable_webstatus", True),
                              utf8validateIncoming = c.get("validate_utf8", True),
                              maskServerFrames = c.get("mask_server_frames", False),
                              requireMaskedClientFrames = c.get("require_masked_client_frames", True),
                              applyMask = c.get("apply_mask", True),
                              maxFramePayloadSize = c.get("max_frame_size", 0),
                              maxMessagePayloadSize = c.get("max_message_size", 0),
                              autoFragmentSize = c.get("auto_fragment_size", 0),
                              failByDrop = c.get("fail_by_drop", False),
                              echoCloseCodeReason = c.get("echo_close_codereason", False),
                              openHandshakeTimeout = openHandshakeTimeout,
                              closeHandshakeTimeout = closeHandshakeTimeout,
                              tcpNoDelay = c.get("tcp_nodelay", True))

   ## WebSocket compression
   ##
   factory.setProtocolOptions(perMessageCompressionAccept = lambda _: None)
   if 'compression' in c:

      ## permessage-deflate
      ##
      if 'deflate' in c['compression']:

         log.msg("enabling WebSocket compression (permessage-deflate)")

         params = c['compression']['deflate']

         requestNoContextTakeover   = params.get('request_no_context_takeover', False)
         requestMaxWindowBits       = params.get('request_max_window_bits', 0)
         noContextTakeover          = params.get('no_context_takeover', None)
         windowBits                 = params.get('max_window_bits', None)
         memLevel                   = params.get('memory_level', None)

         def accept(offers):
            for offer in offers:
               if isinstance(offer, PerMessageDeflateOffer):
                  if (requestMaxWindowBits == 0 or offer.acceptMaxWindowBits) and \
                     (not requestNoContextTakeover or offer.acceptNoContextTakeover):
                     return PerMessageDeflateOfferAccept(offer,
                                                         requestMaxWindowBits = requestMaxWindowBits,
                                                         requestNoContextTakeover = requestNoContextTakeover,
                                                         noContextTakeover = noContextTakeover,
                                                         windowBits = windowBits,
                                                         memLevel = memLevel)

         factory.setProtocolOptions(perMessageCompressionAccept = accept)



import traceback


class CrossbarWampWebSocketServerProtocol(WampWebSocketServerProtocol):

   ## authid -> cookie -> set(connection)

   def onConnect(self, request):

      if self.factory.debug_traffic:
         from twisted.internet import reactor

         def print_traffic():
            print("Traffic {}: {} / {} in / out bytes - {} / {} in / out msgs".format(self.peer,
               self.trafficStats.incomingOctetsWireLevel,
               self.trafficStats.outgoingOctetsWireLevel,
               self.trafficStats.incomingWebSocketMessages,
               self.trafficStats.outgoingWebSocketMessages))
            reactor.callLater(1, print_traffic)

         print_traffic()

      protocol, headers = WampWebSocketServerProtocol.onConnect(self, request)

      try:

         self._origin = request.origin

         ## transport authentication
         ##
         self._authid = None
         self._authrole = None
         self._authmethod = None

         ## cookie tracking
         ##
         self._cbtid = None

         if self.factory._cookiestore:

            self._cbtid = self.factory._cookiestore.parse(request.headers)

            ## if no cookie is set, create a new one ..
            if self._cbtid is None:

               self._cbtid, headers['Set-Cookie'] = self.factory._cookiestore.create()

               if self.debug:
                  log.msg("Setting new cookie: %s" % headers['Set-Cookie'])

            else:
               if self.debug:
                  log.msg("Cookie already set")

            ## add this WebSocket connection to the set of connections
            ## associated with the same cookie
            self.factory._cookiestore.addProto(self._cbtid, self)

            if self.debug:
               log.msg("Cookie tracking enabled on WebSocket connection {}".format(self))

            ## if cookie-based authentication is enabled, set auth info from cookie store
            ##
            if 'auth' in self.factory._config and 'cookie' in self.factory._config['auth']:

               self._authid, self._authrole, self._authmethod = self.factory._cookiestore.getAuth(self._cbtid)

               if self.debug:
                  log.msg("Authenticated client via cookie", self._authid, self._authrole, self._authmethod)
            else:
               if self.debug:
                  log.msg("Cookie-based authentication disabled")

         else:

            if self.debug:
               log.msg("Cookie tracking disabled on WebSocket connection {}".format(self))

         ## accept the WebSocket connection, speaking subprotocol `protocol`
         ## and setting HTTP headers `headers`
         return (protocol, headers)

      except Exception as e:
         traceback.print_exc()


   def sendServerStatus(self, redirectUrl = None, redirectAfter = 0):
      """
      Used to send out server status/version upon receiving a HTTP/GET without
      upgrade to WebSocket header (and option serverStatus is True).
      """
      try:
         page = self.factory._templates.get_template('cb_ws_status.html')
         self.sendHtml(page.render(redirectUrl = redirectUrl,
                                   redirectAfter = redirectAfter,
                                   cbVersion = crossbar.__version__,
                                   wsUri = self.factory.url,
                                   peer = self.peer,
                                   workerPid = os.getpid()))
      except Exception as e:         
         log.msg("Error rendering WebSocket status page template: %s" % e)


   def onDisconnect(self):
      ## remove this WebSocket connection from the set of connections
      ## associated with the same cookie
      if self._cbtid:
         self.factory._cookiestore.dropProto(self._cbtid, self)





class CookieStore:
   """
   A cookie store.
   """

   def __init__(self, config, debug = False):
      """
      Ctor.

      :param config: The cookie configuration.
      :type config: dict
      """
      self.debug = debug
      if self.debug:
         log.msg("CookieStore.__init__()", config)

      self._config = config      
      self._cookie_id_field = config.get('name', 'cbtid')
      self._cookie_id_field_length = int(config.get('length', 24))
      self._cookie_max_age = int(config.get('max_age', 86400 * 30 * 12))

      self._cookies = {}


   def parse(self, headers):
      """
      Parse HTTP header for cookie. If cookie is found, return cookie ID,
      else return None.
      """
      if self.debug:
         log.msg("CookieStore.parse()", headers)

      ## see if there already is a cookie set ..
      if 'cookie' in headers:
         try:
            cookie = http_cookies.SimpleCookie()
            cookie.load(str(headers['cookie']))
         except http_cookies.CookieError:
            pass
         else:
            if self._cookie_id_field in cookie:
               id = cookie[self._cookie_id_field].value
               if id in self._cookies:
                  return id
      return None


   def create(self):
      """
      Create a new cookie, returning the cookie ID and cookie header value.
      """
      if self.debug:
         log.msg("CookieStore.create()")

      ## http://tools.ietf.org/html/rfc6265#page-20
      ## 0: delete cookie
      ## -1: preserve cookie until browser is closed

      id = util.newid(self._cookie_id_field_length)

      cbtData = {'created': util.utcnow(),
                 'authid': None,
                 'authrole': None,
                 'authmethod': None,
                 'max_age': self._cookie_max_age,
                 'connections': set()}

      self._cookies[id] = cbtData

      ## do NOT add the "secure" cookie attribute! "secure" refers to the
      ## scheme of the Web page that triggered the WS, not WS itself!!
      ##
      return id, '%s=%s;max-age=%d' % (self._cookie_id_field, id, cbtData['max_age'])


   def exists(self, id):
      """
      Check if cookie with given ID exists.
      """
      if self.debug:
         log.msg("CookieStore.exists()", id)

      return id in self._cookies


   def getAuth(self, id):
      """
      Return `(authid, authrole, authmethod)` triple given cookie ID.
      """
      if self.debug:
         log.msg("CookieStore.getAuth()", id)

      if id in self._cookies:
         c = self._cookies[id]
         return c['authid'], c['authrole'], c['authmethod']
      else:
         return None, None, None


   def setAuth(self, id, authid, authrole, authmethod):
      """
      Set `(authid, authrole, authmethod)` triple for given cookie ID.
      """
      if id in self._cookies:
         c = self._cookies[id]
         c['authid'] = authid
         c['authrole'] = authrole
         c['authmethod'] = authmethod


   def addProto(self, id, proto):
      """
      Add given WebSocket connection to the set of connections associated
      with the cookie having the given ID. Return the new count of
      connections associated with the cookie.
      """
      if self.debug:
         log.msg("CookieStore.addProto()", id, proto)

      if id in self._cookies:
         self._cookies[id]['connections'].add(proto)
         return len(self._cookies[id]['connections'])
      else:
         return 0


   def dropProto(self, id, proto):
      """
      Remove given WebSocket connection from the set of connections associated
      with the cookie having the given ID. Return the new count of
      connections associated with the cookie.
      """
      if self.debug:
         log.msg("CookieStore.dropProto()", id, proto)

      ## remove this WebSocket connection from the set of connections
      ## associated with the same cookie
      if id in self._cookies:
         self._cookies[id]['connections'].discard(proto)
         return len(self._cookies[id]['connections'])
      else:
         return 0


   def getProtos(self, id):
      """
      Get all WebSocket connections currently associated with the cookie.
      """
      if id in self._cookies:
         return self._cookies[id]['connections']
      else:
         return []



if _HAS_ADBAPI:

   class PersistentCookieStore(CookieStore):
      """
      A persistent cookie store.
      """

      def __init__(self, dbfile, config, debug = False):
         CookieStore.__init__(self, config, debug)
         self._dbfile = dbfile

         ## initialize database and create database connection pool
         self._init_db()
         self._dbpool = adbapi.ConnectionPool('sqlite3', self._dbfile, check_same_thread = False)


      def _init_db(self):
         if not os.path.isfile(self._dbfile):

            db = sqlite3.connect(self._dbfile)
            cur = db.cursor()

            cur.execute("""
                        CREATE TABLE cookies (
                           id                TEXT     NOT NULL,
                           created           TEXT     NOT NULL,
                           max_age           INTEGER  NOT NULL,
                           authid            TEXT,
                           authrole          TEXT,
                           authmethod        TEXT,
                           PRIMARY KEY (id))
                        """)

            log.msg("Cookie DB created.")

         else:
            log.msg("Cookie DB already exists.")

            db = sqlite3.connect(self._dbfile)
            cur = db.cursor()

            cur.execute("SELECT id, created, max_age, authid, authrole, authmethod FROM cookies")
            n = 0
            for row in cur.fetchall():
               id = row[0]
               cbtData = {'created': row[1],
                          'max_age': row[2],
                          'authid': row[3],
                          'authrole': row[4],
                          'authmethod': row[5],
                          'connections': set()}
               self._cookies[id] = cbtData
               n += 1
            log.msg("Loaded {} cookies into cache.".format(n))


      def create(self):
         id, header = CookieStore.create(self)

         def run(txn):
            c = self._cookies[id]
            txn.execute("INSERT INTO cookies (id, created, max_age, authid, authrole, authmethod) VALUES (?, ?, ?, ?, ?, ?)",
               [id, c['created'], c['max_age'], c['authid'], c['authrole'], c['authmethod']])
            if self.debug:
               log.msg("Cookie {} stored".format(id))

         self._dbpool.runInteraction(run)

         return id, header


      def setAuth(self, id, authid, authrole, authmethod):
         CookieStore.setAuth(self, id, authid, authrole, authmethod)

         def run(txn):
            txn.execute("UPDATE cookies SET authid = ?, authrole = ?, authmethod = ? WHERE id = ?",
               [authid, authrole, authmethod, id])
            if self.debug:
               log.msg("Cookie {} updated".format(id))

         self._dbpool.runInteraction(run)




class CrossbarWampWebSocketServerFactory(WampWebSocketServerFactory):

   protocol = CrossbarWampWebSocketServerProtocol

   def __init__(self, factory, cbdir, config, templates):
      """
      Ctor.

      :param factory: WAMP session factory.
      :type factory: An instance of ..
      :param cbdir: The Crossbar.io node directory.
      :type cbdir: str
      :param config: Crossbar transport configuration.
      :type config: dict 
      """
      self.debug = config.get('debug', False)
      self.debug_traffic = config.get('debug_traffic', False)

      options = config.get('options', {})

      server = "Crossbar/{}".format(crossbar.__version__)
      externalPort = options.get('external_port', None)

      ## explicit list of WAMP serializers
      ##
      if 'serializers' in config:
         serializers = []
         sers = set(config['serializers'])

         if 'json' in sers:
            ## try JSON WAMP serializer
            try:
               from autobahn.wamp.serializer import JsonSerializer
               serializers.append(JsonSerializer())
            except ImportError:
               print("Warning: could not load WAMP-JSON serializer")
            else:
               sers.discard('json')

         if 'msgpack' in sers:
            ## try MsgPack WAMP serializer
            try:
               from autobahn.wamp.serializer import MsgPackSerializer
               serializers.append(MsgPackSerializer())
            except ImportError:
               print("Warning: could not load WAMP-MsgPack serializer")
            else:
               sers.discard('msgpack')

         if not serializers:
            raise Exception("no valid WAMP serializers specified")

         if len(sers) > 0:
            raise Exception("invalid WAMP serializers specified: {}".format(sers))

      else:
         serializers = None

      WampWebSocketServerFactory.__init__(self,
                                          factory,
                                          serializers = serializers,
                                          url = config.get('url', None),
                                          server = server,
                                          externalPort = externalPort,
                                          debug = self.debug,
                                          debug_wamp = self.debug)

      ## Crossbar.io node directory
      self._cbdir = cbdir

      ## transport configuration
      self._config = config

      ## Jinja2 templates for 404 etc
      self._templates = templates

      ## cookie tracking
      if 'cookie' in config:
         if 'database' in config['cookie'] and _HAS_ADBAPI:
            dbfile = os.path.abspath(os.path.join(self._cbdir, config['cookie']['database']))
            self._cookiestore = PersistentCookieStore(dbfile, config['cookie'])
            log.msg("Persistent cookie store active: {}".format(dbfile))
         else:
            self._cookiestore = CookieStore(config['cookie'])
            log.msg("Transient cookie store active.")
      else:
         self._cookiestore = None

      ## set WebSocket options
      set_websocket_options(self, options)



class CrossbarWampRawSocketServerProtocol(WampRawSocketServerProtocol):

   def connectionMade(self):
      WampRawSocketServerProtocol.connectionMade(self)
      ## transport authentication
      ##
      self._authid = None
      self._authrole = None
      self._authmethod = None



class CrossbarWampRawSocketServerFactory(WampRawSocketServerFactory):

   protocol = CrossbarWampRawSocketServerProtocol

   def __init__(self, factory, config):

      ## transport configuration
      self._config = config

      ## WAMP serializer
      ##
      serid = config.get('serializer', 'msgpack')

      if serid == 'json':
         ## try JSON WAMP serializer
         try:
            from autobahn.wamp.serializer import JsonSerializer
            serializer = JsonSerializer()
         except ImportError:
            raise Exception("could not load WAMP-JSON serializer")

      elif serid == 'msgpack':
         ## try MsgPack WAMP serializer
         try:
            from autobahn.wamp.serializer import MsgPackSerializer
            serializer = MsgPackSerializer()
            serializer._serializer.ENABLE_V5 = False ## FIXME
         except ImportError:
            raise Exception("could not load WAMP-MsgPack serializer")

      else:
         raise Exception("invalid WAMP serializer '{}'".format(serid))

      debug = config.get('debug', False)

      WampRawSocketServerFactory.__init__(self, factory, serializer, debug = debug)




class CrossbarWampRawSocketClientProtocol(WampRawSocketClientProtocol):
   """
   """



class CrossbarWampRawSocketClientFactory(WampRawSocketClientFactory):
   """
   """
   protocol = CrossbarWampRawSocketClientProtocol

   def __init__(self, factory, config):

      ## transport configuration
      self._config = config

      ## WAMP serializer
      ##
      serid = config.get('serializer', 'msgpack')

      if serid == 'json':
         ## try JSON WAMP serializer
         try:
            from autobahn.wamp.serializer import JsonSerializer
            serializer = JsonSerializer()
         except ImportError:
            raise Exception("could not load WAMP-JSON serializer")

      elif serid == 'msgpack':
         ## try MsgPack WAMP serializer
         try:
            from autobahn.wamp.serializer import MsgPackSerializer
            serializer = MsgPackSerializer()
            serializer._serializer.ENABLE_V5 = False ## FIXME
         except ImportError:
            raise Exception("could not load WAMP-MsgPack serializer")

      else:
         raise Exception("invalid WAMP serializer '{}'".format(serid))

      WampRawSocketClientFactory.__init__(self, factory, serializer)




class CrossbarWampWebSocketClientProtocol(WampWebSocketClientProtocol):
   """
   """



class CrossbarWampWebSocketClientFactory(WampWebSocketClientFactory):
   """
   """
   protocol = CrossbarWampWebSocketClientProtocol

   # def __init__(self, factory, config):

   #    ## transport configuration
   #    self._config = config

   #    WampWebSocketClientFactory.__init__(self, config)

   #    self.setProtocolOptions(failByDrop = False)



   def buildProtocol(self, addr):
      self._proto = WampWebSocketClientFactory.buildProtocol(self, addr)
      return self._proto

