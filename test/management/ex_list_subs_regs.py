# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import pprint
import itertools

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
GET_SUBSCRIPTIONS = WAMP.format(u'wamp.subscription.list')
GET_SUBSCRIPTION = WAMP.format(u'wamp.subscription.get')
GET_REGISTRATIONS = WAMP.format(u'wamp.registration.list')
GET_REGISTRATION = WAMP.format(u'wamp.registration.get')


async def main(session):
    """
    Iterate over all nodes, and all (router) workers on each node, all realms
    on each router, list of sessions on each, and then retrieve list of subscriptions
    and list of registrations for each session. if verbose, retrieve details for
    each subscription and registration.
    """
    verbose = True

    regs_out = {}
    subs_out = {}

    nodes = await session.call(GET_NODES, status=u'online')
    print('nodes: {}'.format(nodes))
    for node_id in nodes:
        workers = await session.call(GET_WORKERS, node_id)
        print('  workers on node {}: {}'.format(node_id, workers))
        for worker_id in workers:
            worker = await session.call(GET_WORKER, node_id, worker_id)
            if worker[u'type'] == u'router':
                realms = await session.call(GET_ROUTER_REALMS, node_id,
                                            worker_id)
                print('    realms on worker {}: {}'.format(worker_id, realms))
                for realm in realms:
                    sessions = await session.call(GET_SESSIONS, node_id,
                                                  worker_id, realm)
                    print('        sessions on realm {}: {}'.format(
                        realm, sessions))
                    for session_id in sessions:

                        subscriptions = await session.call(
                            GET_SUBSCRIPTIONS, node_id, worker_id, realm,
                            session_id)
                        sub_ids = list(
                            itertools.chain(*subscriptions.values()))
                        print(
                            '          subscriptions on session {}: {}'.format(
                                session_id, sub_ids))

                        if verbose:
                            for sub_type, sub_ids in subscriptions.items():
                                for sub_id in sub_ids:
                                    if sub_id not in subs_out:
                                        sub = await session.call(
                                            GET_SUBSCRIPTION, node_id,
                                            worker_id, realm, sub_id)
                                        subs_out[sub_id] = sub

                        registrations = await session.call(
                            GET_REGISTRATIONS, node_id, worker_id, realm,
                            session_id)
                        reg_ids = list(
                            itertools.chain(*registrations.values()))
                        print(
                            '          registrations on session {}: {}'.format(
                                session_id, reg_ids))

                        if verbose:
                            for _, reg_ids in registrations.items():
                                for reg_id in reg_ids:
                                    if reg_id not in regs_out:
                                        reg = await session.call(
                                            GET_REGISTRATION, node_id,
                                            worker_id, realm, reg_id)
                                        regs_out[reg_id] = reg

    if verbose:
        print('\nsubscriptions retrieved:\n')
        for sub in subs_out.values():
            pprint.pprint(sub)

        print('\nregistrations retrieved:\n')
        for reg in regs_out.values():
            pprint.pprint(reg)


if __name__ == '__main__':
    client.run(main)
