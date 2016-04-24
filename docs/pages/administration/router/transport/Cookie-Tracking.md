[Documentation](.) > [Administration](Administration) > [Router Transports](Router Transports) > [WebSocket Transport](WebSocket Transport) > Cookie Tracking

# Cookie Tracking

Cookie tracking identifies and tracks WAMP-over-WebSocket client connections using HTTP cookies.

Cookie tracking can be enabled on [WebSocket-](WebSocket-Transport) and [Web-Transport](Web-Transport-and-Services). It is not available on other transport types such as [RawSocket](RawSocket-Transport).

> While enabling cookie tracking is a prerequisite for cookie-based WAMP authentication, it can be used without authentication.


## How it works

Cookie tracking is backed by a configurable cookie store. Currently we have two types of store:

* memory-backed
* file-backed

> In the future, we'll have an LMDB backed cookie store as well.

The stored information for a cookie includes the cookie ID as well as authentication information (see [Cookie Authentication](Cookie-Authentication)).

With a memory-backed cookie store, cookies are stored in in-memory objects, and, obviously, those cookies will be gone after stopping Crossbar.io

With a file-backed cookie store, cookies are stored in an append-only, on-disk file.


## Cookie Tracking without Authentication

Cookie tracking can be enabled without using cookie-based authentication as well.

This is the case when

1. no authentication is configured at all
2. only anonymous authentication is configured
3. only non-cookie based authentication is configured

With 1) and 2) and cookie tracking enabled, Crossbar.io will automatically use the cookie ID as the authentication ID (`authid`) for the client.

This way, you still can **identify** clients across reconnects using WAMP `authid`. Without cookies, in case of 1) and 2), a WAMP client will get a random `authid` **each time** it connects.

On the other hand, with 3), the authentication ID (`authid`) still comes from the respective authentication method used.


## Cookie Tracking with Authentication

Please see [Cookie Authentication](Cookie-Authentication).


## Configuration
The following parameters are all optional and shared between different backing stores:

option | description
---|---
**`name`** | The field name where Crossbar.io will store its (random) tracking ID within the Cookie set. The default is `"cbtid"`. Must match the regular expression `^[a-z][a-z0-9_]+$`.
**`length`** | The length of the value for the tracking ID. The default is 24 (which amounts to 144 bits of randomness). The default should be large enough to reduce the collision probability to essentially zero. Must be between 6 and 64.
**`max_age`**| The maximum Cookie lifetime in seconds. The default is 1 day. Must be between 1 second and 10 years.
**`store`** | A dictionary with cookie store configuration (see below).

The `store` is a dictionary with the following attributes for a **memory-backed** cookie store:

attribute | description
---|---
**`type`** | Must be `"memory"`.

and for a **file-backed** cookie store:

attribute | description
---|---
**`type`** | Must be `"file"`.
**`filename`** | Either an absolute path or a relative path (relative to the node directory)

---

## Examples

To configure a memory-backed cookie store:

```json
{
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
                        "name": "cbtid",
                        "length": 24,
                        "max_age": 864000,
                        "store": {
                           "type": "memory"
                        }
                     }
                  }
               }
            }
         ]
}
```

To configure a file-backed cookie store:

```json
{
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
                        "name": "cbtid",
                        "length": 24,
                        "max_age": 864000,
                        "store": {
                           "type": "file",
                           "filename": "cookies.dat"
                        }
                     }
                  }
               }
            }
         ]
}
```

In above example, the cookie store would reside in `.crossbar/cookies.dat` for a default node directory.

> Note that the cookie file is "growing forever". There is no purging whatsoever, as the file is written append-only. The LMDB cookie store will provide a more advanced store.

---
