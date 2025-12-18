Introduction
============

**Crossbar.io** is an open source networking platform for distributed and
microservice applications. It implements the open Web Application Messaging
Protocol (WAMP), is feature rich, scalable, robust and secure.

What is Crossbar.io?
--------------------

Crossbar.io is a WAMP router that provides:

* **Publish/Subscribe** (PubSub) messaging for real-time notifications
* **Remote Procedure Calls** (RPC) for request/response patterns
* **Routed RPC** for decoupled distributed systems
* **Pattern-based routing** for flexible message targeting

Key Features
------------

**WAMP Router**
    Full implementation of the WAMP protocol for both Basic and Advanced Profiles

**Multi-Transport**
    Support for WebSocket, RawSocket, and HTTP/Long-Poll transports

**Authentication**
    Multiple authentication methods including WAMP-CRA, Ticket, TLS client certificates,
    Cookie-based, and Anonymous

**Authorization**
    Fine-grained, URI pattern-based authorization for all WAMP operations

**Web Services**
    Built-in static file serving, reverse proxy, CGI, and more

**MQTT Bridge**
    Protocol bridging to MQTT for IoT device integration

Why Crossbar.io?
----------------

* **Open Source**: Apache 2.0 licensed
* **Production Ready**: Battle-tested in production deployments
* **Scalable**: Horizontal scaling with router clustering
* **Secure**: TLS/SSL, end-to-end encryption support
* **Flexible**: Extensive configuration options

Getting Started
---------------

New to Crossbar.io? Start with:

1. :doc:`Installation` - Get Crossbar.io installed
2. :doc:`Getting-Started` - Your first WAMP application
3. :doc:`Basic-Concepts` - Understanding WAMP messaging

.. note::

    Crossbar.io builds on `Autobahn|Python <https://autobahn.readthedocs.io/>`_
    for WebSocket and WAMP protocol implementation.
