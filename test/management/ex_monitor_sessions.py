# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

from pprint import pformat
import asyncio

from crossbar.shell import client

# the following requires options.bridge_meta_api=true in the options
# of the Crossbar.io router realm called into. it might also require elevated
# rights on CFC for authorization on the URIs
#
# these URIs access the WAMP meta API within Crossbar.io router realms and behave
# exactly the same as a WAMP client locally attached to the respective app router
# would see.
#
WAMP = u'crossbarfabriccenter.remote.realm.meta.{}'
ON_SESSION_JOIN = WAMP.format(u'wamp.session.on_join')
ON_SESSION_LEAVE = WAMP.format(u'wamp.session.on_leave')


async def main(session):
    """
    Iterate over all nodes, and all (router) workers on each node, all realms
    on each router, list of sessions on each, and then retrieve session detail info.
    """

    def on_session_join(node_id, worker_id, realm_id, session_details):
        session.log.info(
            'session joined on node "{node_id}", worker "{worker_id}", realm "{realm_id}":\n{session_details}\n',
            node_id=node_id,
            worker_id=worker_id,
            realm_id=realm_id,
            session_details=pformat(session_details))

    await session.subscribe(on_session_join, ON_SESSION_JOIN)

    def on_session_leave(node_id, worker_id, realm_id, session_id):
        session.log.info(
            'session "{session_id}" left on node "{node_id}", worker "{worker_id}", realm "{realm_id}\n"',
            node_id=node_id,
            worker_id=worker_id,
            realm_id=realm_id,
            session_id=session_id)

    await session.subscribe(on_session_leave, ON_SESSION_LEAVE)

    monitor_time = 600
    session.log.info(
        'ok, subscribed to session join/leave meta events - now sleeping for {monitor_time} secs ..',
        monitor_time=monitor_time)
    await asyncio.sleep(monitor_time)


if __name__ == '__main__':
    client.run(main)
