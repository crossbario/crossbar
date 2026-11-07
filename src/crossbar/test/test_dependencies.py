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

# Security floors on dependencies crossbar declares directly, see #2388: the first release
# with the fix for the advisories listed against the previous lock (PyPI vulnerability
# data, 2026-11-07). crossbar must declare at least this floor (on every requirement line
# of the package, e.g. per-platform twisted), uv.lock must pin at least this version, and
# an installed version must be at least this version.
SECURITY_FLOORS_DIRECT = {
    # 7 advisories, among them HTTP/2 Rapid Reset (CVE-2023-44487) and header-value
    # request smuggling (CVE-2026-115877)
    "twisted": (26, 10, 0),
    # GHSA-2gqc: WebSocket opening handshake header smuggling, see #2379
    "autobahn": (26, 11, 1),
    # PKCS#7 Bleichenbacher oracle fixed in 50.0.0 (same floor as autobahn)
    "cryptography": (50, 0, 0),
    # CVE-2025-57804 (HTTP/2 request splitting, fixed in 4.3.0), CVE-2026-71554 (4.4.1)
    "h2": (4, 4, 1),
    # CVE-2024-3651, CVE-2026-45409 (DoS in idna.encode(), complete fix in 3.15)
    "idna": (3, 15),
    # 9 DoS advisories in the BER/CER/DER decoders
    "pyasn1": (0, 6, 5),
    # CVE-2026-32874, CVE-2026-32875, CVE-2026-44660, CVE-2026-54911
    "ujson": (5, 13, 0),
    # 3 safe_join advisories (Windows device names)
    "werkzeug": (3, 1, 9),
    # CVE-2026-27205
    "flask": (3, 1, 3),
    # CVE-2026-25645
    "requests": (2, 33, 0),
    # CVE-2025-69277 (libsodium)
    "pynacl": (1, 6, 2),
    # CVE-2026-4539
    "pygments": (2, 20, 0),
    # 11 advisories (CPU exhaustion, include directive)
    "mistune": (3, 3, 0),
}

# Security floors on dependencies crossbar gets only transitively, see #2388: crossbar
# does not declare these (it does not import them), but uv.lock must pin at least this.
SECURITY_FLOORS_TRANSITIVE = {
    # CVE-2026-59980 (via h2)
    "hpack": (4, 2, 0),
    # CVE-2026-57585, CVE-2026-114613 (via autobahn)
    "msgpack": (1, 2, 3),
    # CVE-2026-33936 (via autobahn, xbr)
    "ecdsa": (0, 19, 2),
    # GHSA-6q48-6c7w-9gw2 (via requests)
    "certifi": (2026, 10, 18),
}

UV_LOCK = Path(__file__).parents[3] / "uv.lock"


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


class TestDependencies(unittest.TestCase):
    """
    Tests for the runtime dependencies crossbar declares in its package metadata.
    """

    def _requirements(self):
        # base dependencies only (requirements of optional extras carry an "extra ==" marker)
        return [r for r in requires("crossbar") or [] if "extra ==" not in r]

    def _locked_packages(self):
        if not UV_LOCK.exists():
            raise unittest.SkipTest(f"{UV_LOCK} not found (not a source checkout)")
        with UV_LOCK.open("rb") as f:
            return tomllib.load(f)["package"]

    def _requirement_names(self):
        return [re.split(r"[\s;<>=!~]", r, maxsplit=1)[0].lower() for r in self._requirements()]

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
        packages = self._locked_packages()
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

    def test_declared_security_floors(self):
        """
        crossbar declares a floor at or above the first fixed release for each direct
        dependency with a known advisory. See #2388.
        """
        reqs = self._requirements()
        for name, fixed in SECURITY_FLOORS_DIRECT.items():
            lines = [r for r in reqs if re.split(r"[\s\[;<>=!~]", r, maxsplit=1)[0].lower() == name]
            self.assertTrue(lines, f"{name} not declared")
            for line in lines:
                spec = line.split(";", 1)[0]
                floors = [_vtuple(v) for v in re.findall(r">=\s*([0-9][0-9.]*)", spec)]
                self.assertTrue(floors and max(floors) >= fixed, f"{line!r} allows versions below {fixed}")

    def test_locked_security_floors(self):
        """
        uv.lock pins versions at or above the first fixed release for every dependency
        with a known advisory, direct or transitive. See #2388.
        """
        packages = self._locked_packages()
        for name, fixed in {**SECURITY_FLOORS_DIRECT, **SECURITY_FLOORS_TRANSITIVE}.items():
            # a forked resolution can lock a package more than once: check every entry
            locked = [p["version"] for p in packages if p["name"] == name]
            self.assertTrue(locked, f"{name} not in uv.lock")
            for v in locked:
                self.assertGreaterEqual(_vtuple(v), fixed, f"{name} {v} in uv.lock")

    def test_installed_security_floors(self):
        """
        The installed dependencies are at or above the first fixed release. See #2388.
        """
        for name, fixed in {**SECURITY_FLOORS_DIRECT, **SECURITY_FLOORS_TRANSITIVE}.items():
            try:
                installed = version(name)
            except PackageNotFoundError:
                # e.g. a dependency only installed on some platforms or implementations
                continue
            self.assertGreaterEqual(_vtuple(installed), fixed, f"{name} {installed} installed")
