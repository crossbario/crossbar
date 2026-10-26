#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import platform
import re
import tomllib
from importlib.metadata import PackageNotFoundError, requires, version
from pathlib import Path

from twisted.trial import unittest

# first versions with the fix for CVE-2026-111497 (brotli decoder out-of-bounds write), see #2379
BROTLI_FIXED = {"brotli": (1, 2, 1), "brotlicffi": (1, 2, 1, 0)}

# autobahn[compress] installs brotli on CPython and brotlicffi on PyPy
BROTLI_BACKEND = "brotli" if platform.python_implementation() == "CPython" else "brotlicffi"

UV_LOCK = Path(__file__).parents[3] / "uv.lock"


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


class TestDependencies(unittest.TestCase):
    """
    Tests for the runtime dependencies crossbar declares in its package metadata.
    """

    def _requirement_names(self):
        # base dependencies only (requirements of optional extras carry an "extra ==" marker)
        reqs = [r for r in requires("crossbar") or [] if "extra ==" not in r]
        return [re.split(r"[\s;<>=!~]", r, maxsplit=1)[0].lower() for r in reqs]

    def test_no_wsaccel(self):
        """
        wsaccel is no longer used: autobahn accelerates WebSocket with its own NVX
        (CFFI), and wsaccel has no CPython 3.14 wheel. See #2372.
        """
        names = [n.split("[")[0] for n in self._requirement_names()]
        self.assertNotIn("wsaccel", names)

    def test_autobahn_all(self):
        """
        crossbar requires autobahn with all its extras, as cfxdb does. See #2372.
        """
        self.assertIn("autobahn[all]", self._requirement_names())

    def test_locked_brotli(self):
        """
        uv.lock pins brotli / brotlicffi versions with the fix for CVE-2026-111497. See #2379.
        """
        if not UV_LOCK.exists():
            raise unittest.SkipTest(f"{UV_LOCK} not found (not a source checkout)")
        with UV_LOCK.open("rb") as f:
            packages = tomllib.load(f)["package"]
        for name, fixed in BROTLI_FIXED.items():
            # a forked resolution can lock a package more than once: check every entry
            locked = [p["version"] for p in packages if p["name"] == name]
            self.assertTrue(locked, f"{name} not in uv.lock")
            for v in locked:
                self.assertGreaterEqual(_vtuple(v), fixed, f"{name} {v} in uv.lock")

    def test_installed_brotli(self):
        """
        The installed brotli (CPython) / brotlicffi (PyPy) has the fix for CVE-2026-111497. See #2379.
        """
        try:
            installed = version(BROTLI_BACKEND)
        except PackageNotFoundError:
            raise unittest.SkipTest(f"{BROTLI_BACKEND} is not installed")
        self.assertGreaterEqual(_vtuple(installed), BROTLI_FIXED[BROTLI_BACKEND], f"{BROTLI_BACKEND} {installed}")
