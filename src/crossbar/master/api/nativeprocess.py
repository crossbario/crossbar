###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from typing import Dict, List  # noqa

from crossbar.master.api.remote import RemoteApi

__all__ = ("RemoteNativeProcessApi",)


class RemoteNativeProcessApi(RemoteApi):
    """
    Remote API to CF native node processes:

    * node controller
    * router worker
    * container worker
    * proxy worker
    """

    PREFIX = "crossbarfabriccenter.remote.nativeprocess."

    PROCS = {
        # these are node level procedures
        "node": [
            "get_cpu_count",
            "get_cpu_affinity",
            "set_cpu_affinity",
            "get_process_info",
            "get_process_stats",
            "set_process_stats_monitoring",
            "get_process_monitor",
            "trigger_gc",
            "start_manhole",
            "stop_manhole",
            "get_manhole",
        ],
    }

    EVENTS = {
        # these are node level topics
        "node": []
    }  # type: Dict[str, List]
