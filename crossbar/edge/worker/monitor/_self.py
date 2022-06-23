##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import time

import psutil

from crossbar.edge.worker.monitor._base import Monitor
from txaio import perf_counter_ns

__all__ = ('SelfMonitor', )


class SelfMonitor(Monitor):
    """
    Monitor the load induced by the monitoring (native worker) process itself.
    """

    ID = u'self'

    def __init__(self, config=None):
        Monitor.__init__(self, config)
        self._process = psutil.Process()

    def poll(self, sensors=[]):
        """
        Measure current stats value and return new stats.
        """
        hdata = Monitor.poll(self)

        start = perf_counter_ns()

        hdata['io_counters'] = self._process.io_counters()._asdict()
        hdata['cpu_times'] = self._process.cpu_times()._asdict()
        a = round(((self._process.cpu_times().user + self._process.cpu_times().system) * 100) /
                  (time.time() - self._process.create_time()), 3)
        hdata['percent'] = a

        for sensor in sensors:
            hdata[sensor.ID] = sensor._elapsed

        hdata[u'elapsed'] = perf_counter_ns() - start

        self._last_value = hdata

        return hdata
