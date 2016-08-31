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

from .protocol import (
    MQTTServerProtocol, Failure,
    Connect, ConnACK,
    Subscribe, SubACK,
    Unsubscribe, UnsubACK,
    Publish, PubACK,
)

from twisted.internet.protocol import Protocol
from twisted.internet.defer import inlineCallbacks, succeed


class MQTTServerTwistedProtocol(Protocol):

    def __init__(self, handler):
        self._mqtt = MQTTServerProtocol()
        self._handler = handler
        self._in_flight_publishes = set()
        self._waiting_for_ack = {}
        self._timeout = None

    def dataReceived(self, data):
        # Pause the producer as we need to process some of these things
        # serially -- for example, subscribes in Autobahn are a Deferred op,
        # so we don't want any more data yet
        self.transport.pauseProducing()
        d = self._handle(data)
        d.addCallback(lambda _: self.transport.resumeProducing())

    def send_publish(self, topic, qos, body):

        if qos == 0:
            publish = Publish(duplicate=False, qos_level=qos, retain=False,
                              packet_identifier=None, topic_name=topic,
                              payload=body)

        elif qos == 1:
            packet_id = self._get_packet_id()
            publish = Publish(duplicate=False, qos_level=qos, retain=False,
                              packet_identifier=packet_id, topic_name=topic,
                              payload=body)

            self._waiting_for_ack[packet_id] = (1, 0)

        self.transport.write(publish.serialise())

    @inlineCallbacks
    def _handle(self, data):

        events = self._mqtt.data_received(data)

        for event in events:
            print("Got event", event)

            if isinstance(event, Connect):
                connack_details = yield self._handler.process_connect(event)
                connack = ConnACK(session_present=connack_details[0],
                                  return_code=connack_details[1])
                self.transport.write(connack.serialise())

                if connack.return_code != 0:
                    self.transport.loseConnection()
                    return

                continue

            elif isinstance(event, Subscribe):
                return_codes = yield self._handler.process_subscribe(event)

                suback = SubACK(packet_identifier=event.packet_identifier,
                                return_codes=return_codes)
                self.transport.write(suback.serialise())
                continue

            elif isinstance(event, Unsubscribe):
                yield self._handler.process_unsubscribe(event)
                unsuback = UnsubACK(packet_identifier=event.packet_identifier)
                self.transport.write(unsuback.serialise())
                continue

            elif isinstance(event, Publish):
                if event.qos_level == 0:
                    # Publish, no acks
                    self._handler.publish_qos_0(event)
                    continue

                elif event.qos_level == 1:
                    # Publish > PubACK
                    def _acked(*args):
                        puback = PubACK(
                            packet_identifier=event.packet_identifier)
                        self.transport.write(puback.serialise())

                    d = self._handler.publish_qos_1(event)
                    d.addCallback(_acked)
                    continue

                elif event.qos_level == 2:
                    # Publish > PubREC > PubREL > PubCOMP

                    # add to set, send pubrec here -- in the branching loop,
                    # handle pubrel + pubcomp

                    raise ValueError("Dunno about this yet.")

            elif isinstance(event, Failure):
                print(event)
                self.transport.loseConnection()
                return
            else:
                # Something else!
                print("I don't understand %r" % (event,))
                self.transport.loseConnection()
                return
