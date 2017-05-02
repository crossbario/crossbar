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

import six
from txaio import make_logger
from pytrie import StringTrie

from zope.interface import implementer

from collections import OrderedDict

from twisted.internet.interfaces import IHandshakeListener, ISSLTransport
from twisted.internet.protocol import Protocol, Factory
from twisted.internet.defer import inlineCallbacks, Deferred, returnValue, succeed

from crossbar.adapter.mqtt.tx import MQTTServerTwistedProtocol
from crossbar.router.session import RouterSession

from autobahn import util
from autobahn.wamp import message, role
from autobahn.wamp.message import _URI_PAT_LOOSE_NON_EMPTY, _URI_PAT_LOOSE_LAST_EMPTY, _URI_PAT_LOOSE_EMPTY
from autobahn.wamp.serializer import JsonObjectSerializer, MsgPackObjectSerializer, CBORObjectSerializer, UBJSONObjectSerializer
from autobahn.twisted.util import transport_channel_id, peer2str
from autobahn.websocket.utf8validator import Utf8Validator

_validator = Utf8Validator()


def _mqtt_topicfilter_to_wamp(topic):
    """
    Convert a MQTT topic as used in MQTT Subscribe (and hence ptoentially containing
    special characters "+" and "#") to a WAMP URI and a match policy.
    """
    if type(topic) != six.text_type:
        raise TypeError('invalid type "{}" for MQTT topic filter'.format(type(topic)))

    if u'+' in topic:
        # check topic filter containing single-level wildcard character

        # this is a restriction following from WAMP! we cannot have both
        # wildcard and prefix matching combined.
        if u'#' in topic:
            raise TypeError('MQTT topic filter "{}" contains both single-level and multi-level wildcards, and this cannot be mapped to WAMP'.format(topic))

        for c in topic.split(u'/'):
            if c != u'+' and u'+' in c:
                raise TypeError('invalid MQTT filter "{}": single-level wildcard characters must stand on their own in components'.format(topic))

        _match = u'wildcard'
        _topic = topic.replace(u'+', u'')

    elif u'#' in topic:
        # check topic filter containing multi-level wildcard character
        # there can be only one occurence, and it must be at the end
        if topic.find('#') != len(topic) - 1:
            raise TypeError('invalid MQTT topic filter "{}": # multi-level wildcard character must only appear as last character'.format(topic))
        if len(topic) > 1:
            if topic[-2] != u'/':
                raise TypeError('invalid MQTT topic filter "{}": # multi-level wildcard character must either appear solely, or be preceded by a / topic separator character'.format(topic))
        _match = u'prefix'
        _topic = topic[:-1]

    else:
        _match = u'exact'
        _topic = topic[:]

    # MQTT spec 4.7.1.1: "The use of the topic level separator is significant when either
    # of the two wildcard characters is encountered in the Topic Filters specified by subscribing Clients."
    #
    # FIXME: However, we still cannot leave the "/" character untouched and uninterpreted
    # when no "+" or "#" was encountered
    if True or _match != u'exact':
        # replace MQTT level separator "/" with WAMP level separator "."
        _topic = u'.'.join(_topic.split(u'/'))

    if (_match == u'exact' and not _URI_PAT_LOOSE_NON_EMPTY.match(_topic)) or \
       (_match == u'prefix' and not _URI_PAT_LOOSE_LAST_EMPTY.match(_topic)) or \
       (_match == u'wildcard' and not _URI_PAT_LOOSE_EMPTY.match(_topic)):
            raise TypeError('invalid WAMP URI "{}" (match="{}") after conversion from MQTT topic filter "{}"'.format(_topic, _match, topic))

    return _topic, _match


def _mqtt_topicname_to_wamp(topic):
    """
    Convert a MQTT topic as used in MQTT Publish to a WAMP URI.
    """
    if type(topic) != six.text_type:
        raise TypeError('invalid type "{}" for MQTT topic name'.format(type(topic)))

    if u'#' in topic or u'+' in topic:
        raise TypeError('invalid MQTT topic name "{}" - contains wildcard characters'.format(topic))

    if u'/' in topic:
        _topic = u'.'.join(topic.split(u'/'))
    else:
        _topic = topic

    if not _URI_PAT_LOOSE_NON_EMPTY.match(_topic):
        raise TypeError('invalid WAMP URI "{}" after conversion from MQTT topic name "{}"'.format(_topic, topic))

    return _topic


