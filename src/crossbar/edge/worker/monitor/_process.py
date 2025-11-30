##############################################################################
#
#                        Crossbar.io
#     Copyright (C) typedef int GmbH. All rights reserved.
#
##############################################################################

import datetime
import time

import psutil
from autobahn.util import utcnow, utcstr
from twisted.internet.threads import deferToThread

from crossbar.edge.worker.monitor._base import Monitor


class ProcessMonitor(Monitor):
    ID = "process"

    def __init__(self, config=None):
        Monitor.__init__(self, config)

        # Map of process types.
        self._ptypes = self._config.get("process_types", {})

        # Process type to map otherwise unmapped processes to.
        self._ptype_unassigned = self._config.get("process_type_unassigned", "unassigned")

        # Filter processes by these types.
        filter_ptypes = self._config.get("filter_process_types", None)
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
            "timestamp": utcnow(),
            # the effective last period in secods
            "last_period": self._last_period,
            # actual process statistics
            "processes": {},
        }

        # normalize with effective period
        diff = self._last_period or 1.0

        cmd_started = time.time()

        for proc in psutil.process_iter():
            pinfo = {}
            try:
                # map process executable to (user defined) process type
                #
                proc_id = hash(proc) % (2**53)  # JavaScript represent numbers as IEEE double!
                pinfo["exe"] = proc.exe()
                pinfo["type"] = self._ptypes.get(pinfo["exe"], self._ptype_unassigned)

                # if no filtering by process type is active OR if the process type is in
                # the filter list, do the thing ..
                #
                if self._filter_ptypes is None or pinfo["type"] in self._filter_ptypes:
                    pinfo["id"] = proc_id
                    pinfo["pid"] = proc.pid
                    pinfo["user"] = proc.username()
                    pinfo["status"] = proc.status()
                    pinfo["name"] = proc.name()
                    pinfo["cmdline"] = " ".join(proc.cmdline())

                    created = proc.create_time()
                    pinfo["created"] = utcstr(datetime.datetime.fromtimestamp(created))

                    pinfo["num_fds"] = proc.num_fds()
                    pinfo["num_threads"] = proc.num_threads()
                    pinfo["num_fds"] = proc.num_fds()

                    # the following values are cumulative since process creation!
                    #
                    num_ctx_switches = proc.num_ctx_switches()
                    pinfo["num_ctx_switches_voluntary"] = num_ctx_switches.voluntary
                    pinfo["num_ctx_switches_involuntary"] = num_ctx_switches.involuntary

                    iocounters = proc.io_counters()
                    pinfo["read_ios"] = iocounters.read_count
                    pinfo["write_ios"] = iocounters.write_count
                    pinfo["read_bytes"] = iocounters.read_bytes
                    pinfo["write_bytes"] = iocounters.write_bytes

                    cpu = proc.cpu_times()
                    pinfo["cpu_user"] = cpu.user
                    pinfo["cpu_system"] = cpu.system

                    current["processes"][proc_id] = pinfo

            except psutil.NoSuchProcess:
                pass

        current["command_duration"] = time.time() - cmd_started

        if self._last_value:
            for proc_id in current["processes"]:
                if proc_id in self._last_value["processes"]:
                    proc = current["processes"][proc_id]
                    last = self._last_value["processes"][proc_id]
                    for key in [
                        "read_ios",
                        "write_ios",
                        "read_bytes",
                        "write_bytes",
                        "cpu_user",
                        "cpu_system",
                        "num_ctx_switches_voluntary",
                        "num_ctx_switches_involuntary",
                    ]:
                        proc["{}_per_sec".format(key)] = float(proc[key] - last[key]) / diff
                else:
                    # should not arrive here!
                    pass
            self._last_value = current
            return current
        else:
            self._last_value = current
            return None
