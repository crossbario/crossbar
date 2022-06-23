##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import time
import datetime
import psutil

from twisted.internet.threads import deferToThread

from autobahn.util import utcnow, utcstr

from crossbar.edge.worker.monitor._base import Monitor


class ProcessMonitor(Monitor):

    ID = u'process'

    def __init__(self, config=None):
        Monitor.__init__(self, config)

        # Map of process types.
        self._ptypes = self._config.get(u'process_types', {})

        # Process type to map otherwise unmapped processes to.
        self._ptype_unassigned = self._config.get(u'process_type_unassigned', u'unassigned')

        # Filter processes by these types.
        filter_ptypes = self._config.get(u'filter_process_types', None)
        self._filter_ptypes = set(filter_ptypes) if filter_ptypes else None

    def poll(self):
        """
        Measure current stats value and return new stats.
        """
        Monitor.poll(self)
        return deferToThread(self._poll)

    def _poll(self):

        # create new, empty event
        #
        current = {
            # the UTC timestamp when measurement was taken
            u'timestamp': utcnow(),

            # the effective last period in secods
            u'last_period': self._last_period,

            # actual process statistics
            u'processes': {}
        }

        # normalize with effective period
        diff = self._last_period or 1.

        cmd_started = time.time()

        for proc in psutil.process_iter():
            pinfo = {}
            try:
                # map process executable to (user defined) process type
                #
                proc_id = hash(proc) % (2**53)  # JavaScript represent numbers as IEEE double!
                pinfo[u'exe'] = proc.exe()
                pinfo[u'type'] = self._ptypes.get(pinfo[u'exe'], self._ptype_unassigned)

                # if no filtering by process type is active OR if the process type is in
                # the filter list, do the thing ..
                #
                if self._filter_ptypes is None or pinfo[u'type'] in self._filter_ptypes:

                    pinfo[u'id'] = proc_id
                    pinfo[u'pid'] = proc.pid
                    pinfo[u'user'] = proc.username()
                    pinfo[u'status'] = proc.status()
                    pinfo[u'name'] = proc.name()
                    pinfo[u'cmdline'] = u' '.join(proc.cmdline())

                    created = proc.create_time()
                    pinfo[u'created'] = utcstr(datetime.datetime.fromtimestamp(created))

                    pinfo[u'num_fds'] = proc.num_fds()
                    pinfo[u'num_threads'] = proc.num_threads()
                    pinfo[u'num_fds'] = proc.num_fds()

                    # the following values are cumulative since process creation!
                    #
                    num_ctx_switches = proc.num_ctx_switches()
                    pinfo[u'num_ctx_switches_voluntary'] = num_ctx_switches.voluntary
                    pinfo[u'num_ctx_switches_involuntary'] = num_ctx_switches.involuntary

                    iocounters = proc.io_counters()
                    pinfo[u'read_ios'] = iocounters.read_count
                    pinfo[u'write_ios'] = iocounters.write_count
                    pinfo[u'read_bytes'] = iocounters.read_bytes
                    pinfo[u'write_bytes'] = iocounters.write_bytes

                    cpu = proc.cpu_times()
                    pinfo[u'cpu_user'] = cpu.user
                    pinfo[u'cpu_system'] = cpu.system

                    current[u'processes'][proc_id] = pinfo

            except psutil.NoSuchProcess:
                pass

        current[u'command_duration'] = time.time() - cmd_started

        if self._last_value:
            for proc_id in current[u'processes']:
                if proc_id in self._last_value[u'processes']:
                    proc = current[u'processes'][proc_id]
                    last = self._last_value[u'processes'][proc_id]
                    for key in [
                            u'read_ios', u'write_ios', u'read_bytes', u'write_bytes', u'cpu_user', u'cpu_system',
                            u'num_ctx_switches_voluntary', u'num_ctx_switches_involuntary'
                    ]:
                        proc[u'{}_per_sec'.format(key)] = float(proc[key] - last[key]) / diff
                else:
                    # should not arrive here!
                    pass
            self._last_value = current
            return current
        else:
            self._last_value = current
            return None
