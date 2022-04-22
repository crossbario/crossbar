#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import json
import uuid
import datetime
from pprint import pformat
from typing import Optional, Tuple, Dict, Any, List

from http import cookies as http_cookies

import numpy as np

import zlmdb

import txaio
txaio.use_twisted()  # noqa
from txaio import make_logger, time_ns

from autobahn import util
from autobahn.util import hltype, hlval, hlid
# from crossbar.router.protocol import WampWebSocketServerProtocol
from cfxdb import cookiestore

__all__ = (
    'CookieStoreMemoryBacked',
    'CookieStoreFileBacked',
    'CookieStoreDatabaseBacked',
)


class _CookieStore(object):
    """
    Cookie store common base.
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

        # transient sessions per cookie database
        self._connections = {}

        self.log.debug("Cookie stored created with config {config}", config=config)

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
                header_cookie = str(headers['cookie'])
                cookie.load(header_cookie)

                if self._cookie_id_field not in cookie and self._cookie_id_field in header_cookie:
                    # Sometimes Python can't parse cookie. So let's parse it manually.
                    header_cookies_as_array = header_cookie.split(";")
                    if len(header_cookies_as_array) != 0:
                        header_cookie_id_indexes = []
                        for cookie_raw in header_cookies_as_array:
                            if (self._cookie_id_field + "=") in cookie_raw:
                                header_cookie_id_indexes.append(header_cookies_as_array.index(cookie_raw))
                        if len(header_cookie_id_indexes) > 0:
                            cookie.load(header_cookies_as_array[header_cookie_id_indexes[0]])
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

        # cookie tracking data
        cbtData = {
            # UTC timestamp when the cookie was created
            'created': util.utcnow(),

            # maximum lifetime of the tracking/authenticating cookie
            'max_age': self._cookie_max_age,

            # when a cookie has been set, and the WAMP session
            # was successfully authenticated thereafter, the latter
            # auth info is store here
            'authid': None,
            'authrole': None,
            'authrealm': None,
            'authmethod': None,
            'authextra': None,
        }

        self._cookies[cbtid] = cbtData

        # set of WAMP transports (WebSocket connections) this
        # cookie is currently used on
        self._connections[cbtid] = set()

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
        Return `(authid, authrole, authmethod, authrealm, authextra)` tuple given cookie ID.
        """
        if cbtid in self._cookies:
            c = self._cookies[cbtid]
            cookie_auth_info = c['authid'], c['authrole'], c['authmethod'], c['authrealm'], c['authextra']
        else:
            cookie_auth_info = None, None, None, None, None

        self.log.debug("Cookie auth info for {cbtid} retrieved: {cookie_auth_info}",
                       cbtid=cbtid,
                       cookie_auth_info=cookie_auth_info)

        return cookie_auth_info

    def setAuth(self, cbtid, authid, authrole, authmethod, authextra, authrealm):
        """
        Set `(authid, authrole, authmethod, authextra)` for given cookie ID.
        """
        if cbtid in self._cookies:
            c = self._cookies[cbtid]
            c['authid'] = authid
            c['authrole'] = authrole
            c['authrealm'] = authrealm
            c['authmethod'] = authmethod
            c['authextra'] = authextra

    def addProto(self, cbtid: str, proto: 'WampWebSocketServerProtocol') -> int:
        """
        Add given WebSocket connection to the set of connections associated
        with the cookie having the given ID. Return the new count of
        connections associated with the cookie.
        """
        self.log.info('{func} adding proto {proto} for cookie "{cbtid}"', proto=proto, cbtid=hlid(cbtid))
        if self.exists(cbtid):
            if cbtid not in self._connections:
                self._connections[cbtid] = set()
            self._connections[cbtid].add(proto)
            return len(self._connections[cbtid])
        else:
            if cbtid in self._connections:
                del self._connections[cbtid]
            return 0

    def dropProto(self, cbtid: str, proto: 'WampWebSocketServerProtocol'):
        """
        Remove given WebSocket connection from the set of connections associated
        with the cookie having the given ID. Return the new count of
        connections associated with the cookie.
        """
        self.log.info('{func} removing proto {proto} from cookie "{cbtid}"', proto=proto, cbtid=hlid(cbtid))

        if self.exists(cbtid):
            if cbtid in self._connections:
                # remove this WebSocket connection from the set of connections
                # associated with the same cookie
                self._connections[cbtid].discard(proto)
                remaining = len(self._connections[cbtid])
                if remaining:
                    return remaining
                else:
                    del self._connections[cbtid]
        else:
            if cbtid in self._connections:
                del self._connections[cbtid]
        return 0

    def getProtos(self, cbtid: str) -> List['WampWebSocketServerProtocol']:
        """
        Get all WebSocket connections currently associated with the cookie.
        """
        if self.exists(cbtid):
            if cbtid in self._connections:
                return list(self._connections[cbtid])
        return []


