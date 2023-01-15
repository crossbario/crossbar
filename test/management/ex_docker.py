# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from crossbar.shell import client


async def main(session):
    """
    Test remote management of Docker running on a CF node.
    """
    nodes = await session.call(
        u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
    for node_id in nodes:

        node_status = await session.call(
            u'crossbarfabriccenter.remote.node.get_status', node_id)

        if node_status[u'has_docker']:
            docker_info = await session.call(
                u'crossbarfabriccenter.remote.docker.get_info', node_id)
            session.log.info(
                'Node "{node_id}" has Docker enabled with status: {docker_info}',
                node_id=node_id,
                docker_info=docker_info)

            docker_images = await session.call(
                u'crossbarfabriccenter.remote.docker.get_images', node_id)
            for image_id in docker_images:
                docker_image = await session.call(
                    u'crossbarfabriccenter.remote.docker.get_image', node_id,
                    image_id)
                session.log.info(
                    'Found Docker image: {image_id} - {docker_image}',
                    image_id=image_id,
                    docker_image=docker_image)

            docker_containers = await session.call(
                u'crossbarfabriccenter.remote.docker.get_containers', node_id)
            for container_id in docker_containers:
                docker_container = await session.call(
                    u'crossbarfabriccenter.remote.docker.get_container',
                    node_id, container_id)
                session.log.info(
                    'Found Docker container: {container_id} - {docker_container}',
                    container_id=container_id,
                    docker_container=docker_container)

        else:
            session.log.info(
                'Node "{node_id}" does not have Docker (enabled)',
                node_id=node_id)


if __name__ == '__main__':
    client.run(main)
