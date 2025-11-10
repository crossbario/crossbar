###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ("RemoteNodeApi",)


class RemoteNodeApi(RemoteApi):
    """
    Remote API to CF node controller.
    """

    PREFIX = "crossbarfabriccenter.remote.node."

    PROCS = {
        # these are node level procedures
        u'node': [
            u'get_cpu_count',
            u'get_cpu_affinity',
            u'set_cpu_affinity',
            u'get_process_info',
            u'get_process_stats',
            u'set_process_stats_monitoring',
            u'trigger_gc',
            u'start_manhole',
            u'stop_manhole',
            u'get_manhole',
            u'get_status',
            u'get_system_stats',
            u'shutdown',
            u'get_worker_log',
            u'get_workers',
            u'get_worker',
            u'start_worker',
            u'stop_worker',
        ],
    }  # yapf: disable

    EVENTS = {
        # these are node level topics
        "node": [
            "on_node_starting",
            "on_node_started",
            "on_node_heartbeat",
            "on_node_stopping",
            "on_node_stopped",
            "on_router_starting",
            "on_router_started",
            "on_container_starting",
            "on_container_started",
            "on_guest_starting",
            "on_guest_started",
            "on_proxy_starting",
            "on_proxy_started",
            "on_xbrmm_starting",
            "on_xbrmm_started",
        ],
    }