class CookieStoreMemoryBacked(_CookieStore):
    """
    Memory-backed cookie store.
    """


class CookieStoreFileBacked(_CookieStore):
    """
    A persistent, file-backed cookie store.

    This cookie store is backed by a file, which is written to in append-only mode.
    Hence, the file is "growing forever". Whenever information attached to a cookie
    is changed (such as a previously anonymous cookie is authenticated), a new cookie
    record is appended. When the store is booting, the file is sequentially scanned.
    The last record for a given cookie ID is remembered in memory.
    """
    def __init__(self, cookie_file_name, config):
        _CookieStore.__init__(self, config)

        self._cookie_file_name = cookie_file_name

        if not os.path.isfile(self._cookie_file_name):
            self.log.debug("File-backed cookie store created")
        else:
            self.log.debug("File-backed cookie store already exists")

        self._cookie_file = open(self._cookie_file_name, 'a')

        # initialize cookie database
        self._init_store()

        if config['store'].get('purge_on_startup', False):
            self._clean_cookie_file()

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

    def _persist(self, id, c, status='created'):

        self._cookie_file.write(
            json.dumps({
                'id': id,
                status: c['created'],
                'max_age': c['max_age'],
                'authid': c['authid'],
                'authrole': c['authrole'],
                'authmethod': c['authmethod'],
                'authrealm': c['authrealm'],
                'authextra': c['authextra'],
            }) + '\n')
        self._cookie_file.flush()
        os.fsync(self._cookie_file.fileno())

    def _init_store(self):
        n = 0
        for cookie in self._iter_persisted():
            id = cookie.pop('id')
            if id not in self._cookies:
                self._cookies[id] = {}
            self._cookies[id].update(cookie)
            n += 1

        self.log.info("Loaded {cnt_cookie_records} cookie records from file. Cookie store has {cnt_cookies} entries.",
                      cnt_cookie_records=n,
                      cnt_cookies=len(self._cookies))

    def create(self):
        cbtid, header = _CookieStore.create(self)

        c = self._cookies[cbtid]

        self._persist(cbtid, c)

        self.log.debug("Cookie {cbtid} stored", cbtid=cbtid)

        return cbtid, header

    def setAuth(self, cbtid, authid, authrole, authmethod, authextra, authrealm):

        if self.exists(cbtid):

            cookie = self._cookies[cbtid]

            # only set the changes and write them to the file if any of the values changed
            if authid != cookie['authid'] or authrole != cookie['authrole'] or authmethod != cookie[
                    'authmethod'] or authrealm != cookie['authrealm'] or authextra != cookie['authextra']:
                _CookieStore.setAuth(self, cbtid, authid, authrole, authmethod, authextra, authrealm)
                self._persist(cbtid, cookie, status='modified')

    def _clean_cookie_file(self):
        with open(self._cookie_file_name, 'w') as cookie_file:
            for cbtid, cookie in self._cookies.items():
                expiration_delta = datetime.timedelta(seconds=int(cookie['max_age']))
                upper_limit = util.utcstr(datetime.datetime.now() - expiration_delta)
                if cookie['created'] < upper_limit:
                    # This cookie is expired, discard
                    continue

                cookie_record = json.dumps({
                    'id': cbtid,
                    'created': cookie['created'],
                    'max_age': cookie['max_age'],
                    'authid': cookie['authid'],
                    'authrole': cookie['authrole'],
                    'authmethod': cookie['authmethod'],
                    'authrealm': cookie['authrealm'],
                    'authextra': cookie['authextra'],
                }) + '\n'
                cookie_file.write(cookie_record)

            cookie_file.flush()
            os.fsync(cookie_file.fileno())


