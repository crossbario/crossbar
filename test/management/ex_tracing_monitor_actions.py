# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import pprint
import asyncio

from crossbar.shell import client


async def main(session):
    """
    Subscribe to all tracing related topics to monitor tracing on any node/worker.
    """
    verbose = False

    def on_trace_started(node_id, worker_id, trace_id, trace_started):
        session.log.info(
            'Trace "{trace_id}" started on node "{node_id}" / worker "{worker_id}":\n{trace_started}',
            node_id=node_id,
            worker_id=worker_id,
            trace_id=trace_id,
            trace_started=pprint.pformat(trace_started))

    await session.subscribe(
        on_trace_started,
        u'crossbarfabriccenter.remote.tracing.on_trace_started',
    )

    def on_trace_stopped(node_id, worker_id, trace_id, trace_stopped):
        session.log.info(
            'Trace "{trace_id}" stopped on node "{node_id}" / worker "{worker_id}":\n{trace_stopped}',
            node_id=node_id,
            worker_id=worker_id,
            trace_id=trace_id,
            trace_stopped=pprint.pformat(trace_stopped))

    await session.subscribe(
        on_trace_stopped,
        u'crossbarfabriccenter.remote.tracing.on_trace_stopped',
    )

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
        on_trace_data,
        u'crossbarfabriccenter.remote.tracing.on_trace_data',
    )

    # start tracing on all router workers on all nodes
    started_traces = []
    node_id = u'cf1'
    worker_id = u'worker-001'

    # stop any currently running traces (we don't want to get data from orphaned traces)
    traces = await session.call(
        u'crossbarfabriccenter.remote.tracing.get_traces', node_id, worker_id)
    for trace_id in traces:
        trace = await session.call(
            u'crossbarfabriccenter.remote.tracing.get_trace', node_id,
            worker_id, trace_id)
        if trace[u'status'] == u'running':
            stopped = await session.call(
                u'crossbarfabriccenter.remote.tracing.stop_trace', node_id,
                worker_id, trace_id)
            session.log.info(
                'Stopping orphaned trace "{trace_id}" on node "{node_id}" / worker "{worker_id}"',
                trace_id=trace_id,
                node_id=node_id,
                worker_id=worker_id)

    # start a new trace
    trace_id = None
    trace_options = {
        # if provided, run trace for this many secs and then auto-stop
        u'duration': None,

        # trace at the WAMP action level (calls and publications), vs tracing at the
        # raw WAMP message level
        u'trace_level': u'action',

        # trace messages will be batched for this many ms, and only then a trace data event is published
        u'batching_period': 200,

        # not yet implemented (when a trace was stopped, or the router is restarted, trace data is gone)
        u'persist': False
    }
    trace = await session.call(
        u'crossbarfabriccenter.remote.tracing.start_trace',
        node_id,
        worker_id,
        trace_id,
        trace_options=trace_options)
    trace_id = trace['id']
    started_traces.append((node_id, worker_id, trace_id))
    session.log.info(
        'Trace "{trace_id} on node "{node_id}" / worker "{worker_id}" started with options {trace_options}:\n{trace}"',
        node_id=node_id,
        worker_id=worker_id,
        trace_id=trace_id,
        trace_options=trace_options,
        trace=pprint.pformat(trace))

    # here, we run for a finite time. for a UI client,
    monitor_time = 6000
    session.log.info(
        'ok, subscribed to tracing events - now sleeping for {monitor_time} secs ..',
        monitor_time=monitor_time)
    await asyncio.sleep(monitor_time)

    # stop traces
    for node_id, worker_id, trace_id in started_traces:
        stopped = await session.call(
            u'crossbarfabriccenter.remote.tracing.stop_trace', node_id,
            worker_id, trace_id)

        session.log.info(
            'Trace "{trace_id}" on "{node_id}/{worker_id}" stopped:\n{stopped}',
            node_id=node_id,
            worker_id=worker_id,
            trace_id=trace_id,
            stopped=pprint.pformat(stopped))


if __name__ == '__main__':
    client.run(main)
