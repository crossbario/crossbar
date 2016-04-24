[Documentation](.) > [Administration](Administration) > [Web Services](Web Services) > Long-poll Service

# Long-poll Service

The default transport for WAMP is WebSocket. For clients not supporting WebSocket, the WAMP specification defines [WAMP-over-Longpoll](https://github.com/wamp-proto/wamp-proto/blob/master/rfc/draft-oberstet-hybi-tavendo-wamp.html), a transport that runs over a HTTP long-poll mechanism. This can come in handy to support old browsers lacking WebSocket like IE9 and earlier or old Android WebKit.

## Configuration

To configure a Long-poll Service, attach a dictionary element to a path in your [Web transport](Web Transport and Services):

option | description
---|---
**`type`** | MUST be `"longpoll"` (*required*)
**`options`** | A dictionary of options (optional, see below).

The `options` dictionary has the following configuration parameters:

option | description
---|---
**`request_timeout`** | An integer which determines the timeout in seconds for long-poll requests. If `0`, do not timeout. (default: **`10`**). After this period, the request is returned even if there is no data to transmit. Note that clients may have their own timeouts, and that this should be set to a value greater than the `request_timeout`.
**`session_timeout`** | An integer which determines the timeout on inactivity of sessions. If `0`, do not timeout. (default: **`30`**)
**`queue_limit_bytes`** | Limit the number of total queued bytes. If 0, don't enforce a limit. (default: **`131072`**)
**`queue_limit_messages`** | Limit the number of queued messages. If 0, don't enforce a limit. (default: **`100`**)
**`debug`** | A boolean that activates debug output for this service. (default: **`false`**).
**`debug_transport_id`** | If given (e.g. `"kjmd3sBLOUnb3Fyr"`), use this fixed transport ID. (default: **`null`**).


## Example

The *Long-Poll Service* is configured on a path of a Web transport - here is part of a Crossbar configuration:

```javascript
{
   "workers": [
      {
         "type": "router",
         ...
         "transports": [
            {
               "type": "web",
               ...
               "paths": {
                  ...
                  "lp": {
                     "type": "longpoll"
                  }
               }
            }
         ]
      }
   ]
}
```

### Using AutobahnJS

AutobahnJS fully supports WAMP-over-Longpoll and you can find a complete working example in the Crossbar.io examples [here](https://github.com/crossbario/crossbarexamples/tree/master/longpoll).


### Using curl

For developers that want to add WAMP-over-Longpoll support to their WAMP client library, we have another [example](https://github.com/crossbario/crossbarexamples/tree/master/longpoll_curl) which demonstrates the transport using **curl** only.

> This example can be useful during development and debugging. It is **not** intended for end-users.
