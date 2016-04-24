[Documentation](.) > [Administration](Administration) > [Router Transports](Router Transports) > Flash Policy Transport

# Flash Policy Transport

Quick Links: **[Transport Endpoints](Transport Endpoints)**

Old Web browsers like IE8 and IE9 do no support WebSocket natively. *One* option to work around is using [web-socket-js](https://github.com/gimite/web-socket-js), a WebSocket implementation written in Adobe Flash.

When using Adobe Flash to open a TCP socket, Flash will only allow the (outgoing) TCP connection *after* checking for a so called *Flash policy file* on the target server. And this policy file needs to be served on TCP port 843.

Crossbar.io includes a *pseudo transport* for serving a Flash policy file. It is a *pseudo* transport, since in itself, it does not provide a WAMP transport, but its only purpose is to serve the Flash policy.

> The [Crossbar.io examples repository](https://github.com/crossbario/crossbarexamples) contains a [working example](https://github.com/crossbario/crossbarexamples/tree/master/flash) for this.

## Configuration

In the configuration (`.crossbar/config.json`), you'll find:

```json
{
   "workers": [
      {
         "type": "router",
         "transports": [
            {
               "type": "flashpolicy",
               "allowed_domain": "*",
               "allowed_ports": [8080],
               "endpoint": {
                  "type": "tcp",
                  "port": 843
               }
            }
         ]
      }
   ]
}
```

---

## Usage

The only difference client side (in the HTML) versus a standard client is that you now include the Flash implementation *before* AutobahnJS:

```html
<!-- Adobe Flash implementation of WebSocket: https://github.com/gimite/web-socket-js -->
<script>
   WEB_SOCKET_SWF_LOCATION = "WebSocketMain.swf";
   // set the following to false for production, otherwise
   // it _always_ uses Flash
   WEB_SOCKET_FORCE_FLASH = true;
   WEB_SOCKET_DEBUG = true;
</script>
<script src="swfobject.js"></script>
<script src="web_socket.js"></script>

<!-- AutobahnJS -->
<script src="autobahn.min.js"></script>
```

---

## Configuration

option | description
---|---
**`id`** | ID of the transport within the running node (default: **`transport<N>`** where `N` is numbered automatically starting from `1`)
**`type`** | Type of transport - must be `"flash"`.
**`endpoint`** | Listening endpoint for transport. See [Transport Endpoints](Transport Endpoints) for configuration
**`allowed_domain`** | Domain (a string) clients should be allowed to connect to or `null` to allow any domain (default: **`null`**)
**`allowed_ports`** | List of ports (a list of integers from `[1, 65535]`) clients should be allowed to connect to or `null` to allow any port (default: **`null`**)
**`debug`** | Turn on debug logging for this transport instance (default: **`false`**).

---
