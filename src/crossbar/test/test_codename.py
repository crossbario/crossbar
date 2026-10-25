#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.trial import unittest

import crossbar
from crossbar._codename import get_codename, get_codename_suffix


class TestCodename(unittest.TestCase):
    """
    Tests for the per-release codename lookup. See issue #2227.
    """

    def test_known_series(self):
        self.assertEqual(get_codename("26.6.1"), "Resistance Is Futile")

    def test_known_series_26_7(self):
        self.assertEqual(get_codename("26.7.1"), "Shields Up")

    def test_known_series_26_10(self):
        self.assertEqual(get_codename("26.10.1"), "Poke The Bear")
        # 26.9 was never released, its codename moved to 26.10 (#2326)
        self.assertIsNone(get_codename("26.9.1"))

    def test_known_series_26_11(self):
        self.assertEqual(get_codename("26.11.1"), "Friendly Positive")

    def test_dev_suffix(self):
        # a .devN suffix on a known year.month series still resolves
        self.assertEqual(get_codename("26.6.1.dev1"), "Resistance Is Futile")

    def test_unknown_series_returns_none(self):
        self.assertIsNone(get_codename("19.1.1"))

    def test_malformed_version_returns_none(self):
        # must never raise, just return None
        self.assertIsNone(get_codename("garbage"))
        self.assertIsNone(get_codename("26"))
        self.assertIsNone(get_codename(""))

    def test_default_version(self):
        # called without an argument, uses crossbar.__version__ and must not raise
        self.assertEqual(get_codename(), get_codename(crossbar.__version__))

    def test_suffix_present(self):
        self.assertEqual(get_codename_suffix("26.6.1"), " — Resistance Is Futile")

    def test_suffix_absent(self):
        self.assertEqual(get_codename_suffix("19.1.1"), "")

    def test_banner_contains_codename(self):
        # the running version is a 26.6.x release, which has a codename, so the
        # startup banner must include it
        from crossbar.personality import Personality

        codename = get_codename(crossbar.__version__)
        if codename is None:
            raise unittest.SkipTest("running version {} has no codename".format(crossbar.__version__))
        self.assertIn(codename, Personality.BANNER)

    def test_release_gate_stable_has_codename(self):
        # release gate: a stable (non-dev) release MUST have a codename assigned
        # in crossbar/_codename.py. Development builds (.devN) are exempt.
        version = crossbar.__version__
        if ".dev" in version:
            raise unittest.SkipTest("development build {}; codename optional".format(version))
        self.assertIsNotNone(
            get_codename(version),
            "stable release {} has no codename - add one to crossbar/_codename.py".format(version),
        )
