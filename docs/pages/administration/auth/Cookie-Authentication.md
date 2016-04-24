[Documentation](.) > [Administration](Administration) > [Authentication](Authentication) > Cookie Authentication

# Cookie Authentication

## Introduction

Cookie authentication works like this.

With cookie tracking enabled, a browser client or generally any WAMP client connecting via WAMP-over-WebSocket is handed out a randomly assigned cookie by Crossbar.io.

When the client then authenticates using a WAMP authentication method such as WAMP-CRA, upon successful authentication, Crossbar.io will attached the authentication information to the cookie stored in the cookie store (either transiently or persistently).

When the client then comes back later, and sends the cookie handed out previously, Crossbar.io will look up the cookie, and if the cookie has attached authentication information, it will immediately authenticate the client using the previously stored information.

## Configuration

Here is part of a node configuration that enables cookie-tracking on a WebSocket transport, as well as enabling cookie-based authentication plus WAMP-CRA.

You can find a *complete example [here](https://github.com/crossbario/crossbarexamples/tree/master/authentication/cookie)*.


```json
 "transports": [
    {
       "type": "web",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "paths": {
          "/": {
             "type": "static",
             "directory": "../web"
          },
          "ws": {
             "type": "websocket",
             "cookie": {
                "store": {
                   "type": "file",
                   "filename": "cookies.dat"
                }
             },
             "auth": {
                "wampcra": {
                   "type": "static",
                   "users": {
                      "joe": {
                         "role": "frontend",
                         "secret": "123456"
                      }
                   }
                },
                "cookie": {
                }
             }
          }
       }
    }
]
```

Note that to use cookie-based authentication you have to activate cookie-tracking and at least one non-cookie based authentication method.
