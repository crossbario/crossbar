
import unittest

from crossbar.router.wildcard import WildcardMatcher, WildcardTrieMatcher

wildcards = ['a..c', 'a.b.', 'a..']
matches = {
    'a': [],
    'a.b': [],
    'a.b.c': ['a..c', 'a.b.', 'a..'],
    'a.x.c': ['a..c', 'a..'],
    'a.b.x': ['a.b.', 'a..'], 
    'a.x.x': ['a..']
}

class TestWildcardMatcher(unittest.TestCase):
    def test_add(self):
        matcher = WildcardMatcher()
        for w in wildcards:
            matcher[w] = None
        for w in wildcards:
            self.assertTrue(w in matcher)
    
    def test_del(self):
        matcher = WildcardMatcher()
        for w in wildcards:
            matcher[w] = None
        for w in wildcards:
            del matcher[w]
        for w in wildcards:
            self.assertTrue(w not in matcher)

    def test_get(self):
        matcher = WildcardMatcher()
        for i, w in enumerate(wildcards):
            matcher[w] = i
        for i, w in enumerate(wildcards):
            self.assertTrue(matcher.get(w) == i)
        self.assertTrue(matcher.get('NA') == None)

    def test_iter_matches(self):
        matcher = WildcardMatcher()
        for w in wildcards:
            matcher[w] = w
        for uri, excepted in matches.items():
            s = set(matcher.iter_matches(uri))
            self.assertTrue(s == set(excepted))


class TestWildcardTrieMatcher(unittest.TestCase):
    def test_add(self):
        matcher = WildcardTrieMatcher()
        for w in wildcards:
            matcher[w] = None
        for i, w in enumerate(wildcards):
            self.assertTrue(matcher.get(w) == i)

    def test_get(self):
        matcher = WildcardTrieMatcher()
        for i, w in enumerate(wildcards):
            matcher[w] = i
        for i, w in enumerate(wildcards):
            self.assertTrue(matcher.get(w) == i)
        self.assertTrue(matcher.get('NA') == None)

    def test_iter_matches(self):
        matcher = WildcardTrieMatcher()
        for w in wildcards:
            matcher[w] = w
        for uri, excepted in matches.items():
            s = set(matcher.iter_matches(uri))
            self.assertTrue(s == set(excepted))