class CookieStoreDatabaseBacked(_CookieStore):
    """
    A persistent, database-backed cookie store. This implementation uses a zLMDB
    based embedded database with Flatbuffers data serialization.
    """
    def __init__(self, dbpath, config):
        self.log.info('{func}: initializing database-backed cookiestore with config=\n{config}',
                      func=hltype(self.__init__),
                      config=pformat(config))
        _CookieStore.__init__(self, config)

        maxsize = config['store'].get('maxsize', 1024 * 2**20)
        assert type(maxsize) == int, "maxsize must be an int, was {}".format(type(maxsize))
        # allow maxsize 128kiB to 128GiB
        assert maxsize >= 128 * 1024 and maxsize <= 128 * 2**30, "maxsize must be >=128kiB and <=128GiB, was {}".format(
            maxsize)

        readonly = config['store'].get('readonly', False)
        assert type(readonly) == bool, "readonly must be a bool, was {}".format(type(readonly))

        sync = config['store'].get('sync', True)
        assert type(sync) == bool, "sync must be a bool, was {}".format(type(sync))

        if config['store'].get('purge_on_startup', False):
            zlmdb.Database.scratch(dbpath)
            self.log.warn('{func}: scratched embedded database (purge_on_startup is enabled)!',
                          func=hltype(self.__init__))

        self._db = zlmdb.Database(dbpath=dbpath, maxsize=maxsize, readonly=readonly, sync=sync)
        # self._db.__enter__()
        self._schema = cookiestore.CookieStoreSchema.attach(self._db)

        dbstats = self._db.stats(include_slots=True)

        self.log.info('{func}: database-backed cookiestore opened from dbpath="{dbpath}" - dbstats=\n{dbstats}',
                      func=hltype(self.__init__),
                      dbpath=hlval(dbpath),
                      dbstats=pformat(dbstats))

    def exists(self, cbtid: str) -> bool:
        with self._db.begin() as txn:
            cookie_exists = self._schema.idx_cookies_by_value[txn, cbtid] is not None
        self.log.info('{func}(cbtid="{cbtid}") -> {cookie_exists}',
                      func=hltype(self.exists),
                      cbtid=hlval(cbtid),
                      cookie_exists=hlval(cookie_exists))
        return cookie_exists

    def create(self) -> Tuple[str, str]:
        cookie = cookiestore.Cookie()
        cookie.oid = uuid.uuid4()
        cookie.created = np.datetime64(time_ns(), 'ns')
        cookie.max_age = self._cookie_max_age
        cookie.name = self._cookie_id_field
        cookie.value = util.newid(self._cookie_id_field_length)

        with self._db.begin(write=True) as txn:
            self._schema.cookies[txn, cookie.oid] = cookie

        self._cookies[cookie.value] = {'connections': set()}

        self.log.info('{func} new cookie {cbtid} stored in database', func=hltype(self.create), cbtid=cookie.value)

        return cookie.value, '%s=%s;max-age=%d' % (cookie.name, cookie.value, cookie.max_age)

    def getAuth(self, cbtid):
        with self._db.begin() as txn:
            cookie_oid = self._schema.idx_cookies_by_value[txn, cbtid]
            if cookie_oid:
                cookie = self._schema.cookies[txn, cookie_oid]
                assert cookie
                cbtid = cookie.value

                # FIXME: cookie.authmethod
                cookie_auth_info = cookie.authid, cookie.authrole, 'cookie', cookie.authrealm, cookie.authextra
            else:
                cbtid = None
                cookie_auth_info = None, None, None, None, None

        if cbtid:
            self.log.info('{func} cookie auth info for "{cbtid}" retrieved: {cookie_auth_info}',
                          func=hltype(self.getAuth),
                          cbtid=hlid(cbtid),
                          cookie_auth_info=cookie_auth_info)
        else:
            self.log.info('{func} no cookie for "{cbtid}" stored in cookiestore database',
                          func=hltype(self.getAuth),
                          cbtid=hlid(cbtid))

        return cookie_auth_info

    def setAuth(self, cbtid: str, authid: Optional[str], authrole: Optional[str], authmethod: Optional[str],
                authextra: Optional[Dict[str, Any]], authrealm: Optional[str]):

        was_existing = False
        was_modified = False
        with self._db.begin(write=True) as txn:
            cookie_oid = self._schema.idx_cookies_by_value[txn, cbtid]
            if cookie_oid:
                cookie = self._schema.cookies[txn, cookie_oid]
                assert cookie
                was_existing = True
                if (authid != cookie.authid or authrole != cookie.authrole or authmethod != cookie.authmethod
                        or authrealm != cookie.authrealm or authextra != cookie.authextra):
                    cookie.authid = authid
                    cookie.authrole = authrole

                    # FIXME
                    # cookie.authmethod = authmethod

                    cookie.authrealm = authrealm
                    cookie.authextra = authextra
                    self._schema.cookies[txn, cookie.oid] = cookie
                    was_modified = True

        if was_existing:
            if was_modified:
                self.log.info(
                    '{func} cookie with cbtid="{cbtid}" exists, and was updated (authid="{authid}", authrole='
                    '"{authrole}", authmethod="{authmethod}", authrealm="{authrealm}", authextra={authextra})',
                    func=hltype(self.setAuth),
                    cbtid=hlid(cbtid),
                    authid=hlval(authid),
                    authrole=hlval(authrole),
                    authmethod=hlval(authmethod),
                    authrealm=hlval(authrealm),
                    authextra=pformat(authextra))
            else:
                self.log.info('{func} cookie with cbtid="{cbtid}" exists, but needs no update',
                              func=hltype(self.setAuth),
                              cbtid=hlid(cbtid))
        else:
            self.log.info('{func} no cookie to modify with cbtid="{cbtid}" exists',
                          func=hltype(self.setAuth),
                          cbtid=hlid(cbtid))

        return was_modified
