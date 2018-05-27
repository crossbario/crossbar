title: Registration Meta Events and Procedures
toc: [Documentation, Programming Guide, Registration Meta Events and Procedures]

# Registration Meta-Events and Procedures

A registration is created within Crossbar.io when a first client issues a registration request for a topic, and it is deleted when the last client unregistrers or its session is disconnected. In between, depending on the [invocation rule](Shared Registrations) used during the first registration, other client sessions may be attached to the registration or removed from it.

Registration meta-events give information about these events.

Additionally, there is a set of meta-procedures which can be called to receive information about currently existing registrations.

Meta-events are created by the router itself. This means that the events as well as the data received when calling a meta-procedure can be accorded the same trust level as the router.

## Use cases for registration meta-events and procedures

-- add me --

## Events

The set of meta events covers the lifecycle of a registration. A client can subscribe to the following registration meta events:

* `wamp.registration.on_create`: Is fired when a registration is created through a registration request for an URI which was previously without a registration.
* `wamp.registration.on_register`: Is fired when a session is added to a registration.
* `wamp.registration.on_unregister`: Is fired when a session is removed from a registration.
* `wamp.registration.on_delete`: Is fired when a registration is deleted after the last session attached to it has been removed.

> Note: A `wamp.registration.on_register` event is always fired subsequent to a `wamp.registration.on_create` event, since the first registration results in both the creation of the registration and the addition of a session. Similarly, the `wamp.registration.on_delete` event is always preceded by a `wamp.registration.on_unregister` event.

The WAMP registration meta events are dispatched by the router to the *same realm* as the WAMP session which triggered the event.

**Important**: To receive and process these events, your component will need to have *subscribe* permission on the respective topic.

## Procedures

It is possible to actively retrieve information about registrations via the following procedures.

### Retrieving registration IDs

You can retrieve registration IDs via the following three procedures:

* `wamp.registration.list`: Returns an object with three lists of the registration IDs for all current registrations for exact matching, prefix matching and wildcard matching.
* `wamp.registration.lookup`: Returns the registration ID for an existing registration to the provided URI, or null if no such registration exists. The matching policy to apply is set as an option, with exact matching applied if this is omitted.
* `wamp.registration.match`: Returns a list of IDs of registrations which currently match the URI using any matching strategy.

Example code for retrieving the **lists of current registrations**:

```javascript
session.call("wamp.registration.list").then(session.log, session.log)
```

Example code for **looking up a registration**:

```javascript
session.call("wamp.registration.lookup", ["com.myapp.procedure1"]).then(session.log, session.log)
```

```javascript
session.call("wamp.registration.lookup", ["com.myapp", { match: "prefix" }]).then(session.log, session.log)
```

```javascript
session.call("wamp.registration.lookup", ["com.myapp..create", { match: "wildcard" }]).then(session.log, session.log)
```

Example code for **matching registrations**:

```javascript
session.call("wamp.registration.match", ["com.myapp.procedure1"]).then(session.log, session.log)
```


### Retrieving information about a specific registration


Using a registration ID, information about a specific registration can be retrieved using:

* `wamp.registration.get`: Returns data about the registration itself: the registration URI, ID, matching policy, invocation rule and creation date.
* `wamp.registration.list_callees`: Returns a list of session IDs for sessions currently attached to the registration.
* `wamp.registration.count_callees`: Returns the number of sessions currently attached to the registration.

Example code for **getting data about a registration**:

```javascript
session.call("wamp.registration.get", [23560753]).then(session.log, session.log)
```

Example code for **getting the callees for a registration**:

```javascript
session.call("wamp.registration.list_callees", [23560753]).then(session.log, session.log)
```

Example code for **getting the callee count**:

```javascript
session.call("wamp.registration.count_callees", [23560753]).then(session.log, session.log)
```

### Forcefully removing a callee

It is possible to forcefully remove an individual callee from a registration by using

* `wamp.subscription.remove_callee`: Removes a single calle from a registration based on a provided registration ID and callee ID.

Example code for **removing a subscriber**:

```javaScript
session.call("wamp.registration.remove_callee", [23560753, 483984922713478]).then(session.log, session.log)
```

> Note: Access the to the meta-API should, of course, be limited in your configuration to avoid rogue clients wreaking havoc on your application.


> Note: the above examples are for Autobahn|JS since we also maintain and use this WAMP client library, and JavaScript is the closest there is to a lingua franca in programming. Users of other WAMP client libraries should feel free to add code examples for these!

## Working Example

For a full working example in JavaScript, see [Crossbar Examples](https://github.com/crossbario/crossbarexamples/tree/master/metaapi).
