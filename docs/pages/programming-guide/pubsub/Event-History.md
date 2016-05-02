title: Event History
toc: [Documentation, Programming Guide, WAMP Features, PubSub, Event History]

# Event History

Event history allows a WAMP client to retrieve a set of past events for a subscription. Retrieval is by subscription ID, and for a set number of events.

## Configuration in Crossbar.io

Crossbar.io does not normally store PubSub events. To enable event history for a topic, you need to configure an event store as part of the Crossbar.io config.

An example for this is 

```json
{
   "name": "realm1",
   "roles": [
   ],
   "store": {
      "type": "memory",
      "event-history": [
         {
            "uri": "com.example.oncounter",
            "limit": 10000
         }
      ]
   }
}
```

The above configures a store on the realm `realm1` which resides in memory, and which stores the last 1000 events for the topic `com.example.oncounter`.

For the time being, `memory` is the only valid argument for where the store is kept, so there is no event history across restarts of Crossbar.io. We are going to implement an LMDB database which will allow persistence across program restarts.

For the time being, event history can only be stored for a specific topic URI. Use of pattern-based subscriptions is not supported.

## Required Client Permissions

To be able to retrieve event history, a client needs to have two permissions:

* It must be allowed to call the retrieval procedure ('wamp.subscription.get_events').
* It must be allowed to subscribe to the subscription (as identified by the subscription ID given in the call). This requirement is necessary to prevent clients for circumeventing the subscription permissions by simply periodically retrieving events for a subscription.

For the time being, the only way to get that subscription ID locally is to actually subscribe to to the topic. (We are thinking about implementing a call to retrieve the subscription ID without subscribing, or an extra argument for the subscribe request to allow this.)

## Calling to Get the Events

The actual call to retrieve events is

```javascript
session.call('wamp.subscription.get_events', [subcriptionID, 20]).then(
   function (history) {
      console.log("got history for " + history.length + " events");
      for (var i = 0; i < history.length; ++i) {
         console.log(history[i].timestamp, history[i].publication, history[i].args[0]);
      }
   },
   function (err) {
      console.log("could not retrieve event history", err);
   }
);
```

where the arguments are the subscription ID to retrieve events for and the number of past events to be retrieved.

The event history is returned as an array of event objects.