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

import attr
import collections

from .protocol import (
    MQTTServerProtocol, Failure,
    Connect, ConnACK,
    Subscribe, SubACK,
    Unsubscribe, UnsubACK,
    Publish, PubACK,
    PingREQ, PingRESP,
)

from twisted.internet.protocol import Protocol
from twisted.internet.defer import inlineCallbacks, succeed


@attr.s
class Session(object):

    session = attr.ib()
    queued_messages = attr.ib(default=attr.Factory(collections.deque))


@attr.s
class Message(object):

    topic = attr.ib()
    body = attr.ib()
    qos = attr.ib()


class MQTTServerTwistedProtocol(Protocol):

    def __init__(self, handler, reactor, mqtt_sessions):
        self._reactor = reactor
        self._mqtt = MQTTServerProtocol()
        self._handler = handler
        self._in_flight_publishes = set()
        self._waiting_for_ack = {}
        self._timeout = None
        self._timeout_time = 0
        self._mqtt_sessions = mqtt_sessions
        self._flush_publishes = None

    def _reset_timeout(self):
        if self._timeout:
            self._timeout.reset(self._timeout_time)

    def dataReceived(self, data):
        # The client is alive, reset the timeout
        self._reset_timeout()

        # Pause the producer as we need to process some of these things
        # serially -- for example, subscribes in Autobahn are a Deferred op,
        # so we don't want any more data yet
        self.transport.pauseProducing()
        d = self._handle(data)
        d.addBoth(lambda _: self.transport.resumeProducing())

    def connectionLost(self, reason):
        if self._timeout:
            self._timeout.cancel()
            self._timeout = None

    def send_publish(self, topic, qos, body):

        self.session.queued_messages.append(Message(topic=topic, qos=qos, body=body))
        if not self._flush_publishes:
            self._flush_publishes = self.reactor.callLater(0, self._flush_saved_messages)

    def _send_publish(self, topic, qos, body):

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

    def _lose_connection(self):
        print("MQTT client is timed out... Nothing for %d seconds" % (self._timeout_time,))
        self.transport.loseConnection()

    def _send_packet(self, packet):
        print("Sending %r" %(packet,))
        self.transport.write(packet.serialise())

    def _flush_saved_messages(self):

        if self._flush_publishes:
            self._flush_publishes = None

        for message in self.session.queued_messages:
            self.send_publish(message.topic, message.qos, message.body)


    @inlineCallbacks
    def _handle(self, data):

        events = self._mqtt.data_received(data)

        for event in events:
            print("Got event", event)

            if isinstance(event, Connect):
                accept_conn = yield self._handler.process_connect(event)

                if accept_conn == 0:
                    # If we have a connection, we should make sure timeouts
                    # don't happen. MQTT-3.1.2-24 says it is 1.5x the keep
                    # alive time.
                    if event.keep_alive:
                        self._timeout_time = event.keep_alive * 1.5
                        self._timeout = self._reactor.callLater(
                            self._timeout_time, self._lose_connection)

                    if event.flags.clean_session:
                        # Delete the session, so the next check will fail
                        # See MQTT-3.2.2-1
                        del self._mqtt_sessions[event.client_id]

                    if event.client_id in self._mqtt_sessions:
                        self.session = self._mqtt_sessions[event.client_id]
                        self.reactor.callLater(self._flush_saved_messages)
                        self._handler.existing_wamp_session(self.session)
                        # Have a session, set to 1 as in MQTT-3.2.2-2
                        session_present = 1
                    else:
                        self.session = Session()
                        self.session.wamp_session = yield self._handler.new_wamp_session(event)
                        # Don't have session, set to 0 as in MQTT-3.2.2-3
                        session_present = 0

                elif accept_conn in [1, 2, 3, 4, 5]:
                    # If it's a valid, non-zero return code, the
                    # session_present must be 0, as per MQTT-3.2.2-4
                    session_present = 0

                else:
                    # No valid return codes, so drop the connection, as per
                    # MQTT-3.2.2-6
                    self.transport.loseConnection()
                    return

                connack = ConnACK(session_present=session_present,
                    return_code=accept_conn)
                self._send_packet(connack)

                if accept_conn != 0:
                    # If we send a CONNACK with a non-0 response code, drop the
                    # connection after sending the CONNACK, as in MQTT-3.2.2-5
                    self.transport.loseConnection()
                    return

                continue

            elif isinstance(event, Subscribe):
                return_codes = yield self._handler.process_subscribe(event)

                suback = SubACK(packet_identifier=event.packet_identifier,
                                return_codes=return_codes)
                self._send_packet(suback)
                continue

            elif isinstance(event, Unsubscribe):
                yield self._handler.process_unsubscribe(event)
                unsuback = UnsubACK(packet_identifier=event.packet_identifier)
                self._send_packet(unsuback)
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
                        self._send_packet(puback)

                    d = self._handler.publish_qos_1(event)
                    d.addCallback(_acked)
                    continue

                elif event.qos_level == 2:
                    # Publish > PubREC > PubREL > PubCOMP

                    # add to set, send pubrec here -- in the branching loop,
                    # handle pubrel + pubcomp

                    raise ValueError("Dunno about this yet.")

            elif isinstance(event, PingREQ):
                resp = PingRESP()
                self._send_packet(resp)
                continue

            else:
                if isinstance(event, Failure):
                    print("Protocol violation, closing the connection: %r" % (
                        event,))
                else:
                    print("I don't understand %r, closing conn" % (event,))

                # Conformance statement MQTT-4.8.0-1: Must close the connection
                # on a protocol violation.
                self.transport.loseConnection()
                return
