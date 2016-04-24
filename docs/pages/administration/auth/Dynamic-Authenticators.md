[Documentation](.) > [Administration](Administration) > [Authentication](Authentication) > Dynamic Authenticators


# Dynamic Authenticators

All authentication methods can be configured statically, i.e. the credentials are contained in the the Crossbar.io configuration.

Alternatively it is possible to give the URI for an authentication component which is called on each authentication attempt.

For example, for Ticket authentication, an example configuration for a dynamic authenticator is

```javascript
"auth": {
   "ticket": {
      "type": "dynamic",
      "authenticator": "com.example.authenticate"
   }
}
```

A dynamic authenticator receives the full set of details about a connecting client, not just the minimum information required for a particular authentication method.

As an example, for a ticket authentication, the dynamic authorizer receives

```javascript
{
    "session": 508715025212448,
    "ticket": "123sekret",
    "transport": {
       "cbtid": null,
       "protocol": "wamp.2.msgpack.batched",
       "http_headers_received": {
          "upgrade": "WebSocket",
          "sec-websocket-version": "13",
          "sec-websocket-protocol": "wamp.2.msgpack.batched,wamp.2.msgpack,wamp.2.json.batched,wamp.2.json",
          "host": "localhost:8080",
          "sec-websocket-key": "xWszwpILt1/lMXVdGmIkfw==",
          "user-agent": "AutobahnPython/0.11.0",
          "connection": "Upgrade",
          "pragma": "no-cache",
          "cache-control": "no-cache"
       },
       "peer": "tcp4:127.0.0.1:17185",
       "http_headers_sent": {},
       "type": "websocket",
       "client_cert": null
    }
 }
```

## Running authenticators in configurable realms

By default, dynamic authenticators must run in the same realm as the session that is connecting.

In some situations, this can be a pain, and it is possible to invoke dynamic authenticators on a different realm than the session connecting by configuring an explicit realm:

```javascript
"auth": {
   "ticket": {
      "type": "dynamic",
      "authenticator": "com.example.authenticate",
      "authenticator-realm": "realm-auth"
   }
}
```

With the above, the authenticator (which needs to be connected to `realm-auth`) is invoked irrespective of the realm that a client using ticket authentication connects to.

## Data the authenticator can set

I many methods, the authenticator need only return the `authrole` which it determines.

It can, however, also always return an `authid` and a `realm`. In cases where these are provided by the client, this allows overwriting the clients' requests for these.

### Custom Data

An authenticator can return custom data, which is passed on to authenticated clients in the WELCOME message as part of the details.

As an example, in a dynamic authenticator component written in Python for a ticket authentication, this could return the following result:

```python
res = {
   u'realm': principal[u'realm'],
   u'role': principal[u'role'],
   u'extra': {
      u'my-custom-welcome-data': [1, 2, 3]
   }
}
return res
```

where the `extra` dictionary can contain any data the implementer wants.


## Example

We provide a [full working example](https://github.com/crossbario/crossbarexamples/tree/master/authentication/advanced) for the above. (This uses ticket authentication, but the principles apply to other authentication types.)
