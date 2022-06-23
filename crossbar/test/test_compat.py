#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.trial.unittest import TestCase

from crossbar import _compat as compat


class NativeStringTestCase(TestCase):
    """
    Tests for C{crossbar._compat.native_string}.
    """
    def test_bytes_always_native(self):
        """
        C{native_string}, with a bytes input, will always give a str output.
        """
        self.assertEqual(type(compat.native_string(b"foo")), str)

    def test_unicode_not_allowed(self):
        """
        A unicode argument should never be allowed.
        """
        with self.assertRaises(ValueError):
            compat.native_string("bar")
