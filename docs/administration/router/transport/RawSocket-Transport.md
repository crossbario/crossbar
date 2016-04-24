[Documentation](.) > [Administration](Administration) > [Router Transports](Router Transports) > RawSocket Transport

# RawSocket Transport

Quick Links: **[Transport Endpoints](Transport Endpoints)**

The **RawSocket Transport** implements WAMP-over-RawSocket and supports TCP/TLS as well as Unix domain socket, each combined with JSON and MsgPack for serialization.

"RawSocket" is an (alternative) transport for WAMP that uses length-prefixed, binary messages - a message framing different from WebSocket. Compared to WebSocket, "RawSocket" is extremely simple to implement.

* [Listening RawSocket Transport Configuration](#listening-transports)
* [Listening RawSocket Transport Example](#example---listening-transport)

as well as **connecting transports**

* [Connecting RawSocket Transport Configuration](#connecting-transports)
* [Connecting RawSocket Transport Example](#example---connecting-transport)

> RawSocket can run over TCP, TLS or Unix domain socket. When run over TLS on a (misused) standard Web port (443), it is also able to traverse most locked down networking environments (unless Man-in-the-Middle intercepting proxies are in use). However, it does not support compression or automatic negotiation of WAMP serialization (as WebSocket allows). Perhaps most importantly, RawSocket cannot be used with Web browser clients.

## Configuration

Crossbar.io supports both **listening** as well as **connecting** WAMP-over-RawSocket transports.

Listening transports are used with [routers](Router Configuration) to allow WAMP clients connect to Crossbar.io, whereas connecting transports are used with [containers](Container Configuration) to allow hosted components to connect to their upstream router.

### Listening Transports

Listening transports are used with [routers](Router Configuration) to allow WAMP clients connect to Crossbar.io. The available parameters for RawSocket listening transports are:

Parameter | Description
---|----
**`id`** | The (optional) transport ID - this must be unique within the router this transport runs in (default: **`"transportN"`** where **N** is numbered starting with **1**)
**`type`** | Must be `"rawsocket"` (**required**)
**`endpoint`** |  A network connection for data transmission - see [Transport Endpoints](Transport Endpoints) (**required**)
**`serializers`** | List of serializers to use from `"json"` or `"msgpack"` (default: **all available**)
**`max_message_size`** | Maximum size in bytes of incoming RawSocket messages accepted. Must be between 1 and 64MB (default: **128kB**)
**`auth`** | Authentication to be used for this *Endpoint* - see [[Authentication]]
**`debug`** | Enable transport level debug output. (default: **`false`**)

---

### Connecting Transports

Connecting transports are used with [containers](Container Configuration) to allow hosted components to connect to their upstream router. The available parameters for RawSocket connecting transports are:

Parameter | Description
---|----
**`id`** | The (optional) transport ID - this must be unique within the router this transport runs in (default: **`"transportN"`** where **N** is numbered starting with **1**)
**`type`** | Must be `"rawsocket"` (**required**)
**`endpoint`** |  A network connection for data transmission - see [Transport Endpoints](Transport Endpoints) (**required**)
**`serializer`** | The serializer to use: `"json"` or `"msgpack"` (**required**)
**`debug`** | Enable transport level debug output. (default: **`false`**)

---

## Example

### Example - Listening Transport

Here is an example *Transport* that will run WAMP-over-RawSocket on a Unix domain socket using MsgPack serialization:

```javascript
{
   "type": "rawsocket",
   "serializers": ["json", "msgpack"],
   "endpoint": {
      "type": "unix",
      "path": "/tmp/mysocket1"
   }
}
```

---

### Example - Connecting Transport

Write me.

---

