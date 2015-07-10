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

from autobahn import util

from crossbar._logging import make_logger

__all__ = (
    'CookieStore',
    'PersistentCookieStore',
)


class CookieStore:
    """
    A transient cookie store.
    """

    log = make_logger()

    def __init__(self, config):
        """
        Ctor.

        :param config: The cookie configuration.
        :type config: dict
        """
        self._config = config

        # name of the HTTP cookie in use
        self._cookie_id_field = config.get('name', 'cbtid')

        # length of the cookie (random) ID value
        self._cookie_id_field_length = int(config.get('length', 24))

        # lifetime of the cookie in seconds (http://tools.ietf.org/html/rfc6265#page-20)
        self._cookie_max_age = int(config.get('max_age', 86400 * 7))

        # transient cookie database
        self._cookies = {}

        self.log.info("Transient cookie stored created with config {config}", config=config)

    def parse(self, headers):
        """
        Parse HTTP header for cookie. If cookie is found, return cookie ID,
        else return None.
        """
        self.log.debug("Parsing cookie from {headers}", headers=headers)

        # see if there already is a cookie set ..
        if 'cookie' in headers:
            try:
                cookie = http_cookies.SimpleCookie()
                cookie.load(str(headers['cookie']))
            except http_cookies.CookieError:
                pass
            else:
                if self._cookie_id_field in cookie:
                    cbtid = cookie[self._cookie_id_field].value
                    if cbtid in self._cookies:
                        return cbtid
        return None

    def create(self):
        """
        Create a new cookie, returning the cookie ID and cookie header value.
        """
        # http://tools.ietf.org/html/rfc6265#page-20
        # 0: delete cookie
        # -1: preserve cookie until browser is closed

        cbtid = util.newid(self._cookie_id_field_length)

        cbtData = {'created': util.utcnow(),
                   'authid': None,
                   'authrole': None,
                   'authmethod': None,
                   'max_age': self._cookie_max_age,
                   'connections': set()}

        self._cookies[cbtid] = cbtData

        self.log.debug("New cookie {cbtid} created", cbtid=cbtid)

        # do NOT add the "secure" cookie attribute! "secure" refers to the
        # scheme of the Web page that triggered the WS, not WS itself!!
        #
        return cbtid, '%s=%s;max-age=%d' % (self._cookie_id_field, cbtid, cbtData['max_age'])

    def exists(self, cbtid):
        """
        Check if cookie with given ID exists.
        """
        cookie_exists = cbtid in self._cookies
        self.log.debug("Cookie {cbtid} exists = {cookie_exists}", cbtid=cbtid, cookie_exists=cookie_exists)
        return cookie_exists

    def getAuth(self, cbtid):
        """
        Return `(authid, authrole, authmethod)` triple given cookie ID.
        """
        if cbtid in self._cookies:
            c = self._cookies[cbtid]
            cookie_auth_info = c['authid'], c['authrole'], c['authmethod']
        else:
            cookie_auth_info = None, None, None

        self.log.debug("Cookie auth info for {cbtid} retrieved: {cookie_auth_info}", cbtid=cbtid, cookie_auth_info=cookie_auth_info)

        return cookie_auth_info

    def setAuth(self, cbtid, authid, authrole, authmethod):
        """
        Set `(authid, authrole, authmethod)` triple for given cookie ID.
        """
        if cbtid in self._cookies:
            c = self._cookies[cbtid]
            c['authid'] = authid
            c['authrole'] = authrole
            c['authmethod'] = authmethod

    def addProto(self, cbtid, proto):
        """
        Add given WebSocket connection to the set of connections associated
        with the cookie having the given ID. Return the new count of
        connections associated with the cookie.
        """
        self.log.debug("Adding proto {proto} to cookie {cbtid}", proto=proto, cbtid=cbtid)

        if cbtid in self._cookies:
            self._cookies[cbtid]['connections'].add(proto)
            return len(self._cookies[cbtid]['connections'])
        else:
            return 0

    def dropProto(self, cbtid, proto):
        """
        Remove given WebSocket connection from the set of connections associated
        with the cookie having the given ID. Return the new count of
        connections associated with the cookie.
        """
        self.log.debug("Removing proto {proto} from cookie {cbtid}", proto=proto, cbtid=cbtid)

        # remove this WebSocket connection from the set of connections
        # associated with the same cookie
        if cbtid in self._cookies:
            self._cookies[cbtid]['connections'].discard(proto)
            return len(self._cookies[cbtid]['connections'])
        else:
            return 0

    def getProtos(self, cbtid):
        """
        Get all WebSocket connections currently associated with the cookie.
        """
        if cbtid in self._cookies:
            return self._cookies[cbtid]['connections']
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
            self.log.info("File for file-based cookie store created")
        else:
            self.log.info("File for file-based cookie store already exists")

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

        self.log.info("Loaded {cnt_cookies} from file-based cookie store", cnt_cookies=n)

    def create(self):
        cbtid, header = CookieStore.create(self)

        c = self._cookies[cbtid]

        self._persist(cbtid, c)

        self.log.debug("Cookie {cbtid} stored", cbtid=cbtid)

        return cbtid, header

    def setAuth(self, cbtid, authid, authrole, authmethod):

        if self.exists(cbtid):

            cookie = self._cookies[cbtid]

            # only set the changes and write them to the file if any of the values changed
            if authid != cookie['authid'] or authrole != cookie['authrole'] or authmethod != cookie['authmethod']:
                CookieStore.setAuth(self, cbtid, authid, authrole, authmethod)
                self._persist(cbtid, cookie)
