##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import psutil

from crossbar.edge.worker.monitor._base import Monitor
from txaio import perf_counter_ns

__all__ = ('NetMonitor', )


class NetMonitor(Monitor):
    """
    Network monitoring via psutils.
    """

    ID = u'network'

    def poll(self):
        """
        Measure current stats value and return new stats.
        """
        hdata = Monitor.poll(self)

        start = perf_counter_ns()

        counters = {}
        io_counters = psutil.net_io_counters(True)
        for dev in io_counters:
            if dev.startswith('virbr') or dev.startswith('lo') or dev.startswith('docker'):
                continue
            counters[dev] = io_counters[dev]._asdict()

        hdata['net_io_counters'] = counters
        hdata['net_if_addrs'] = psutil.net_if_addrs()

        hdata[u'elapsed'] = perf_counter_ns() - start

        self._last_value = hdata

        return hdata
