##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import psutil

from crossbar.edge.worker.monitor._base import Monitor
from txaio import perf_counter_ns

__all__ = ('StorageMonitor', )


class StorageMonitor(Monitor):
    """
    Storage and disk IO monitoring via psutils.
    """

    ID = u'storage'

    def poll(self):
        """
        Measure current stats value and return new stats.
        """
        hdata = Monitor.poll(self)

        start = perf_counter_ns()

        devices = {}
        usage = {}
        counters = psutil.disk_io_counters(True)
        for dev in psutil.disk_partitions():
            if dev.device.startswith('/dev/loop'):
                continue
            key = dev.device.split('/')[-1]
            if key not in devices:
                if key in counters:
                    devices[key] = dict(dev._asdict(), **counters[key]._asdict())
                else:
                    devices[key] = dev._asdict()
                usage[key] = psutil.disk_usage(dev.mountpoint)._asdict()

        hdata['devices'] = devices
        hdata['usage'] = usage

        hdata[u'elapsed'] = perf_counter_ns() - start

        self._last_value = hdata

        return hdata
