#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import re
from importlib.metadata import requires

from twisted.trial import unittest


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
