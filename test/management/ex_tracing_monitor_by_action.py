# Copyright (c) typedef int GmbH, licensed under The MIT License (MIT)

import pprint
import asyncio

from crossbar.shell import client

completed = 0


async def main(session):
    """
    Subscribe to all tracing related topics to monitor tracing on any node/worker.

    Aggregate received trace records into traced WAMP actions.

    Example output: https://gist.githubusercontent.com/oberstet/101e97c9d2fb9fbb03a9b1d5bb3e95de/raw/d5f034dd61b71a4f0d54b2ee2720940588993395/gistfile1.txt
    """
    verbose = False
    verbose_verbose = False

    action_by_correlation = {}

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
            if verbose_verbose:
                session.log.info(
                    'Trace "{trace_id}" on node "{node_id}" / worker "{worker_id}":\n\nperiod = {period}\n\ntrace_data = {trace_data}\n\n',
                    node_id=node_id,
                    worker_id=worker_id,
                    trace_id=trace_id,
                    period=pprint.pformat(period),
                    trace_data=pprint.pformat(trace_data))
            else:
                print()
                print('{:10} {:10} {:10} {:3} {:12} {:18} {:8} {:8} {:38} {}'.
                      format('Node', 'Worker', 'Trace', 'Dir', 'Type',
                             'Session', 'Anchor', 'Last', 'Correlation ID',
                             'Correlation URI'))
                print('.' * 160)
                for trace_rec in trace_data:
                    print(
                        '{:10} {:10} {:10} {:3} {:12} {:18} {:8} {:8} {:38} {}'.
                        format(node_id, worker_id, trace_id,
                               trace_rec[u'direction'].upper(),
                               trace_rec[u'msg_type'],
                               str(trace_rec[u'session_id']),
                               str(trace_rec[u'correlation_is_anchor']),
                               str(trace_rec[u'correlation_is_last']),
                               trace_rec[u'correlation'],
                               trace_rec[u'correlation_uri']))

        def on_action_complete(action, with_header=False):
            if with_header:
                print()
                print('{:20} {:8} {:10} {:8} {:8} {:24} {:18} {}'.format(
                    'Completed', 'Node', 'Worker', 'Trace', 'Type',
                    'Action URI', 'Origin', 'Targets'))
                print('.' * 160)
            if action[u'type'] in [u'Call', u'Publish']:
                print('{:20} {:8} {:10} {:8} {:8} {:24} {:18} {}'.format(
                    str(action[u'completed']), action[u'node_id'],
                    action[u'worker_id'], action[u'trace_id'], action[u'type'],
                    action[u'uri'], str(action[u'origin']),
                    pprint.pformat(action[u'targets'])))

        global completed  # pylint: disable=W0603

        for trace_rec in trace_data:

            session_id = trace_rec[u'session_id']
            msg_type = trace_rec[u'msg_type']

            corr_id = trace_rec[u'correlation']
            corr_uri = trace_rec[u'correlation_uri']
            correlation_is_anchor = trace_rec[u'correlation_is_anchor']
            correlation_is_last = trace_rec[u'correlation_is_last']
            ts = trace_rec[u'ts']  # noqa
            pc = trace_rec[u'pc']

            if msg_type in [u'Publish', u'Event', u'Call', u'Yield', u'Result', u'Error'] and \
               not corr_uri.startswith('wamp.'):

                if corr_id not in action_by_correlation:
                    assert correlation_is_anchor
                    assert not correlation_is_last
                    assert msg_type in [u'Call', u'Publish']
                    action_by_correlation[corr_id] = {
                        u'node_id': node_id,
                        u'worker_id': worker_id,
                        u'trace_id': trace_id,
                        u'type': msg_type,
                        u'uri': corr_uri,
                        u'origin': session_id,
                        u'targets': [],
                        u'completed': None
                    }
                else:
                    assert corr_uri == action_by_correlation[corr_id][u'uri']
                    action_type = action_by_correlation[corr_id][u'type']
                    if action_type == u'Publish':
                        assert msg_type == u'Event'
                        action_by_correlation[corr_id][u'targets'].append(
                            session_id)
                        if correlation_is_last:
                            action_by_correlation[corr_id][u'completed'] = pc
                            action_by_correlation[
                                corr_id][u'targets'] = sorted(
                                    action_by_correlation[corr_id][u'targets'])
                            on_action_complete(action_by_correlation[corr_id],
                                               completed % 20 == 0)
                            completed += 1
                            del action_by_correlation[corr_id]
                        continue
                    elif action_type == u'Call':
                        if msg_type == u'Yield':
                            action_by_correlation[corr_id][u'targets'].append(
                                session_id)
                            continue
                        elif msg_type in [u'Result', u'Error']:
                            action_by_correlation[corr_id][u'completed'] = pc
                            on_action_complete(action_by_correlation[corr_id],
                                               completed % 20 == 0)
                            completed += 1
                            del action_by_correlation[corr_id]
                            continue
                        else:
                            session.log.warn('should not arrive here [1]')
                    session.log.warn('should not arrive here [2]')

    await session.subscribe(
        on_trace_data,
        u'crossbarfabriccenter.remote.tracing.on_trace_data',
    )

    # start tracing on all router workers on all nodes
    started_traces = []
    nodes = await session.call(
        u'crossbarfabriccenter.mrealm.get_nodes', status=u'online')
    for node_id in nodes:
        workers = await session.call(
            u'crossbarfabriccenter.remote.node.get_workers', node_id)
        for worker_id in workers:
            worker = await session.call(
                u'crossbarfabriccenter.remote.node.get_worker', node_id,
                worker_id)

            if worker[u'type'] == u'router':

                # stop any currently running traces (we don't want to get data from orphaned traces)
                traces = await session.call(
                    u'crossbarfabriccenter.remote.tracing.get_traces', node_id,
                    worker_id)
                for trace_id in traces:
                    trace = await session.call(
                        u'crossbarfabriccenter.remote.tracing.get_trace',
                        node_id, worker_id, trace_id)
                    if trace[u'status'] == u'running':
                        stopped = await session.call(
                            u'crossbarfabriccenter.remote.tracing.stop_trace',
                            node_id, worker_id, trace_id)
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

                    # if true, also trace app payload (args/kwargs)
                    u'trace_app_payload': False,

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
