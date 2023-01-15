# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import pprint
import asyncio

from crossbar.shell import client

TRACE_ID = u'hackathon-actions-trace'


async def main(session):
    """
    Subscribe to all tracing related topics to monitor tracing on any node/worker.
    """
    verbose = True

    #
    # subscribe to tracing lifecycle events
    #
    def on_trace_created(trace_id, trace_created):
        session.log.info(
            'Trace "{trace_id}" created:\n{trace_created}',
            trace_id=trace_id,
            trace_created=pprint.pformat(trace_created))

    await session.subscribe(
        on_trace_created,
        u'crossbarfabriccenter.mrealm.tracing.on_trace_created')

    def on_trace_starting(trace_id):
        session.log.info('Trace "{trace_id}" starting ..', trace_id=trace_id)

    await session.subscribe(
        on_trace_starting,
        u'crossbarfabriccenter.mrealm.tracing.on_trace_starting')

    def on_trace_started(trace_id, trace_started):
        session.log.info(
            'Trace "{trace_id}":\n{trace_started}',
            trace_id=trace_id,
            trace_started=pprint.pformat(trace_started))

    await session.subscribe(
        on_trace_started,
        u'crossbarfabriccenter.mrealm.tracing.on_trace_started')

    def on_trace_stopping(trace_id):
        session.log.info('Trace "{trace_id}" stopping ..', trace_id=trace_id)

    await session.subscribe(
        on_trace_stopping,
        u'crossbarfabriccenter.mrealm.tracing.on_trace_stopping')

    def on_trace_stopped(trace_id, trace_stopped):
        session.log.info(
            'Trace "{trace_id}" stopped:\n{trace_stopped}',
            trace_id=trace_id,
            trace_stopped=pprint.pformat(trace_stopped))

    await session.subscribe(
        on_trace_stopped,
        u'crossbarfabriccenter.mrealm.tracing.on_trace_stopped')

    def on_trace_deleted(trace_id, trace_deleted):
        session.log.info(
            'Trace "{trace_id}" deleted:\n{trace_deleted}',
            trace_id=trace_id,
            trace_deleted=pprint.pformat(trace_deleted))

    await session.subscribe(
        on_trace_deleted,
        u'crossbarfabriccenter.mrealm.tracing.on_trace_deleted')

    #
    # get IDs of defined traces (to which we are allowed read access)
    #
    trace_ids = await session.call(
        u'crossbarfabriccenter.mrealm.tracing.get_traces')
    session.log.info(
        'traces defined: {trace_ids}', trace_ids=pprint.pformat(trace_ids))

    #
    # check if our trace exists, and exit if not, or if it is not running ..
    #
    trace = await session.call(
        u'crossbarfabriccenter.mrealm.tracing.get_trace', TRACE_ID)
    if trace:
        session.log.info(
            'trace "{trace_id}" exists, current status: "{status}"',
            trace_id=TRACE_ID,
            status=trace['status'])
        if trace[u'status'] != u'running':
            session.log.info(
                'trace "{trace_id}" exists, but is not running. exiting.',
                trace_id=TRACE_ID)
            return
    else:
        session.log.info(
            'no trace "{trace_id}" exists. exiting.', trace_id=TRACE_ID)
        return

    #
    # get trace data records (this will query directly into the traced nodes)
    #
    # trace_data = await session.call(u'crossbarfabriccenter.mrealm.tracing.get_trace_data', TRACE_ID, limit=5)
    # print('TRACE DATA:\n{}'.format(pprint.pformat(trace_data)))

    #
    # list for trace data live
    #
    def on_trace_data(node_id, worker_id, trace_id, period, trace_data):
        if verbose:
            session.log.info(
                'Trace "{trace_id}" on node "{node_id}" / worker "{worker_id}":\n\nperiod = {period}\n\ntrace_data = {trace_data}\n\n',
                node_id=node_id,
                worker_id=worker_id,
                trace_id=trace_id,
                period=pprint.pformat(period),
                trace_data=pprint.pformat(trace_data))
        else:
            print()
            print('{:8} {:8} {:12} {:10} {:12} {:8} {:<16} {:<10} {:38} {}'.
                  format('Trace', 'Node', 'Worker', 'Realm', 'Action',
                         'Success', 'Originator', 'Responders',
                         'Correlation ID', 'Correlation URI'))
            print('.' * 160)
            for trace_rec in trace_data:
                print(
                    '{:8} {:8} {:12} {:10} {:12} {:8} {:<16} {:<10} {:38} {}'.
                    format(trace_id, node_id, worker_id, trace_rec[u'realm'],
                           trace_rec[u'action'], str(trace_rec[u'success']),
                           trace_rec[u'originator'],
                           len(trace_rec[u'responders']),
                           trace_rec[u'correlation_id'],
                           trace_rec[u'correlation_uri']))

    await session.subscribe(
        on_trace_data, u'crossbarfabriccenter.mrealm.tracing.on_trace_data')

    #
    # here, we run for a finite time. for a UI client,
    #
    monitor_time = 6000
    session.log.info(
        'ok, subscribed to tracing events - now sleeping for {monitor_time} secs ..',
        monitor_time=monitor_time)
    await asyncio.sleep(monitor_time)


if __name__ == '__main__':
    client.run(main)
