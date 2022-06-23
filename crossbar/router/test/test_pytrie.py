#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.trial import unittest

from pytrie import StringTrie


class TestPyTrie(unittest.TestCase):
    def test_empty_tree(self):
        """
        Test trie ctor, and that is doesn't match on "any" prefix.
        """
        t = StringTrie()
        for key in ['', 'f', 'foo', 'foobar']:
            with self.assertRaises(KeyError):
                t.longest_prefix_value(key)

    def test_contains(self):
        """
        Test the contains operator.
        """
        t = StringTrie()
        test_keys = ['', 'f', 'foo', 'foobar', 'baz']
        for key in test_keys:
            t[key] = key
        for key in test_keys:
            self.assertTrue(key in t)
        for key in ['x', 'fb', 'foob', 'fooba', 'bazz']:
            self.assertFalse(key in t)

    def test_longest_prefix_1(self):
        """
        Test that keys are detected as prefix of themselfes.
        """
        t = StringTrie()
        test_keys = ['f', 'foo', 'foobar', 'baz']
        for key in test_keys:
            t[key] = key
        for key in test_keys:
            self.assertEqual(t.longest_prefix_value(key), key)

    def test_longest_prefix_2(self):
        """
        Test matching prefix lookups.
        """
        t = StringTrie()
        test_keys = ['f', 'foo', 'foobar']
        for key in test_keys:
            t[key] = key

        test_keys = {
            'foobarbaz': 'foobar',
            'foobaz': 'foo',
            'fool': 'foo',
            'foo': 'foo',
            'fob': 'f',
            'fo': 'f',
            'fx': 'f',
            'f': 'f',
        }
        for key in test_keys:
            self.assertEqual(t.longest_prefix_value(key), test_keys[key])

    def test_longest_prefix_3(self):
        """
        Test non-matching prefix lookups.
        """
        t = StringTrie()

        for key in ['x', 'fop', 'foobar']:
            t[key] = key

        for key in ['y', 'yfoo', 'fox', 'fooba']:
            with self.assertRaises(KeyError):
                t.longest_prefix_value(key)

    def test_longest_prefix_4(self):
        """
        Test that a trie with an empty string as a key contained
        matches a non-empty prefix matching lookup.
        """
        self.skip = True
        # stored_key = 'x'  # this works (and of course it should!)
        stored_key = ''  # this blows up! (and it _should_ work)
        test_key = 'xyz'

        t = StringTrie()
        t[stored_key] = stored_key
        self.assertTrue(stored_key in t)
        self.assertTrue(test_key.startswith(stored_key))
        self.assertEqual(t.longest_prefix_value(test_key), stored_key)

    # pytrie behavior is broken wrt to string keys of zero length!
    # See: https://bitbucket.org/gsakkis/pytrie/issues/4/string-keys-of-zero-length-are-not
    # We have a workaround in place for this at the relevant places.
    test_longest_prefix_4.skip = True
