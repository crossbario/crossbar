[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > [PubSub](PubSub) > How Subscriptions Work

# How Subscriptions Work

With the Publish & Subscribe (PubSub) messaging pattern in WAMP, a WAMP client issues a subscription request to a router, in which it expresses interest in a topic. The router registers this. Whenever a publication to this topic comes in, an event is dispatched to all WAMP clients which are currently registered for the topic.

> Note: WAMP uses URIs to identify topics. There are some [specific rules regarding URI formatting](URI Format).

For example, any WAMP client which has registered a subscription for the topic `com.myapp.topic1` receives an event whenever any other client publishes to the topic `com.myapp.topic1`. (The "any *other*" is because as a default, no event is dispatched to the publisher itself if it is subscribed to the topic. This behavior can be overriden by setting `exclude_me=False` in `PublishOptions` when calling `publish()`).

The 'subscription', as the term is used here, exists within the router. A subscription is created when a client sends a subscription request for a topic where there are currently no other subscribers. It is deleted when the last subscriber cancels its subscriptions, or its session is disconnected.

A subscriber receives a subscription ID as the result of a successful subscription request. E.g. say a client issues a subscription request for a topic `com.myapp.topic1`, it could receive the subscription ID `748038973` on success. This subscription ID is used as part of the unsubscribe request, i.e. an unsubscribe does not contain a topic URI, but a subscription ID.

When an second subscriber issues a subscription request for the same topic, then it receives the same subscription ID. For `com.myapp.topic1`, it would also receive `748038973`. 

When the subscription is deleted, e.g. because the above two clients both issue an unsubscribe for the topic, and then a client issues a subscription request for the same topic, a new subscription is created, and the client receives a new subscription ID.

The act of subscribing and unsubscribing may create or delete a subscription. It necessarily adds or removes a session from a subscription. 

The creation and deletion of subscriptions, as well as the addition or removal of sessions to a subscription lead to subscription meta-events, to which you can subscribe. It is also possible to retrieve information about currently existing subscriptions. For more information see [Subscription Meta-Events and Procedures](Subscription Meta Events and Procedures).

The above explanation used a topic string which was fully matched. WAMP additionally allows for pattern-based subscriptions in two flavors: prefix registration and wildcard registration. These are explained in [Pattern-Based Subscriptions](Pattern Based Subscriptions).

There is also the possibility to exclude certain sessions from receiving an event, or to restrict publication to a certain set of sessions - see [Subscriber Black- and Whitelisting](Subscriber Black and Whitelisting).

There is normally no need for subscribers to know the identity of a publisher, but if required it is possible to disclose this information - see [Publisher Identification](Publisher Identification).

As a default, Publishers do not receive an event if they are also a Subsciber, but this can be overriden - see [Publisher Exclusion](Publisher Exclusion).

# Next

[Basic Subscriptions](Basic Subscriptions)