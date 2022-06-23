##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from autobahn.util import utcnow

from crossbar.edge.worker.monitor._base import Monitor

__all__ = ('IOMonitor', )


class IOMonitor(Monitor):
    """
    IO monitoring. This is using Linux procfs to get measurements.
    """

    ID = u'diskio'

    def __init__(self, config=None):
        Monitor.__init__(self, config)

        self._storage = self._config.get(u'storage', [])

        # flat list of block devices
        #
        self._devices = []
        for subsystem in self._storage:
            for device, _ in subsystem['devices']:
                self._devices.append(device)

        # map indexed by device holding last raw (cumulative) values
        self._last = {}

        # map indexed by device holding last values (since previous sample)
        self._values = {}

        for device in self._devices:
            self._last[device] = None
            self._values[device] = None

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

            # storage subsystem measurements
            u'subsystems': []
        }

        # normalize with effective period
        diff = self._last_period or 1.

        # get IO stats per device from procfs (/sys/block/<device>/stat)
        # see: https://www.kernel.org/doc/Documentation/block/stat.txt
        #
        for device in self._devices:
            with open('/sys/block/{}/stat'.format(device)) as fd:
                res = fd.read()

                new = [int(s.strip()) for s in res.split()]

                if not self._last[device]:
                    self._last[device] = new

                last = self._last[device]

                self._values[device] = {
                    u'read_ios': int((new[0] - last[0]) / diff),
                    u'read_merges': int((new[1] - last[1]) / diff),
                    u'read_bytes': int(512 * (new[2] - last[2]) / diff),
                    u'read_ticks': int((new[3] - last[3]) / diff),
                    u'write_ios': int((new[4] - last[4]) / diff),
                    u'write_merges': int((new[5] - last[5]) / diff),
                    u'write_bytes': int(512 * (new[6] - last[6]) / diff),
                    u'write_ticks': int((new[7] - last[7]) / diff),
                    u'in_flight': new[8],
                    u'io_ticks': int((new[9] - last[9]) / diff),
                    u'time_in_queue': int((new[10] - last[10]) / diff)
                }

                self._last[device] = new

        # transform raw measurements into target event structure
        #
        for subsys in self._storage:
            subsystem = {u'id': subsys[u'id'], u'devices': []}

            for device_id, device_label in subsys[u'devices']:
                values = self._values[device_id]
                device = {
                    u'id': device_id,
                    u'type': device_label,
                    u'read_ios': values['read_ios'],
                    u'read_bytes': values['read_bytes'],
                    u'read_ms': values['read_ticks'],
                    u'write_ios': values['write_ios'],
                    u'write_bytes': values['write_bytes'],
                    u'write_ms': values['write_ticks'],
                    u'in_flight': values['in_flight'],
                    u'active_ms': values['io_ticks'],
                    u'wait_ms': values['time_in_queue'],
                }
                subsystem[u'devices'].append(device)

            current[u'subsystems'].append(subsystem)

        self._last_value = current

        return self._last_value
