# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import asyncio

from crossbar.shell import client

# the ID of the guest worker we will start (on each node)
GUEST_ID = u'sleeper1'

# the config of the guest worker we will start
GUEST_CONFIG = {
    u'type': u'guest',
    u'executable': u'/bin/sleep',
    u'arguments': [u'10'],
    u'options': {}
}


async def main(session):
    '''
    Iterate over all nodes and start a guest worker on each one. Wait a little,
    and then stop all guest workers previously started.
    '''
    workers_started = []

    nodes = await session.call(
        u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
    for node_id in nodes:

        workers = await session.call(
            u'crossbarfabriccenter.remote.node.get_workers', node_id)

        # if there currently is a worker running with the ID of the guest worker that
        # we want to start, then first stop the currently running worker
        if GUEST_ID in workers:
            worker_stopped = await session.call(
                u'crossbarfabriccenter.remote.node.stop_worker',
                node_id,
                GUEST_ID,
                # this will hard kill the worker (by sending SIGKILL to the worker)
                kill=True)

            session.log.info(
                'Worker "{worker_id}" on node "{node_id}" stopped: {worker_stopped}',
                node_id=node_id,
                worker_id=GUEST_ID,
                worker_stopped=worker_stopped)

        # now start a new guest worker with respective config
        worker_started = await session.call(
            u'crossbarfabriccenter.remote.node.start_worker', node_id,
            GUEST_ID, u'guest', GUEST_CONFIG)

        # remember the node/worker we started
        workers_started.append((node_id, GUEST_ID))

        session.log.info(
            'Worker "{worker_id}" on node "{node_id}" started: {worker_started}',
            node_id=node_id,
            worker_id=GUEST_ID,
            worker_started=worker_started)

    # let the workers run for some time ..
    session.log.info('sleeping ..')
    await asyncio.sleep(2)

    # stop all workers we started
    if True:
        for node_id, worker_id in workers_started:
            worker_stopped = await session.call(
                u'crossbarfabriccenter.remote.node.stop_worker',
                node_id,
                worker_id,
                # this will only soft stop the worker (by closing stdin/stdout pipes and sending SIGTERM to the worker)
                kill=False)

            session.log.info(
                'Worker "{worker_id}" on node "{node_id}" stopped: {worker_stopped}',
                node_id=node_id,
                worker_stopped=worker_stopped,
                worker_id=worker_id)
    else:
        session.log.info(
            'The following workers will continue to run: {workers_started}',
            workers_started=workers_started)


if __name__ == '__main__':
    client.run(main)
