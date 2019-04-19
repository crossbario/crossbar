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

from __future__ import absolute_import, division

import json

from crossbar.router.test.helpers import make_router, connect_application_session, add_realm_to_router

from twisted.trial.unittest import TestCase
from twisted.internet.task import Clock, LoopingCall
from twisted.test.proto_helpers import AccumulatingProtocol
from twisted.test.iosim import connect, FakeTransport
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import Factory, Protocol
from twisted.internet import selectreactor
from twisted.python.filepath import FilePath

from autobahn.wamp.types import ComponentConfig
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from crossbar.router.role import RouterRoleStaticAuth

from crossbar.bridge.mqtt.wamp import WampMQTTServerFactory
from crossbar.bridge.mqtt._events import (
    Connect, ConnectFlags, ConnACK, Publish, PubACK,
    Subscribe, SubscriptionTopicRequest, SubACK,
    Disconnect,
)
from crossbar._logging import LogCapturer
from crossbar.common.twisted.endpoint import (create_listening_endpoint_from_config,
                                              create_connecting_endpoint_from_config)

from txaio.tx import make_logger

# import txaio
# txaio.start_logging(level='info')


class ObservingSession(ApplicationSession):
    _topic = u'test'

    @inlineCallbacks
    def onJoin(self, details):
        self.events = []

        def on_event(*a, **kw):
            evt = {'args': a, 'kwargs': kw}
            self.events.append(evt)
            print(evt)
            self.log.info('event on {topic}: {evt}', topic=self._topic, evt=evt)

        self.s = yield self.subscribe(on_event, self._topic)


def build_mqtt_server():

    reactor = Clock()
    router_factory, server_factory, session_factory = make_router()

    add_realm_to_router(router_factory, session_factory)
    router = add_realm_to_router(router_factory,
                                 session_factory,
                                 realm_name=u'mqtt',
                                 realm_options={})

    # allow everything
    default_permissions = {
        u'uri': u'',
        u'match': u'prefix',
        u'allow': {
            u'call': True,
            u'register': True,
            u'publish': True,
            u'subscribe': True
        }
    }

    router.add_role(RouterRoleStaticAuth(router, u'mqttrole', default_permissions=default_permissions))

    class AuthenticatorSession(ApplicationSession):

        @inlineCallbacks
        def onJoin(self, details):

            def authenticate(realm, authid, details):

                if authid == u"test123":

                    if details["ticket"] != u'password':
                        raise ApplicationError(u'com.example.invalid_ticket', u'nope')

                    res = {
                        u'realm': u'mqtt',
                        u'role': u'mqttrole',
                        u'extra': {}
                    }
                    return res

                else:
                    raise ApplicationError(u'com.example.no_such_user', u'nah')

            yield self.register(authenticate, u'com.example.auth')

            def tls(realm, authid, details):
                ACCEPTED_CERTS = set([u'95:1C:A9:6B:CD:8D:D2:BD:F4:73:82:01:55:89:41:12:9C:F8:AF:8E'])

                if 'client_cert' not in details['transport'] or not details['transport']['client_cert']:
                    raise ApplicationError(u"com.example.no_cert", u"no client certificate presented")

                client_cert = details['transport']['client_cert']
                sha1 = client_cert['sha1']
                subject_cn = client_cert['subject']['cn']

                if sha1 not in ACCEPTED_CERTS:
                    raise ApplicationError(u"com.example.invalid_cert", u"certificate with SHA1 {} denied".format(sha1))
                else:
                    return {
                        u'authid': subject_cn,
                        u'role': u'mqttrole',
                        u'realm': u'mqtt'
                    }

            yield self.register(tls, u'com.example.tls')

    config = ComponentConfig(u"default", {})
    authsession = AuthenticatorSession(config)
    session_factory.add(authsession, router, authrole=u"trusted")

    options = {
        u"options": {
            u"realm": u"mqtt",
            u"role": u"mqttrole",
            u"payload_mapping": {
                u"": {
                    u"type": u"native",
                    u"serializer": u"json"
                }
            },
            u"auth": {
                u"ticket": {
                    u"type": u"dynamic",
                    u"authenticator": u"com.example.auth",
                    u"authenticator-realm": u"default",
                },
                u"tls": {
                    u"type": u"dynamic",
                    u"authenticator": u"com.example.tls",
                    u"authenticator-realm": u"default",
                }
            }
        }
    }

    mqtt_factory = WampMQTTServerFactory(session_factory, options, reactor)

    server_factory._mqtt_factory = mqtt_factory

    return reactor, router, server_factory, session_factory


