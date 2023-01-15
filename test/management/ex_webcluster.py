# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from crossbar.shell import client


CLUSTERS = [
    {
        'name': 'wc3',
        'description': 'Test Web cluster of project-x.',
        'tags': ['test', 'projectx']
    },
    {
        'name': 'wc5',
        'description': 'Production Web cluster of project-x.',
        'tags': ['prod', 'projectx']
    },
]


async def main(session):
    clusters = await session.call(u'crossbarfabriccenter.mrealm.webcluster.list_webclusters')
    session.log.info('Existing clusters: {clusters}', clusters=clusters)

    current = {}
    for oid in clusters:
        cluster = await session.call(u'crossbarfabriccenter.mrealm.webcluster.get_webcluster', oid)
        current[cluster['name']] = cluster
        session.log.info('Cluster oid={oid}: {cluster}', oid=oid, cluster=cluster)
        if cluster['name'] not in CLUSTERS:
            await session.call(u'crossbarfabriccenter.mrealm.webcluster.delete_webcluster', oid)
            session.log.info('Deleted cluster with oid={oid} not in our target configuration', oid=oid)

    for cluster in CLUSTERS:
        if cluster['name'] in current:
            session.log.info('cluster {name} already exists', name=cluster['name'])
        else:
            oid = await session.call(u'crossbarfabriccenter.mrealm.webcluster.create_webcluster', cluster)
            session.log.info('cluster {name} created: {oid}', oid=oid, name=cluster['name'])


async def main2(session):
    for cluster in CLUSTERS:
        oid = await session.call(u'crossbarfabriccenter.mrealm.webcluster.create_webcluster', cluster)
        session.log.info('cluster {name} created: {oid}', oid=oid, name=cluster['name'])

if __name__ == '__main__':
    client.run(main)
