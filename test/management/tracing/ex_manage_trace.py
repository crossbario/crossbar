# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import argparse

from crossbar.shell import client

#
# configuration of the trace we create and manage
#
TRACE_ID = u'hackathon-actions-trace'

TRACED_WORKERS = [(u'cf1', u'router1'), (u'cf2', u'router1'), (u'cf3',
                                                               u'router1')]
TRACED_WORKERS = [
    (u'node1', u'router1'),
    (u'node2', u'router1'),
]

TRACE_OPTIONS = {
    u'trace_level': u'action',
    u'batching_period': 200
}

ELIGIBLE_READER_ROLES = [
    # allow read-only access to the running trace to management realm
    # owner and public (= anonymous!)
    u'owner',
    u'public',

    # only allow access to management realm owner
    # u'owner',
]
EXCLUDE_READER_ROLES = None


async def main(session):
    """
    Demonstrates how to manage traces and the tracing API.
    """
    trace_id = TRACE_ID
    action = session.config.extra['args'].action

    trace = await session.call(
        u'crossbarfabriccenter.mrealm.tracing.get_trace', trace_id)

    if trace:
        session.log.info(
            'trace "{trace_id}" exists, current status: "{status}"',
            trace_id=trace_id,
            status=trace['status'])
    else:
        session.log.info(
            'no trace "{trace_id}" exists. creating ..', trace_id=trace_id)

    if action == u'create':
        if trace:
            session.log.warn('cannot create trace: trace already exists')
            return
        else:
            trace_created = await session.call(
                u'crossbarfabriccenter.mrealm.tracing.create_trace', trace_id,
                TRACED_WORKERS, TRACE_OPTIONS, ELIGIBLE_READER_ROLES,
                EXCLUDE_READER_ROLES)
            session.log.info(
                'trace created: {trace_created}', trace_created=trace_created)

    elif action == u'start':
        if not trace or trace[u'status'] != u'stopped':
            session.log.warn('cannot start trace: trace does not exist')
            return
        else:
            trace_started = await session.call(
                u'crossbarfabriccenter.mrealm.tracing.start_trace', trace_id)
            session.log.info(
                'trace started: {trace_started}', trace_started=trace_started)

    elif action == u'stop':
        if not trace or trace[u'status'] != u'running':
            session.log.warn(
                'cannot stop trace: trace does not exist or is not running')
            return
        else:
            trace_stopped = await session.call(
                u'crossbarfabriccenter.mrealm.tracing.stop_trace', trace_id)
            session.log.info(
                'trace stopped: {trace_stopped}', trace_stopped=trace_stopped)

    elif action == u'delete':
        if not trace or trace[u'status'] != u'stopped':
            session.log.warn(
                'cannot delete trace: trace does not exist or is not stopped')
            return
        else:
            trace_deleted = await session.call(
                u'crossbarfabriccenter.mrealm.tracing.delete_trace', trace_id)
            session.log.info(
                'trace deleted: {trace_deleted}', trace_deleted=trace_deleted)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'action',
        choices=['create', 'start', 'stop', 'delete'],
        help='Management action, one of "create", "start", "stop" or "delete" a trace.'
    )
    client.run(main, parser)
