title: Publisher Identification
toc: [Documentation, Programming Guide, Publisher Identification]

# Publisher Identification

Generally, PubSub is used to decouple publishers and subscribers. Publishers do not have any knowledge of subscribers and vice versa.

Depending on your app design, it may be useful however for a subscriber to know the identity of a publisher.

## In the Crossbar.io Config

Disclosure of caller identity can be configured as part of the Crossbar.io config, e.g.

```javascript
"roles": [
   {
      "name": "anonymous",
      "permissions": [
         {
            "uri": "",
            "match": "prefix",
            "allow": {
               "call": true,
               "register": true,
               "publish": true,
               "subscribe": true
            },
            "disclose": {
               "caller": true,
               "publisher": true
            }
         }
      ]
   }
]
```

In the above example, the identity for publishers which have the role `anonymous` is diclosed to all subscribers. Limiting this to specific URIs or URI patterns works just like for other permissions.

We provide a [full working example](https://github.com/crossbario/crossbarexamples/tree/master/disclose).

## From a Dynamic Authorizer

Since the `authorizer` replaces the `permissions` dict, the authorizer has to take care of the disclose option as well - if disclosure is desired (otherwise the default is to not disclose). To do so, just return `"disclose": true` as an additional argument in the return of your authorizer.

> Note: This is a change to the previous behavior, where the caller or publisher needed to request the disclosure of its identity on each call or publication. This was not ideal in that it led to the possibility of a callee receiving caller identity or not based on a caller's decision. For publisher disclosure, having this at the control of the subscriber would have meant either having an additional serialization of the event (with the identity details), which is something we are loath to do for performance reasons) or having all subscribers receive the details once a single subscriber has requested them. In the end it seemed the cleanest solution across both RPC and PubSub to have this set in the config.
