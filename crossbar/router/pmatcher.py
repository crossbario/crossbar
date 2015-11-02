import collections


class _Node(dict):
    __slots__ = 'value'
    NULL = object()

    def __init__(self, value=NULL):
        self.value = value

    def _iterate(self, lkey):
        if self.value is not self.NULL:
            yield '.'.join(lkey), self.value
        nlkey = lkey + [None]   # placeholder
        for k, nd in self.items():
            nlkey[-1] = k
            for item in nd._iterate(nlkey):
                yield item

    def _getsize(self):
        current = int(self.value is not self.NULL)
        return current + sum(nd._getsize() for nd in self.values())


class PatternMatcher(collections.MutableMapping):
    def __init__(self, *args, **kwargs):
        self._root = _Node()
        self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        node = self._root
        for sym in key.split('.'):
            node = node.setdefault(sym, _Node())
        node.value = value

    def __getitem__(self, key):
        try:
            node = self._root
            for sym in key.split('.'):
                node = node[sym]
            if node.value is node.NULL:
                raise KeyError
            return node.value
        except KeyError:
            raise KeyError(key)

    def __delitem__(self, key):
        lst = []
        try:
            parent, node = None, self._root
            for k in key.split('.'):
                parent, node = node, node[k]
                lst.append((parent, k, node))
            node.value = node.NULL
        except KeyError:
            raise KeyError(key)
        else:  # cleanup
            for parent, k, node in reversed(lst):
                if node or node.value is not node.NULL:
                    break
                del parent[k]

    def __len__(self):
        return self._root._getsize()

    def keys(self):
        return iter(k for k, v in self._root._iterate([]))

    def values(self):
        return iter(v for k, v in self._root._iterate([]))

    def items(self):
        return iter(self._root._iterate([]))

    __iter__ = keys

    def look_for(self, key, joker=''):
        key = key.split('.')
        key_len = len(key)

        def rec(node, i):
            if i == key_len:
                if node.value is not node.NULL:
                    yield node.value
            else:
                nd = node.get(key[i])
                if nd is not None:
                    for e in rec(nd, i + 1):
                        yield e
                nd = node.get(joker)
                if nd is not None:
                    for e in rec(nd, i + 1):
                        yield e

        return rec(self._root, 0)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, dict(self.items()))
