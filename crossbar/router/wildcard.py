#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

__all__ = ('WildcardMatcher', 'WildcardTrieMatcher')


class _Node(dict):

    __slots__ = 'value',


class WildcardTrieMatcher(object):
    def __init__(self):
        self._root = _Node()
        self._values = set()

    def __setitem__(self, key, value):
        node = self._root
        for sym in key.split('.'):
            node = node.setdefault(sym, _Node())
        node.value = value
        self._values.add(value)

    def __getitem__(self, key):
        node = self._root
        try:
            for sym in key.split('.'):
                node = node[sym]
            return node.value
        except (KeyError, AttributeError):
            raise KeyError(key)

    def __delitem__(self, key):
        lst = []
        node = self._root
        try:
            for k in key.split('.'):
                lst.append((node, k))
                node = node[k]
            self._values.discard(node.value)
            del node.value
        except (KeyError, AttributeError):
            raise KeyError(key)
        else:
            for parent, k in reversed(lst):
                if node or hasattr(node, 'value'):
                    break
                del parent[k]
                node = parent

    def __contains__(self, key):
        try:
            self[key]
            return True
        except KeyError:
            return False

    def values(self):
        return list(self._values)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def iter_matches(self, key):
        key = key.split('.')
        key_len = len(key)

        def rec(node, i):
            if i == key_len:
                if hasattr(node, 'value'):
                    yield node.value
            else:
                nd = node.get(key[i])
                if nd is not None:
                    for e in rec(nd, i + 1):
                        yield e
                nd = node.get('')  # wildcard
                if nd is not None:
                    for e in rec(nd, i + 1):
                        yield e

        return rec(self._root, 0)


class WildcardMatcher(object):
    def __init__(self):
        self._wildcard = {}
        self._wildcard_patterns = {}

    def __setitem__(self, key, value):
        self._wildcard[key] = value

        pattern = tuple([part == "" for part in key.split('.')])
        pattern_len = len(pattern)

        # setup map: pattern length -> patterns
        if pattern_len not in self._wildcard_patterns:
            self._wildcard_patterns[pattern_len] = {}

        # setup map: (pattern length, pattern) -> pattern count
        if pattern not in self._wildcard_patterns[pattern_len]:
            self._wildcard_patterns[pattern_len][pattern] = 1
        else:
            self._wildcard_patterns[pattern_len][pattern] += 1

    def __delitem__(self, key):
        # remove actual observation
        del self._wildcard[key]

        pattern = tuple([part == "" for part in key.split('.')])
        pattern_len = len(pattern)

        # cleanup if this was the last observation with given pattern
        self._wildcard_patterns[pattern_len][pattern] -= 1
        if not self._wildcard_patterns[pattern_len][pattern]:
            del self._wildcard_patterns[pattern_len][pattern]

        # cleanup if this was the last observation with given pattern length
        if not self._wildcard_patterns[pattern_len]:
            del self._wildcard_patterns[pattern_len]

    def __getitem__(self, key):
        return self._wildcard[key]

    def __contains__(self, key):
        return key in self._wildcard

    def values(self):
        return self._wildcard.values()

    def get(self, key, default=None):
        return self._wildcard.get(key, default)

    def iter_matches(self, key):
        parts = key.split('.')
        pattern_len = len(parts)
        if pattern_len in self._wildcard_patterns:
            for pattern in self._wildcard_patterns[pattern_len]:
                patterned = '.'.join(['' if pattern[i] else parts[i] for i in range(pattern_len)])
                if patterned in self._wildcard:
                    yield self._wildcard[patterned]
