[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > [PubSub](PubSub) > Pattern-Based Subscriptions

# Pattern Based Subscriptions

As a default, topic URIs in subscription requests are processed with exact matching, i.e. an event will be dispatched to subscribers if the topic of the publication exactly matches the topic of the subscription.

## Use cases for Pattern-Based Subscriptions

There are use cases where more flexibility is required. As an example, in a chat application users may create individual channels, e.g. "com.mychatapp.privatechannel.34", "com.mychatapp.privatechannel.145", but a logging component may want to log all channels without the need to create a subscription for each and every channel. In the same chat application, you may want to centrally monitor status updates published with URIs such as "com.mychatapp.privatechannel.145.currentstatus", and the component monitoring these wants to receive only the status updates, but across all channels.

WAMP offers two matching mechanisms to cover use cases such as these:

* prefix matching
* wildcard matching

## Prefix Matching

With prefix matching, an event is dispatched to a subscriber when the subscription topic URI matches the publication URI as a prefix.

For example, the subscription topic URI

`com.myapp`

in a prefix subscription would match (and receive events for) publications with the topics

`com.myapp`
`com.myapp.topic1`
`com.myapp.topic1.update`
`com.myapp.2`
`com.myapp2.foobar`

but not

`com.otherapp`
`com.thirdapp.topic1`

Using this, in the chat application mentioned initially, the logging component would subscribe to `com.mychatapp.privatechannel` using prefix matching, and receive the events for any private channels.

To enable prefix matching, the matching policy `prefix` needs to be set within the subscription options.

As an example, in an application written in JavaScript and using Autobahn|JS as the WAMP client library, the subscription would be

```javascript
session.subscribe("com.mychatapp.privatechannel", logPrivateChannels, { match: "prefix" });
```

Since with prefix matching there is no local knowledge of the URI for a received event, events which are dispatched to subscribers here contain the URI of the publication.

For example, when the handler `logPrivateChannels` is called based on the above subscription, the handler can only be certain that the URI of the publication based on which it received an event begins with `com.mychatapp.privatechannel`. The event contains the information about the topic as part of the event details, e.g.

```javascript
{publication: 464157938, publisher: undefined, topic: "com.myapp.topic1"}
```

## Wildcard Matching

With wildcard matching, one or more URI components in a topic URI can be replaced by wildcards, and any URI which contains the given components will be matched.

For example, the subscription topic URI

`com.myapp..create`

contains three defined URI components (`com`, `myapp`, `create`) and one wildcard, which is indicated by the double dots between `myapp` and `create`.

This would be matched by

`com.myapp.product.create`
`com.myapp.123.create`

but not

`com.myapp.product.delete`
`com.myapp.product.123.create`

Using this, in the chat application mentioned initially, the component monitoring status updates would subscribe to `com.mychatapp.privatechannel..statusupdate` using wildcard matching and receive just the status updates for any private channels.

To enable wildcard matching, the matchin policy `wildcard` needs to be set within the subscription options.

As an example, in an application written in JavaScript and using Autobahn|JS as the WAMP client library, the subscription would be

```javascript
session.subscribe("com.mychatapp.privatechannel..statusupdate", monitorStatusUpdates, { match: "wildcard" });
```

> Using wildcard matching, only entire component parts of URIs can be set as wildcards. There is no mechanism to match partially identical components, e.g. `com.myapp.user3278378` and `com.myapp.user7727278`.


Just as with prefix matching, with wildcard matching the publication URI is part of the event details.

## Exact matching

While is possibly to explicitly set the matching policy for exact matching, e.g.

```javascript
session.subscribe("com.mychatapp.privatechannel.123", printMyEvents, { match: "exact" });
```

this is unnecessary, unless there is a need to make the matching policy explicit as a marker in the code. Absent an explicit setting of `match`, the default value `exact` applies.


> Note: the above examples are for Autobahn|JS since we also maintain and use this WAMP client library, and JavaScript is the closest there is to a lingua franca in programming. Users of other WAMP client libraries should feel free to add code examples for these!

## Multiple Matching Subscriptions

With pattern-based subscriptions it becomes possible that a component has multiple subscriptions which match the topic URI of a publication. Since subscriptions are separate entities, the component then receives one event for each of its subscriptions.

## No Set-Based Subscription Logic

Subscriptions are entities which are based on a combination of registration URI and matching policy. It is thus not possible to perform any set-based logic with subscriptions.

As an example:

There is an existing subscription for the URI `com.myapp` using prefix matching. It is then not possible to send an 'unsubscribe' for the URI `com.myapp.topic2` in order to exclude events published to this URI from being dispatched to the subscriber.

## Equivalent notations

Above an explicit setting of the matching strategy is described.

Alterantively, it is possible to use the common notation using `*` as part of the string to match.

Here the rules are:

* if `*` is used and the **matching policy is set explicitly**, then this is treated as a normal part of the string (this means that `*` *need not* be a reserved character!)

otherwise, if there is **no explicitly set matching policy**

* `*` within a an URI string is interpreted as a wildcard
* `*` at the end of a string is interpreted to mean prefix registration
* `**` at the end means wildcard

This enables maximum flexibility and should not lead to confusion as long as you stick to using one form of notation.

> Note: This is upward compatible to the old behavior which always required setting an explicit matching policy. No need to change anything in your existing configurations.

## Working Example

For a full working example in JavaScript, see [Crossbar Examples](https://github.com/crossbario/crossbarexamples/tree/master/patternsubs).