def _wamp_topic_to_mqtt(topic):
    """
    Convert a WAMP URI as used in WAMP Publish to a MQTT topic.
    """
    return u'/'.join(topic.split(u'.'))


class WampTransport(object):
    _authid = None

    def __init__(self, factory, on_message, real_transport):
        self.factory = factory
        self.on_message = on_message
        self.transport = real_transport
        real_transport._transport_config = {u'foo': 32}
        self._transport_info = {
            u'type': u'mqtt',
            u'peer': peer2str(self.transport.getPeer()),
        }

    def send(self, msg):
        self.on_message(msg)

    def get_channel_id(self, channel_id_type=u'tls-unique'):
        return transport_channel_id(self.transport, is_server=True, channel_id_type=channel_id_type)


@implementer(IHandshakeListener)
class WampMQTTServerProtocol(Protocol):

    log = make_logger()

    def __init__(self, reactor):
        self._mqtt = MQTTServerTwistedProtocol(self, reactor)
        self._request_to_packetid = {}
        self._waiting_for_connect = None
        self._inflight_subscriptions = {}
        self._subrequest_to_mqtt_subrequest = {}
        self._subrequest_callbacks = {}
        self._topic_lookup = {}
        self._wamp_session = None

    def on_message(self, inc_msg):

        try:
            self._on_message(inc_msg)
        except:
            self.log.failure()

    @inlineCallbacks
    def _on_message(self, inc_msg):
        self.log.debug('WampMQTTServerProtocol._on_message(inc_msg={inc_msg})', inc_msg=inc_msg)

        if isinstance(inc_msg, message.Challenge):
            assert inc_msg.method == u"ticket"

            msg = message.Authenticate(signature=self._pw_challenge)
            del self._pw_challenge

            self._wamp_session.onMessage(msg)

        elif isinstance(inc_msg, message.Welcome):
            self._waiting_for_connect.callback((0, False))

        elif isinstance(inc_msg, message.Abort):
            self._waiting_for_connect.callback((1, False))

        elif isinstance(inc_msg, message.Subscribed):
            # Successful subscription!
            mqtt_id = self._subrequest_to_mqtt_subrequest[inc_msg.request]
            self._inflight_subscriptions[mqtt_id][inc_msg.request]["response"] = 0
            self._topic_lookup[inc_msg.subscription] = self._inflight_subscriptions[mqtt_id][inc_msg.request]["topic"]

            if -1 not in [x["response"] for x in self._inflight_subscriptions[mqtt_id].values()]:
                self._subrequest_callbacks[mqtt_id].callback(None)

        elif (isinstance(inc_msg, message.Error) and
              inc_msg.request_type == message.Subscribe.MESSAGE_TYPE):
            # Failed subscription :(
            mqtt_id = self._subrequest_to_mqtt_subrequest[inc_msg.request]
            self._inflight_subscriptions[mqtt_id][inc_msg.request]["response"] = 128

            if -1 not in [x["response"] for x in self._inflight_subscriptions[mqtt_id].values()]:
                self._subrequest_callbacks[mqtt_id].callback(None)

        elif isinstance(inc_msg, message.Event):

            topic = inc_msg.topic or self._topic_lookup[inc_msg.subscription]

            try:
                payload_format, mapped_topic, payload = yield self.factory.transform_wamp(topic, inc_msg)
            except:
                self.log.failure()
            else:
                self._mqtt.send_publish(mapped_topic, 0, payload, retained=inc_msg.retained or False)

        elif isinstance(inc_msg, message.Goodbye):
            if self._mqtt.transport:
                self._mqtt.transport.loseConnection()
                self._mqtt.transport = None

        else:
            self.log.warn('cannot process unimplemented message: {inc_msg}', inc_msg=inc_msg)

    def connectionMade(self, ignore_handshake=False):
        if ignore_handshake or not ISSLTransport.providedBy(self.transport):
            self._when_ready()

    def connectionLost(self, reason):
        if self._wamp_session:
            msg = message.Goodbye()
            self._wamp_session.onMessage(msg)
            del self._wamp_session

    def handshakeCompleted(self):
        self._when_ready()

    def _when_ready(self):
        if self._wamp_session:
            return

        self._mqtt.transport = self.transport

        self._wamp_session = RouterSession(self.factory._router_session_factory._routerFactory)
        self._wamp_transport = WampTransport(self.factory, self.on_message, self.transport)
        self._wamp_session.onOpen(self._wamp_transport)
        self._wamp_session._transport_config = self.factory._options

    def process_connect(self, packet):
        """
        Process the initial Connect message from the MQTT client.

        This should return a pair `(accept_conn, session_present)`, where
        `accept_conn` is a return code:

        0: connection accepted
        1-5: connection refused (see MQTT spec 3.2.2.3)
        """

        # Connect(client_id='paho/4E23D8C09DD9C6CF2C',
        #         flags=ConnectFlags(username=False,
        #                            password=False,
        #                            will=False,
        #                            will_retain=False,
        #                            will_qos=0,
        #                            clean_session=True,
        #                            reserved=False),
        #         keep_alive=60,
        #         will_topic=None,
        #         will_message=None,
        #         username=None,
        #         password=None)
        self.log.info('WampMQTTServerProtocol.process_connect(packet={packet})', packet=packet)

        # we don't support session resumption: https://github.com/crossbario/crossbar/issues/892
        if not packet.flags.clean_session:
            self.log.warn('denying MQTT connect from {peer}, as the clients wants to resume a session (which we do not support)', peer=peer2str(self.transport.getPeer()))
            return succeed((1, False))

        # we won't support QoS 2: https://github.com/crossbario/crossbar/issues/1046
        if packet.flags.will and packet.flags.will_qos not in [0, 1]:
            self.log.warn('denying MQTT connect from {peer}, as the clients wants to provide a "last will" event with QoS {will_qos} (and we only support QoS 0/1 here)', peer=peer2str(self.transport.getPeer()), will_qos=packet.flags.will_qos)
            return succeed((1, False))

        # this will be resolved when the MQTT connect handshake is completed
        self._waiting_for_connect = Deferred()

        roles = {
            u"subscriber": role.RoleSubscriberFeatures(
                payload_transparency=True,
                pattern_based_subscription=True),
            u"publisher": role.RolePublisherFeatures(
                payload_transparency=True,
                x_acknowledged_event_delivery=True)
        }

        realm = self.factory._options.get(u'realm', None)

        authmethods = []
        authextra = {
            u'mqtt': {
                u'client_id': packet.client_id,
                u'will': bool(packet.flags.will),
                u'will_topic': packet.will_topic
            }
        }

        if ISSLTransport.providedBy(self.transport):
            authmethods.append(u"tls")

        if packet.username and packet.password:
            authmethods.append(u"ticket")
            msg = message.Hello(
                realm=realm,
                roles=roles,
                authmethods=authmethods,
                authid=packet.username,
                authextra=authextra)
            self._pw_challenge = packet.password

        else:
            authmethods.append(u"anonymous")
            msg = message.Hello(
                realm=realm,
                roles=roles,
                authmethods=authmethods,
                authid=packet.client_id,
                authextra=authextra)

        self._wamp_session.onMessage(msg)

        if packet.flags.will:

            # it's unclear from the MQTT spec whether a) the publication of the last will
            # is to happen in-band during "connect", and if it fails, deny the connection,
            # or b) the last will publication happens _after_ "connect", and the connection
            # succeeds regardless whether the last will publication succeeds or not.
            #
            # we opt for b) here!
            #
            @inlineCallbacks
            @self._waiting_for_connect.addCallback
            def process_will(res):

                self.log.info()

                payload_format, mapped_topic, options = yield self.factory.transform_mqtt(packet.will_topic, packet.will_message)

                request = util.id()

                msg = message.Call(
                    request=request,
                    procedure=u"wamp.session.add_testament",
                    args=[
                        mapped_topic,
                        options.get('args', None),
                        options.get('kwargs', None),
                        {
                            # specifiy "retain" for when the testament (last will)
                            # will be auto-published by the broker later
                            u'retain': bool(packet.flags.will_retain)
                        }
                    ])

                self._wamp_session.onMessage(msg)

                returnValue(res)

        return self._waiting_for_connect

    @inlineCallbacks
    def _publish(self, event, acknowledge=None):
        """
        Given a MQTT event, create a WAMP Publish message and
        forward that on the forwarding WAMP session.
        """
        try:
            payload_format, mapped_topic, options = yield self.factory.transform_mqtt(event.topic_name, event.payload)
        except:
            self.log.failure()
            return

        request = util.id()

        msg = message.Publish(
            request=request,
            topic=mapped_topic,
            exclude_me=False,
            acknowledge=acknowledge,
            retain=event.retain,
            **options)

        self._wamp_session.onMessage(msg)

        if event.qos_level > 0:
            self._request_to_packetid[request] = event.packet_identifier

        returnValue(0)

    def process_publish_qos_0(self, event):
        try:
            return self._publish(event)
        except:
            self.log.failure()

    def process_publish_qos_1(self, event):
        try:
            return self._publish(event, acknowledge=True)
        except:
            self.log.failure()

    def process_puback(self, event):
        return

    def process_pubrec(self, event):
        return

    def process_pubrel(self, event):
        return

    def process_pubcomp(self, event):
        return

    def process_subscribe(self, packet):

        packet_watch = OrderedDict()
        d = Deferred()

        @d.addCallback
        def _(ign):
            self._mqtt.send_suback(packet.packet_identifier, [x["response"] for x in packet_watch.values()])
            del self._inflight_subscriptions[packet.packet_identifier]
            del self._subrequest_callbacks[packet.packet_identifier]

        self._subrequest_callbacks[packet.packet_identifier] = d
        self._inflight_subscriptions[packet.packet_identifier] = packet_watch

        for n, x in enumerate(packet.topic_requests):

            topic, match = _mqtt_topicfilter_to_wamp(x.topic_filter)

            self.log.info('process_subscribe -> topic={topic}, match={match}', topic=topic, match=match)

            request_id = util.id()

            msg = message.Subscribe(
                request=request_id,
                topic=topic,
                match=match,
                get_retained=True,
            )

            try:
                packet_watch[request_id] = {"response": -1, "topic": x.topic_filter}
                self._subrequest_to_mqtt_subrequest[request_id] = packet.packet_identifier
                self._wamp_session.onMessage(msg)
            except:
                self.log.failure()
                packet_watch[request_id] = {"response": 128}

    @inlineCallbacks
    def process_unsubscribe(self, packet):

        for topic in packet.topics:
            if topic in self._subscriptions:
                yield self._subscriptions.pop(topic).unsubscribe()

        return

    def dataReceived(self, data):
        self._mqtt.dataReceived(data)


