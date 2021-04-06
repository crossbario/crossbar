#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from os import getcwd, chdir

from twisted.trial.unittest import TestCase as _TestCase


class TestCase(_TestCase):
    """
    A Trial TestCase that makes sure that it is in the same directory when it
    finishes as when it began. This is because the CLI changes directories,
    meaning we can end up making thousands deep file structures.
    """
    def setUp(self):
        cb_original_dir = getcwd()
        self.addCleanup(lambda: chdir(cb_original_dir))
        return super(TestCase, self).setUp()
