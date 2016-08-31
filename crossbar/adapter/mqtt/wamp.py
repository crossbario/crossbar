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

import json

from functools import partial

from twisted.internet.protocol import Protocol, Factory
from twisted.internet.defer import succeed, inlineCallbacks, returnValue

from crossbar.adapter.mqtt.tx import MQTTServerTwistedProtocol

from autobahn.wamp.types import PublishOptions, ComponentConfig
from autobahn.twisted.wamp import ApplicationSession


class WampMQTTServerProtocol(Protocol):

    def __init__(self, session, reactor):
        self._session = session
        self._mqtt = MQTTServerTwistedProtocol(self, reactor)
        self._subscriptions = {}

    def connectionMade(self):
        self._mqtt.transport = self.transport

    def process_connect(self, packet):

        # XXX: Do some better stuff here wrt session continuation
        return succeed((False, 0))

    def _publish(self, event, options):

        payload = {'mqtt_message': event.payload.decode('utf8')}

        return self._session.publish(event.topic_name, options=options,
                                     **payload)

    def publish_qos_0(self, event):
        return self._publish(event, None)

    def publish_qos_1(self, event):
        return self._publish(event,
                             options=PublishOptions(acknowledge=True))

    @inlineCallbacks
    def process_subscribe(self, packet):

        def handle_publish(topic, qos, *args, **kwargs):
            # If there's a single kwarg which is mqtt_message, then just send
            # that, so that CB can be 'drop in'
            if not args and kwargs.keys() == "mqtt_message":
                body = kwargs["mqtt_message"].encode('utf8')
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
                    sub = yield self._session.subscribe(
                        partial(handle_publish, x.topic_filter, x.max_qos),
                        x.topic_filter)
                    self._subscriptions[x.topic_filter] = sub

                    # We don't allow QoS 2 subscriptions
                    if x.max_qos > 1:
                        responses.append(1)
                    else:
                        responses.append(x.max_qos)
                except Exception as e:
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
        self._session_factory = session_factory
        self._config = config["options"]
        self._reactor = reactor

    def buildProtocol(self, addr):

        session_config = ComponentConfig(realm=self._config['realm'],
                                         extra=None)
        session = ApplicationSession(session_config)

        self._session_factory.add(
            session,
            authrole=self._config.get('role', u'anonymous'))

        return self.protocol(session, self._reactor)
