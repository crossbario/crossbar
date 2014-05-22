###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

from __future__ import absolute_import

__all__ = ['NativeWorker']

import sys
import socket


try:
   import psutil
except ImportError:
   _HAS_PSUTIL = False
else:
   _HAS_PSUTIL = True


## http://pythonhosted.org/psutil/
## http://linux.die.net/man/5/proc


if _HAS_PSUTIL:

   class SystemInfo:
      """
      Access system global information and statistics.
      """

      def cpu(self):
         return {
            'physical_count': psutil.cpu_count(logical = False),
            'logical_count': psutil.cpu_count(logical = True)
         }

      def cpu_stats(self):
         """
         Returns CPU times per (logical) CPU.
         """
         res = []
         for c in psutil.cpu_times(percpu = True):
            res.append({
               'user': c.user,
               'system': c.system,
               'idle': c.idle
            })
         return res


      def net_stats(self):
         """
         Returns network I/O statistics per network interface.
         """
         res = {}
         ns = psutil.net_io_counters(pernic = True)
         for nic in ns.keys():
            stats = ns[nic]
            res[nic] = {
               'bytes_sent': stats.bytes_sent,
               'bytes_recv': stats.bytes_recv,
               'packets_sent': stats.packets_sent,
               'packets_recv': stats.packets_recv,
               'errin': stats.errin,
               'errout': stats.errout,
               'dropin': stats.dropin,
               'dropout': stats.dropout
            }
         return res



   class ProcessInfo:
      """
      Access process related information and statistics
      """

      _ADDRESS_TYPE_FAMILY_MAP = {
         (socket.AF_INET, socket.SOCK_STREAM): 'tcp4',
         (socket.AF_INET6, socket.SOCK_STREAM): 'tcp6',
         (socket.AF_INET, socket.SOCK_DGRAM): 'udp4',
         (socket.AF_INET6, socket.SOCK_DGRAM): 'udp6',
         (socket.AF_UNIX, socket.SOCK_STREAM): 'unix',
         (socket.AF_UNIX, socket.SOCK_DGRAM): 'unix'
      }

      def __init__(self):
         """
         Ctor.
         """
         self._p = psutil.Process()


      def cpu_stats(self):
         """
         """
         res = {}
         s = self._p.num_ctx_switches()
         c = self._p.cpu_times()
         m = self._p.memory_info()
         f = self._p.io_counters()
         res['voluntary'] = s[0]
         res['nonvoluntary'] = s[1]
         res['user'] = c.user
         res['system'] = c.system
         res['resident'] = m.rss
         res['virtual'] = m.vms
         res['reads'] = f.read_count
         res['writes'] = f.write_count
         return res


      def used_descriptors(self):
         """
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
            'files': len(self._p.open_files()),
            'sockets': len(self._p.connections(kind = 'all'))
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

         for c in self._p.connections(kind = 'all'):
            socket_type = ProcessInfo._ADDRESS_TYPE_FAMILY_MAP.get((c.family, c.type))
            if c.family == socket.AF_UNIX:
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
               'type': socket_type,
               'local': laddr,
               'remote': raddr,
               'status': status
            })
         return res



      def open_fds(self):
         """
         Returns files and sockets currently opened by this process.

         :returns: dict -- A dict with two lists.
         """
         res = {}
         res['sockets'] = self.open_sockets()
         res['files'] = self.open_files()
         return res
