###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ('RemoteWorkerApi', )


class RemoteWorkerApi(RemoteApi):

    PREFIX = u'crossbarfabriccenter.remote.worker.'

    PROCS = {
        # these are worker level procedures
        u'worker': [
            u'shutdown',
            u'get_status',
            u'get_pythonpath',
            u'add_pythonpath',
            u'get_cpu_affinity',
            u'set_cpu_affinity',
            u'get_profilers',
            u'start_profiler',
            u'get_profile',
            u'get_process_info',
            u'get_process_stats',
            u'set_process_stats_monitoring',
        ],
    }

    EVENTS = {
        # these are worker level topics
        u'worker': [
            u'on_worker_log',
            u'on_profile_started',
            u'on_profile_finished',
        ]
    }
