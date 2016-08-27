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

from __future__ import absolute_import, division, print_function

from pymqtt.protocol import MQTTServerProtocol, Connect, ConnACK, Failure

from twisted.internet.protocol import Protocol
from twisted.internet.defer import inlineCallbacks, succeed

class MQTTServerTwistedProtocol(Protocol):

    def __init__(self):
        self._mqtt = MQTTServerProtocol()

    def dataReceived(self, data):
        # Pause the producer as we need to process some of these things
        # serially -- for example, subscribes in Autobahn are a Deferred op,
        # so we don't want any more data yet
        self.transport.pauseProducing()
        d = self._handle(data)
        d.addCallback(lambda _: self.transport.resumeProducing())

    @inlineCallbacks
    def _handle(self, data):

        # ugh generators
        yield succeed(True)

        events = self._mqtt.data_received(data)

        for event in events:

            if isinstance(event, Connect):
                # XXX: Do some better stuff here wrt session continuation
                connack = ConnACK(session_present=False, return_code=0)
                self.transport.write(connack.serialise())

            elif isinstance(event, Failure):
                print(event)
                self.transport.loseConnection()
                return
