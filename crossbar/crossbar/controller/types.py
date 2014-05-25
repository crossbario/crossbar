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
   Internal run-time representation of a worker process.
   """

   TYPE = 'worker'

   def __init__(self, id, who):
      """
      Ctor.

      :param id: The ID of the worker.
      :type id: str
      :param who: Who triggered creation of this worker.
      :type who: str
      """
      self.id = id
      self.who = who
      self.status = "starting"

      self.created = datetime.utcnow()
      self.connected = None
      self.started = None

      ## A deferred that resolves when the worker is ready.
      self.ready = Deferred()

      ## A deferred that resolves when the worker has exited.
      self.exit = Deferred()



class NativeWorkerProcess(WorkerProcess):
   """
   Internal run-time representation of a native worker (router or
   container currently) process.
   """

   TYPE = 'native'

   def __init__(self, id, who):
      """
      Ctor.

      :param id: The ID of the worker.
      :type id: str
      :param who: Who triggered creation of this worker.
      :type who: str
      """
      WorkerProcess.__init__(self, id, who)

      self.factory = None
      self.proto = None



class RouterWorkerProcess(NativeWorkerProcess):
   """
   Internal run-time representation of a router worker process.
   """

   TYPE = 'router'



class ContainerWorkerProcess(NativeWorkerProcess):
   """
   Internal run-time representation of a container worker process.
   """

   TYPE = 'container'



class GuestWorkerProcess(WorkerProcess):
   """
   Internal run-time representation of a guest worker process.
   """

   TYPE = 'guest'

   def __init__(self, id, who):
      """
      Ctor.

      :param id: The ID of the worker.
      :type id: str
      :param who: Who triggered creation of this worker.
      :type who: str
      """
      WorkerProcess.__init__(self, id, who)

      self.proto = None
