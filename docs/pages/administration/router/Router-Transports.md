[Documentation](.) > [Administration](Administration) > Router Transports

# Router Transports

Transports are necessary for allowing incoming connections to *Routers*. This applies to WAMP connections as well as for other services that *Routers* provide, such as [Web Services](Web Services).

Crossbar.io provides the following transports for WAMP

* [WebSocket Transport](WebSocket Transport)
* [RawSocket Transport](RawSocket Transport)

as well as

* [Web Transport and Services](Web Transport and Services)

which include WebSocket as one suboption.

All of above is running over [Transport Endpoints](Transport Endpoints), so you need that as well to get a fully working transport.

> For completeness, there is also the [Flash Policy auxiliary transport](Flash Policy Transport), and special transports for [TCP Benchmarks](Stream Testee) and [WebSocket Testing](WebSocket Compliance Testing).


## Background

[WAMP](http://wamp.ws/) runs over any transport with the following characteristics (see the [spec](https://github.com/tavendo/WAMP/blob/master/spec/basic.md#transports)):

1. message-based
2. reliable
3. ordered
4. bidirectional (full-duplex)

Over which WAMP transport an application component is connected to a router does not matter. It's completely transparent from the application component point of view.

The [WAMP spec](https://github.com/wamp-proto/wamp-proto/blob/master/rfc/draft-oberstet-hybi-tavendo-wamp.html) currently defines these transports:

* [WAMP-over-WebSocket Transport]
* [WAMP-over-RawSocket Transport]
* [WAMP-over-Longpoll Transport]

Crossbar.io currently supports **18** WAMP transports in total:

![Crossbar.io: supported WAMP Transports](/static/img/docs/gen/crossbar_transports_1.png)

The most common transports are the following:

![Common WAMP Transports](/static/img/docs/gen/crossbar_transports_2.png)

---
