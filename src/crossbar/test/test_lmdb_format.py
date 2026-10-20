#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
from unittest import mock

import zlmdb
from twisted.trial import unittest
from zlmdb import lmdb

from crossbar.edge.worker.realmstore import RealmStoreDatabase
from crossbar.router.cookiestore import CookieStoreDatabaseBacked

# LMDB engine versions bundled in zlmdb, by LMDB format
_ENGINES = {
    "1.0": ".".join(str(x) for x in lmdb.version(lib_version=1)),
    "0.9": ".".join(str(x) for x in lmdb.version(lib_version=0)),
}


def _info_kwargs(log, marker):
    """
    Keyword arguments of the (first) log.info() call whose format string contains marker.
    """
    for call in log.info.call_args_list:
        if marker in call.args[0]:
            return call.kwargs
    raise AssertionError("no log.info() call containing {!r}".format(marker))


class _LmdbFormatTestCase(unittest.TestCase):
    def setUp(self):
        self.dbpath = os.path.abspath(self.mktemp())

    def _create_existing(self, lib_version):
        """
        Create an (empty) database in the given LMDB format at self.dbpath, and close it.
        """
        db = zlmdb.Database(dbpath=self.dbpath, lib_version=lib_version)
        db.__exit__(None, None, None)

    def _close(self, db):
        self.addCleanup(db.__exit__, None, None, None)


class RealmStoreLmdbFormatTests(_LmdbFormatTestCase):
    """
    The database-backed realm store logs the LMDB format of its database and the LMDB engine servicing
    it (#2320).
    """

    def _open(self):
        with mock.patch.object(RealmStoreDatabase, "log") as log:
            store = RealmStoreDatabase(None, None, {"type": "cfxdb", "path": self.dbpath})
        self._close(store._db)
        return _info_kwargs(log, "realm store initialized")

    def test_new_database(self):
        kwargs = self._open()
        self.assertEqual(kwargs["lmdb_format"], "1.0")
        self.assertEqual(kwargs["lmdb_version"], _ENGINES["1.0"])

    def test_existing_database_lmdb09(self):
        self._create_existing("0.9")
        kwargs = self._open()
        self.assertEqual(kwargs["lmdb_format"], "0.9")
        self.assertEqual(kwargs["lmdb_version"], _ENGINES["0.9"])


class CookieStoreLmdbFormatTests(_LmdbFormatTestCase):
    """
    The database-backed cookie store logs the LMDB format of its database and the LMDB engine servicing
    it (#2320).
    """

    def _open(self):
        with mock.patch.object(CookieStoreDatabaseBacked, "log") as log:
            store = CookieStoreDatabaseBacked(self.dbpath, {"store": {"type": "database", "path": self.dbpath}})
        self._close(store._db)
        return _info_kwargs(log, "database-backed cookiestore opened")

    def test_new_database(self):
        kwargs = self._open()
        self.assertEqual(kwargs["lmdb_format"], "1.0")
        self.assertEqual(kwargs["lmdb_version"], _ENGINES["1.0"])

    def test_existing_database_lmdb09(self):
        self._create_existing("0.9")
        kwargs = self._open()
        self.assertEqual(kwargs["lmdb_format"], "0.9")
        self.assertEqual(kwargs["lmdb_version"], _ENGINES["0.9"])
