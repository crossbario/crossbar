# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import asyncio

from crossbar.shell import client

ROUTER_ID = u'my-router1'

ROUTER_OPTIONS = {u'pythonpath': [u'..']}

REALM_ID = u'my-realm1'

REALM_CONFIG = {u'name': u'realm1'}

ROLE_ID = u'my-role1'

ROLE_CONFIG = {
    u"name":
    u"anonymous",
    u"permissions": [{
        u"uri": u"",
        u"match": u"prefix",
        u"allow": {
            u"call": True,
            u"register": True,
            u"publish": True,
            u"subscribe": True,
        },
        u"disclose": {
            u"caller": False,
            u"publisher": False
        },
        u"cache": True
    }]
}

TRANSPORT_ID = u'my-transport1'

TRANSPORT_CONFIG = {
    u'type': u'web',
    u'endpoint': {
        u'type': u'tcp',
        u'port': 8000
    },
    u'paths': {
        u'/': {
            u'type': u'static',
            u'directory': u'..',
            u'options': {
                u'enable_directory_listing': True
            }
        }
    }
}

WEB_SERVICES = {
    u'temp': {
        u'type': u'static',
        u'directory': u'/tmp',
        u'options': {
            u'enable_directory_listing': True
        }
    },
    u'ws': {
        u'type': u'websocket'
    },
    u'proxy1': {
        u'type': u'websocket-reverseproxy',
        u'backend': {
            u'type': u'websocket',
            u'endpoint': {
                u'type': u'tcp',
                u'host': u'127.0.0.1',
                u'port': 9000
            },
            u'url': "ws://localhost:9000"
        }
    },
}


