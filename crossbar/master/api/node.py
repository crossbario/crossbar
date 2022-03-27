###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ('RemoteNodeApi', )


class RemoteNodeApi(RemoteApi):
    """
    Remote API to CF node controller.
    """

    PREFIX = u'crossbarfabriccenter.remote.node.'

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
        u'node': [
            u'on_node_starting',
            u'on_node_started',
            u'on_node_heartbeat',
            u'on_node_stopping',
            u'on_node_stopped',
            u'on_router_starting',
            u'on_router_started',
            u'on_container_starting',
            u'on_container_started',
            u'on_guest_starting',
            u'on_guest_started',
            u'on_proxy_starting',
            u'on_proxy_started',
            u'on_xbrmm_starting',
            u'on_xbrmm_started',
        ],
    }
