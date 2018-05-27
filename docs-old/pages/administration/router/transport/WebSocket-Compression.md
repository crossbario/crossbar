title: WebSocket Compression
toc: [Documentation, Administration, Router Transports, WebSocket Transport, WebSocket Compression]

# WebSocket Compression

WebSocket already has hugely lower overhead than HTTP, Comet or REST based solutions.

On the other hand, [WAMP](http://wamp.ws/), the application protocol used by Crossbar.io uses JSON or MsgPack for serialization, and that still has significant potential for compression (in particular JSON).

The WebSocket protocol allows for extensions, and with [permessage-deflate](https://tools.ietf.org/html/draft-ietf-hybi-permessage-compression), there is an upcoming compression extension for WebSocket.

WebSocket compression compresses the payload of WebSocket messages which can lead to a further reduction of wire level payload by a factor of 2-15x. Here is a good [overview article](http://www.igvita.com/2013/11/27/configuring-and-optimizing-websocket-compression/).

WebSocket compression (**permessage-deflate**) is fully supported by Crossbar.io.

Browser support is coming: Chrome has it since version 32, Firefox [will](https://bugzilla.mozilla.org/show_bug.cgi?id=792831) get it.

## Activating Compression

Here is how you enable WebSocket compression in Crossbar.io on a WebSocket transport:

```javascript
{
   "type": "websocket",
   "endpoint": {
      "type": "tcp",
      "port": "9000"
   },
   "url": "ws://localhost:9000",
   "options": {
      "compression": {
         "deflate": {
         }
      }
   }
}
```

That's it.

Crossbar.io will now negotiate the **permessage-deflate** extension with any client connecting during the WebSocket opening handshake.

## Compression Options

The compression configuration has a couple of options:

```javascript
{
   "type": "websocket",
   "endpoint": {
      "type": "tcp",
      "port": "9000"
   },
   "url": "ws://localhost:9000",
   "options": {
      "compression": {
         "deflate": {
            "request_no_context_takeover": true,
            "request_max_window_bits": 12,
            "no_context_takeover": true,
            "max_window_bits": 12,
            "memory_level": 5
         }
      }
   }
}
```

where

 * `request_no_context_takeover`: request the client to not takeover compression context from message to message (default: **false**)
 * `request_max_window_bits`: request the client to use a maximum compression window size of this many bits. Permissible values are 8 .. 15 (default: **15**)
 * `no_context_takeover`: while sending, do not takeover compression context from message to message (default: **false**)
 * `max_window_bits`: while sending, use a maximum compression window size of this many bits. Permissible values are 8 .. 15 (default: **15**)
 * `memory_level`: while sending, limit memory consumption to this level. Permissible values are 1 .. 9 (default: **8**)

## Production Settings

There is no free lunch. In the context of compression, this translates into a tradeoff between wire-level efficiency (size) versus memory consumed and CPU cycles burned.

With the default settings for compression, each WebSocket connection might additionally consume several hundred kB memory on the server side for keeping compression context etc.

For production, you might want to limit this. Here is what we recommend:

```
"compression": {
   "deflate": {
      "request_no_context_takeover": false,
      "request_max_window_bits": 11,
      "no_context_takeover": false,
      "max_window_bits": 11,
      "memory_level": 4
   }
}
```

> Note: turning off "context takeover" will severly limit the usefulness of compression altogether.

Above parameter suggestions are based on [expert advice](http://www.ietf.org/mail-archive/web/hybi/current/msg10222.html). You can use [this tool](https://github.com/zaphoyd/ws-pmce-stats) to test parameter sets yourself.
