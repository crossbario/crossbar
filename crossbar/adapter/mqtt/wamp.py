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

from crossbar.adapter.mqtt.tx import MQTTServerTwistedProtocol, ConnACK

from autobahn.wamp.types import PublishOptions, ComponentConfig
from autobahn.twisted.wamp import ApplicationSession


class WampMQTTServerProtocol(Protocol):

    def __init__(self, session):
        self._session = session
        self._mqtt = MQTTServerTwistedProtocol(self)

    def connectionMade(self):
        self._mqtt.transport = self.transport

    def process_connect(self, packet):

        # XXX: Do some better stuff here wrt session continuation
        return succeed(ConnACK(session_present=False, return_code=0))

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
            body = json.dumps({"args": args, "kwargs": kwargs}).encode('utf8')
            self._mqtt.send_publish(topic, qos, body)

        responses = []

        for x in packet.topic_requests:
            if "$" in x.topic_filter or "#" in x.topic_filter or "+" in x.topic_filter or "*" in x.topic_filter:
                responses.append(128)
                continue
            else:
                yield self._session.subscribe(
                    partial(handle_publish, x.topic_filter, x.max_qos),
                    x.topic_filter)

                # We don't allow subscribes with a QoS larger than 2
                if x.max_qos > 1:
                    responses.append(1)
                else:
                    responses.append(x.max_qos)

        returnValue(responses)

    def dataReceived(self, data):
        self._mqtt.dataReceived(data)


class WampMQTTServerFactory(Factory):

    protocol = WampMQTTServerProtocol

    def __init__(self, session_factory, config):
        self._session_factory = session_factory
        self._config = config["options"]

    def buildProtocol(self, addr):

        session_config = ComponentConfig(realm=self._config['realm'],
                                         extra=None)
        session = ApplicationSession(session_config)

        self._session_factory.add(
            session,
            authrole=self._config.get('role', u'anonymous'))

        p = self.protocol(session)

        return p
