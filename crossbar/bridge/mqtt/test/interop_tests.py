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

from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.selectreactor import SelectReactor

from .interop import Result, ReplayClientFactory, Frame, ConnectionLoss
from crossbar.bridge.mqtt_events import (
    Connect, ConnectFlags, ConnACK,
    Publish, PubACK, PubREL, PubREC, PubCOMP,
    Subscribe, SubscriptionTopicRequest, SubACK,
    Disconnect)


def test_connect(host, port):
    record = [
        Frame(
            send=True,
            data=Connect(client_id=u"test_cleanconnect",
                         flags=ConnectFlags(clean_session=True))),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            data=Disconnect()),
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
        Frame(
            send=True,
            data=b"\x10\x15\x00\x04MQTT\x04\x02\x00x\x00\x07testqrk\x00\x00"),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            data=Disconnect()),
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
        Frame(
            send=True,
            data=Connect(client_id=u"test_reserved15",
                         flags=ConnectFlags(clean_session=True))),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
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
        Frame(
            send=True,
            data=Connect(client_id=u"test_reserved0",
                         flags=ConnectFlags(clean_session=True))),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
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
        Frame(
            send=True,
            data=Connect(client_id=u"test_puback",
                         flags=ConnectFlags(clean_session=True))),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            data=PubACK(packet_identifier=1234)),
        Frame(
            send=False,
            data=b""),
        Frame(
            send=True,
            data=Disconnect()),
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
        Frame(
            send=True,
            data=Connect(client_id=u"test_pubrel",
                         flags=ConnectFlags(clean_session=True))),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            data=PubREL(packet_identifier=1234)),
        Frame(
            send=False,
            data=PubCOMP(packet_identifier=1234)),
        Frame(
            send=True,
            data=Disconnect()),
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
        Frame(
            send=True,
            data=Connect(client_id=u"test_selfsub",
                         flags=ConnectFlags(clean_session=True))),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            data=Subscribe(packet_identifier=1234,
                           topic_requests=[SubscriptionTopicRequest(u"foo", 2)])),
        Frame(
            send=False,
            data=SubACK(packet_identifier=1234, return_codes=[2])),
        Frame(
            send=True,
            data=Publish(duplicate=False, qos_level=0, topic_name=u"foo",
                         payload=b"abc", retain=False)),
        Frame(
            send=False,
            data=Publish(duplicate=False, qos_level=0, topic_name=u"foo",
                         payload=b"abc", retain=False)),
        Frame(
            send=True,
            data=Disconnect()),
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
        Frame(
            send=True,
            data=Connect(client_id=u"test_wrong_confirm_qos2",
                         flags=ConnectFlags(clean_session=True))),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            data=Subscribe(packet_identifier=1234,
                           topic_requests=[SubscriptionTopicRequest(u"foo", 2)])),
        Frame(
            send=False,
            data=SubACK(packet_identifier=1234, return_codes=[2])),
        Frame(
            send=True,
            data=Publish(duplicate=False, qos_level=2, topic_name=u"foo",
                         payload=b"abc", retain=False, packet_identifier=12)),
        Frame(
            send=False,
            data=[
                PubREC(packet_identifier=12),
                Publish(duplicate=False, qos_level=2, topic_name=u"foo",
                        payload=b"abc", retain=False, packet_identifier=1),
                PubCOMP(packet_identifier=12)]),
        Frame(
            send=True,
            data=PubREL(packet_identifier=12)),
        Frame(
            send=True,
            data=PubACK(packet_identifier=1)),
        Frame(
            send=False,
            data=b""),
        Frame(
            send=True,
            data=Disconnect()),
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
        Frame(
            send=True,
            data=Connect(client_id=u"test_wrong_confirm_qos1",
                         flags=ConnectFlags(clean_session=True))),
        Frame(
            send=False,
            data=ConnACK(session_present=False, return_code=0)),
        Frame(
            send=True,
            data=Subscribe(packet_identifier=1234,
                           topic_requests=[SubscriptionTopicRequest(u"foo", 2)])),
        Frame(
            send=False,
            data=SubACK(packet_identifier=1234, return_codes=[2])),
        Frame(
            send=True,
            data=Publish(duplicate=False, qos_level=1, topic_name=u"foo",
                         payload=b"abc", retain=False, packet_identifier=12)),
        Frame(
            send=False,
            data=[
                PubACK(packet_identifier=12),
                Publish(duplicate=False, qos_level=1, topic_name=u"foo",
                        payload=b"abc", retain=False, packet_identifier=1)]),
        # We send a pubrel to the packet_id expecting a puback
        Frame(
            send=True,
            data=PubREL(packet_identifier=1)),
        # ..aaaaand we get a pubcomp back (even though mosquitto warns).
        Frame(
            send=False,
            data=PubCOMP(packet_identifier=1)),
        Frame(
            send=True,
            data=Disconnect()),
        ConnectionLoss(),
    ]

    r = SelectReactor()
    f = ReplayClientFactory(r, record)
    e = TCP4ClientEndpoint(r, host, port)
    e.connect(f)
    r.run()

    return Result("qos1_wrong_confirm", f.success, f.reason, f.client_transcript)