def connect_mqtt_server(server_factory):

    server_protocol = server_factory.buildProtocol(None)
    server_transport = FakeTransport(server_protocol, True)

    client_protocol = AccumulatingProtocol()
    client_transport = FakeTransport(client_protocol, False)

    mqtt_pump = connect(server_protocol, server_transport, client_protocol,
                        client_transport, debug=False)

    return client_transport, client_protocol, mqtt_pump


class MQTTAdapterTests(TestCase):

    def setUp(self):

        self.logs = LogCapturer()
        self.logs.__enter__()
        self.addCleanup(lambda: self.logs.__exit__(None, None, None))

    def _test_basic_publish(self):

        reactor, router, server_factory, session_factory = build_mqtt_server()

        session, pump = connect_application_session(
            server_factory, ObservingSession, component_config=ComponentConfig(realm=u"mqtt"))
        client_transport, client_protocol, mqtt_pump = connect_mqtt_server(server_factory)

        client_transport.write(
            Connect(client_id=u"testclient", username=u"test123", password=u"password",
                    flags=ConnectFlags(clean_session=False, username=True, password=True)).serialise())
        mqtt_pump.flush()

        # We get a CONNECT
        self.assertEqual(client_protocol.data,
                         ConnACK(session_present=False, return_code=0).serialise())
        client_protocol.data = b""

        client_transport.write(
            Publish(duplicate=False, qos_level=0, retain=False, topic_name=u"test", payload=b'{"kwargs": {"bar": "baz"}}').serialise())
        mqtt_pump.flush()
        pump.flush()

        # This needs to be replaced with the real deal, see https://github.com/crossbario/crossbar/issues/885
        self.assertEqual(len(session.events), 1)
        self.assertEqual(
            session.events,
            [{"args": tuple(),
              "kwargs": {u'bar': u'baz'}}])

    def _test_tls_auth(self):
        """
        A MQTT client can connect using mutually authenticated TLS
        authentication.
        """
        reactor, router, server_factory, session_factory = build_mqtt_server()
        real_reactor = selectreactor.SelectReactor()
        logger = make_logger()

        session, pump = connect_application_session(
            server_factory, ObservingSession, component_config=ComponentConfig(realm=u"mqtt"))

        endpoint = create_listening_endpoint_from_config({
            "type": "tcp",
            "port": 1099,
            "interface": "0.0.0.0",
            "tls": {
                "certificate": "server.crt",
                "key": "server.key",
                "dhparam": "dhparam",
                "ca_certificates": [
                    "ca.cert.pem",
                    "intermediate.cert.pem"
                ]},
        }, FilePath(__file__).sibling('certs').path, real_reactor, logger)

        client_endpoint = create_connecting_endpoint_from_config({
            "type": "tcp",
            "host": "127.0.0.1",
            "port": 1099,
            "tls": {
                "certificate": "client.crt",
                "hostname": u"localhost",
                "key": "client.key",
                "ca_certificates": [
                    "ca.cert.pem",
                    "intermediate.cert.pem"
                ]},
        }, FilePath(__file__).sibling('certs').path, real_reactor, logger)

        p = []
        l = endpoint.listen(server_factory)

        class TestProtocol(Protocol):
            data = b""
            expected = (ConnACK(session_present=False, return_code=0).serialise() + PubACK(packet_identifier=1).serialise())

            def dataReceived(self_, data):
                self_.data = self_.data + data

                if len(self_.data) == len(self_.expected):
                    self.assertEqual(self_.data, self_.expected)
                    real_reactor.stop()

        @l.addCallback
        def _listening(factory):
            d = client_endpoint.connect(Factory.forProtocol(TestProtocol))

            @d.addCallback
            def _(proto):
                p.append(proto)

                proto.transport.write(
                    Connect(client_id=u"test123",
                            flags=ConnectFlags(clean_session=False)).serialise())

                proto.transport.write(
                    Publish(duplicate=False, qos_level=1, retain=False, topic_name=u"test", payload=b"{}", packet_identifier=1).serialise())

        lc = LoopingCall(pump.flush)
        lc.clock = real_reactor
        lc.start(0.01)

        def timeout():
            print("Timing out :(")
            real_reactor.stop()
            print(self.logs.log_text.getvalue())

        # Timeout, just in case
        real_reactor.callLater(10, timeout)
        real_reactor.run()

        client_protocol = p[0]

        # We get a CONNECT
        self.assertEqual(client_protocol.data,
                         ConnACK(session_present=False, return_code=0).serialise() + PubACK(packet_identifier=1).serialise())
        client_protocol.data = b""

        pump.flush()

        # This needs to be replaced with the real deal, see https://github.com/crossbario/crossbar/issues/885
        self.assertEqual(len(session.events), 1)
        self.assertEqual(
            session.events,
            [{"args": tuple(),
              "kwargs": {}}])

    def test_tls_auth_denied(self):
        """
        A MQTT client offering the wrong certificate won't be authenticated.
        """
        reactor, router, server_factory, session_factory = build_mqtt_server()
        real_reactor = selectreactor.SelectReactor()
        logger = make_logger()

        session, pump = connect_application_session(
            server_factory, ObservingSession, component_config=ComponentConfig(realm=u"mqtt"))

        endpoint = create_listening_endpoint_from_config({
            "type": "tcp",
            "port": 1099,
            "interface": "0.0.0.0",
            "tls": {
                "certificate": "server.crt",
                "key": "server.key",
                "dhparam": "dhparam",
                "ca_certificates": [
                    "ca.cert.pem",
                    "intermediate.cert.pem"
                ]},
        }, FilePath(__file__).sibling('certs').path, real_reactor, logger)

        client_endpoint = create_connecting_endpoint_from_config({
            "type": "tcp",
            "host": "127.0.0.1",
            "port": 1099,
            "tls": {
                # BAD key: trusted by the CA, but wrong ID
                "certificate": "client_1.crt",
                "hostname": u"localhost",
                "key": "client_1.key",
                "ca_certificates": [
                    "ca.cert.pem",
                    "intermediate.cert.pem"
                ]},
        }, FilePath(__file__).sibling('certs').path, real_reactor, logger)

        p = []
        l = endpoint.listen(server_factory)

        class TestProtocol(Protocol):
            data = b""
            expected = (
                ConnACK(session_present=False, return_code=1).serialise())

            def dataReceived(self_, data):
                self_.data = self_.data + data

                if len(self_.data) == len(self_.expected):
                    self.assertEqual(self_.data, self_.expected)
                    real_reactor.stop()

        @l.addCallback
        def _listening(factory):
            d = client_endpoint.connect(Factory.forProtocol(TestProtocol))

            @d.addCallback
            def _(proto):
                p.append(proto)

                proto.transport.write(
                    Connect(client_id=u"test123",
                            flags=ConnectFlags(clean_session=False)).serialise())

                proto.transport.write(
                    Publish(duplicate=False, qos_level=1, retain=False, topic_name=u"test", payload=b"{}", packet_identifier=1).serialise())

        lc = LoopingCall(pump.flush)
        lc.clock = real_reactor
        lc.start(0.01)

        def timeout():
            print("Timing out :(")
            real_reactor.stop()
            print(self.logs.log_text.getvalue())

        # Timeout, just in case
        real_reactor.callLater(10, timeout)
        real_reactor.run()

        client_protocol = p[0]

        # We get a CONNECT
        self.assertEqual(client_protocol.data,
                         ConnACK(session_present=False, return_code=1).serialise())
        client_protocol.data = b""

        pump.flush()

        # No events!
        self.assertEqual(len(session.events), 0)

    def _test_basic_subscribe(self):
        """
        The MQTT client can subscribe to a WAMP topic and get messages.
        """
        reactor, router, server_factory, session_factory = build_mqtt_server()
        client_transport, client_protocol, mqtt_pump = connect_mqtt_server(server_factory)

        session, pump = connect_application_session(
            server_factory, ApplicationSession, component_config=ComponentConfig(realm=u"mqtt"))

        client_transport.write(
            Connect(client_id=u"testclient", username=u"test123", password=u"password",
                    flags=ConnectFlags(clean_session=False, username=True, password=True)).serialise())
        client_transport.write(
            Subscribe(packet_identifier=1, topic_requests=[
                SubscriptionTopicRequest(topic_filter=u"com/test/wamp", max_qos=0)
            ]).serialise())

        mqtt_pump.flush()

        self.assertEqual(
            client_protocol.data,
            (ConnACK(session_present=False, return_code=0).serialise() + SubACK(packet_identifier=1, return_codes=[0]).serialise()))
        client_protocol.data = b""

        session.publish(u"com.test.wamp", u"bar")
        pump.flush()

        reactor.advance(0.1)
        mqtt_pump.flush()

        self.assertEqual(
            client_protocol.data,
            Publish(duplicate=False, qos_level=0, retain=False,
                    topic_name=u"com/test/wamp",
                    payload=b'{"args":["bar"]}').serialise()
        )

    def _test_retained(self):
        """
        The MQTT client can set and receive retained messages.
        """
        reactor, router, server_factory, session_factory = build_mqtt_server()
        client_transport, client_protocol, mqtt_pump = connect_mqtt_server(server_factory)

        client_transport.write(
            Connect(client_id=u"testclient", username=u"test123", password=u"password",
                    flags=ConnectFlags(clean_session=False, username=True, password=True)).serialise())

        client_transport.write(
            Publish(duplicate=False, qos_level=1, retain=True,
                    topic_name=u"com/test/wamp", packet_identifier=123,
                    payload=b'{}').serialise())

        mqtt_pump.flush()

        self.assertEqual(
            client_protocol.data,
            (
                ConnACK(session_present=False, return_code=0).serialise() + PubACK(packet_identifier=123).serialise()
            ))
        client_protocol.data = b""

        client_transport.write(
            Subscribe(packet_identifier=1, topic_requests=[
                SubscriptionTopicRequest(topic_filter=u"com/test/wamp", max_qos=0)
            ]).serialise())

        mqtt_pump.flush()

        self.assertEqual(
            client_protocol.data,
            SubACK(packet_identifier=1, return_codes=[0]).serialise())
        client_protocol.data = b""

        reactor.advance(0.1)
        mqtt_pump.flush()

        # This needs to be replaced with the real deal, see https://github.com/crossbario/crossbar/issues/885
        self.assertEqual(
            client_protocol.data,
            Publish(duplicate=False, qos_level=0, retain=True,
                    topic_name=u"com/test/wamp",
                    payload=json.dumps(
                        {},
                        sort_keys=True).encode('utf8')
                    ).serialise()
        )

    def _test_lastwill(self):
        """
        FIXME: reactivate this test.

        The MQTT client can set a last will message which will be published
        when it disconnects.
        """
        reactor, router, server_factory, session_factory = build_mqtt_server()
        session, pump = connect_application_session(
            server_factory, ObservingSession, component_config=ComponentConfig(realm=u"mqtt"))
        client_transport, client_protocol, mqtt_pump = connect_mqtt_server(server_factory)

        client_transport.write(
            Connect(client_id=u"testclient", username=u"test123", password=u"password",
                    will_topic=u"test", will_message=b'{"args":["foobar"]}',
                    flags=ConnectFlags(clean_session=False, username=True,
                                       password=True, will=True)).serialise())

        mqtt_pump.flush()

        # We get a CONNECT
        self.assertEqual(client_protocol.data,
                         ConnACK(session_present=False, return_code=0).serialise())
        client_protocol.data = b""

        client_transport.write(Disconnect().serialise())

        mqtt_pump.flush()
        pump.flush()

        self.assertEqual(client_transport.disconnected, True)

        # This needs to be replaced with the real deal, see https://github.com/crossbario/crossbar/issues/885
        self.assertEqual(len(session.events), 1)
        self.assertEqual(
            session.events,
            [{"args": [u"foobar"]}])
