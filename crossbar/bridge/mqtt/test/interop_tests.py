#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.selectreactor import SelectReactor

from .interop import Result, ReplayClientFactory, Frame, ConnectionLoss
from crossbar.bridge.mqtt_events import (Connect, ConnectFlags, ConnACK, Publish, PubACK, PubREL, PubREC, PubCOMP,
                                         Subscribe, SubscriptionTopicRequest, SubACK, Disconnect)


def test_connect(host, port):
    record = [
        Frame(send=True, data=Connect(client_id="test_cleanconnect", flags=ConnectFlags(clean_session=True))),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(send=True, data=Disconnect()),
        ConnectionLoss(),
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("connect", f.success, f.reason, f.client_transcript)


def test_quirks_mode_connect(host, port):
    record = [
        Frame(send=True, data=b"\x10\x15\x00\x04MQTT\x04\x02\x00x\x00\x07testqrk\x00\x00"),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(send=True, data=Disconnect()),
        ConnectionLoss(),
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("connect_quirks", f.success, f.reason, f.client_transcript)


def test_reserved_packet_15(host, port):
    record = [
        Frame(send=True, data=Connect(client_id="test_reserved15", flags=ConnectFlags(clean_session=True))),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            #        v pkt 15 right here
            data=b"\xf0\x13\x00\x04MQTT\x04\x02\x00\x02\x00\x07test123"),
        ConnectionLoss()
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("reserved_pkt15", f.success, f.reason, f.client_transcript)


def test_reserved_packet_0(host, port):
    record = [
        Frame(send=True, data=Connect(client_id="test_reserved0", flags=ConnectFlags(clean_session=True))),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            #        v pkt 0 right here
            data=b"\x00\x13\x00\x04MQTT\x04\x02\x00\x02\x00\x07test123"),
        ConnectionLoss()
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("reserved_pkt0", f.success, f.reason, f.client_transcript)


def test_uninvited_puback(host, port):
    record = [
        Frame(send=True, data=Connect(client_id="test_puback", flags=ConnectFlags(clean_session=True))),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(send=True, data=PubACK(packet_identifier=1234)),
        Frame(send=False, data=b""),
        Frame(send=True, data=Disconnect()),
        ConnectionLoss(),
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("uninvited_puback", f.success, f.reason, f.client_transcript)


def test_uninvited_pubrel(host, port):
    record = [
        Frame(send=True, data=Connect(client_id="test_pubrel", flags=ConnectFlags(clean_session=True))),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(send=True, data=PubREL(packet_identifier=1234)),
        Frame(send=False, data=PubCOMP(packet_identifier=1234)),
        Frame(send=True, data=Disconnect()),
        ConnectionLoss(),
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("uninvited_pubrel", f.success, f.reason, f.client_transcript)


def test_self_subscribe(host, port):
    record = [
        Frame(send=True, data=Connect(client_id="test_selfsub", flags=ConnectFlags(clean_session=True))),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(send=True, data=Subscribe(packet_identifier=1234, topic_requests=[SubscriptionTopicRequest("foo", 2)])),
        Frame(send=False, data=SubACK(packet_identifier=1234, return_codes=[2])),
        Frame(send=True, data=Publish(duplicate=False, qos_level=0, topic_name="foo", payload=b"abc", retain=False)),
        Frame(send=False, data=Publish(duplicate=False, qos_level=0, topic_name="foo", payload=b"abc", retain=False)),
        Frame(send=True, data=Disconnect()),
        ConnectionLoss(),
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("self_subscribe", f.success, f.reason, f.client_transcript)


def test_qos2_send_wrong_confirm(host, port):
    record = [
        Frame(send=True, data=Connect(client_id="test_wrong_confirm_qos2", flags=ConnectFlags(clean_session=True))),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(send=True, data=Subscribe(packet_identifier=1234, topic_requests=[SubscriptionTopicRequest("foo", 2)])),
        Frame(send=False, data=SubACK(packet_identifier=1234, return_codes=[2])),
        Frame(send=True,
              data=Publish(duplicate=False,
                           qos_level=2,
                           topic_name="foo",
                           payload=b"abc",
                           retain=False,
                           packet_identifier=12)),
        Frame(send=False,
              data=[
                  PubREC(packet_identifier=12),
                  Publish(duplicate=False,
                          qos_level=2,
                          topic_name="foo",
                          payload=b"abc",
                          retain=False,
                          packet_identifier=1),
                  PubCOMP(packet_identifier=12)
              ]),
        Frame(send=True, data=PubREL(packet_identifier=12)),
        Frame(send=True, data=PubACK(packet_identifier=1)),
        Frame(send=False, data=b""),
        Frame(send=True, data=Disconnect()),
        ConnectionLoss(),
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("qos2_wrong_confirm", f.success, f.reason, f.client_transcript)


def test_qos1_send_wrong_confirm(host, port):
    record = [
        Frame(send=True, data=Connect(client_id="test_wrong_confirm_qos1", flags=ConnectFlags(clean_session=True))),
        Frame(send=False, data=ConnACK(session_present=False, return_code=0)),
        Frame(send=True, data=Subscribe(packet_identifier=1234, topic_requests=[SubscriptionTopicRequest("foo", 2)])),
        Frame(send=False, data=SubACK(packet_identifier=1234, return_codes=[2])),
        Frame(send=True,
              data=Publish(duplicate=False,
                           qos_level=1,
                           topic_name="foo",
                           payload=b"abc",
                           retain=False,
                           packet_identifier=12)),
        Frame(send=False,
              data=[
                  PubACK(packet_identifier=12),
                  Publish(duplicate=False,
                          qos_level=1,
                          topic_name="foo",
                          payload=b"abc",
                          retain=False,
                          packet_identifier=1)
              ]),
        # We send a pubrel to the packet_id expecting a puback
        Frame(send=True, data=PubREL(packet_identifier=1)),
        # ..aaaaand we get a pubcomp back (even though mosquitto warns).
        Frame(send=False, data=PubCOMP(packet_identifier=1)),
        Frame(send=True, data=Disconnect()),
        ConnectionLoss(),
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("qos1_wrong_confirm", f.success, f.reason, f.client_transcript)
