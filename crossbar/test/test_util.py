##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import copy
import json
import pkg_resources

import pytest

from crossbar._util import merge_config, _deep_merge_object
from crossbar.master import Personality as MasterPersonality


@pytest.fixture(scope='function')
def master_personality():
    return MasterPersonality


@pytest.fixture(scope='function')
def master_config():
    # built-in config
    # filename = pkg_resources.resource_filename('crossbar', 'master/node/config.json')

    # "copied" built-in config for testing
    filename = pkg_resources.resource_filename('crossbar', 'test/test_config.json')

    with open(filename) as f:
        config = json.load(f)
        MasterPersonality.check_config(MasterPersonality, config)
    return config


def test_deep_merge_map1():
    """
    Test merging two empty maps.
    """
    a = {}
    b = {}
    c = _deep_merge_object(a, b)
    assert c == {}


def test_deep_merge_map2():
    """
    Test merging an empty map into a non-empty map.
    """
    a = {'foo': 23}
    b = {}
    c = _deep_merge_object(a, b)
    assert c == a


def test_deep_merge_map3():
    """
    Test merging a non-empty map into an empty map.
    """
    a = {}
    b = {'foo': 23}
    c = _deep_merge_object(a, b)
    assert c == b


def test_deep_merge_map4():
    """
    Test removing a key from a non-empty map.
    """
    a = {'foo': 23}
    b = {'foo': None}
    c = _deep_merge_object(a, b)
    assert c == {}


def test_deep_merge_map5():
    """
    Test removing a non-existent key from a map.
    """
    a = {'foo': 23}
    b = {'bar': None}
    c = _deep_merge_object(a, b)
    assert c == a


def test_deep_merge_map6():
    """
    Test adding a new key to a map.
    """
    a = {'foo': 23}
    b = {'bar': 666}
    c = _deep_merge_object(a, b)
    assert c == {'foo': 23, 'bar': 666}


def test_deep_merge_map7():
    """
    Test "expanding" a nested map with an empty map.
    """
    a = {'foo': 23, 'bar': {'baz': 666}}
    b = {'bar': {}}
    c = _deep_merge_object(a, b)
    assert c == {'foo': 23, 'bar': {'baz': 666}}


def test_deep_merge_map8():
    """
    Test removing an existing key in a nested map.
    """
    a = {'foo': 23, 'bar': {'baz': 666}}
    b = {'bar': {'baz': None}}
    c = _deep_merge_object(a, b)
    assert c == {'foo': 23, 'bar': {}}


def test_deep_merge_map9():
    """
    Test replacing an existing key in a nested map.
    """
    a = {'foo': 23, 'bar': {'baz': 666}}
    b = {'bar': {'baz': 888}}
    c = _deep_merge_object(a, b)
    assert c == {'foo': 23, 'bar': {'baz': 888}}


def test_deep_merge_map10():
    """
    Test expanding a nested map with a new key.
    """
    a = {'foo': 23, 'bar': {'baz': 666}}
    b = {'bar': {'moo': 888}}
    c = _deep_merge_object(a, b)
    assert c == {'foo': 23, 'bar': {'baz': 666, 'moo': 888}}


def test_deep_merge_list1():
    """
    Test merging two empty lists.
    """
    a = []
    b = []
    c = _deep_merge_object(a, b)
    assert c == []


def test_deep_merge_list2():
    """
    Test copying a list.
    """
    a = [1, 2, 3]
    b = ['COPY', 'COPY', 'COPY']
    c = _deep_merge_object(a, b)
    assert c == [1, 2, 3]


def test_deep_merge_list3():
    """
    Test copying a list.
    """
    a = [1, 2, 3]
    b = [None, None, None]
    c = _deep_merge_object(a, b)
    assert c == []


def test_deep_merge_list4():
    """
    Test expanding a list at the tail.
    """
    a = [1, 2, 3]
    b = ['COPY', 'COPY', 'COPY', 4]
    c = _deep_merge_object(a, b)
    assert c == [1, 2, 3, 4]


