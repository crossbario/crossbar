###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ("RemoteWorkerApi",)


class RemoteWorkerApi(RemoteApi):
    PREFIX = "crossbarfabriccenter.remote.worker."

    PROCS = {
        # these are worker level procedures
        "worker": [
            "shutdown",
            "get_status",
            "get_pythonpath",
            "add_pythonpath",
            "get_cpu_affinity",
            "set_cpu_affinity",
            "get_profilers",
            "start_profiler",
            "get_profile",
            "get_process_info",
            "get_process_stats",
            "set_process_stats_monitoring",
        ],
    }

    EVENTS = {
        # these are worker level topics
        "worker": [
            "on_worker_log",
            "on_profile_started",
            "on_profile_finished",
        ]
    }
