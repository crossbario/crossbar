###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ('RemoteTracingApi', )


class RemoteTracingApi(RemoteApi):

    # remote procedures and topics are exposed under this prefix
    PREFIX = u'crossbarfabriccenter.remote.tracing.'

    PROCS = {
        # these are worker level procedures
        u'worker': [
            u'get_traces',
            u'get_trace',
            u'start_trace',
            u'stop_trace',
            u'get_trace_data',
        ],
    }

    EVENTS = {
        # these are worker level topics
        u'worker': [
            u'on_trace_started',
            u'on_trace_stopped',
            u'on_trace_data',
        ]
    }
