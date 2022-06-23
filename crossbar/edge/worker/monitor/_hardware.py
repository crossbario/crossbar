##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import psutil

from crossbar.edge.worker.monitor._base import Monitor
from txaio import perf_counter_ns

__all__ = ('HWMonitor', )


class HWMonitor(Monitor):
    """
    Hardware monitoring. This monitor is reading hardware sensor data via psutil.
    """

    ID = u'hardware'

    def poll(self):
        """
        Measure current stats value and return new stats.
        """
        hdata = Monitor.poll(self)

        start = perf_counter_ns()

        battery = None
        bat = psutil.sensors_battery()
        if bat:
            battery = bat._asdict()

        fans = []
        for key, val in (psutil.sensors_fans() or {}).items():
            for item in val:
                item = item._asdict()
                item['device'] = key
                fans.append(item)

        temperatures = []
        for key, val in (psutil.sensors_temperatures() or {}).items():
            for item in val:
                item = item._asdict()
                item['device'] = key
                temperatures.append(item)

        hdata['battery'] = battery
        hdata['fans'] = fans
        hdata['temperatures'] = temperatures

        hdata[u'elapsed'] = perf_counter_ns() - start

        self._last_value = hdata

        return hdata