def test_deep_merge_list5():
    """
    Test replacing a list.
    """
    a = [1, 2, 3]
    b = [None, None, None, 4, 5]
    c = _deep_merge_object(a, b)
    assert c == [4, 5]


def test_deep_merge_list6():
    """
    Test partially dropping items, copying and appending items.
    """
    a = [1, 2, 3]
    b = [None, 'COPY', None, 4]
    c = _deep_merge_object(a, b)
    assert c == [2, 4]


def test_deep_merge_list7():
    """
    Test partially dropping items, copying and appending items.
    """
    a = [1, 2, 3]
    b = [0, None, 'COPY', 4, 5]
    c = _deep_merge_object(a, b)
    assert c == [0, 3, 4, 5]


def test_deep_merge_list8():
    """
    """
    a = [{'foo': 23}, {'bar': 666}, {'baz': 42}]
    b = ['COPY', 'COPY', 'COPY']
    c = _deep_merge_object(a, b)
    assert c == a


def test_deep_merge_list9():
    """
    """
    a = [{'foo': 23}, {'bar': 666}, {'baz': 42}]
    b = ['COPY', None, 'COPY']
    c = _deep_merge_object(a, b)
    assert c == [{'foo': 23}, {'baz': 42}]


def test_deep_merge_list10():
    """
    """
    a = [{'foo': 23}, {'bar': 666}, {'baz': 42}]
    b = [None, 'COPY', 'COPY', {'moo': 99}]
    c = _deep_merge_object(a, b)
    assert c == [{'bar': 666}, {'baz': 42}, {'moo': 99}]


def test_deep_merge_list11():
    """
    """
    a = [{'foo': 23}, {'bar': 666}]
    b = [{'foo': 33}, {'goo': 17}]
    c = _deep_merge_object(a, b)
    assert c == [{'foo': 33}, {'bar': 666, 'goo': 17}]


def test_deep_merge_complex1():
    """
    """
    a = [{'foo': [1, 2, 3]}, {'bar': [{'baz': 666}, [4, 5, 6]]}]
    b = [{'foo': [None, 5, 'COPY', 9]}, {'bar': [{'goo': 777}, 'COPY']}]
    c = _deep_merge_object(a, b)
    assert c == [{'foo': [5, 3, 9]}, {'bar': [{'baz': 666, 'goo': 777}, [4, 5, 6]]}]


def test_merge_empty(master_personality, master_config):
    cfg = merge_config(master_config, {})
    assert cfg == master_config


def test_merge_same(master_personality, master_config):
    same_config = copy.deepcopy(master_config)
    cfg = merge_config(master_config, same_config)

    assert cfg == master_config


def make_test_func(cfg_name):
    def test_merge_config(master_personality, master_config):
        filename = pkg_resources.resource_filename('crossbar', 'tests/test_{}.json'.format(cfg_name))
        with open(filename) as f:
            test_config = json.load(f)

            # a mergeable override-config does NOT need to be valid in itself
            # MasterPersonality.check_config(MasterPersonality, test_config)

        filename = pkg_resources.resource_filename('crossbar', 'tests/test_{}_merged.json'.format(cfg_name))
        with open(filename) as f:
            test_config_merged = json.load(f)
            MasterPersonality.check_config(MasterPersonality, test_config_merged)

        cfg = merge_config(master_config, test_config)

        assert cfg == test_config_merged

    return test_merge_config


current_module = __import__(__name__)

for cfg_name in ['config1', 'config2', 'config3']:
    setattr(current_module, 'test_merge_{}'.format(cfg_name), make_test_func(cfg_name))

if __name__ == '__main__':
    import sys
    sys.setrecursionlimit(10000)

    # this is the base config into the test configs will be merged
    filename = pkg_resources.resource_filename('crossbar', 'tests/test_config.json')
    with open(filename) as f:
        _master_config = json.load(f)

    same_config = copy.deepcopy(_master_config)
    same_config = {
        'controller': {
            'id': 'mynode1',
        },
        'workers': [
            'COPY',
            'COPY',
        ]
    }
    same_config = {
        'controller': {
            'id': 'mynode1',
        }
    }
    cfg = merge_config(_master_config, same_config)
    assert cfg == _master_config
