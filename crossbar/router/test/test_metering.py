#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
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
import shutil
import random
import unittest


class TestLmdb(unittest.TestCase):

    DBFILE = 'test.dat'

    def _scratch(self):
        if os.path.exists(self.DBFILE):
            if os.path.isdir(self.DBFILE):
                shutil.rmtree(self.DBFILE)
            else:
                os.remove(self.DBFILE)

    def _insert_data1(self, n=10, shuffle=True):
        data = []
        for i in range(n):
            data.append(('key{}'.format(i).encode('utf8'),
                         'data{}'.format(i).encode('utf8')))

        inserted = data[:]
        if shuffle:
            random.shuffle(inserted)

        with self.db.begin(write=True) as txn:
            for d in inserted:
                txn.put(d[0], d[1], db=self.db1)

        return data

    def setUp(self):
        try:
            import lmdb
        except ImportError:
            raise unittest.SkipTest("skipping LMDB tests (LMDB not installed)")

        self._scratch()

        self.db = lmdb.open(self.DBFILE, max_dbs=10)
        self.db1 = self.db.open_db(b'table1', create=True)
        self.addCleanup(self.db.close)
        self.addCleanup(self._scratch)

    def test_insert(self):
        data = self._insert_data1()
        data_inserted = []
        with self.db.begin() as txn:
            cursor = txn.cursor(db=self.db1)
            cursor.first()
            for key, value in cursor:
                data_inserted.append((key, value))

        self.assertEqual(data_inserted, data)

    def test_iterate_from(self):
        data = self._insert_data1()
        data_read = []
        with self.db.begin() as txn:
            cursor = txn.cursor(db=self.db1)

            # Position at first key >= 'key5'
            if cursor.set_range(b'key5'):
                for key, value in cursor:
                    data_read.append((key, value))

        self.assertEqual(data_read, data[5:])
