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


@inlineCallbacks
def test_webcluster_crud(cfx_master, cfx_edge1):

    mrealm = 'mrealm1'

    management_session, _ = yield functest_management_session(realm=mrealm)
    yield sleep(.1)

    node_oids = yield management_session.call('crossbarfabriccenter.mrealm.get_nodes')
    assert node_oids
    print(hl(node_oids, bold=True))
    yield sleep(.1)

    webcluster_oids_initial = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.list_webclusters')
    print(hl(webcluster_oids_initial, bold=True))

    webcluster_config = {
        'name':'my_webcluster_1',
        'tcp_port': 8080,
        'tcp_shared': True,
        'tcp_interface': '127.0.0.1',
        'tcp_backlog': 100,
        'http_display_tracebacks': True,
    }
    webcluster_created = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.create_webcluster', webcluster_config)
    print(hl(webcluster_created, bold=True))
    yield sleep(.1)

    webcluster_oids = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.list_webclusters')
    print(hl(webcluster_oids, bold=True))
    assert len(webcluster_oids) == len(webcluster_oids_initial) + 1

    path = 'info'
    webservice1 = {
        'type': 'nodeinfo',
    }
    webcluster_service1_added = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.add_webcluster_service', webcluster_created['oid'], path, webservice1)
    print(hl(webcluster_service1_added, bold=True))

    path = 'temp'
    webservice2 = {
        'type': 'static',
        'directory': '/tmp',
        'options': {
            'enable_directory_listing': True
        }
    }
    webcluster_service2_added = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.add_webcluster_service', webcluster_created['oid'], path, webservice2)
    print(hl(webcluster_service2_added, bold=True))

    # FIXME
    if False:
        webcluster_service2_deleted = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.remove_webcluster_service', webcluster_created['oid'], webcluster_service2_added['oid'])
        print(hl(webcluster_service2_deleted, bold=True))

        webcluster_service1_deleted = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.remove_webcluster_service', webcluster_created['oid'], webcluster_service1_added['oid'])
        print(hl(webcluster_service1_deleted, bold=True))

        yield sleep(.1)

    # FIXME
    if False:
        for node_id in node_oids:
            webcluster_node_added = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.add_webcluster_node', webcluster_created['oid'], node_id)
            print(hl(webcluster_node_added, bold=True))
        yield sleep(.1)

        for node_id in node_oids:
            webcluster_node_removed = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.remove_webcluster_node', webcluster_created['oid'], node_id)
            print(hl(webcluster_node_removed, bold=True))
        yield sleep(.1)

    webcluster_deleted = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.delete_webcluster', webcluster_created['oid'])
    print(hl(webcluster_deleted, bold=True))

    webcluster_oids = yield management_session.call('crossbarfabriccenter.mrealm.webcluster.list_webclusters')
    print(hl(webcluster_oids, bold=True))
    assert len(webcluster_oids) == len(webcluster_oids_initial)

    yield management_session.leave()
