# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from pprint import pformat

from crossbar.shell import client


async def main(session):
    """
    Iterate over all nodes, and all workers on each nodes to retrieve and
    print worker information.
    """
    nodes = await session.call(
        u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
    for node_id in nodes:

        workers = await session.call(
            u'crossbarfabriccenter.remote.node.get_workers', node_id)
        for worker_id in workers:
            worker = await session.call(
                u'crossbarfabriccenter.remote.node.get_worker',
                node_id,
                worker_id,
                include_stats=True)
            session.log.info(
                'Node "{node_id}" / Worker "{worker_id}":\n{worker}',
                node_id=node_id,
                worker_id=worker_id,
                worker=pformat(worker))


if __name__ == '__main__':
    client.run(main)
