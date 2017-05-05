title: Subscription Meta Events and Procedures
toc: [Documentation, Programming Guide, Subscription Meta Events and Procedures]

# Subscription Meta Events and Procedures

A subscription is created within Crossbar.io when a first client issues a subscription request for a topic, and it is deleted when the last client unsubscribes or its session is disconnected. In between, other client sessions may be attached to the subscription or removed from it.

Subscription meta-events give information about these events. Additionally, there is a set of meta-procedures which can be called to receive information about currently existing subscriptions.

Meta-events are created by the router itself. This means that the events as well as the data received when calling a meta-procedure can be accorded the same trust level as the router.

## Use cases for subscription meta events and procedures

Within an application, it may be desirable for a publisher to know whether a publication to a specific topic currently makes sense, i.e. whether there are any subscribers who would receive an event based on the publication. It may also be desirable to keep a current count of subscribers to a topic to then be able to filter out any subscribers who are not supposed to receive an event.

## Events

The set of meta events covers the lifecycle of a subscription. A client can subscribe to the following subscription meta events:

* `wamp.subscription.on_create`: Is fired when a subscription is created through a subscription request for a topic which was previously without subscribers.
* `wamp.subscription.on_subscribe`: Is fired when a session is added to a subscription.
* `wamp.subscription.on_unsubscribe`: Is fired when a session is removed from a subscription.
* `wamp.subscription.on_delete`: Is fired when a subscription is deleted after the last session attached to it has been removed.

> Note: A `wamp.subscription.on_subscribe` event is always fired subsequent to a `wamp.subscription.on_create` event, since the first subscribe results in both the creation of the subscription and the addition of a session. Similarly, the `wamp.subscription.on_delete` event is always preceded by a `wamp.subscription.on_unsubscribe` event.

The WAMP subscription meta events are dispatched by the router to the *same realm* as the WAMP session which triggered the event.

**Important**: To receive and process these events, your component will need to have *subscribe* permission on the respective topic.

## Procedures

It is possible to actively retrieve information about subscriptions via the following procedures.

### Retrieve Subscription IDs

You can retrieve subscription IDs via the following three procedures:

* `wamp.subscription.list`: Returns an object with three lists of the subscription IDs for all current subscriptions for exact matching, prefix matching and wildcard matching.
* `wamp.subscription.lookup`: Returns the subscription ID for an existing subscription to the provided topic URI, or null if no such subscription exists. The matching policy to apply is set as an option, with exact matching applied if this is omitted.
* `wamp.subscription.match`: Returns a list of IDs of subscriptions which match the URI, irrespetive of what matching policy this match is based, i.e. a list of the IDs of all subscriptions which would presently receive a publication to the URI.

Example code for retrieving the **lists of current subscriptions**:

```javascript
session.call("wamp.subscription.list").then(session.log, session.log)
```

Example code for **looking up a subscription**:

```javascript
session.call("wamp.subscription.lookup", ["com.myapp.topic1"]).then(session.log, session.log)
```

```javascript
session.call("wamp.subscription.lookup", ["com.myapp", { match: "prefix" }]).then(session.log, session.log)
```

```javascript
session.call("wamp.subscription.lookup", ["com.myapp..create", { match: "wildcard" }]).then(session.log, session.log)
```

Example code for **matching subscriptions**:

```javascript
session.call("wamp.subscription.match", ["com.myapp.topic1"]).then(session.log, session.log)
```

### Retrieve information about a subscription

Using a subscription ID, information about a specific subscription can be retrieved using:

* `wamp.subscription.get`: Returns data about the subscription itself: the subscription URI, ID, matching policy and creation date.
* `wamp.subscription.list_subscribers`: Returns a list of session IDs for sessions currently attached to the subscription.
* `wamp.subscription.count_subscribers`: Returns the number of sessions currently attached to the subscription.

Example code for **getting data about a subscription**:

```javascript
session.call("wamp.subscription.get", [23560753]).then(session.log, session.log)
```

Example code for **getting the subscribers to a subscription**:

```javascript
session.call("wamp.subscription.list_subscribers", [23560753]).then(session.log, session.log)
```

Example code for **getting the subscriber count**:

```javascript
session.call("wamp.subscription.count_subscribers", [23560753]).then(session.log, session.log)
```

### Forcefully remove a subscriber

It is possible to forcefully remove an individual subscriber from a subscription by using

* `wamp.subscription.remove_subscriber`: Removes a single subscriber from a subscription based on a provided subscription ID and subscriber ID.

Example code for **removing a subscriber**:

```javaScript
session.call("wamp.subscription.remove_subscriber", [23560753, 483984922713478]).then(session.log, session.log)
```

> Note: Access the to the meta-API should, of course, be limited in your configuration to avoid rogue clients wreaking havoc on your application.

> Note: the above examples are for Autobahn|JS. Users of other WAMP client libraries should feel free to add code examples for these!

## Working Example

For a full working example in JavaScript, see [Crossbar Examples](https://github.com/crossbario/crossbarexamples/tree/master/metaapi).


## Event History

For the possibility to retrieve past events for a topic see the [Event History doc page](Event History).
