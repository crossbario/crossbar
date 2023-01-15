# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from pprint import pformat
import asyncio

from crossbar.shell import client


async def main(session):
    """
    Connect to CFC, get system status and exit.

    IMPORTANT: This example is supposed to be run against the global users
    realm on CFC!
    """
    status = await session.call(u'crossbarfabriccenter.domain.get_status')
    session.log.info('CFC domain status:\n{status}', status=pformat(status))

    mrealms = await session.call(u'crossbarfabriccenter.mrealm.list_mrealms')
    for mrealm_name in mrealms:
        mrealm = await session.call(u'crossbarfabriccenter.mrealm.get_mrealm',
                                    mrealm_name)
        session.log.info(
            'management realm "{mrealm_name}":\n{mrealm}',
            mrealm_name=mrealm_name,
            mrealm=pformat(mrealm))

        # nodes = await session.call(u'crossbarfabriccenter.mrealm.get_nodes', mrealm_name)
        # for node_id in nodes:
        #     node = await session.call(u'crossbarfabriccenter.mrealm.get_node', mrealm_name, node_id)
        #     session.info.log('    node "{node_id}": {node}', node_id=node_id, node=pformat(node))

    return

    # FIXME: activate when the topic URI in CFC is fixed!

    def on_tick(ticked):  # pylint: disable=W0101
        session.log.info('received tick: {ticked}', ticked=ticked)

    await session.subscribe(on_tick, u'crossbarfabriccenter.domain.on_tick')

    await asyncio.sleep(10)


if __name__ == '__main__':
    client.run(main)
