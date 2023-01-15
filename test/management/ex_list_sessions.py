# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import pprint

from crossbar.shell import client

GET_NODES = u'crossbarfabriccenter.mrealm.get_nodes'

GET_WORKERS = u'crossbarfabriccenter.remote.node.get_workers'
GET_WORKER = u'crossbarfabriccenter.remote.node.get_worker'
GET_ROUTER_REALMS = u'crossbarfabriccenter.remote.router.get_router_realms'

# the following requires options.bridge_meta_api=true in the options
# of the Crossbar.io router realm called into. it might also require elevated
# rights on CFC for authorization on the URIs
#
# these URIs access the WAMP meta API within Crossbar.io router realms and behave
# exactly the same as a WAMP client locally attached to the respective app router
# would see.
#

WAMP = u'crossbarfabriccenter.remote.realm.meta.{}'

GET_SESSIONS = WAMP.format(u'wamp.session.list')
GET_SESSION = WAMP.format(u'wamp.session.get')


async def main(session):
    """
    Iterate over all nodes, and all (router) workers on each node, all realms
    on each router, list of sessions on each, and then retrieve session detail info.
    """
    nodes = await session.call(GET_NODES, status=u'online')
    for node_id in nodes:
        workers = await session.call(GET_WORKERS, node_id)
        for worker_id in workers:
            worker = await session.call(GET_WORKER, node_id, worker_id)
            if worker[u'type'] == u'router':
                realms = await session.call(GET_ROUTER_REALMS, node_id,
                                            worker_id)
                for realm in realms:
                    sessions = await session.call(GET_SESSIONS, node_id,
                                                  worker_id, realm)
                    print(
                        'node "{}" / router "{}" / realm "{}" has currently {} sessions connected: {}'.
                        format(realm, node_id, worker_id, len(sessions),
                               sessions))
                    for session_id in sessions:
                        session_info = await session.call(
                            GET_SESSION, node_id, worker_id, realm, session_id)
                        pprint.pprint(session_info)


if __name__ == '__main__':
    client.run(main)
