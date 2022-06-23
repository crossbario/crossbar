#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import sys
import socket

from txaio import time_ns
from autobahn.util import utcnow

try:
    import psutil
except ImportError:
    _HAS_PSUTIL = False
else:
    _HAS_PSUTIL = True

__all__ = ('SystemInfo', 'ProcessInfo')

# http://pythonhosted.org/psutil/
# http://linux.die.net/man/5/proc

if _HAS_PSUTIL:

    if sys.platform.startswith("win"):
        _HAS_AF_UNIX = False
    else:
        _HAS_AF_UNIX = True

    class SystemInfo:
        """
        Access system global information and statistics.
        """
        def __init__(self):
            """
            """

        def cpu(self):
            return {'physical_count': psutil.cpu_count(logical=False), 'logical_count': psutil.cpu_count(logical=True)}

        def stats(self):
            """
            """
            res = {}
            res['ts'] = utcnow()
            res['cpu'] = self.cpu_stats()
            res['mem'] = self.mem_stats()
            res['net'] = self.net_stats()
            res['disk'] = self.disk_stats()
            return res

        def cpu_stats(self):
            """
            Returns CPU times per (logical) CPU.
            """
            res = {}
            i = 0
            for c in psutil.cpu_times(percpu=True):
                res[i] = {'user': c.user, 'system': c.system, 'idle': c.idle}
                i += 1
            return res

        def mem_stats(self):
            res = {}
            m = psutil.virtual_memory()
            res['total'] = m.total
            res['available'] = m.available
            return res

        def net_stats(self):
            """
            Returns network I/O statistics per network interface.
            """
            res = {}
            ns = psutil.net_io_counters(pernic=True)
            for nic in ns.keys():
                stats = ns[nic]
                res[nic] = {
                    'out': {
                        'bytes': stats.bytes_sent,
                        'packets': stats.packets_sent,
                        'errors': stats.errout,
                        'dropped': stats.dropout
                    },
                    'in': {
                        'bytes': stats.bytes_recv,
                        'packets': stats.packets_recv,
                        'errors': stats.errin,
                        'dropped': stats.dropin
                    }
                }
            return res

        def disk_stats(self):
            """
            Returns disk I/O statistics per disk.
            """
            res = {}
            ds = psutil.disk_io_counters(perdisk=True)
            for disk in ds.keys():
                stats = ds[disk]
                res[disk] = {
                    'read': {
                        'ops': stats.read_count,
                        'bytes': stats.read_bytes,
                        'time': stats.read_time
                    },
                    'write': {
                        'ops': stats.write_count,
                        'bytes': stats.write_bytes,
                        'time': stats.write_time
                    }
                }
            return res

    class ProcessInfo(object):
        """
        Access process related information and statistics
        """
        _ADDRESS_TYPE_FAMILY_MAP = {
            (socket.AF_INET, socket.SOCK_STREAM): 'tcp4',
            (socket.AF_INET6, socket.SOCK_STREAM): 'tcp6',
            (socket.AF_INET, socket.SOCK_DGRAM): 'udp4',
            (socket.AF_INET6, socket.SOCK_DGRAM): 'udp6',
        }

        if _HAS_AF_UNIX:
            _ADDRESS_TYPE_FAMILY_MAP.update({
                (socket.AF_UNIX, socket.SOCK_STREAM): 'unix',
                (socket.AF_UNIX, socket.SOCK_DGRAM): 'unix'
            })

        def __init__(self, pid=None):
            """

            :param pid: Optional PID, if given, track info/stats for
                the given PID, otherwise track the current process.
            :type pid: int
            """
            self._pid = pid or os.getpid()
            self._p = psutil.Process(self._pid)
            if hasattr(self._p, 'cpu_affinity'):
                self._cpus = sorted(self._p.cpu_affinity())
            else:
                # osx lacks CPU process affinity altogether, and
                # only has thread affinity (since osx 10.5)
                # => if you can't make it, fake it;)
                # https://superuser.com/questions/149312/how-to-set-processor-affinity-on-os-x
                import multiprocessing
                self._cpus = list(range(multiprocessing.cpu_count()))

        @property
        def cpus(self):
            return self._cpus

        def get_stats(self):
            """
            Get process statistics.
            """
            res = {}
            res['ts'] = utcnow()
            res['time'] = time_ns()
            res['pid'] = self._pid

            s = self._p.num_ctx_switches()

            c = self._p.cpu_times()
            c_perc = self._p.cpu_percent()

            m = self._p.memory_info()
            m_perc = self._p.memory_percent()

            f = self._p.io_counters()

            # process status
            res['status'] = self._p.status()

            # context switches
            res['voluntary'] = s[0]
            res['nonvoluntary'] = s[1]

            # cpu
            res['user'] = c.user
            res['system'] = c.system
            res['cpu_percent'] = c_perc

            # memory
            res['resident'] = m.rss
            res['virtual'] = m.vms
            res['mem_percent'] = m_perc

            # disk
            res['reads'] = f.read_count
            res['writes'] = f.write_count
            return res

        def get_info(self):
            """
            Gets process information.
            """
            descriptors = None
            try:
                if sys.platform.startswith('win'):
                    descriptors = self._p.num_handles()
                else:
                    descriptors = self._p.num_fds()
            except:
                pass
            cnt_threads = self._p.num_threads()
            res = {
                'descriptors': descriptors,
                'threads': cnt_threads,
                'files': self.open_files(),
                'sockets': self.open_sockets()
            }
            return res

        def open_files(self):
            """
            Returns list of files currently opened by this process.

            :returns: list -- List of files (sorted by path ascending).
            """
            res = [f.path for f in self._p.open_files()]
            return sorted(res)

        def open_sockets(self):
            """
            Returns list of open sockets currently opened by this process.

            :returns: list -- List of dicts with socket information.
            """
            res = []

            for c in self._p.connections(kind='all'):
                socket_type = ProcessInfo._ADDRESS_TYPE_FAMILY_MAP.get((c.family, c.type))
                if _HAS_AF_UNIX and c.family == socket.AF_UNIX:
                    laddr = c.laddr
                    raddr = ""
                else:
                    laddr = "{}:{}".format(c.laddr[0], c.laddr[1])
                    if c.raddr and len(c.raddr) == 2:
                        raddr = "{}:{}".format(c.raddr[0], c.raddr[1])
                    else:
                        raddr = ""
                status = str(c.status)
                res.append({'type': socket_type, 'local': laddr, 'remote': raddr, 'status': status})
            return res
