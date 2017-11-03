title: HTTP Bridge Publisher
toc: [Documentation, Administration, HTTP Bridge, HTTP Bridge Publisher]

# HTTP Bridge Publisher

## Introduction

> The *HTTP Publisher* (formerly *HTTP Pusher*) feature is available starting with Crossbar **0.9.5**.

The *HTTP Publisher* is a service that allows clients to submit PubSub events via HTTP/POST requests.
Crossbar will receive the event data via the request and forward the event via standard WAMP to any connected subscribers in real-time.

## Try it

Clone the [Crossbar.io examples repository](https://github.com/crossbario/crossbarexamples), and go to the `rest/publisher` subdirectory.

Now start Crossbar:

```console
crossbar start
```

and open [http://localhost:8080](http://localhost:8080) in your browser. Open the JavaScript console to see events received.

To submit events via HTTP/POST, you can use [curl](http://curl.haxx.se/):

```console
curl -H "Content-Type: application/json" \
   -d '{"topic": "com.myapp.topic1", "args": ["Hello, world"]}' \
   http://127.0.0.1:8080/publish
```

...or any other HTTP/POST capable tool or library.

## Using Python

To make using the *HTTP Publisher* service even easier, we've created a (trivial) library which you can install by doing:

```console
pip install crossbarconnect
```

> `crossbarconnect` does *not* depend on `crossbar`, `autobahn`, `twisted` or `asyncio`. It only uses the Python standard library. It only does HTTP/POST requests.

You can publish events from Python like this:

```python
import crossbarconnect

client = crossbarconnect.Client("http://127.0.0.1:8080/publish")
client.publish("com.myapp.topic1", "Hello, world!", 23)
```

The example also contains two Python scripts for testing unsigned requests:

```console
python publish.py
```

and signed requests:

```console
python publish_signed.py
```

## Configuration

The *HTTP Publisher* is configured on a path of a Web transport - here is part of a Crossbar configuration:

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
                  "publish": {
                     "type": "publisher",
                     "realm": "realm1",
                     "role": "anonymous"
                  }
               }
            }
         ]
      }
   ]
}
```

The service dictionary has the following parameters:

option | description
---|---
**`type`** | MUST be `"publisher"` (*required*)
**`realm`** | The realm to which the forwarding session is attached that will inject the submitted events, e.g. `"realm1"` (*required*)
**`role`** | The fixed (authentication) role the forwarding session is authenticated as when attaching to the router-realm, e.g. `"role1"` (*required*)
**`options`** | A dictionary of options (optional, see below).

The `options` dictionary has the following configuration parameters:

option | description
---|---
**`key`** | A string that when present provides the *key* from which request signatures are computed. If present, the `secret` must also be provided. E.g. `"myapp1"`.
**`secret`** | A string with the *secret* from which request signatures are computed. If present, the `key` must also be provided. E.g. `"kkjH68GiuUZ"`).
**`post_body_limit`** | An integer when present limits the length (in bytes) of a HTTP/POST body that will be accepted. If the request body exceed this limit, the request is rejected. If 0, accept unlimited length. (default: **0**)
**`timestamp_delta_limit`** | An integer when present limits the difference (in seconds) between a signature's timestamp and current time. If 0, allow any divergence. (default: **0**).
**`require_ip`** | A list of strings with single IP addresses or IP networks. When given, only clients with an IP from the designated list are accepted. Otherwise a request is denied. E.g. `["192.168.1.1/255.255.255.0", "127.0.0.1"]` (default: **-**).
**`require_tls`** | A flag that indicates if only requests running over TLS are accepted. (default: **false**).
**`debug`** | A boolean that activates debug output for this service. (default: **false**).

## Running Standalone

If you only want to run WebSocket and the HTTP Publisher Service (and no other Web path services), here is an example configuration:

```javascript
{
   "workers": [
      {
         "type": "router",
         "realms": [
            {
               "name": "realm1",
               "roles": [
                  {
                     "name": "anonymous",
                     "permissions": [
                        {
                           "uri": "*",
                           "allow": {
                              "call": true,
                              "register": true,
                              "publish": true,
                              "subscribe": true
                           },
                        }
                     ]
                  }
               ]
            }
         ],
         "transports": [
            {
               "type": "websocket",
               "endpoint": {
                  "type": "tcp",
                  "port": 9000
               }
            },
            {
               "type": "web",
               "endpoint": {
                  "type": "tcp",
                  "port": 8080
               },
               "paths": {
                  "/": {
                     "type": "publisher",
                     "realm": "realm1",
                     "role": "anonymous"
                  }
               }
            }
         ]
      }
   ]
}
```

This will run:

 1. a WAMP-over-WebSocket endpoint on `ws://localhost:9000`
 2. a HTTP Push Bridge endpoint on `http://localhost:8080`

You can test this using

```html
<!DOCTYPE html>
<html>
   <body>
      <script src="autobahn.min.js"></script>
      <script>
         var connection = new autobahn.Connection({
            url: "ws://127.0.0.1:9000",
            realm: "realm1"
         });

         connection.onopen = function (session) {

            console.log("Connected");

            function onevent (args, kwargs) {
               console.log("Got event:", args, kwargs);
            }

            session.subscribe('com.myapp.topic1', onevent);
         };

         connection.onclose = function () {
            console.log("Connection lost", arguments);
         }

         connection.open();
      </script>
   </body>
</html>
```

and publishing from curl:

```console
curl -H "Content-Type: application/json" \
   -d '{"topic": "com.myapp.topic1", "args": ["Hello, world"]}' \
   http://127.0.0.1:8080/
   ```

## Making Requests

To submit events through Crossbar, issue a HTTP/POST request to the URL of the Crossbar HTTP Publisher service with:

1. Content type `application/json`
2. Body containing a JSON object
3. Two query parameters: `timestamp` and `seq`

For a call to a HTTP Publisher service, the body MUST be a JSON object with the following attributes:

* `topic`: A string with the URI of the topic to publish to.
* `args`: An (optional) list of positional event payload arguments.
* `kwargs`: An (optional) dictionary of keyword event payload arguments.
* `options`: An (optional) dictionary of WAMP publication options (see below).

### Signed Requests

Signed requests work like unsigned requests, but have the following additional query parameters. All query parameters (below and above) are mandatory for signed requests.

* `key`: The key to be used for computing the signature.
* `nonce`: A random integer from [0, 2^53]
* `signature`: See below.

The signature computed as the Base64 encoding of the following value:

```
HMAC[SHA256]_{secret} (key | timestamp | seq | nonce | body)
```

Here, `secret` is the secret shared between the publishing application and Crossbar. This value will never travel over the wire.

The **HMAC[SHA256]** is computed w.r.t. the `secret`, and over the concatenation

```
key | timestamp | seq | nonce | body
```

The `body` is the JSON serialized event.


## PHP - Symfony Publisher Bundle

For PHP/Symfony users, there is a bundle which makes publishing via HTTP comfortable - [Crossbar HTTP Publisher Bundle](https://github.com/facile-it/crossbar-http-publisher-bundle) (thanks to [peelandsee](https://github.com/peelandsee) for providing this).
