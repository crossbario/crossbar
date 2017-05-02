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
)
from ._events import (
    Connect, ConnACK,
    Subscribe, SubACK,
    Unsubscribe, UnsubACK,
    Publish, PubACK, PubREC, PubREL, PubCOMP,
    PingREQ, PingRESP,
    Disconnect,
)

from twisted.internet.protocol import Protocol
from twisted.internet.defer import inlineCallbacks, returnValue

_ids = count()
_SIXTEEN_BIT_MAX = 65535


@attr.s
class Session(object):

    client_id = attr.ib()
    queued_messages = attr.ib(default=attr.Factory(collections.deque))
    _count = attr.ib(default=attr.Factory(count))

    def get_packet_id(self):

        x = next(self._count)
        if x == _SIXTEEN_BIT_MAX or x == 0:
            self._count = count(start=1)
            x = next(self._count)
        return x


@attr.s
class Message(object):

    topic = attr.ib()
    body = attr.ib()
    qos = attr.ib()
    retained = attr.ib()


class MQTTServerTwistedProtocol(Protocol):

    log = make_logger()

    def __init__(self, handler, reactor, _id_maker=_ids):
        self._reactor = reactor
        self._mqtt = MQTTParser()
        self._handler = handler
        self._timeout = None
        self._timeout_time = 0
        self._flush_publishes = None
        self._connection_id = next(_id_maker)
        self.session = Session(client_id=u"<still connecting>")

    @property
    def _connected(self):

        if not self.transport:
            return False

        # Omg wtf is this
        connected = getattr(self.transport, "connected", None)
        disconnected = getattr(self.transport, "disconnected", None)
        disconnecting = getattr(self.transport, "disconnecting", None)

        if connected and not disconnected and not disconnecting:
            return True
        elif disconnected:
            return False
        elif disconnecting:
            return False
        elif connected is None and not disconnected and not disconnecting:
            return True
        elif not connected:
            return False
        else:
            return True

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
        if self._connected:
            self.transport.resumeProducing()

    def connectionLost(self, reason):
        if self._timeout:
            self._timeout.cancel()
            self._timeout = None

    def send_suback(self, packet_identifier, return_codes):

        # MQTT-3.8.4-1 - we always need to send back this SubACK, even
        #                if the subscriptions are unsuccessful -- their
        #                unsuccessfulness is listed in the return codes
        # MQTT-3.8.4-2 - the suback needs to have the same packet id
        suback = SubACK(packet_identifier=packet_identifier,
                        return_codes=return_codes)
        self._send_packet(suback)

    def send_publish(self, topic, qos, body, retained):

        if qos not in [0, 1, 2]:
            raise ValueError("QoS must be [0, 1, 2]")

        self.session.queued_messages.append(
            Message(topic=topic, qos=qos, body=body, retained=retained))

        if not self._flush_publishes and self._connected:
            self._flush_publishes = self._reactor.callLater(0, self._flush_saved_messages)

    def _send_publish(self, topic, qos, body, retained):

        if qos == 0:
            publish = Publish(duplicate=False, qos_level=qos, retain=retained,
                              packet_identifier=None, topic_name=topic,
                              payload=body)

        elif qos == 1:
            packet_id = self.session.get_packet_id()
            publish = Publish(duplicate=False, qos_level=qos, retain=retained,
                              packet_identifier=packet_id, topic_name=topic,
                              payload=body)

        elif qos == 2:

            packet_id = self.session.get_packet_id()
            publish = Publish(duplicate=False, qos_level=qos, retain=retained,
                              packet_identifier=packet_id, topic_name=topic,
                              payload=body)

        else:
            self.log.warn(log_category="MQ303")
            return

        self._send_packet(publish)

    def _lose_connection(self):
        self.log.debug(log_category="MQ400", client_id=self.session.client_id,
                       seconds=self._timeout_time,
                       conn_id=self._connection_id)
        if self.transport:
            self.transport.loseConnection()
        else:
            self.log.debug(log_category="MQ404")

    def _send_packet(self, packet):
        self.log.trace(log_category="MQ101", client_id=self.session.client_id,
                       packet=packet, conn_id=self._connection_id)
        self.transport.write(packet.serialise())

    def _flush_saved_messages(self):

        if self._flush_publishes:
            self._flush_publishes = None

        # Closed connection, we don't want to send messages here
        if not self._connected:
            return None

        # New, queued messages
        while self.session.queued_messages:
            message = self.session.queued_messages.popleft()
            self._send_publish(message.topic, message.qos, message.body,
                               message.retained)

    @inlineCallbacks
    def _handle(self, data):

        try:
            res = yield self._handle_data(data)
            returnValue(res)
        except Exception:
            raise

    def _handle_data(self, data):

        events = self._mqtt.data_received(data)

        if events:
            # We've got at least one full control packet -- the client is
            # alive, reset the timeout.
            self._reset_timeout()

        return self._handle_events(events)

    @inlineCallbacks
    def _handle_events(self, events):

        for event in events:
            self.log.trace(log_category="MQ100", conn_id=self._connection_id,
                           client_id=self.session.client_id, packet=event)

            if isinstance(event, Connect):
                try:
                    accept_conn, session_present = yield self._handler.process_connect(event)
                except:
                    # MQTT-4.8.0-2 - If we get a transient error (like
                    # connecting raising an exception), we must close the
                    # connection.
                    self.log.failure(log_category="MQ500")
                    self.transport.loseConnection()
                    returnValue(None)

                if accept_conn == 0:
                    # If we have a connection, we should make sure timeouts
                    # don't happen. MQTT-3.1.2-24 says it is 1.5x the keep
                    # alive time.
                    if event.keep_alive:
                        self._timeout_time = event.keep_alive * 1.5
                        self._timeout = self._reactor.callLater(
                            self._timeout_time, self._lose_connection)

                    self.session.client_id = event.client_id

                elif accept_conn in [1, 2, 3, 4, 5]:
                    # If it's a valid, non-zero return code, the
                    # session_present must be 0/False, as per MQTT-3.2.2-4
                    session_present = False

                else:
                    # No valid return codes, so drop the connection, as per
                    # MQTT-3.2.2-6
                    self.transport.loseConnection()
                    returnValue(None)

                connack = ConnACK(session_present=session_present,
                                  return_code=accept_conn)
                self._send_packet(connack)

                if accept_conn != 0:
                    # If we send a CONNACK with a non-0 response code, drop the
                    # connection after sending the CONNACK, as in MQTT-3.2.2-5
                    self.transport.loseConnection()
                    returnValue(None)

                self.log.debug(log_category="MQ200", client_id=event.client_id)
                continue

            elif isinstance(event, Subscribe):
                try:
                    self._handler.process_subscribe(event)
                except:
                    # MQTT-4.8.0-2 - If we get a transient error (like
                    # subscribing raising an exception), we must close the
                    # connection.
                    self.log.failure()
                    self.log.failure(
                        log_category="MQ501", client_id=self.session.client_id)
                    self.transport.loseConnection()
                    returnValue(None)

                continue

            elif isinstance(event, Unsubscribe):
                try:
                    yield self._handler.process_unsubscribe(event)
                except:
                    # MQTT-4.8.0-2 - If we get a transient error (like
                    # unsubscribing raising an exception), we must close the
                    # connection.
                    self.log.failure(
                        log_category="MQ502", client_id=self.session.client_id)
                    self.transport.loseConnection()
                    returnValue(None)
                unsuback = UnsubACK(packet_identifier=event.packet_identifier)
                self._send_packet(unsuback)
                continue

            elif isinstance(event, Publish):
                if event.qos_level == 0:
                    # Publish, no acks
                    try:
                        yield self._handler.process_publish_qos_0(event)
                    except:
                        # MQTT-4.8.0-2 - If we get a transient error (like
                        # publishing raising an exception), we must close the
                        # connection.
                        self.log.failure(log_category="MQ503",
                                         client_id=self.session.client_id)
                        self.transport.loseConnection()
                        returnValue(None)

                    self.log.debug(log_category="MQ201", publish=event,
                                   client_id=self.session.client_id)
                    continue

                elif event.qos_level == 1:
                    # Publish > PubACK
                    try:
                        self._handler.process_publish_qos_1(event)
                    except:
                        # MQTT-4.8.0-2 - If we get a transient error (like
                        # publishing raising an exception), we must close the
                        # connection.
                        self.log.failure()
                        self.log.failure(log_category="MQ504",
                                         client_id=self.session.client_id)
                        self.transport.loseConnection()
                        returnValue(None)

                    self.log.debug(log_category="MQ202", publish=event,
                                   client_id=self.session.client_id)

                    puback = PubACK(packet_identifier=event.packet_identifier)
                    self._send_packet(puback)
                    continue

                elif event.qos_level == 2:
                    # Publish > PubREC > PubREL > PubCOMP

                    # add to set, send pubrec here -- in the branching loop,
                    # handle pubrel + pubcomp

                    try:
                        self._handler.process_publish_qos_2(event)
                    except:
                        # MQTT-4.8.0-2 - If we get a transient error (like
                        # publishing raising an exception), we must close the
                        # connection.
                        self.log.failure(log_category="MQ505",
                                         client_id=self.session.client_id)
                        self.transport.loseConnection()
                        returnValue(None)

                    self.log.debug(log_category="MQ203", publish=event,
                                   client_id=self.session.client_id)

                    pubrec = PubREC(packet_identifier=event.packet_identifier)
                    self._send_packet(pubrec)
                    continue

                else:
                    # MQTT-3.3.1-4 - We got a QoS "3" (both QoS bits set)
                    # packet -- something the spec does not allow! Nor our
                    # events implementation (it will be caught before it gets
                    # here), but the tests do some trickery to cover this
                    # case :)
                    self.log.error(log_category="MQ403",
                                   client_id=self.session.client_id)
                    self.transport.loseConnection()
                    return

            elif isinstance(event, PingREQ):
                resp = PingRESP()
                self._send_packet(resp)
                continue

            elif isinstance(event, PubACK):

                try:
                    self._handler.process_puback(event)
                except:
                    # MQTT-4.8.0-2 - If we get a transient errorm we must close
                    # the connection.
                    self.transport.loseConnection()
                    returnValue(None)

            elif isinstance(event, PubREC):

                try:
                    self._handler.process_pubrec(event)
                except:
                    # MQTT-4.8.0-2 - If we get a transient errorm we must close
                    # the connection.
                    self.transport.loseConnection()
                    returnValue(None)

                # MQTT-4.3.3-1: MUST send back a PubREL -- even if it's not an
                # ID we know about, apparently, according to Mosquitto and
                # ActiveMQ.
                resp = PubREL(packet_identifier=event.packet_identifier)
                self._send_packet(resp)

            elif isinstance(event, PubREL):

                try:
                    self._handler.process_pubrel(event)
                except:
                    # MQTT-4.8.0-2 - If we get a transient error we must close
                    # the connection.
                    self.transport.loseConnection()
                    returnValue(None)

                resp = PubCOMP(packet_identifier=event.packet_identifier)
                self._send_packet(resp)
                continue

            elif isinstance(event, PubCOMP):

                try:
                    self._handler.process_pubcomp(event)
                except:
                    # MQTT-4.8.0-2 - If we get a transient error we must close
                    # the connection.
                    self.transport.loseConnection()
                    returnValue(None)

            elif isinstance(event, Disconnect):
                # TODO: get rid of some will messages

                # 3.14.4 -- we can close it if we want to
                self.transport.loseConnection()
                self.transport = None
                returnValue(None)

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
                returnValue(None)
