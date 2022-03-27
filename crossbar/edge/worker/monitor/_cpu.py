##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import re
import psutil

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.utils import getProcessOutput

from autobahn.util import utcnow

from crossbar.edge.worker.monitor._base import Monitor

__all__ = ('CPUMonitor', )


class CPUMonitor(Monitor):
    """
    CPU load, frequency and temperature monitoring.
    """

    ID = u'cpu'

    # Physical id 3
    _PATH_SENSORS_PHYS_SOCKET_ID = re.compile(r"^Physical id (\d+)$")

    # Core 10
    _PATH_SENSORS_PHYS_CORE_ID = re.compile(r"^Core (\d+)$")

    def __init__(self, config=None):
        Monitor.__init__(self, config)

        self._cpu_last = None

        self._processors = {}
        self._sockets = []
        self._physid_to_id = {}
        self._id_to_physid = {}

        sockets = {}

        with open('/proc/cpuinfo', 'r') as fd:

            processor_id = None
            physical_socket_id = None
            physical_core_id = None

            for line in fd.readlines():

                line = line.strip()

                if line == "":
                    self._processors[processor_id] = (physical_socket_id, physical_core_id)
                    if physical_socket_id not in sockets:
                        sockets[physical_socket_id] = []
                    sockets[physical_socket_id].append(physical_core_id)
                else:
                    key, value = line.split(':')
                    key = key.strip()
                    value = value.strip()

                    if key == "processor":
                        processor_id = int(value)

                    elif key == "physical id":
                        physical_socket_id = int(value)

                    elif key == "core id":
                        physical_core_id = int(value)

        i = 0
        for pi in sorted(sockets.keys()):
            cores = []
            j = 0
            for pj in sorted(sockets[i]):
                cores.append(pj)
                self._physid_to_id[(pi, pj)] = (i, j)
                self._id_to_physid[(i, j)] = (pi, pj)
                j += 1
            self._sockets.append((pi, cores))
            i += 1

    @inlineCallbacks
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

            # readings per CPU socket
            u'sockets': []
        }

        # fill in per-socket/per-core structures
        #
        for i in range(len(self._sockets)):
            socket = {
                # sequentially numbered socket ID
                u'id': i,

                # physical socket ID
                u'physical_id': self._sockets[i][0],

                # CPU socket temperature
                u'temperature': None,

                # CPU cores on this socket
                u'cores': []
            }
            for j in range(len(self._sockets[i][1])):
                core = {
                    # sequentially numbered core ID
                    u'id': j,

                    # physical core ID on this socket
                    u'physical_id': self._sockets[i][1][j],

                    # CPU core load
                    u'user': None,
                    u'system': None,
                    u'nice': None,
                    u'idle': None,
                    u'iowait': None,
                    u'irq': None,
                    u'softirq': None,
                    u'steal': None,
                    u'total': None,

                    # CPU core frequency
                    u'frequency': None,

                    # CPU core temperature
                    u'temperature': None
                }
                socket[u'cores'].append(core)
            current[u'sockets'].append(socket)

        # get current CPU load (via psutil)
        #
        cpu_now = psutil.cpu_times(percpu=True)

        if not self._cpu_last:
            self._cpu_last = cpu_now
        else:
            for i in range(len(cpu_now)):

                socket_id, core_id = self._physid_to_id[self._processors[i]]

                core = current[u'sockets'][socket_id][u'cores'][core_id]

                digits = 8

                # CPU core load stats
                core[u'user'] = round(cpu_now[i].user - self._cpu_last[i].user, digits)
                core[u'system'] = round(cpu_now[i].system - self._cpu_last[i].system, digits)
                core[u'nice'] = round(cpu_now[i].nice - self._cpu_last[i].nice, digits)
                core[u'idle'] = round(cpu_now[i].idle - self._cpu_last[i].idle, digits)
                core[u'iowait'] = round(cpu_now[i].iowait - self._cpu_last[i].iowait, digits)
                core[u'irq'] = round(cpu_now[i].irq - self._cpu_last[i].irq, digits)
                core[u'softirq'] = round(cpu_now[i].softirq - self._cpu_last[i].softirq, digits)
                core[u'steal'] = round(cpu_now[i].steal - self._cpu_last[i].steal, digits)

                # total CPU core load (= user + nice + system)
                core[u'total'] = round((cpu_now[i].user + cpu_now[i].nice + cpu_now[i].system) -
                                       (self._cpu_last[i].user + self._cpu_last[i].nice + self._cpu_last[i].system),
                                       digits)

                # normalize with effective period
                diff = self._last_period or 1.
                for k in core:
                    if (k != 'id' and k != 'physical_id' and k != 'frequency' and k != 'temperature'):
                        core[k] = round(core[k] / diff, digits)

            self._cpu_last = cpu_now

        # get current CPU frequency (from procfs)
        #
        with open('/proc/cpuinfo', 'r') as fd:

            physical_socket_id = None
            physical_core_id = None
            frequency = None

            for line in fd.readlines():

                line = line.strip()

                if line == "":
                    socket_id, core_id = self._physid_to_id[(physical_socket_id, physical_core_id)]
                    core = current[u'sockets'][socket_id][u'cores'][core_id]
                    core[u'frequency'] = frequency
                else:
                    key, value = line.split(':')
                    key = key.strip()
                    value = value.strip()

                    if key == "physical id":
                        physical_socket_id = int(value)

                    elif key == "core id":
                        physical_core_id = int(value)

                    elif key == "cpu MHz":
                        frequency = float(value)

        # get current CPU temperature (via /usr/bin/sensors)
        #
        res = yield getProcessOutput('/usr/bin/sensors')

        physical_socket_id = None
        physical_core_id = None
        # socket_temperature = None
        core_temperature = -1

        for line in res.splitlines():

            line = line.strip()

            if line == "":
                pass
            else:
                if line.startswith("Physical"):
                    key, value = line.split(':')
                    match = self._PATH_SENSORS_PHYS_SOCKET_ID.match(key)
                    if match:
                        physical_socket_id = int(match.groups()[0])
                        value = value.strip()
                        # socket_temperature = float(value[1:5])

                elif line.startswith("Core"):
                    key, value = line.split(':')
                    match = self._PATH_SENSORS_PHYS_CORE_ID.match(key)
                    if match:
                        physical_core_id = int(match.groups()[0])
                        value = value.strip()
                        core_temperature = float(value[1:5])

                        socket_id, core_id = self._physid_to_id[(physical_socket_id, physical_core_id)]

                        core = current[u'sockets'][socket_id][u'cores'][core_id]
                        core[u'temperature'] = core_temperature

        self._last_value = current

        returnValue(self._last_value)
