title: Long-poll Service
toc: [Documentation, Administration, Web Services, Long-Poll Service]

# Long-poll Service

The default transport for WAMP is WebSocket. For clients not supporting WebSocket, or for blocking clients, the WAMP specification defines [WAMP-over-Longpoll](https://github.com/wamp-proto/wamp-proto/blob/master/rfc/text/advanced/ap_transport_http_longpoll.md), a WAMP transport that runs over regular HTTP 1.0 requests.

> The HTTP Long-pool transport can come in handy to support old browsers lacking WebSocket like IE9 and earlier or old Android WebKit. It is also useful to integrate with clients that cannot work asynchronously or have an inherent blocking, synchronous execution environment like PostgreSQL background processes for database sessions.


## Configuration

To configure a Long-poll Service, attach a dictionary element to a path in your [Web transport](Web Transport and Services):

option | description
---|---
**`type`** | MUST be `"longpoll"` (*required*)
**`options`** | A dictionary of options (optional, see below).

The `options` dictionary has the following configuration parameters:

option | description
---|---
**`request_timeout`** | An integer which determines the timeout in seconds for Long-poll requests. If `0`, do not timeout. (default: **`10`**). After this period, the request is returned even if there is no data to transmit. Note that clients may have their own timeouts, and that this should be set to a value greater than the `request_timeout`.
**`session_timeout`** | An integer which determines the timeout on inactivity of sessions. If `0`, do not timeout. (default: **`30`**)
**`queue_limit_bytes`** | Limit the number of total queued bytes. If 0, don't enforce a limit. (default: **`131072`**)
**`queue_limit_messages`** | Limit the number of queued messages. If 0, don't enforce a limit. (default: **`100`**)
**`debug`** | A boolean that activates debug output for this service. (default: **`false`**).
**`debug_transport_id`** | If given (e.g. `"kjmd3sBLOUnb3Fyr"`), use this fixed transport ID. (default: **`null`**).


**Example**

The *Long-poll Service* is configured on a path of a Web transport - here is part of a Crossbar configuration:

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
                     "type": "longpoll",
                     "options": {
                        "session_timeout": 30
                     }
                  }
               }
            }
         ]
      }
   ]
}
```

## Test using curl

For developers that want to add WAMP-over-Longpoll support to their WAMP client library, we have an [example](https://github.com/crossbario/crossbarexamples/tree/master/longpoll_curl) which demonstrates the transport using plain **[curl](https://curl.haxx.se/)** only.

> This example can be useful during development and debugging. It is **not** intended for end-users.


## Use with AutobahnJS

[AutobahnJS](https://github.com/crossbario/autobahn-js) fully supports WAMP-over-Longpoll and you can find a complete working example in the Crossbar.io examples [here](https://github.com/crossbario/crossbarexamples/tree/master/longpoll).


## Use with AutobahnPostgres

**upcoming**

[AutobahnPostgres](https://github.com/crossbario/autobahn-postgres) uses WAMP-over-Longpoll to natively integrate PostgreSQL with Crossbar.io.
