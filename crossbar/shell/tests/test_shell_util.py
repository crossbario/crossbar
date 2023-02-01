###############################################################################
#
# Crossbar.io Shell
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.shell.util import localnow


def test_localnow():
    now = localnow()
    assert isinstance(now, str)


class TestClass(object):
    def test_one(self):
        assert True
