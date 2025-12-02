###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ("RemoteTracingApi",)


class RemoteTracingApi(RemoteApi):
    # remote procedures and topics are exposed under this prefix
    PREFIX = "crossbarfabriccenter.remote.tracing."

    PROCS = {
        # these are worker level procedures
        "worker": [
            "get_traces",
            "get_trace",
            "start_trace",
            "stop_trace",
            "get_trace_data",
        ],
    }

    EVENTS = {
        # these are worker level topics
        "worker": [
            "on_trace_started",
            "on_trace_stopped",
            "on_trace_data",
        ]
    }