class WampMQTTServerFactory(Factory):

    log = make_logger()

    protocol = WampMQTTServerProtocol

    serializers = {
        u'json': JsonObjectSerializer(),
        u'msgpack': MsgPackObjectSerializer(),
        u'cbor': CBORObjectSerializer(),
        u'ubjson': UBJSONObjectSerializer(),
    }

    def __init__(self, router_session_factory, config, reactor):
        self._router_session_factory = router_session_factory
        self._router_factory = router_session_factory._routerFactory
        self._options = config.get(u'options', {})
        self._realm = self._options.get(u'realm', None)
        self._reactor = reactor
        self._payload_mapping = StringTrie()
        for topic, pmap in self._options.get(u'payload_mapping', {}).items():
            self._set_payload_format(topic, pmap)

    def buildProtocol(self, addr):
        protocol = self.protocol(self._reactor)
        protocol.factory = self
        return protocol

    def _get_payload_format(self, topic):
        """
        Map a WAMP topic URI to MQTT payload format.
        :param topic: WAMP URI.
        :type topic: str

        :returns: Payload format metadata.
        :rtype: dict
        """
        try:
            pmap = self._payload_mapping.longest_prefix_value(topic)
        except KeyError:
            return None
        else:
            return pmap

    def _set_payload_format(self, topic, pmap=None):
        if pmap is None:
            if topic in self._payload_mapping:
                del self._payload_mapping[topic]
        else:
            self._payload_mapping[topic] = pmap

    @inlineCallbacks
    def transform_wamp(self, topic, msg):
        # check for cached transformed payload
        cache_key = u'_{}_{}'.format(self.__class__.__name__, id(self))
        cached = msg._serialized.get(cache_key, None)

        if cached:
            payload_format, mapped_topic, payload = cached
            self.log.debug('using cached payload for {cache_key} in message {msg_id}!', msg_id=id(msg), cache_key=cache_key)
        else:
            # convert WAMP URI to MQTT topic
            mapped_topic = _wamp_topic_to_mqtt(topic)

            # for WAMP->MQTT, the payload mapping is determined from the
            # WAMP URI (not the transformed MQTT topic)
            payload_format = self._get_payload_format(topic)
            payload_format_type = payload_format[u'type']

            if payload_format_type == u'passthrough':
                payload = msg.payload

            elif payload_format_type == u'native':
                serializer = payload_format.get(u'serializer', None)
                payload = self._transform_wamp_native(serializer, msg)

            elif payload_format_type == u'dynamic':
                    encoder = payload_format.get(u'encoder', None)
                    codec_realm = payload_format.get(u'realm', self._realm)
                    payload = yield self._transform_wamp_dynamic(encoder, codec_realm, mapped_topic, topic, msg)
            else:
                raise Exception('payload format {} not implemented'.format(payload_format))

            msg._serialized[cache_key] = (payload_format, mapped_topic, payload)

        self.log.debug('transform_wamp({topic}, {msg}) -> payload_format={payload_format}, mapped_topic={mapped_topic}, payload={payload}', topic=topic, msg=msg, payload_format=payload_format, mapped_topic=mapped_topic, payload=payload)
        returnValue((payload_format, mapped_topic, payload))

    @inlineCallbacks
    def _transform_wamp_dynamic(self, encoder, codec_realm, mapped_topic, topic, msg):
        codec_session = self._router_factory.get(codec_realm)._realm.session
        payload = yield codec_session.call(encoder, mapped_topic, topic, msg.args, msg.kwargs)
        returnValue(payload)

    def _transform_wamp_native(self, serializer, msg):
        obj = {}
        for opt in [u'args',
                    u'kwargs',
                    u'exclude',
                    u'exclude_authid',
                    u'exclude_authrole',
                    u'eligible',
                    u'eligible_authid',
                    u'eligible_authrole']:
            attr = getattr(msg, opt, None)
            if attr is not None:
                obj[opt] = attr

        if serializer in self.serializers:
            payload = self.serializers[serializer].serialize(obj)
        else:
            raise Exception('MQTT native mode payload transform: invalid serializer {}'.format(serializer))

        return payload

    @inlineCallbacks
    def transform_mqtt(self, topic, payload):
        # transform MQTT topic to WAMP URI
        mapped_topic = _mqtt_topicname_to_wamp(topic)

        # for MQTT->WAMP, the payload mapping is determined from the
        # transformed WAMP URI (not the original MQTT topic)
        payload_format = self._get_payload_format(mapped_topic)
        payload_format_type = payload_format[u'type']

        if payload_format_type == u'passthrough':
            options = {
                u'payload': payload,
                u'enc_algo': u'mqtt'
            }

        elif payload_format_type == u'native':
            serializer = payload_format.get(u'serializer', None)
            options = self._transform_mqtt_native(serializer, payload)

        elif payload_format_type == u'dynamic':
            decoder = payload_format.get(u'decoder', None)
            codec_realm = payload_format.get(u'realm', self._realm)
            options = yield self._transform_mqtt_dynamic(decoder, codec_realm, mapped_topic, topic, payload)

        else:
            raise Exception('payload format {} not implemented'.format(payload_format))

        self.log.debug('transform_mqtt({topic}, {payload}) -> payload_format={payload_format}, mapped_topic={mapped_topic}, options={options}', topic=topic, payload=payload, payload_format=payload_format, mapped_topic=mapped_topic, options=options)
        returnValue((payload_format, mapped_topic, options))

    @inlineCallbacks
    def _transform_mqtt_dynamic(self, decoder, codec_realm, mapped_topic, topic, payload):
        codec_session = self._router_factory.get(codec_realm)._realm.session
        options = yield codec_session.call(decoder, mapped_topic, topic, payload)
        returnValue(options)

    def _transform_mqtt_native(self, serializer, payload):
        """
        Transform MQTT binary payload from a MQTT Publish to keyword dict
        suitable for the constructor of a WAMP Publish message,
        that is :class:`autobahn.wamp.message.Publish`.
        """
        options = {}
        if serializer in self.serializers:
            if serializer == u'json':
                if not _validator.validate(payload)[0]:
                    # invalid UTF-8: drop the event
                    raise Exception('invalid UTF8 in JSON encoded MQTT payload')
            obj = self.serializers[serializer].unserialize(payload)[0]
        else:
            raise Exception('"{}" serializer for encoded MQTT payload not implemented'.format(serializer))

        if type(obj) != dict:
            raise Exception('invalid type {} for "{}" encoded MQTT payload'.format(type(obj), serializer))

        for opt in [u'args',
                    u'kwargs',
                    u'exclude',
                    u'exclude_authid',
                    u'exclude_authrole',
                    u'eligible',
                    u'eligible_authid',
                    u'eligible_authrole']:
            if opt in obj:
                options[opt] = obj[opt]

        return options
