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

import json

from zope.interface import implementer

from functools import partial

from twisted.internet.interfaces import IHandshakeListener, ISSLTransport
from twisted.internet.protocol import Protocol, Factory
from twisted.internet.defer import succeed, inlineCallbacks, returnValue, Deferred

from crossbar.adapter.mqtt.tx import MQTTServerTwistedProtocol
from crossbar.router.session import RouterSession

from autobahn import util
from autobahn.wamp import message, role
from autobahn.wamp.types import PublishOptions
from autobahn.twisted.util import transport_channel_id


class WampTransport(object):
    _authid = None

    def __init__(self, on_message, real_transport):
        self.on_message = on_message
        self.transport = real_transport

    def send(self, msg):
        self.on_message(msg)

    def get_channel_id(self, channel_id_type=u'tls-unique'):
        return transport_channel_id(self.transport, is_server=True, channel_id_type=channel_id_type)


@implementer(IHandshakeListener)
class WampMQTTServerProtocol(Protocol):

    def __init__(self, reactor):
        self._mqtt = MQTTServerTwistedProtocol(self, reactor)
        self._request_to_packetid = {}
        self._waiting_for_connect = Deferred()

    def on_message(self, inc_msg):

        if isinstance(inc_msg, message.Challenge):
            assert inc_msg.method == u"ticket"

            msg = message.Authenticate(signature=self._pw_challenge)
            del self._pw_challenge

            self._wamp_session.onMessage(msg)

        elif isinstance(inc_msg, message.Welcome):
            print(inc_msg)
            self._waiting_for_connect.callback((0, False))

        elif isinstance(inc_msg, message.Abort):
            print(inc_msg)
            self._waiting_for_connect.callback((1, False))

    def connectionMade(self):
        if not ISSLTransport.providedBy(self.transport):
            self._when_ready()

    def handshakeCompleted(self):
        self._when_ready()

    def _when_ready(self):
        self._mqtt.transport = self.transport

        self._wamp_session = RouterSession(self.factory._wamp_session_factory._routerFactory)
        self._wamp_transport = WampTransport(self.on_message, self.transport)
        self._wamp_transport.factory = self.factory
        self._wamp_session.onOpen(self._wamp_transport)

    def process_connect(self, packet):

        roles = {
            u"subscriber": role.RoleSubscriberFeatures(
                payload_transparency=True),
            u"publisher": role.RolePublisherFeatures(
                payload_transparency=True,
                x_acknowledged_event_delivery=True)
        }

        # Will be autoassigned
        realm = None
        methods = []

        if ISSLTransport.providedBy(self.transport):
            methods.append(u"tls")

        if packet.username and packet.password:
            methods.append(u"ticket")
            msg = message.Hello(
                realm=realm,
                roles=roles,
                authmethods=methods,
                authid=packet.username)
            self._pw_challenge = packet.password

        else:
            methods.append(u"anonymous")
            msg = message.Hello(
                realm=realm,
                roles=roles,
                authmethods=methods,
                authid=packet.client_id)

        self._wamp_session.onMessage(msg)

        # Should add some authorisation here?
        return self._waiting_for_connect

    def _publish(self, event, options):

        request = util.id()
        msg = message.Publish(
            request=request,
            topic=event.topic_name,
            args=tuple(),
            kwargs={'mqtt_message': event.payload.decode('utf8'),
                    'mqtt_qos': event.qos_level},
            **options.message_attr())

        self._wamp_session.onMessage(msg)

        if event.qos_level > 0:
            self._request_to_packetid[request] = event.packet_identifier

        return succeed(0)

    def process_publish_qos_0(self, event):
        return self._publish(event, options=PublishOptions(exclude_me=False))

    def process_publish_qos_1(self, event):
        return self._publish(event,
                             options=PublishOptions(acknowledge=True, exclude_me=False))

    def process_puback(self, event):
        return

    def process_pubrec(self, event):
        return

    def process_pubrel(self, event):
        return

    def process_pubcomp(self, event):
        return

    @inlineCallbacks
    def process_subscribe(self, packet):

        def handle_publish(topic, qos, *args, **kwargs):
            # If there's a single kwarg which is mqtt_message, then just send
            # that, so that CB can be 'drop in'
            if not args and set(kwargs.keys()) == set(["mqtt_message", "mqtt_qos"]):
                body = kwargs["mqtt_message"].encode('utf8')

                if kwargs["mqtt_qos"] < qos:
                    # If the QoS of the message is lower than our max QoS, use
                    # the lower QoS. Otherwise, bracket it at our QoS.
                    qos = kwargs["mqtt_qos"]

            else:
                body = json.dumps({"args": args,
                                   "kwargs": kwargs}).encode('utf8')
            self._mqtt.send_publish(topic, qos, body)

        responses = []

        for x in packet.topic_requests:
            if "$" in x.topic_filter or "#" in x.topic_filter or "+" in x.topic_filter or "*" in x.topic_filter:
                responses.append(128)
                continue
            else:
                try:
                    if x.topic_filter in self._subscriptions:
                        yield self._subscriptions[x.topic_filter].unsubscribe()

                    sub = yield self._wamp_session.subscribe(
                        partial(handle_publish, x.topic_filter, x.max_qos),
                        x.topic_filter)
                    self._full_session.subscriptions[x.topic_filter] = sub

                    # We don't allow QoS 2 subscriptions
                    if x.max_qos > 1:
                        responses.append(1)
                    else:
                        responses.append(x.max_qos)
                except Exception:
                    print("Failed subscribing to topic %s" % (x.topic_filter,))
                    responses.append(128)

        returnValue(responses)

    @inlineCallbacks
    def process_unsubscribe(self, packet):

        for topic in packet.topics:
            if topic in self._subscriptions:
                yield self._subscriptions.pop(topic).unsubscribe()

        return

    def dataReceived(self, data):
        self._mqtt.dataReceived(data)


class WampMQTTServerFactory(Factory):

    protocol = WampMQTTServerProtocol

    def __init__(self, session_factory, config, reactor):
        self._wamp_session_factory = session_factory
        self._config = config["options"]
        self._reactor = reactor

    def buildProtocol(self, addr):

        protocol = self.protocol(self._reactor)
        protocol.factory = self
        return protocol
