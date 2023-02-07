# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from pprint import pprint, pformat

from crossbar.shell import client


async def main(session):
    """
    Iterate over all nodes in management realm. For nodes that are currently
    online, query the node remotely for status.
    """

    # get list of node IDs
    nodes = await session.call(u'crossbarfabriccenter.mrealm.get_nodes')
    print('got nodes:', nodes)

    for node_id in nodes:

        # get node information
        node = await session.call(u'crossbarfabriccenter.mrealm.get_node',
                                  node_id)
        print('got node:', pformat(node))

        # since we didn't filter for nodes that are currently only, we need to check manually:
        if node[u'status'] == u'online':

            # if the node is online, query it remotely ..
            node_status = await session.call(
                u'crossbarfabriccenter.remote.node.get_status', node_id)

            session.log.info('Node "{node_id}" is online:\n', node_id=node_id)
            print(pformat(node_status))
        else:
            session.log.info('Node "{node_id}" is currently offline')


if __name__ == '__main__':
    client.run(main)
