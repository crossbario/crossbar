:orphan:

Router Transports
=================

Transports are necessary for allowing incoming connections to *Routers*.
This applies to WAMP connections as well as for other services that
*Routers* provide, such as :doc:`Web Services <../web-service/Web-Services>` .

Crossbar.io provides the following transports for WAMP

-  :doc:`WebSocket Transport <transport/WebSocket-Transport>`
-  :doc:`RawSocket Transport <transport/RawSocket-Transport>`

as well as

-  :doc:`Web Transport and Services <transport/Web-Transport-and-Services>`

which include WebSocket as one suboption.

All of above is running over :doc:`Transport
Endpoints <transport/Transport-Endpoints>`, so you need that as well to get a
fully working transport.

    For completeness, there is also the  :doc:`Flash Policy auxiliary
    transport <transport/Flash-Policy-Transport>`, and special transports
    for  :doc:`TCP Benchmarks <../production/Stream-Testee>` and  :doc:`WebSocket
    Testing <../production/WebSocket-Compliance-Testing>`.

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

-  :doc:`WAMP over WebSocket Transport <transport/WebSocket-Transport>`
-  :doc:`WAMP over RawSocket Transport <transport/RawSocket-Transport>`
-  :doc:`WAMP over Longpoll            <../web-service/Long-Poll-Service>`