##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import os
import psutil

from crossbar.edge.worker.monitor._base import Monitor
from txaio import perf_counter_ns

__all__ = ('SystemMonitor', )


class SystemMonitor(Monitor):
    """
    System monitoring via psutils.
    """

    ID = u'system'

    def poll(self):
        hdata = Monitor.poll(self)

        start = perf_counter_ns()

        hdata['cpu'] = psutil.cpu_times_percent()._asdict()
        hdata['memory'] = psutil.virtual_memory()._asdict()
        hdata['loadavg'] = os.getloadavg()

        # uptime, as all durations, is in ns
        hdata['uptime'] = int(hdata['timestamp'] - psutil.boot_time() * 10**10)

        hdata[u'elapsed'] = perf_counter_ns() - start

        self._last_value = hdata

        return hdata
