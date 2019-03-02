#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

import os
from zlmdb import time_ns
import sys
import socket

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
            return {
                u'physical_count': psutil.cpu_count(logical=False),
                u'logical_count': psutil.cpu_count(logical=True)
            }

        def stats(self):
            """
            """
            res = {}
            res[u'ts'] = utcnow()
            res[u'cpu'] = self.cpu_stats()
            res[u'mem'] = self.mem_stats()
            res[u'net'] = self.net_stats()
            res[u'disk'] = self.disk_stats()
            return res

        def cpu_stats(self):
            """
            Returns CPU times per (logical) CPU.
            """
            res = {}
            i = 0
            for c in psutil.cpu_times(percpu=True):
                res[i] = {
                    u'user': c.user,
                    u'system': c.system,
                    u'idle': c.idle
                }
                i += 1
            return res

        def mem_stats(self):
            res = {}
            m = psutil.virtual_memory()
            res[u'total'] = m.total
            res[u'available'] = m.available
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
                    u'out': {
                        u'bytes': stats.bytes_sent,
                        u'packets': stats.packets_sent,
                        u'errors': stats.errout,
                        u'dropped': stats.dropout
                    },
                    u'in': {
                        u'bytes': stats.bytes_recv,
                        u'packets': stats.packets_recv,
                        u'errors': stats.errin,
                        u'dropped': stats.dropin
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
                    u'read': {
                        u'ops': stats.read_count,
                        u'bytes': stats.read_bytes,
                        u'time': stats.read_time
                    },
                    u'write': {
                        u'ops': stats.write_count,
                        u'bytes': stats.write_bytes,
                        u'time': stats.write_time
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
            res[u'ts'] = utcnow()
            res[u'time'] = time_ns()
            res[u'pid'] = self._pid

            s = self._p.num_ctx_switches()

            c = self._p.cpu_times()
            c_perc = self._p.cpu_percent()

            m = self._p.memory_info()
            m_perc = self._p.memory_percent()

            f = self._p.io_counters()

            # process status
            res[u'status'] = self._p.status()

            # context switches
            res[u'voluntary'] = s[0]
            res[u'nonvoluntary'] = s[1]

            # cpu
            res[u'user'] = c.user
            res[u'system'] = c.system
            res[u'cpu_percent'] = c_perc

            # memory
            res[u'resident'] = m.rss
            res[u'virtual'] = m.vms
            res[u'mem_percent'] = m_perc

            # disk
            res[u'reads'] = f.read_count
            res[u'writes'] = f.write_count
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
                u'descriptors': descriptors,
                u'threads': cnt_threads,
                u'files': self.open_files(),
                u'sockets': self.open_sockets()
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
                res.append({
                    u'type': socket_type,
                    u'local': laddr,
                    u'remote': raddr,
                    u'status': status
                })
            return res
