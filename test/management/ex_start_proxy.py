# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import asyncio

from autobahn.wamp.exception import ApplicationError

from crossbar.shell import client

PROXY_ID = u'my-proxy{}'

PROXY_OPTIONS = {
    # worker level options
}

TRANSPORT_ID = u'my-proxy{}-transport{}'

TRANSPORT_CONFIG = {
    # proxy listening transport in all its variations,
    # including Web services on Web transports and such
}


async def main(session):
    """
    Start N proxy workers on each node, each opening a (shared) listening transport,
    and each opening backend connections to 1 router worker.
    """
    try:
        # remember (container) workers we started
        workers_started = []

        nodes = await session.call(
            u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
        for node_id in nodes:

            workers = await session.call(
                u'crossbarfabriccenter.remote.node.get_workers', node_id)
            for proxy_id in [PROXY_ID.format(i) for i in range(2)]:

                # stop any worker running with our worker ID
                if proxy_id in workers:
                    worker_stopped = await session.call(
                        u'crossbarfabriccenter.remote.node.stop_worker',
                        node_id, proxy_id)
                    session.log.info(
                        'Worker {worker_id} stopped: {worker_stopped}',
                        worker_id=proxy_id,
                        worker_stopped=worker_stopped)

                # now actually start a new proxy worker
                worker_started = await session.call(
                    u'crossbarfabriccenter.remote.node.start_worker', node_id,
                    proxy_id, u'proxy', PROXY_OPTIONS)

                workers_started.append((node_id, proxy_id))

                session.log.info(
                    'Node "{node_id}" / Worker "{worker_id}" started: {worker_started}',
                    node_id=node_id,
                    worker_id=proxy_id,
                    worker_started=worker_started)

        session.log.info('sleeping ..')
        await asyncio.sleep(5)

        # stop everything ..
        if True:
            for node_id, worker_id in workers_started:

                # .. stopping the whole worker
                try:
                    worker_stopped = await session.call(
                        u'crossbarfabriccenter.remote.worker.shutdown',
                        node_id, worker_id)

                # FIXME: remove this once the respective CF bug is fixed
                except ApplicationError as e:
                    if e.error == u'wamp.error.canceled':
                        worker_stopped = None
                    else:
                        raise

                session.log.info(
                    'Worker {worker_id} stopped: {worker_stopped}',
                    worker_stopped=worker_stopped,
                    worker_id=worker_id)

    except Exception as e:
        print('fatal: {}'.format(e))


if __name__ == '__main__':
    client.run(main)
