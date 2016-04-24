[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > [PubSub](PubSub) > Basic Subscriptions

# Basic Subscriptions

As a default, subscriptions use exact matching, i.e. a subscriber for topic `com.myapp.topic1` will receive events for publications to topic `com.myapp.topic1` only. (There are also [pattern-based subscriptions](Pattern Based Subscriptions) which can be selected via an option when subscribing.)

> Note: There are some [specific rules](URI Format) regarding the formatting of URIs used to identify topics.

WAMP mandates a single subscription per session for each URI. If a client issues a second subscription request for an URI, the WAMP router returns the same subscription ID (as it would for any other client issuing a subscription request for this URI). Only a single event is dispatched to the subscriber, irrespective of how many subscription requests it has issued.

WAMP client libraries may allow multiple independent registrations from within the code which can be managed separately, but this is above the WAMP protocol level. For an example of this, see the [Autobahn|JS documentation](http://autobahn.ws/js/reference.html).

Here's an example for a simple subscription in JavaScript using Autobahn|JS:

```javascript
session.subscribe("com.myapp.topic1", myTopicHandler);
```

This is equivalent to 

```javascript
session.subscribe("com.myapp.topic1", myTopicHandler, { match: "exact" });
```

With exact matching, there is no need to explicitly set the matching policy as an option.

