title: Retained Events
toc: [Documentation, Programming Guide, Retained Events]

# Retained Events

When publishing an event, the publisher can set an option (`retain=True`) in the `PublishOptions` which will cause the Broker to retain the even being published as the most-recent event on this topic.

Note that [[Event History]] is similar to this feature, but not the same.

No configuration is required in Crossbar in order to take advantage of this; it is up to the publisher.

# Retrieving an Event

Upon subscription, a client can pass `get_retained=True` in the `SubscribeOptions`. If there is any retained event, it will be immediately sent to the subscriber.

# Example

There is a completely-worked example [in the Autobahn-Python repository](https://github.com/crossbario/autobahn-python/tree/master/examples/twisted/wamp/pubsub).
