import time
import sys
import os

def test_import_1():
    started = time.monotonic_ns()
    import autobahn
    ended = time.monotonic_ns()
    return ended - started

def test_import_2():
    started = time.monotonic_ns()
    from autobahn import xbr
    ended = time.monotonic_ns()
    return ended - started

def test_import_3():
    started = time.monotonic_ns()
    from crossbar import personality as standalone
    ended = time.monotonic_ns()
    return ended - started

def test_import_4():
    started = time.monotonic_ns()
    from crossbar import personality as standalone
    from crossbar import edge
    from crossbar import network
    from crossbar import master
    from crossbar.node.main import main
    ended = time.monotonic_ns()
    return ended - started

def test_import_5():
    started = time.monotonic_ns()
    import zlmdb
    ended = time.monotonic_ns()
    return ended - started

def test_import_6():
    started = time.monotonic_ns()
    import cfxdb
    ended = time.monotonic_ns()
    return ended - started

def test_import_7():
    started = time.monotonic_ns()
    import autobahn
    import cbor2
    import flatbuffers
    import numpy
    import multihash
    import txaio
    import click
    import web3
    import zlmdb
    ended = time.monotonic_ns()
    return ended - started

tests = {
    '1': (test_import_1, 'only autobahn'),
    '2': (test_import_2, 'xbr from autobahn'),
    '3': (test_import_3, 'crossbar oss'),
    '4': (test_import_4, 'crossbar full'),
    '5': (test_import_5, 'only zlmdb'),
    '6': (test_import_6, 'cfxdb'),
    '7': (test_import_7, 'all cfxdb deps'),
}

test = None
if len(sys.argv) > 1:
    test, test_desc = tests.get(sys.argv[1], (None, None))

if test:
    dur = test()
    print('test {} ("{}") ran in {} seconds'.format(sys.argv[1], test_desc, dur / 10**9))
    print()
else:
    for i in range(len(tests)):
        cmd = ' '.join([sys.executable, __file__, str(i + 1)])
        os.system(cmd)
