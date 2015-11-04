
import unittest

from crossbar.router.wildcard import WildcardMatcher, WildcardTrieMatcher

WILDCARDS = ['.', 'a..c', 'a.b.', 'a..', '.b.', 
            '..', 'x..', '.x.', '..x', 'x..x', 'x.x.', '.x.x', 'x.x.x']
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


class TestWildcardMatcher(unittest.TestCase):
    def test_setitem(self):
        matcher = WildcardMatcher()
        for w in WILDCARDS:
            matcher[w] = None
        self.assertTrue(True)

    def test_getitem(self):
        matcher = WildcardMatcher()
        for i, w in enumerate(WILDCARDS):
            matcher[w] = i
        for i, w in enumerate(WILDCARDS):
            self.assertEqual(matcher[w], i)
        try:
            matcher['NA']
        except Exception as e:
            self.assertTrue(type(e) is KeyError)

    def test_delitem(self):
        matcher = WildcardMatcher()
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
        matcher = WildcardMatcher()
        for w in WILDCARDS:
            matcher[w] = None
        for w in WILDCARDS:
            self.assertTrue(w in matcher)
        self.assertFalse('NA' in matcher)

    def test_get(self):
        matcher = WildcardMatcher()
        for i, w in enumerate(WILDCARDS):
            matcher[w] = i
        for i, w in enumerate(WILDCARDS):
            self.assertEqual(matcher.get(w), i)
        self.assertTrue(matcher.get('NA') is None)
        self.assertEqual(matcher.get('NA', ''), '')

    def test_iter_matches(self):
        matcher = WildcardMatcher()
        for w in WILDCARDS:
            matcher[w] = w
        for uri, excepted in MATCHES.items():
            s = set(matcher.iter_matches(uri))
            self.assertEqual(s, set(excepted))


class TestWildcardTrieMatcher(unittest.TestCase):
    def test_setitem(self):
        matcher = WildcardTrieMatcher()
        for w in WILDCARDS:
            matcher[w] = None
        self.assertTrue(True)

    def test_getitem(self):
        matcher = WildcardTrieMatcher()
        for i, w in enumerate(WILDCARDS):
            matcher[w] = i
        for i, w in enumerate(WILDCARDS):
            self.assertEqual(matcher[w], i)
        try:
            matcher['NA']
        except Exception as e:
            self.assertTrue(type(e) is KeyError)

    def test_delitem(self):
        matcher = WildcardTrieMatcher()
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
        matcher = WildcardTrieMatcher()
        for w in WILDCARDS:
            matcher[w] = None
        for w in WILDCARDS:
            self.assertTrue(w in matcher)
        self.assertFalse('NA' in matcher)

    def test_get(self):
        matcher = WildcardTrieMatcher()
        for i, w in enumerate(WILDCARDS):
            matcher[w] = i
        for i, w in enumerate(WILDCARDS):
            self.assertEqual(matcher.get(w), i)
        self.assertTrue(matcher.get('NA') is None)
        self.assertEqual(matcher.get('NA', ''), '')

    def test_iter_matches(self):
        matcher = WildcardTrieMatcher()
        for w in WILDCARDS:
            matcher[w] = w
        for uri, excepted in MATCHES.items():
            s = set(matcher.iter_matches(uri))
            self.assertEqual(s, set(excepted))
