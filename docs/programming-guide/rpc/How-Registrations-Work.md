[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > RPC > How Registrations Work

# How Registrations Work

With the Remote Procedure Call (RPC) messaging pattern in WAMP, any WAMP client can register a procedure for remote calling (become a callee). The procedure is registered for being called using a call URI (e.g. "com.myapp.myprocedure1").

> Note: There are some [specific rules regarding URI formatting](URI Format).

The registration is with the WAMP router, and calls for the procedure are also made to the router. The router then forwards a call to a respective callee. Unlike with traditional RPCs, this means that the caller does not have any knowledge of the callee's identity, and that all calls are routed via a single connection between the caller and the WAMP router respectively the callee and the WAMP router.

The callee receives a registration ID for the procedure it registers. While the caller uses the procedure URI to call a procedure, calls to the procedure from the WAMP router are made using this registration ID.

Using the registration ID, a callee can unregister the procedure at any time.

As a default, exact matching is used for RPCs, i.e. a call is only accepted (and routed to a callee) if a callee has registered for the exact URI used by a caller. Additionally, patter-based registrations are possible, e.g. a callee could register a URI which is prefix-matched, so that a registration for "com.myapp.create" would lead to calls for both "com.myapp.create.user" and  "com.myapp.create.device" to be accepted and invoked on the callee. For more on this see

* [Pattern-Based Registrations](Pattern Based Registrations).

As a default, a procedure can only be registered by a single callee. All further registration attempts return an error. The routed nature of RPCs as implemented by WAMP allows other patterns as well, i.e. multiple registrations may be allowed, and the procedure is then invoked  on the last callee to register which is currently still connected. For more on this see

* [Shared Registrations](Shared Registrations).

Clients can be notfied of events regarding the lifecycle of registrations, and  query for information about existing registrations using the

* [Registration Meta-Events and Procedures](Registration Meta Events and Procedures)

A registered procedure can return a single result (the default) or a set of results over time, see

* [Progressive Call Results](Progressive Call Results)
