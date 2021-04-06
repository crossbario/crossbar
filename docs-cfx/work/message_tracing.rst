Message Tracing
===============

Crossbar.io Fabric nodes, as part of the *router extensions* that come
with it, contains code to trace all WAMP messages flowing through the
routing core of Crossbar.io.

.. contents:: :local:

----------

Tracing API
-----------

The message tracing feature in Crossbar.io Fabric nodes is exposed as
part of the Crossbar.io Fabric Center management API and available to
any management client or app connecting to CFC.

The Tracing API is described
`here <Management-Api.md#messagetracing>`__.

--------------

Trace Records
~~~~~~~~~~~~~

When retrieving trace data from a trace, data is returned as a list of
*trace records*.

For example,
`here <https://gist.github.com/oberstet/862e9c1662961930867f26c1918b49fa>`__
is the output from a 10s tracing run, with 2 Crossbar.io Fabric nodes
and 4 WAMP clients connected to those 2 nodes, the clients doing some
PubSub and RPC messaging.

A trace record holds the following information about a single WAMP
message that was received from a client by Crossbar.io, or that was sent
by Crossbar.io to the client:

.. code:: javascript

    {
        // the sequence number in the trace of messages stored for this trace
        'seq': 4,

        // timestamps when the message was originally traced
        'pc': 129852.050601509,
        'ts': 1502829396.5978456,

        // the direction of the WAMP message flow: Crossbar.io "received" (rx) a message in this case
        'direction': 'rx',

        // the WAMP message type of the message
        'msg_type': 'Publish',

        // the realm, session ID, authid, authrole of the sender of this WAMP message (the publisher in this case)
        'realm': 'realm1',
        'session_id': 1457801355183687,
        'authid': 'E4MW-VYUX-KY3S-Y6US-J5X5-KAUQ',
        'authrole': 'anonymous',

        // message correlation ID: all WAMP messages traced for a given WAMP action
        // like a RPC have identical correlation
        'correlation': 'd5d9bcec-a3eb-4f0e-875b-6933680bb546',

        // the URI for the WAMP action, the same URI for all messages of a given action
        'uri': 'com.example.oncounter',

        // for outgoing messages, a map of serializions to byte length
        'serializations': {},

        // actual raw WAMP message right before serialization
        'msg': [16,
                46,
                {'acknowledge': True, 'exclude_me': False},
                'com.example.oncounter',
                [21, 'E4MW-VYUX-KY3S-Y6US-J5X5-KAUQ', 'Python']],
    }
