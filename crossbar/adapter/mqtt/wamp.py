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

from functools import partial

from twisted.internet.protocol import Protocol, Factory
from twisted.internet.defer import succeed, inlineCallbacks, returnValue

from crossbar.adapter.mqtt.tx import MQTTServerTwistedProtocol

from autobahn.wamp.types import PublishOptions, ComponentConfig
from autobahn.twisted.wamp import ApplicationSession


class WampMQTTServerProtocol(Protocol):

    def __init__(self, reactor, mqtt_sessions):
        self._mqtt = MQTTServerTwistedProtocol(self, reactor, mqtt_sessions)

    def connectionMade(self):
        self._mqtt.transport = self.transport

    def new_wamp_session(self, event):
        session_config = ComponentConfig(realm=self.factory._config['realm'],
                                         extra=None)
        session = ApplicationSession(session_config)

        self.factory._session_factory.add(
            session,
            authrole=self.factory._config.get('role', u'anonymous'))
        self._wamp_session = session

        return session

    def existing_wamp_session(self, session):
        self._full_session = session
        self._wamp_session = session.wamp_session

    def process_connect(self, packet):
        # Should add some authorisation here?
        return succeed(0)

    def _publish(self, event, options):
        payload = {'mqtt_message': event.payload.decode('utf8'),
                   'mqtt_qos': event.qos_level}

        return self._wamp_session.publish(event.topic_name, options=options,
                                          **payload)

    def publish_qos_0(self, event):
        return self._publish(event, options=PublishOptions(exclude_me=False))

    def publish_qos_1(self, event):
        return self._publish(event,
                             options=PublishOptions(acknowledge=True, exclude_me=False))

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
        self._mqtt_sessions = {}

    def buildProtocol(self, addr):

        protocol = self.protocol(self._reactor, self._mqtt_sessions)
        protocol.factory = self
        return protocol