async def main(session):
    """
    Start a router worker on each node, with a realm and a role. Then stop everything again.
    """
    try:

        def on_web_transport_service_starting(node_id,
                                              worker_id,
                                              transport_id,
                                              path,
                                              details=None):
            session.log.info(
                'on_web_transport_service_starting(node_id={node_id}, worker_id={worker_id}, transport_id={transport_id} path={path}, details={details})',
                node_id=node_id,
                worker_id=worker_id,
                transport_id=transport_id,
                path=path,
                details=details)

        await session.subscribe(
            on_web_transport_service_starting,
            u'crossbarfabriccenter.remote.router.on_web_transport_service_starting'
        )

        def on_web_transport_service_started(node_id,
                                             worker_id,
                                             transport_id,
                                             path,
                                             config,
                                             details=None):
            session.log.info(
                'on_web_transport_service_started(node_id={node_id}, worker_id={worker_id}, transport_id={transport_id}, path={path}, config={config}, details={details})',
                node_id=node_id,
                worker_id=worker_id,
                transport_id=transport_id,
                path=path,
                config=config,
                details=details)

        await session.subscribe(
            on_web_transport_service_started,
            u'crossbarfabriccenter.remote.router.on_web_transport_service_started'
        )

        def on_web_transport_service_stopping(node_id,
                                              worker_id,
                                              transport_id,
                                              path,
                                              details=None):
            session.log.info(
                'on_web_transport_service_stopping(node_id={node_id}, worker_id={worker_id}, transport_id={transport_id}, path={path}, details={details})',
                node_id=node_id,
                worker_id=worker_id,
                transport_id=transport_id,
                path=path,
                details=details)

        await session.subscribe(
            on_web_transport_service_stopping,
            u'crossbarfabriccenter.remote.router.on_web_transport_service_stopping'
        )

        def on_web_transport_service_stopped(node_id,
                                             worker_id,
                                             transport_id,
                                             path,
                                             config,
                                             details=None):
            session.log.info(
                'on_web_transport_service_stopped(node_id={node_id}, worker_id={worker_id}, transport_id={transport_id}, path={path}, config={config}, details={details})',
                node_id=node_id,
                worker_id=worker_id,
                transport_id=transport_id,
                path=path,
                config=config,
                details=details)

        await session.subscribe(
            on_web_transport_service_stopped,
            u'crossbarfabriccenter.remote.router.on_web_transport_service_stopped'
        )

        # remember (router) workers we started
        workers_started = []

        nodes = await session.call(
            u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
        for node_id in nodes:

            workers = await session.call(
                u'crossbarfabriccenter.remote.node.get_workers', node_id)
            if ROUTER_ID in workers:
                worker_stopped = await session.call(
                    u'crossbarfabriccenter.remote.worker.shutdown', node_id,
                    ROUTER_ID)
                # worker_stopped = await session.call(u'crossbarfabriccenter.remote.node.stop_worker', node_id, ROUTER_ID)
                session.log.info(
                    'Worker {worker_id} stopped: {worker_stopped}',
                    worker_id=ROUTER_ID,
                    worker_stopped=worker_stopped)

            worker_started = await session.call(
                u'crossbarfabriccenter.remote.node.start_worker', node_id,
                ROUTER_ID, u'router', ROUTER_OPTIONS)

            workers_started.append((node_id, ROUTER_ID))

            session.log.info(
                'Node "{node_id}" / Worker "{worker_id}" started: {worker_started}',
                node_id=node_id,
                worker_id=ROUTER_ID,
                worker_started=worker_started)

            realm_started = await session.call(
                u'crossbarfabriccenter.remote.router.start_router_realm',
                node_id, ROUTER_ID, REALM_ID, REALM_CONFIG)

            session.log.info(
                'Realm started: {realm_started}', realm_started=realm_started)

            role_started = await session.call(
                u'crossbarfabriccenter.remote.router.start_router_realm_role',
                node_id, ROUTER_ID, REALM_ID, ROLE_ID, ROLE_CONFIG)
            session.log.info(
                'Role started: {role_started}', role_started=role_started)

            transport_started = await session.call(
                u'crossbarfabriccenter.remote.router.start_router_transport',
                node_id, ROUTER_ID, TRANSPORT_ID, TRANSPORT_CONFIG)
            session.log.info(
                'Transport started: {transport_started}',
                transport_started=transport_started)

            TRANSPORT_CONFIG[u'endpoint'][u'port'] += 1

        for i in range(2):
            session.log.info('Starting Web services ..')
            for node_id, worker_id in workers_started:
                for path, config in WEB_SERVICES.items():
                    await session.call(
                        u'crossbarfabriccenter.remote.router.start_web_transport_service',
                        node_id, worker_id, TRANSPORT_ID, path, config)

            session.log.info('sleeping ..')
            await asyncio.sleep(5)

            session.log.info('Stopping Web services ..')
            for node_id, worker_id in workers_started:
                for path, config in WEB_SERVICES.items():
                    await session.call(
                        u'crossbarfabriccenter.remote.router.stop_web_transport_service',
                        node_id, worker_id, TRANSPORT_ID, path)

            session.log.info('sleeping ..')
            await asyncio.sleep(5)

        # stop all the router transports we started
        for node_id, worker_id in workers_started:

            role_stopped = await session.call(
                u'crossbarfabriccenter.remote.router.stop_router_realm_role',
                node_id, ROUTER_ID, REALM_ID, ROLE_ID)
            session.log.info(
                'Role stopped: {role_stopped}', role_stopped=role_stopped)

            realm_stopped = await session.call(
                u'crossbarfabriccenter.remote.router.stop_router_realm',
                node_id, ROUTER_ID, REALM_ID)
            session.log.info(
                'Realm stopped: {realm_stopped}', realm_stopped=realm_stopped)

            transport_stopped = await session.call(
                u'crossbarfabriccenter.remote.router.stop_router_transport',
                node_id, worker_id, TRANSPORT_ID)
            session.log.info(
                'Transport {transport_id} on worker {worker_id} ({node_id}) stopped: {transport_stopped}',
                transport_stopped=transport_stopped,
                node_id=node_id,
                worker_id=worker_id,
                transport_id=TRANSPORT_ID)

            worker_stopped = await session.call(
                u'crossbarfabriccenter.remote.worker.shutdown', node_id,
                worker_id)
            session.log.info(
                'Worker {worker_id} stopped: {worker_stopped}',
                worker_stopped=worker_stopped,
                worker_id=worker_id)

    except Exception as e:
        print('fatal: {}'.format(e))


if __name__ == '__main__':
    client.run(main)
