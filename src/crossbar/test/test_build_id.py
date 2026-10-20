#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from twisted.trial import unittest

# the source tree root (the script is not part of the installed package)
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "inject-build-id.py"
VERSION_FILE = ROOT / "src" / "crossbar" / "_version.py"

PLACEHOLDER = '__build__ = "19000101-0000000"'


class TestInjectBuildId(unittest.TestCase):
    """
    Tests for stamping the build ID into ``_version.py`` at build time. See issue #2231.
    """

    def setUp(self):
        if not SCRIPT.exists():
            raise unittest.SkipTest("not running from a source tree")
        fd, name = tempfile.mkstemp(suffix="_version.py")
        os.close(fd)
        self.path = Path(name)
        self.addCleanup(self.path.unlink)
        self.path.write_text('__version__ = "26.10.1"\n' + PLACEHOLDER + "\n")

    def _inject(self, build_id=None):
        env = dict(os.environ)
        env.pop("CROSSBAR_BUILD_ID", None)
        if build_id is not None:
            env["CROSSBAR_BUILD_ID"] = build_id
        return subprocess.run([sys.executable, str(SCRIPT), str(self.path)], env=env, capture_output=True, text=True)

    def test_placeholder_in_version_file(self):
        # the placeholder the script replaces must be the one in _version.py
        self.assertEqual(VERSION_FILE.read_text().count(PLACEHOLDER), 1)

    def test_stamps_build_id(self):
        result = self._inject("20261020-abc1234")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.path.read_text(), '__version__ = "26.10.1"\n__build__ = "20261020-abc1234"\n')

    def test_same_build_id_again(self):
        # e.g. `just build` followed by `just build-sourcedist`
        self._inject("20261020-abc1234")
        result = self._inject("20261020-abc1234")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.path.read_text(), '__version__ = "26.10.1"\n__build__ = "20261020-abc1234"\n')

    def test_unset_keeps_placeholder(self):
        before = self.path.read_text()
        result = self._inject()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.path.read_text(), before)

    def test_no_placeholder_fails(self):
        self.path.write_text('__version__ = "26.10.1"\n__build__ = "20261019-1111111"\n')
        before = self.path.read_text()
        result = self._inject("20261020-abc1234")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.path.read_text(), before)

    def test_malformed_build_id_fails(self):
        before = self.path.read_text()
        result = self._inject('20261020-abc1234"; import os')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.path.read_text(), before)
