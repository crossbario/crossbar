###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. All rights reserved.
#
###############################################################################

from crossbarfx.shell.util import localnow


def test_localnow():
    now = localnow()
    assert isinstance(now, str)


class TestClass(object):
    def test_one(self):
        assert True
