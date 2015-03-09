#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

import os
import json

from six.moves import http_cookies

from twisted.python import log


from autobahn import util


class CookieStore:

    """
    A cookie store.
    """

    def __init__(self, config, debug=False):
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

        # see if there already is a cookie set ..
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

        # http://tools.ietf.org/html/rfc6265#page-20
        # 0: delete cookie
        # -1: preserve cookie until browser is closed

        id = util.newid(self._cookie_id_field_length)

        cbtData = {'created': util.utcnow(),
                   'authid': None,
                   'authrole': None,
                   'authmethod': None,
                   'max_age': self._cookie_max_age,
                   'connections': set()}

        self._cookies[id] = cbtData

        # do NOT add the "secure" cookie attribute! "secure" refers to the
        # scheme of the Web page that triggered the WS, not WS itself!!
        #
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

        # remove this WebSocket connection from the set of connections
        # associated with the same cookie
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


class PersistentCookieStore(CookieStore):

    """
    A persistent cookie store.
    """

    def __init__(self, cookie_file_name, config, debug=False):
        CookieStore.__init__(self, config, debug)

        self._cookie_file_name = cookie_file_name

        if not os.path.isfile(self._cookie_file_name):
            log.msg("Cookie store created.")
        else:
            log.msg("Cookie store already exists.")

        self._cookie_file = open(self._cookie_file_name, 'a')

        # initialize cookie database
        self._init_store()

    def _iter_persisted(self):
        with open(self._cookie_file_name, 'r') as f:
            for c in f.readlines():
                d = json.loads(c)

                # we do not persist the connections
                # here make sure the cookie loaded has a
                # default connections key to avoid key errors
                # other keys that aren't persisted should be set here
                d['connections'] = set()

                yield d

    def _persist(self, id, c):

        self._cookie_file.write(json.dumps({
            'id': id, 'created': c['created'], 'max_age': c['max_age'],
            'authid': c['authid'], 'authrole': c['authrole'],
            'authmethod': c['authmethod']
        }) + '\n')

    def _init_store(self):
        n = 0
        for cookie in self._iter_persisted():
            id = cookie.pop('id')
            self._cookies[id] = cookie
            n += 1

        log.msg("Loaded {} cookies into cache.".format(n))

    def create(self):
        id, header = CookieStore.create(self)

        c = self._cookies[id]

        self._persist(id, c)

        if self.debug:
            log.msg("Cookie {} stored".format(id))

        return id, header

    def setAuth(self, id, authid, authrole, authmethod):

        if self.exists(id):

            cookie = self._cookies[id]

            # only set the changes and write them to the file if any of the values changed
            if authid != cookie['authid'] or authrole != cookie['authrole'] or authmethod != cookie['authmethod']:
                CookieStore.setAuth(self, id, authid, authrole, authmethod)
                self._persist(id, cookie)
