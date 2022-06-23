# Copyright (c) Crossbar.io Technologies GmbH, licensed under The MIT License (MIT)

from pprint import pprint

from crossbar.shell import client


async def main(session):
    """
    This example demonstrates how to retrieve OS process statistics for
    Crossbar.io node controller and worker processes.
    """
    nodes = await session.call(
        u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
    for node_id in nodes:

        # get process stats for node controller process
        process_stats = await session.call(
            u'crossbarfabriccenter.remote.node.get_process_stats', node_id)
        session.log.info(
            'Process stats for node controller on node {node_id}:',
            node_id=node_id)
        pprint(process_stats)

        workers = await session.call(
            u'crossbarfabriccenter.remote.node.get_workers', node_id)
        for worker_id in workers:
            worker = await session.call(
                u'crossbarfabriccenter.remote.node.get_worker',
                node_id,
                worker_id,
                include_stats=True)
            session.log.info(
                'Node "{node_id}" / Worker "{worker_id}": {worker}',
                node_id=node_id,
                worker_id=worker_id,
                worker=worker)

            # get process stats for worker process
            process_stats = await session.call(
                u'crossbarfabriccenter.remote.worker.get_process_stats',
                node_id, worker_id)
            session.log.info(
                'Process stats for worker {worker_id} on node {node_id}:',
                node_id=node_id,
                worker_id=worker_id)
            pprint(process_stats)


if __name__ == '__main__':
    client.run(main)
