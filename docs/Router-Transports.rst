:orphan:

Router Transports
=================

Transports are necessary for allowing incoming connections to *Routers*.
This applies to WAMP connections as well as for other services that
*Routers* provide, such as :doc:`Web Services <Web-Services>` .

Crossbar.io provides the following transports for WAMP

-  :doc:`WebSocket Transport <WebSocket-Transport>`
-  :doc:`RawSocket Transport <RawSocket-Transport>`

as well as

-  :doc:`Web Transport and Services <Web-Transport-and-Services>`

which include WebSocket as one suboption.

All of above is running over :doc:`Transport
Endpoints <Transport-Endpoints>`, so you need that as well to get a
fully working transport.

    For completeness, there is also the  :doc:`Flash Policy auxiliary
    transport <Flash-Policy-Transport>`, and special transports
    for  :doc:`TCP Benchmarks <Stream-Testee>` and  :doc:`WebSocket
    Testing <WebSocket-Compliance-Testing>`.

Background
----------

`WAMP <https://wamp-proto.org/>`__ runs over any transport with the following
characteristics (see the `spec <https://wamp-proto.org/spec.html>`__):

1. message-based
2. reliable
3. ordered
4. bidirectional (full-duplex)

Over which WAMP transport an application component is connected to a
router does not matter. It's completely transparent from the application
component point of view.

The `WAMP spec <https://wamp-proto.org/spec.html>`__ currently defines these
transports:

-  :doc:`WAMP over WebSocket Transport <WebSocket-Transport>`
-  :doc:`WAMP over RawSocket Transport <RawSocket-Transport>`
-  :doc:`WAMP over Longpoll            <Long-Poll-Service>`
