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

import six
import json

from datetime import datetime
from collections import deque

from twisted.internet.defer import Deferred

from crossbar._logging import make_logger, LogLevel, record_separator
from crossbar._logging import cb_logging_aware, escape_formatting

__all__ = ('RouterWorkerProcess',
           'ContainerWorkerProcess',
           'GuestWorkerProcess')


class WorkerProcess(object):
    """
    Internal run-time representation of a worker process.
    """
    _logger = make_logger()

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
        self._log_fds = [2]
        self._log_lineno = 0
        self._log_topic = 'crossbar.node.{}.worker.{}.on_log'.format(self._controller._node_id, self.id)

        self._log_rich = None # Does not support rich logs

        # A deferred that resolves when the worker is ready.
        self.ready = Deferred()

        # A deferred that resolves when the worker has exited.
        self.exit = Deferred()

    def log(self, childFD, data):
        """
        FIXME: line buffering
        """
        assert(childFD in self._log_fds)

        if type(data) != six.text_type:
            data = data.decode('utf8')

        if self._log_rich is None:
            # If it supports rich logging, it will print just the logger aware
            # "magic phrase" as its first message.
            if data == cb_logging_aware + "\n":
                self._log_rich = True
                self._log_data = u"" # Log buffer
                return
            else:
                self._log_rich = False

        system = "{:<10} {:>6}".format(self.LOGNAME, self.pid)

        if self._log_rich:
            # This guest supports rich logs.
            self._log_data += data

            while record_separator in self._log_data:

                log, self._log_data = self._log_data.split(record_separator, 1)

                event = json.loads(log)
                event_text = event["text"]
                level = LogLevel.levelWithName(event["level"])

                self._logger.emit(level, event_text, log_system=system)

                if self._log_topic:
                    self._controller.publish(self._log_topic, event_text)

        else:
            data = escape_formatting(data)
            # Rich logs aren't supported
            self._logger.emit(LogLevel.info, data, log_system=system)

            if self._log_topic:
                self._controller.publish(self._log_topic, data)



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
