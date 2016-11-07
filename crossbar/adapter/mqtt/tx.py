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

from __future__ import absolute_import, division, print_function

import attr
import collections

from itertools import count

from txaio import make_logger

from .protocol import (
    MQTTParser, Failure,
    Connect, ConnACK,
    Subscribe, SubACK,
    Unsubscribe, UnsubACK,
    Publish, PubACK,
    PingREQ, PingRESP,
)

from twisted.internet.protocol import Protocol
from twisted.internet.defer import inlineCallbacks, returnValue

_ids = count()


@attr.s
class Session(object):

    client_id = attr.ib()
    wamp_session = attr.ib()
    queued_messages = attr.ib(default=attr.Factory(collections.deque))
    subscriptions = attr.ib(default=attr.Factory(dict))
    connected = attr.ib(default=False)
    survives = attr.ib(default=False)


@attr.s
class Message(object):

    topic = attr.ib()
    body = attr.ib()
    qos = attr.ib()


class MQTTServerTwistedProtocol(Protocol):

    log = make_logger()

    def __init__(self, handler, reactor, mqtt_sessions, _id_maker=_ids):
        self._reactor = reactor
        self._mqtt = MQTTParser()
        self._handler = handler
        self._in_flight_publishes = set()
        self._waiting_for_ack = {}
        self._timeout = None
        self._timeout_time = 0
        self._mqtt_sessions = mqtt_sessions
        self._flush_publishes = None
        self._connection_id = next(_id_maker)
        self.session = Session(client_id=u"<still connecting>",
                               wamp_session=None)

    def _reset_timeout(self):
        if self._timeout:
            self._timeout.reset(self._timeout_time)

    def dataReceived(self, data):
        # Pause the producer as we need to process some of these things
        # serially -- for example, subscribes in Autobahn are a Deferred op,
        # so we don't want any more data yet
        self.transport.pauseProducing()
        d = self._handle(data)
        d.addErrback(print)
        d.addBoth(lambda _: self._resume_producing())

    def _resume_producing(self):
        if (self.transport.connected and not getattr(
                self.transport, "disconnecting", False)):
            self.transport.resumeProducing()

    def connectionLost(self, reason):
        if self._timeout:
            self._timeout.cancel()
            self._timeout = None

        # Allow other sessions to connect
        self.session.connected = False

        # Destroy the session, if it is not meant to survive, so it cannot be
        # reused.
        # See MQTT-3.1.2-6.
        if not self.session.survives:
            for x in self.session.subscriptions.values():
                x.unsubscribe()

            del self._mqtt_sessions[self.session.client_id]

    def send_publish(self, topic, qos, body):

        self.session.queued_messages.append(Message(topic=topic, qos=qos, body=body))
        if not self._flush_publishes and self.transport.connected:
            self._flush_publishes = self._reactor.callLater(0, self._flush_saved_messages)

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

        self._send_packet(publish)

    def _lose_connection(self):
        self.log.debug(log_category="MQ400", client_id=self.session.client_id,
                       seconds=self._timeout_time,
                       conn_id=self._connection_id)
        self.transport.loseConnection()

    def _send_packet(self, packet):
        self.log.trace(log_category="MQ101", client_id=self.session.client_id,
                       packet=packet, conn_id=self._connection_id)
        self.transport.write(packet.serialise())

    def _flush_saved_messages(self):

        if self._flush_publishes:
            self._flush_publishes = None

        # Closed connection, we don't want to send messages here
        if not self.transport.connected:
            return

        while self.session.queued_messages:
            message = self.session.queued_messages.popleft()
            self._send_publish(message.topic, message.qos, message.body)

    @inlineCallbacks
    def _handle(self, data):

        try:
            res = yield self._handle_data(data)
            returnValue(res)
        except Exception:
            raise

    @inlineCallbacks
    def _handle_data(self, data):

        events = self._mqtt.data_received(data)

        if events:
            # We've got at least one full control packet -- the client is
            # alive, reset the timeout.
            self._reset_timeout()

        for event in events:
            self.log.trace(log_category="MQ100", conn_id=self._connection_id,
                           client_id=self.session.client_id, packet=event)

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

                    # Connected client IDs must be unique, see MQTT-3.1.3-2
                    if event.client_id in self._mqtt_sessions:
                        if self._mqtt_sessions[event.client_id].connected:
                            connack = ConnACK(session_present=True,
                                              return_code=2)
                            self._send_packet(connack)
                            self.transport.loseConnection()
                            return

                    # Use the client ID to control sessions, as per compliance
                    # statement MQTT-3.1.3-2
                    if (event.flags.clean_session and event.client_id in self._mqtt_sessions):
                        # Delete the session if there is one. See MQTT-3.2.2-1
                        session = self._mqtt_sessions[event.client_id]
                        for x in session.subscriptions.values():
                            x.unsubscribe()
                        del self._mqtt_sessions[session.client_id]

                    if event.client_id in self._mqtt_sessions:
                        self.session = self._mqtt_sessions[event.client_id]
                        self._reactor.callLater(0, self._flush_saved_messages)
                        self._handler.existing_wamp_session(self.session)
                        # Have a session, set to 1/True as in MQTT-3.2.2-2
                        session_present = True
                    else:
                        wamp_session = self._handler.new_wamp_session(event)
                        self.session = Session(wamp_session=wamp_session,
                                               client_id=event.client_id)
                        # Don't have session, set to 0/False as in MQTT-3.2.2-3
                        session_present = False

                    self.session.survives = not event.flags.clean_session
                    self.session.connected = True
                    self._mqtt_sessions[event.client_id] = self.session

                elif accept_conn in [1, 2, 3, 4, 5]:
                    # If it's a valid, non-zero return code, the
                    # session_present must be 0/False, as per MQTT-3.2.2-4
                    session_present = False

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

                self.log.debug(log_category="MQ200", client_id=event.client_id)
                continue

            elif isinstance(event, Subscribe):
                try:
                    return_codes = yield self._handler.process_subscribe(event)
                except:
                    # MQTT-4.8.0-2 - If we get a transient error (like
                    # subscribing raising an exception), we must close the
                    # connection.
                    self.log.failure(
                        log_category="MQ500", client_id=self.session.client_id)
                    self.transport.loseConnection()
                    return

                # MQTT-3.8.4-1 - we always need to send back this SubACK, even
                #                if the subscriptions are unsuccessful -- their
                #                unsuccessfulness is listed in the return codes
                # MQTT-3.8.4-2 - the suback needs to have the same packet id
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
                    self.log.error(
                        log_category="MQ401", client_id=self.session.client_id,
                        error=event.reason)
                else:
                    self.log.error(
                        log_category="MQ402", client_id=self.session.client_id,
                        packet_id=event.__class__.__name__)

                # Conformance statement MQTT-4.8.0-1: Must close the connection
                # on a protocol violation.
                self.transport.loseConnection()
                return
