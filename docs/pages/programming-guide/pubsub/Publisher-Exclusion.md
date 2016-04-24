[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > [PubSub](PubSub) > Publisher Exclusion

# Publisher Exclusion

> **Publisher Exclusion** is a feature from the WAMP Advanced Profile. The specification can be found [here](https://github.com/tavendo/WAMP/blob/master/spec/advanced/publisher-exclusion.md).

As per default, a publisher, even if subscribed to the topic being published to, does not receive an event for its own publication.

For example, a component subscribed to `com.example.topic1` will not receive an event if it publishes to `com.example.topic1`. It will receive events published to `com.example.topic1` by **other** components.

This behavior can be overriden by setting `exclude_me` to `false` in the publication options, e.g.

```javascript
session.publish("com.myapp.topic1",
    ["hello"],
    {},
    {
        exclude_me: false
    }
);
```

> Note: if the component is connected via two sessions at the same time, and publishes on the first session, it will receive the event on the second session.

## Why is this the default?

The publisher can execute any local changes which need to occur based on the event which triggers a publish. This obviously does not require any triggering by a PubSub event.

We see this execution independent of an event as a trigger as preferable, as it allows the component to react without being limited by networking speed, and retain a maximum of functionality while there is no connection.

With this model, receiving an event when all actions which could be based on the event have already executed locally creates the necessity to filter out events which originate locally. This leads to both overhead on the wire and more complicated code.

It's now necessary to transmit some kind of unique publication ID, and store this in a way that it is accessible to the event handler. The event handler then needs to check the store of publication IDs on each received event and discard events which are based on local publications.

Exlcuding the publisher from receiving an event as a default avoids this, and the possibility to override this allows use cases where only external triggering is preferable.

---
