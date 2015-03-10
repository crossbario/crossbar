#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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

from datetime import datetime
from collections import deque

from twisted.python import log
from twisted.internet.defer import Deferred

from autobahn.util import utcnow

__all__ = ('RouterWorkerProcess',
           'ContainerWorkerProcess',
           'GuestWorkerProcess')


class WorkerProcess:

    """
    Internal run-time representation of a worker process.
    """

    TYPE = 'worker'
    LOGNAME = 'Worker'

    def __init__(self, controller, id, who, keeplog=None):
        """
        Ctor.

        :param controller: The node controller this worker was created by.
        :type controller: instance of NodeControllerSession
        :param id: The ID of the worker.
        :type id: str
        :param who: Who triggered creation of this worker.
        :type who: str
        :param keeplog: If not `None`, buffer log message received to be later
                        retrieved via getlog(). If `0`, keep infinite log internally.
                        If `> 0`, keep at most such many log entries in buffer.
        :type keeplog: int or None
        """
        self._controller = controller

        self.id = id
        self.who = who
        self.pid = None
        self.status = "starting"

        self.created = datetime.utcnow()
        self.connected = None
        self.started = None

        # a buffered log for log messages coming from the worker
        # native workers will send log messages on stderr, while
        # guest worker may use stdout/stderr
        self._keeplog = keeplog
        if self._keeplog is not None:
            self._log = deque()
        else:
            self._log = None

        self._log_fds = [2]
        self._log_lineno = 0
        self._log_topic = 'crossbar.node.{}.worker.{}.on_log'.format(self._controller._node_id, self.id)

        # A deferred that resolves when the worker is ready.
        self.ready = Deferred()

        # A deferred that resolves when the worker has exited.
        self.exit = Deferred()

    def log(self, childFD, data):
        """
        FIXME: line buffering
        """
        assert(childFD in self._log_fds)

        for msg in data.split('\n'):
            msg = msg.strip()
            if msg != "":

                # log entry used for buffered worker log and/or worker log events
                #
                if self._log is not None or self._log_topic:
                    log_entry = (self._log_lineno, utcnow(), msg)

                # maintain buffered worker log
                #
                if self._log is not None:
                    self._log_lineno += 1
                    self._log.append(log_entry)
                    if self._keeplog > 0 and len(self._log) > self._keeplog:
                        self._log.popleft()

                # publish worker log event
                #
                if self._log_topic:
                    self._controller.publish(self._log_topic, log_entry)

                # log to controller
                #
                log.msg(msg, system="{:<10} {:>6}".format(self.LOGNAME, self.pid), override_system=True)

    def getlog(self, limit=None):
        """
        Get buffered worker log.

        :param limit: Optionally, limit the amount of log entries returned
           to the last N entries.
        :type limit: None or int

        :returns: list -- Buffered log.
        """
        if self._log:
            if limit and len(self._log) > limit:
                return list(self._log)[len(self._log) - limit:]
            else:
                return list(self._log)
        else:
            return []


class NativeWorkerProcess(WorkerProcess):

    """
    Internal run-time representation of a native worker (router or
    container currently) process.
    """

    TYPE = 'native'
    LOGNAME = 'Native'

    def __init__(self, controller, id, who, keeplog=None):
        """
        Ctor.

        :param controller: The node controller this worker was created by.
        :type controller: instance of NodeControllerSession
        :param id: The ID of the worker.
        :type id: str
        :param who: Who triggered creation of this worker.
        :type who: str
        """
        WorkerProcess.__init__(self, controller, id, who, keeplog)

        self.factory = None
        self.proto = None


class RouterWorkerProcess(NativeWorkerProcess):

    """
    Internal run-time representation of a router worker process.
    """

    TYPE = 'router'
    LOGNAME = 'Router'


class ContainerWorkerProcess(NativeWorkerProcess):

    """
    Internal run-time representation of a container worker process.
    """

    TYPE = 'container'
    LOGNAME = 'Container'


class GuestWorkerProcess(WorkerProcess):

    """
    Internal run-time representation of a guest worker process.
    """

    TYPE = 'guest'
    LOGNAME = 'Guest'

    def __init__(self, controller, id, who, keeplog=None):
        """
        Ctor.

        :param controller: The node controller this worker was created by.
        :type controller: instance of NodeControllerSession
        :param id: The ID of the worker.
        :type id: str
        :param who: Who triggered creation of this worker.
        :type who: str
        """
        WorkerProcess.__init__(self, controller, id, who, keeplog)

        self._log_fds = [1, 2]
        self.proto = None
