#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.trial import unittest

from crossbar.node.main import _get_versions


class TestVersions(unittest.TestCase):
    """
    Tests for the software version reporting used by ``crossbar version``.
    """

    def test_lmdb_version_reported(self):
        """
        The LMDB version must be reported via the CFFI binding vendored in
        zlmdb (crossbar has no top-level "lmdb" dependency, so a top-level
        ``import lmdb`` is absent on a clean install and left the line blank).
        See #2156.
        """
        # the installed reactor is only read for its class name by _get_versions
        from twisted.internet import reactor

        v = _get_versions(reactor)

        self.assertTrue(v.lmdb_ver, "LMDB version is empty")
        # format is "<binding-version>/lmdb-<C-library-version>"
        self.assertIn("lmdb-", v.lmdb_ver)

    def test_lmdb_engines_reported(self):
        """
        zlmdb bundles two LMDB engines, LMDB 1.0 for new databases and LMDB 0.9 for existing
        databases in LMDB 0.9 format: both must be reported, with the one for new databases
        marked. See #2320.
        """
        from twisted.internet import reactor
        from zlmdb import lmdb

        v = _get_versions(reactor)

        new = ".".join(str(x) for x in lmdb.version(lib_version=1))
        old = ".".join(str(x) for x in lmdb.version(lib_version=0))
        self.assertIn("lmdb-{} (new databases)".format(new), v.lmdb_ver)
        self.assertIn("lmdb-{}".format(old), v.lmdb_ver)

    def test_zlmdb_version_reported(self):
        """
        zlmdb (which vendors the LMDB binding crossbar uses) must also be
        reported.
        """
        from twisted.internet import reactor

        v = _get_versions(reactor)

        self.assertTrue(v.zlmdb_ver, "zlmdb version is empty")

    def test_flatbuffers_versions_reported(self):
        """
        FlatBuffers is vendored in BOTH autobahn (data-in-transit) and zlmdb
        (data-at-rest); crossbar uses both, so `crossbar version` must report
        each so an admin can verify which version is active and that they agree.
        See #2156.
        """
        from twisted.internet import reactor

        v = _get_versions(reactor)

        self.assertTrue(v.flatbuffers_ver, "in-transit FlatBuffers version is empty")
        self.assertIn("autobahn.flatbuffers", v.flatbuffers_ver)

        self.assertTrue(v.flatbuffers_atrest_ver, "at-rest FlatBuffers version is empty")
        self.assertIn("zlmdb.flatbuffers", v.flatbuffers_atrest_ver)
