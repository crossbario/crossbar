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

import sys
import datetime
import psutil

from twisted.internet.threads import deferToThread
from twisted.internet.defer import inlineCallbacks, returnValue

from autobahn.util import utcstr

from txaio import make_logger
from zlmdb import time_ns

from crossbar.common.checkconfig import check_dict_args


__all__ = ('ProcessMonitor', 'SystemMonitor')


class Monitor(object):
    """
    Monitor base class.
    """

    ID = 'abstract'
    """
    Sensor ID, must defined in derived class.
    """

    log = make_logger()

    def __init__(self, config=None):
        """

        :param config: Submonitor specific configuration.
        :type config: dict or None
        """
        # submonitor specific configuration
        self._config = config

        # incremented on each poll
        self._tick = 0

        # time of last poll: ns Unix time UTC
        self._last_poll = None

        # effective period corresponding to last poll in ns
        self._last_period = None

        # last polled value
        self._last_value = None

        # total elapsed CPU time in ns reading this sensor
        self._elapsed = 0

    def check(self, config):
        """
        Check submonitor configuration item.

        Override in your derived submonitor class.

        Raise a `crossbar.common.checkconfig.InvalidConfigException` exception
        when you find an error in the item configuration.

        :param config: The submonitor configuration item to check.
        :type config: dict
        """
        check_dict_args({}, config, '{} monitor configuration'.format(self.ID))

    def poll(self):
        """
        Measure current stats value and return new stats.

        Override in your derived submonitor class.

        :returns: Current stats from monitor.
        :rtype: dict
        """
        self._tick += 1

        now = time_ns()
        if self._last_poll:
            self._last_period = now - self._last_poll

        current = {
            'tick': self._tick,

            # the UTC timestamp when measurement was taken
            'timestamp': now,

            # the effective last period in ns
            'last_period': self._last_period,

            # duration in seconds the retrieval of sensor values took
            'elapsed': self._elapsed,
        }

        self._last_poll = now
        self._last_value = current

        return current

    def get(self, details=None):
        """
        Get last stats/mesasurement values.

        Usually, there is no need to override this in a derived submonitor, as
        the default implementation already handles storing and returning the
        last submonitor reading.

        :returns: Last stats/values from monitor.
        :rtype: dict or None (when not yet polled)
        """
        self.log.info('{klass}.get(details={})', klass=self.__class__.__name__, details=details)
        return self._last_value


class ProcessMonitor(Monitor):

    ID = 'process'

    def __init__(self, worker_type, config):
        Monitor.__init__(self, config)
        self._p = psutil.Process()
        self._worker_type = worker_type

        self._has_io_counters = False
        if not sys.platform.startswith('darwin'):
            try:
                self._p.io_counters()
                self._has_io_counters = True
            except psutil.AccessDenied:
                pass

    @inlineCallbacks
    def poll(self, verbose=False):
        """
        Measure current stats value and return new stats.

        :returns: A deferred that resolves with a dict containing new process statistics.
        :rtype: :class:`twisted.internet.defer.Deferred`
        """
        self._tick += 1

        now = time_ns()
        if self._last_poll:
            self._last_period = now - self._last_poll

        if verbose:
            _current = {
                'tick': self._tick,

                # the UTC timestamp when measurement was taken
                'timestamp': now,

                # the effective last period in ns
                'last_period': self._last_period,

                # duration in seconds the retrieval of sensor values took
                'elapsed': self._elapsed,
            }
        else:
            _current = {}

        def _poll(current, last_value):

            # normalize with effective period
            diff = 1.
            if self._last_period:
                diff = self._last_period / 10**9

            # cmd_started = time.time()

            current['type'] = self._worker_type
            current['pid'] = self._p.pid
            current['status'] = self._p.status()

            if verbose:
                current['exe'] = self._p.exe()
                current['user'] = self._p.username()
                current['name'] = self._p.name()
                current['cmdline'] = ' '.join(self._p.cmdline())
                created = self._p.create_time()
                current['created'] = utcstr(datetime.datetime.fromtimestamp(created))

            current['num_fds'] = self._p.num_fds()
            current['num_threads'] = self._p.num_threads()
            current['num_fds'] = self._p.num_fds()

            # the following values are cumulative since process creation!
            #
            num_ctx_switches = self._p.num_ctx_switches()
            current['num_ctx_switches_voluntary'] = num_ctx_switches.voluntary
            current['num_ctx_switches_involuntary'] = num_ctx_switches.involuntary

            if self._has_io_counters:
                iocounters = self._p.io_counters()
                current['read_ios'] = iocounters.read_count
                current['write_ios'] = iocounters.write_count
                current['read_bytes'] = iocounters.read_bytes
                current['write_bytes'] = iocounters.write_bytes
            else:
                current['read_ios'] = None
                current['write_ios'] = None
                current['read_bytes'] = None
                current['write_bytes'] = None

            cpu = self._p.cpu_times()
            current['cpu_user'] = cpu.user
            current['cpu_system'] = cpu.system

            # current['command_duration'] = time.time() - cmd_started

            for key in [
                'read_ios', 'write_ios', 'read_bytes', 'write_bytes', 'cpu_user',
                'cpu_system', 'num_ctx_switches_voluntary', 'num_ctx_switches_involuntary'
            ]:
                if last_value and last_value[key] is not None:
                    value = float(current[key] - last_value[key]) / diff
                    current['{}_per_sec'.format(key)] = int(value)

            return current

        new_value = yield deferToThread(_poll, _current, self._last_value)

        self._last_poll = now
        self._last_value = new_value

        returnValue(new_value)


