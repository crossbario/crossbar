##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from twisted.internet.defer import succeed
from autobahn.util import utcnow

from crossbar.edge.worker.monitor._base import Monitor

__all__ = ('MemoryMonitor', )


class MemoryMonitor(Monitor):
    """
    RAM monitoring.
    """

    ID = u'memory'

    def __init__(self, config=None):
        Monitor.__init__(self, config)

    def poll(self):
        """
        Measure current stats value and return new stats.
        """
        Monitor.poll(self)

        # create new, empty event
        #
        current = {
            # the UTC timestamp when measurement was taken
            u'timestamp': utcnow(),

            # the effective last period in secods
            u'last_period': self._last_period,
        }

        # FIXME: add ratio of ram usage

        with open("/proc/meminfo") as f:
            res = f.read()
            new = res.split()
            new_clean = [x.replace(":", "") for x in new if x != 'kB']
            for i in range(0, len(new_clean), 2):
                k = u'{}'.format(new_clean[i])
                current[k] = int(new_clean[i + 1])

        self._last_value = current

        return succeed(self._last_value)
