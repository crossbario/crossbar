# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from crossbar.shell import client


async def main(session):
    """
    Iterate over all nodes, and all workers on each nodes to retrieve and
    print worker information. then exit.
    """
    nodes = await session.call(
        u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
    for node_id in nodes:
        workers = await session.call(
            u'crossbarfabriccenter.remote.node.get_workers', node_id)
        for worker_id in workers:

            session.log.info(
                'Node "{node_id}" / Worker "{worker_id} log":',
                node_id=node_id,
                worker_id=worker_id)

            # retrieve log history of worker (last 100 lines)
            log = await session.call(
                u'crossbarfabriccenter.remote.node.get_worker_log', node_id,
                worker_id, 100)

            for log_rec in log:
                print(log_rec)


if __name__ == '__main__':
    client.run(main)
