# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import asyncio

from autobahn.wamp.exception import ApplicationError

from crossbar.shell import client

CONTAINER_ID = u'my-container1'

CONTAINER_OPTIONS = {u'pythonpath': [u'..']}

COMPONENT_ID = u'my-component{}'

COMPONENT_CONFIG = {
    u'type': u'class',
    u'classname': u'client.ClientSession',
    u'realm': u'realm1',
    u'transport': {
        u'type': u'websocket',
        u'endpoint': {
            u'type': u'tcp',
            u'host': u'127.0.0.1',
            u'port': 8080
        },
        u'url': u'ws://localhost:8080/ws'
    }
}


async def main(session):
    """
    Start a new container worker on each node, with 4 components in each. Then stop everything.
    """
    try:
        # remember (container) workers we started
        workers_started = []

        nodes = await session.call(
            u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
        for node_id in nodes:

            workers = await session.call(
                u'crossbarfabriccenter.remote.node.get_workers', node_id)
            if CONTAINER_ID in workers:
                worker_stopped = await session.call(
                    u'crossbarfabriccenter.remote.node.stop_worker', node_id,
                    CONTAINER_ID)
                session.log.info(
                    'Worker {worker_id} stopped: {worker_stopped}',
                    worker_id=CONTAINER_ID,
                    worker_stopped=worker_stopped)

            worker_started = await session.call(
                u'crossbarfabriccenter.remote.node.start_worker', node_id,
                CONTAINER_ID, u'container', CONTAINER_OPTIONS)

            workers_started.append((node_id, CONTAINER_ID))

            session.log.info(
                'Node "{node_id}" / Worker "{worker_id}" started: {worker_started}',
                node_id=node_id,
                worker_id=CONTAINER_ID,
                worker_started=worker_started)

            for i in range(4):
                component_id = COMPONENT_ID.format(i)
                component_started = await session.call(
                    u'crossbarfabriccenter.remote.container.start_component',
                    node_id, CONTAINER_ID, component_id, COMPONENT_CONFIG)

                session.log.info(
                    'Component "{component_id}" started in container "{container_id}" on node "{node_id}": {component_started}',
                    node_id=node_id,
                    container_id=CONTAINER_ID,
                    component_id=component_id,
                    component_started=component_started)

        session.log.info('sleeping ..')
        await asyncio.sleep(5)

        # stop everything ..
        if True:
            for node_id, worker_id in workers_started:

                # you may or may not stop these manually before ..
                if True:
                    for i in range(4):
                        component_id = COMPONENT_ID.format(i)
                        component_stopped = await session.call(
                            u'crossbarfabriccenter.remote.container.stop_component',
                            node_id, CONTAINER_ID, component_id)

                        session.log.info(
                            'Component "{component_id}" stopped running in container "{container_id}" on node "{node_id}": {component_stopped}',
                            node_id=node_id,
                            container_id=CONTAINER_ID,
                            component_id=component_id,
                            component_stopped=component_stopped)

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
