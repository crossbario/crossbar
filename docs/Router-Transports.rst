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

Connection Limit
----------------

Every listening transport caps the number of connections open at the
same time on its listening port with ``max_connections``. When the cap is
reached, a new connection is closed right after it is accepted, before
any TLS, WebSocket or RawSocket handshake. The router logs refused
connections (at most once every 10 seconds, with the number refused).
Closing an open connection frees its slot again.

``max_connections`` is set on the transport itself, next to
``endpoint``:

.. code:: json

    {
       "type": "websocket",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "max_connections": 100000
    }

It must be an integer greater than 0, and defaults to **50000**. For a
Universal transport, set it on the Universal transport, not on its
``rawsocket``, ``websocket``, ``mqtt`` or ``web`` parts: the cap belongs to
the listening port, which they share.

As a sizing rule, run one router worker per CPU core: one router worker
handles about 50000 concurrent WAMP-over-WebSocket-over-TLS connections.
For example, a single socket server with 8 cores serves about 400000
connections, and one with 64 cores about 3.2 million.

The operating system limits the number of open file descriptors per
process as well (``ulimit -n``). For a cap of 50000, that limit must be
higher than 50000.

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
