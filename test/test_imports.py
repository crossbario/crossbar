import time
import sys
import os

def test_import_0():
    started = time.monotonic_ns()
    from crossbar import personality as standalone
    ended = time.monotonic_ns()
    return ended - started

def test_import_1():
    started = time.monotonic_ns()
    from crossbar import personality as standalone
    from crossbar import edge
    from crossbar import network
    from crossbar import master
    from crossbar.node.main import main
    ended = time.monotonic_ns()
    return ended - started

def test_import_2():
    started = time.monotonic_ns()
    import cfxdb
    ended = time.monotonic_ns()
    return ended - started

def test_import_3():
    started = time.monotonic_ns()
    import autobahn
    import cbor
    import flatbuffers
    import numpy
    import multihash
    import txaio
    import click
    import web3
    import zlmdb
    ended = time.monotonic_ns()
    return ended - started

def test_import_4():
    started = time.monotonic_ns()
    import autobahn
    ended = time.monotonic_ns()
    return ended - started

def test_import_5():
    started = time.monotonic_ns()
    import zlmdb
    ended = time.monotonic_ns()
    return ended - started

tests = {
    '0': (test_import_0, 'crossbar oss'),
    '1': (test_import_1, 'crossbar full'),
    '2': (test_import_2, 'cfxdb'),
    '3': (test_import_3, 'all cfxdb deps'),
    '4': (test_import_4, 'only autobahn'),
    '5': (test_import_5, 'only zlmdb'),
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
        cmd = ' '.join([sys.executable, __file__, str(i)])
        os.system(cmd)
