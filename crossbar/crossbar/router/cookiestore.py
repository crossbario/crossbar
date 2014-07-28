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
import sqlite3
import json

from six.moves import urllib
from six.moves import http_cookies

from twisted.python import log

try:
   from twisted.enterprise import adbapi
   _HAS_ADBAPI = True
except ImportError:
   ## Twisted hasn't ported this to Python 3 yet
   _HAS_ADBAPI = False



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
