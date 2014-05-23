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


from datetime import datetime

from twisted.internet.defer import Deferred



class WorkerProcess:
   """
   Internal run-time representation of a running node worker process.
   """

   worker_type = 'worker'

   def __init__(self, id, who):
      """
      Ctor.

      :param pid: The worker process PID.
      :type pid: int
      :param ready: A deferred that resolves when the worker is ready.
      :type ready: instance of Deferred
      :param exit: A deferred that resolves when the worker has exited.
      :type exit: instance of Deferred
      """
      self.id = id
      self.who = who
      self.status = "starting"
      self.created = datetime.utcnow()
      self.started = None



class NativeWorkerProcess(WorkerProcess):
   """
   Internal run-time representation of a running node worker process.
   """

   TYPE = 'native'

   def __init__(self, id, who):
      """
      Ctor.

      :param pid: The worker process PID.
      :type pid: int
      :param ready: A deferred that resolves when the worker is ready.
      :type ready: instance of Deferred
      :param exit: A deferred that resolves when the worker has exited.
      :type exit: instance of Deferred
      :param factory: The WAMP client factory that connects to the worker.
      :type factory: instance of WorkerClientFactory
      """
      WorkerProcess.__init__(self, id, who)

      ## this will be resolved/rejected when the worker is actually
      ## ready to receive commands via WAMP
      self.ready = Deferred()

      ## this will be resolved when the worker exits (after previously connected)
      self.exit = Deferred()

      self.factory = None
      self.proto = None



class RouterWorkerProcess(NativeWorkerProcess):
   """
   """
   TYPE = 'router'



class ContainerWorkerProcess(NativeWorkerProcess):
   """
   """
   TYPE = 'container'



class GuestWorkerProcess(WorkerProcess):
   """
   Internal run-time representation of a running node guest process.
   """

   TYPE = 'guest'

   def __init__(self, id, pid, ready, exit, proto):
      """
      Ctor.

      :param pid: The worker process PID.
      :type pid: int
      :param ready: A deferred that resolves when the worker is ready.
      :type ready: instance of Deferred
      :param exit: A deferred that resolves when the worker has exited.
      :type exit: instance of Deferred
      :param proto: An instance of GuestClientProtocol.
      :type proto: obj
      """
      WorkerProcess.__init__(self, id, pid, ready, exit)
      self.proto = proto
