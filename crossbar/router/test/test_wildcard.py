#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

import unittest

from crossbar.router.wildcard import WildcardMatcher, WildcardTrieMatcher


WILDCARDS = ['.', 'a..c', 'a.b.', 'a..', '.b.', '..', 'x..', '.x.', '..x', 'x..x', 'x.x.', '.x.x', 'x.x.x']

MATCHES = {
    'abc': [],
    'a.b': ['.'],
    'a.b.c': ['a..c', 'a.b.', 'a..', '.b.', '..'],
    'a.x.c': ['a..c', 'a..', '..', '.x.'],
    'a.b.x': ['a.b.', 'a..', '.b.', '..', '..x'],
    'a.x.x': ['a..', '..', '.x.', '..x', '.x.x'],
    'x.y.z': ['..', 'x..'],
    'a.b.c.d': []
}


class AbstractTestMatcher(object):
    def test_setitem(self):
        matcher = self.Matcher()
        for w in WILDCARDS:
            matcher[w] = None

    def test_getitem(self):
        matcher = self.Matcher()
        for i, w in enumerate(WILDCARDS):
            matcher[w] = i
        for i, w in enumerate(WILDCARDS):
            self.assertEqual(matcher[w], i)
        try:
            matcher['NA']
        except Exception as e:
            self.assertTrue(type(e) is KeyError)

    def test_delitem(self):
        matcher = self.Matcher()
        for w in WILDCARDS:
            matcher[w] = None
        for w in WILDCARDS:
            del matcher[w]
        for w in WILDCARDS:
            self.assertFalse(w in matcher)
        try:
            del matcher['NA']
        except Exception as e:
            self.assertTrue(type(e) is KeyError)

    def test_contains(self):
        matcher = self.Matcher()
        for w in WILDCARDS:
            matcher[w] = None
        for w in WILDCARDS:
            self.assertTrue(w in matcher)
        self.assertFalse('NA' in matcher)

    def test_get(self):
        matcher = self.Matcher()
        for i, w in enumerate(WILDCARDS):
            matcher[w] = i
        for i, w in enumerate(WILDCARDS):
            self.assertEqual(matcher.get(w), i)
        self.assertTrue(matcher.get('NA') is None)
        self.assertEqual(matcher.get('NA', ''), '')

    def test_iter_matches(self):
        matcher = self.Matcher()
        for w in WILDCARDS:
            matcher[w] = w
        for uri, excepted in MATCHES.items():
            s = set(matcher.iter_matches(uri))
            self.assertEqual(s, set(excepted))


class TestWildcardMatcher(AbstractTestMatcher, unittest.TestCase):
    Matcher = WildcardMatcher


class TestWildcardTrieMatcher(AbstractTestMatcher, unittest.TestCase):
    Matcher = WildcardTrieMatcher
