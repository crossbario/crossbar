###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import txaio
txaio.use_twisted()

from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep

# do not directly import fixtures, or session-scoped ones will get run twice.
from ..helpers import *

from autobahn.wamp.exception import ApplicationError


def _test_master_connect(cfx_master):
    assert True


def _test_master_edge1_connect(cfx_master, cfx_edge1):
    assert True


def _test_master_edges_connect(cfx_master, cfx_edge1, cfx_edge2, cfx_edge3):
    assert True


@inlineCallbacks
def test_master_list_mrealms(cfx_master):
    management_session = yield functest_management_session()

    oids = yield management_session.call('crossbarfabriccenter.mrealm.list_mrealms')
    for oid in oids:
        mrealm = yield management_session.call('crossbarfabriccenter.mrealm.get_mrealm', oid)
        print(hl(mrealm, bold=True))

    yield sleep(1)
    yield management_session.leave()


@inlineCallbacks
def test_master_crud_mrealm(cfx_master):
    management_session = yield functest_management_session()

    new_mrealm = {
        'name': 'mrealm1'
    }

    oids = yield management_session.call('crossbarfabriccenter.mrealm.list_mrealms')
    for oid in oids:
        mrealm = yield management_session.call('crossbarfabriccenter.mrealm.get_mrealm', oid)
        if mrealm['name'] == new_mrealm['name']:
            yield management_session.call('crossbarfabriccenter.mrealm.delete_mrealm', oid)
            print(hl('mrealm {} {} deleted!'.format(oid, mrealm['name']), bold=True))
        else:
            print(hl('mrealm {} {} scanned'.format(oid, mrealm['name']), bold=True))

    result = yield management_session.call('crossbarfabriccenter.mrealm.create_mrealm', new_mrealm)
    print(hl(result, bold=True))

    yield management_session.call('crossbarfabriccenter.mrealm.delete_mrealm', result['oid'])
    print(hl('mrealm {} {} deleted!'.format(result['oid'], result['name']), bold=True))

    yield sleep(1)
    yield management_session.leave()


@inlineCallbacks
def test_master_pair_node(cfx_master):
    management_session = yield functest_management_session()

    yield sleep(1)

    new_mrealm = {
        'name': 'mrealm1'
    }

    try:
        result = yield management_session.call('crossbarfabriccenter.mrealm.delete_mrealm_by_name', new_mrealm['name'])
        print(hl(result, bold=True))
    except ApplicationError as e:
        if e.error != 'crossbar.error.no_such_object':
            raise

    yield sleep(1)
    result = yield management_session.call('crossbarfabriccenter.mrealm.create_mrealm', new_mrealm)
    print(hl(result, bold=True))

    nodes = {
        'node1': 'a35a92c77d5cc0d289749a895f91981834a78a2a47c8275081c587d1886f4528',
        'node2': '8ec0d95b623c59d606283c0f698b3e189329433c5f34d46769ee2707ef277d9d',
        'node3': '28d8696911a11399f29576ca10ac38a2d499f1264ccbea36d395184eb3049675',
    }
    yield sleep(1)
    for node_id, pubkey in nodes.items():
        while True:
            try:
                result = yield management_session.call('crossbarfabriccenter.mrealm.pair_node', pubkey, new_mrealm['name'], node_id, {})
                print(hl(result, bold=True))
            except ApplicationError as e:
                if e.error != 'fabric.node-already-paired':
                    raise
                else:
                    result = yield management_session.call('crossbarfabriccenter.mrealm.unpair_node_by_pubkey', pubkey)
                    print(hl(result, bold=True))
            break

    yield sleep(1)
    for pubkey in nodes.values():
        result = yield management_session.call('crossbarfabriccenter.mrealm.unpair_node_by_pubkey', pubkey)
        print(hl(result, bold=True))

    yield sleep(1)
    result = yield management_session.call('crossbarfabriccenter.mrealm.delete_mrealm', result['oid'])
    print(hl(result, bold=True))

    yield sleep(1)
    yield management_session.leave()
