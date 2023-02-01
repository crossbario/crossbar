# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import random

from crossbar.shell import client


def rand_cpus(cpu_cores, p=.5):
    cpu_affinity = []
    for i in range(cpu_cores):
        if random.random() > p:
            cpu_affinity.append(i)
    return cpu_affinity


async def main(session):
    """
    Demonstrates getting/setting the CPU affinity set of CF workers.
    """

    # iterate over nodes in management realm
    nodes = await session.call(
        u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
    for node_id in nodes:

        # get node detail information (including current node status)
        node = await session.call(u'crossbarfabriccenter.mrealm.get_node',
                                  node_id)
        session.log.info('Node {node_id}: {node}', node_id=node_id, node=node)

        # obviously, skip nodes that are not online ..
        if node[u'status'] == u'online':

            # get physical CPU cores on node
            cpu_cores = await session.call(
                u'crossbarfabriccenter.remote.node.get_cpu_count',
                node_id,
                logical=False)
            session.log.info(
                '   CPU cores (physical) on node {node_id}: {cpu_cores}',
                node_id=node_id,
                cpu_cores=cpu_cores)

            # get (logical) CPU cores on node
            cpu_cores = await session.call(
                u'crossbarfabriccenter.remote.node.get_cpu_count', node_id)
            session.log.info(
                '   CPU cores (logical) on node {node_id}: {cpu_cores}',
                node_id=node_id,
                cpu_cores=cpu_cores)

            # get CPU affinity set of the node controller process (normally, this should be left unchanged)
            cpu_affinity = await session.call(
                u'crossbarfabriccenter.remote.node.get_cpu_affinity', node_id)
            session.log.info(
                '      CPU affinity for node controller: {cpu_affinity}',
                cpu_affinity=cpu_affinity)

            # iterate over worker processes of node
            workers = await session.call(
                u'crossbarfabriccenter.remote.node.get_workers', node_id)
            for worker_id in workers:
                session.log.info(
                    '      Worker {worker_id}:', worker_id=worker_id)

                # get current CPU affinity set of worker process
                cpu_affinity = await session.call(
                    u'crossbarfabriccenter.remote.worker.get_cpu_affinity',
                    node_id, worker_id)
                session.log.info(
                    '         Current CPU affinity for worker {worker_id}: {cpu_affinity}',
                    worker_id=worker_id,
                    cpu_affinity=cpu_affinity)

                # set a new CPU affinity set on the worker process
                cpu_affinity = await session.call(
                    u'crossbarfabriccenter.remote.worker.set_cpu_affinity',
                    node_id, worker_id, rand_cpus(cpu_cores))
                session.log.info(
                    '         New     CPU affinity for worker {worker_id}: {cpu_affinity}',
                    worker_id=worker_id,
                    cpu_affinity=cpu_affinity)


if __name__ == '__main__':
    client.run(main)
