[Documentation](.) > [Administration](Administration) > [HTTP Bridge](HTTP Bridge) > HTTP Bridge Caller

# HTTP Bridge Caller

## Introduction

> The *HTTP Caller* feature is available starting with Crossbar **0.10.3**.

The *HTTP Caller* is a service that allows clients to perform WAMP calls via HTTP/POST requests.
Crossbar will forward the call to the performing server and return the result.

## Try it

Clone the [Crossbar.io examples repository](https://github.com/crossbario/crossbarexamples), and go to the `rest/caller` subdirectory.

Now start Crossbar:

```console
crossbar start
```

This will register a simple procedure that takes two integers, adds them together, and returns the result.

To test this out, you can use [curl](http://curl.haxx.se/):

```console
curl -H "Content-Type: application/json" \
	-d '{"procedure": "com.example.add2", "args": [1, 2]}' \
	http://127.0.0.1:8080/call
```

...or any other HTTP/POST capable tool or library.


## Configuration

The *HTTP Caller* is configured on a path of a Web transport - here is part of a Crossbar configuration:

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
                  "call": {
                     "type": "caller",
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
**`type`** | MUST be `"caller"` (*required*)
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


## Making Requests

To call WAMP procedures through Crossbar, issue a HTTP/POST request to the URL of the Crossbar HTTP Caller service with:

1. Content type `application/json`
2. Body containing a JSON object
3. Two query parameters: `timestamp` and `seq`

For a call to a HTTP Caller service, the body MUST be a JSON object with the following attributes:

* `procedure`: A string with the URI of the procedure to call.
* `args`: An (optional) list of positional event payload arguments.
* `kwargs`: An (optional) dictionary of keyword event payload arguments.


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

The `body` is the JSON serialized event. You can look at working code [here](https://github.com/crossbario/crossbarconnect/blob/master/python/lib/crossbarconnect/client.py#L197).