class SystemMonitor(Monitor):
    """
    System monitoring via psutils.
    """

    ID = 'system'

    @inlineCallbacks
    def poll(self, verbose=False):
        """
        Measure current stats value and return new stats.

        :returns: A deferred that resolves with a dict containing new process statistics.
        :rtype: :class:`twisted.internet.defer.Deferred`
        """
        self._tick += 1

        now = time_ns()
        if self._last_poll:
            self._last_period = now - self._last_poll

        if verbose:
            _current = {
                'tick': self._tick,

                # the UTC timestamp when measurement was taken
                'timestamp': now,

                # the effective last period in ns
                'last_period': self._last_period,

                # duration in seconds the retrieval of sensor values took
                'elapsed': self._elapsed,
            }
        else:
            _current = {}

        # uptime, as all durations, is in ns
        _current['uptime'] = int(now - psutil.boot_time() * 10**9)

        def _poll(current, last_value):

            # normalize with effective period
            diff = 1.
            if self._last_period:
                diff = self._last_period / 10**9

            # int values: bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout
            current['network'] = dict(psutil.net_io_counters()._asdict())

            # int values: read_count, write_count, read_bytes, write_bytes, read_time, write_time, read_merged_count, write_merged_count, busy_time
            current['disk'] = dict(psutil.disk_io_counters()._asdict())

            if last_value:
                for k in ['network', 'disk']:
                    d = current[k]
                    for k2 in list(d.keys()):
                        value = float(d[k2] - last_value[k][k2]) / diff
                        d['{}_per_sec'.format(k2)] = int(value)

            # float values: user, nice, system, idle, iowait, irq, softirq, streal, guest, guest_nice
            current['cp'] = dict(psutil.cpu_times_percent(interval=None)._asdict())

            cpu_freq = psutil.cpu_freq()
            current['cp']['freq'] = round(cpu_freq.current) if cpu_freq else None
            s = psutil.cpu_stats()
            current['cp']['ctx_switches'] = s.ctx_switches
            current['cp']['interrupts'] = s.interrupts
            current['cp']['soft_interrupts'] = s.soft_interrupts

            # int values: total, available, used, free, active, inactive, buffers, cached, shared, slab
            # float values: percent
            current['memory'] = dict(psutil.virtual_memory()._asdict())

            # Network connections
            res = {}
            conns = psutil.net_connections(kind='all')
            for c in conns:
                if c.family not in res:
                    res[c.family] = 0
                res[c.family] += 1
            res2 = {}
            for f, cnt in res.items():
                res2[f.name] = cnt
            current['network']['connection'] = res2

            return current

        new_value = yield deferToThread(_poll, _current, self._last_value)

        self._elapsed = time_ns() - now
        new_value['elapsed'] = self._elapsed

        self._last_poll = now
        self._last_value = new_value

        returnValue(new_value)
