title: Session Meta Events and Procedures
toc: [Documentation, Programming Guide, Session Metaevents and Procedures]

# Session Meta Events and Procedures

> **Session Meta Events and Procedures** is a feature from the WAMP Advanced Profile. The specification can be found [here](https://github.com/tavendo/WAMP/blob/master/spec/advanced/session-meta-api.md).

WAMP enables the monitoring of when sessions join a realm on the router or when they leave it via session metaevents.

It also allows retrieving information about currently connected sessions via session metaprocedures.

Meta-events are created by the router itself. This means that the events as well as the data received when calling a meta-procedure can be accorded the same trust level as the router.

## Events

The set of metaevents covers the lifecycle of a session. A client can subscribe to the following session meta events:

* `wamp.session.on_join`: Is fired when a session joins a realm on the router.
* `wamp.session.on_leave`: Is fired when a session leaves a realm on the router or is disconnected.

The WAMP session meta events are dispatched by the router to the *same realm* as the WAMP session which triggered the event.

**Important**: To receive and process these events, your component will need to have *subscribe* permission on the respective topic.

## Procedures

It is possible to actively retrieve information about sessions via the following procedures.

### Information on Sessions

You can get the count of currently attached sessions via

* `wamp.session.count`: Returns the number of sessions currently attached to the realm.

You can retrieve session IDs via

* `wamp.session.list`: Returns an object with a lists of the session IDs for all  sessions currently attached to the realm

Example code for retrieving the **list of current session IDs**:

```javascript
session.call("wamp.session.list").then(session.log, session.log)
```

Using a session ID, information about a specific session can be retrieved using:

* `wamp.session.get`: Returns data about the session itself: the realm, authentication provider, ID, role and method, as well as about the transport used.

Example code for **getting data about a session**:

```javascript
session.call("wamp.session.get", [23560753]).then(session.log, session.log)
```

### Killing a Session

You can forcibly disconnect a session using:

* `wamp.session.kill`: Disconnects the session, giving a provided reason and message as closing details.

Example code for **killing a session**:

```javaScript
session.call("wamp.session.kill", [23560753], {reason: "because", message: "foobar"}).then(session.log, session.log)
```

> Note: the above examples are for Autobahn|JS since we also maintain and use this WAMP client library, and JavaScript is the closest there is to a lingua franca in programming. Users of other WAMP client libraries should feel free to add code examples for these!

## Working Example

For a full working example in JavaScript, see [Crossbar Examples](https://github.com/crossbario/crossbarexamples/tree/master/metaapi).
