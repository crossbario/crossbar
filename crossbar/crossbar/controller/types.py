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



class NodeProcess:
   """
   """
   process_type = "node"

   def __init__(self, id, pid, ready, exit):
      """
      Ctor.

      :param pid: The worker process PID.
      :type pid: int
      :param ready: A deferred that resolves when the worker is ready.
      :type ready: instance of Deferred
      :param exit: A deferred that resolves when the worker has exited.
      :type exit: instance of Deferred
      """
      self.started = datetime.utcnow()
      self.id = id
      self.pid = pid
      self.ready = ready
      self.exit = exit



class NodeControllerProcess(NodeProcess):
   """   
   """
   process_type = "controller"



class NodeWorkerProcess(NodeProcess):
   """
   Internal run-time representation of a running node worker process.
   """

   process_type = 'worker'



class NodeNativeWorkerProcess(NodeWorkerProcess):
   """
   Internal run-time representation of a running node worker process.
   """

   process_type = 'native'

   def __init__(self, id, pid, ready, exit, type, factory, proto):
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
      NodeWorkerProcess.__init__(self, id, pid, ready, exit)
      self.process_type = type
      self.factory = factory
      self.proto = proto



class NodeGuestWorkerProcess(NodeWorkerProcess):
   """
   Internal run-time representation of a running node guest process.
   """

   process_type = 'guest'

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
      NodeWorkerProcess.__init__(self, id, pid, ready, exit)
      self.proto = proto
