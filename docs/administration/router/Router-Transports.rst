title: Router Transports toc: [Documentation, Administration, Router
Transports]

Router Transports
=================

Transports are necessary for allowing incoming connections to *Routers*.
This applies to WAMP connections as well as for other services that
*Routers* provide, such as `Web Services <Web%20Services>`__.

Crossbar.io provides the following transports for WAMP

-  `WebSocket Transport <WebSocket%20Transport>`__
-  `RawSocket Transport <RawSocket%20Transport>`__

as well as

-  `Web Transport and Services <Web%20Transport%20and%20Services>`__

which include WebSocket as one suboption.

All of above is running over `Transport
Endpoints <Transport%20Endpoints>`__, so you need that as well to get a
fully working transport.

    For completeness, there is also the `Flash Policy auxiliary
    transport <Flash%20Policy%20Transport>`__, and special transports
    for `TCP Benchmarks <Stream%20Testee>`__ and `WebSocket
    Testing <WebSocket%20Compliance%20Testing>`__.

Background
----------

`WAMP <http://wamp.ws/>`__ runs over any transport with the following
characteristics (see the `spec <http://wamp-proto.org/spec/>`__):

1. message-based
2. reliable
3. ordered
4. bidirectional (full-duplex)

Over which WAMP transport an application component is connected to a
router does not matter. It's completely transparent from the application
component point of view.

The `WAMP spec <http://wamp-proto.org/spec/>`__ currently defines these
transports:

-  [WAMP-over-WebSocket Transport]
-  [WAMP-over-RawSocket Transport]
-  [WAMP-over-Longpoll Transport]

--------------
