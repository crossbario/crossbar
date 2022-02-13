:orphan:

WebSocket Options
=================

Crossbar.io is built on an advanced and complete WebSocket
implementation that exposes various options and tunables you might be
interested in, especially if you take your server to production.

    For options related to WebSocket compression, please see
    :doc:`here <WebSocket-Compression>`.

To set options on a WebSocket transport, add an ``options`` dictionary
to the transport configuration part. Here is an example:

.. code:: javascript

    {
       "type": "websocket",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "url": "ws://localhost:8080",
       "options": {
          "enable_webstatus": false
       }
    }

Above will run a WebSocket transport, but disable the automatic
rendering of a server status page when the WebSocket server is accessed
from a regular Web client that does not upgrade to WebSocket.

Available Options
-----------------

The available options are:


+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| option                          | description                                                                                                                                                                                            |
+=================================+========================================================================================================================================================================================================+
| allowed_origins                 | A list of allowed WebSocket origins - can use * as a wildcard character, e.g. ["https://\*.tavendo.com", "http://localhost:8080"]                                                                      |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| external_port                   | The external visible port this service be reachable under (i.e. when running behind a L2/L3 forwarding device) (default: null)                                                                         |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| enable_hybi10                   | Enable Hybi-10 version of WebSocket (an intermediary spec). (default: true)                                                                                                                            |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| enable_rfc6455                  | Enable RFC6455 version of WebSocket (the final spec). (default: true)                                                                                                                                  |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| enable_webstatus                | Enable the WebSocket server's status rendering page. (default: true)                                                                                                                                   |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| validate_utf8                   | Validate incoming WebSocket text messages for UTF8 conformance. (default: true)                                                                                                                        |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| mask_server_frames              | Mask server-sent WebSocket frames. WARNING: Enabling this will break protocol compliance! (default: false)                                                                                             |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| require_masked_client_frames    | Require all WebSocket frames received to be masked. (default: true)                                                                                                                                    |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| apply_mask                      | Actually apply WebSocket masking (both in- and outgoing). (default: true)                                                                                                                              |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| max_frame_size                  | Maximum size in bytes of incoming WebSocket frames accepted or 0 to allow any size. (default: 0)                                                                                                       |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| max_message_size                | Maximum size in bytes of incoming WebSocket messages accepted or 0 to allow any size. (default: 0)                                                                                                     |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| auto_fragment_size              | Automatically fragment outgoing WebSocket messages into WebSocket frames of payload maximum specified size in bytes or 0 to disable. (default: 0)                                                      |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| fail_by_drop                    | On severe errors (like WebSocket protocol violations), brutally drop the TCP connection instead of performing a full WebSocket closing handshake. (default: false)                                     |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| echo_close_codereason           | During a WebSocket closing handshake initiated by a peer, echo the peer's close code and reason. Otherwise reply with code 1000 and no reason. (default: false)                                        |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| open_handshake_timeout          | WebSocket opening handshake timeout in ms or 0 to disable. (default: 0)                                                                                                                                |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| close_handshake_timeout         | WebSocket closing handshake timeout in ms or 0 to disable. (default: 0)                                                                                                                                |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| tcp_nodelay                     | Set the TCP No-Delay ("Nagle") socket option (default: true)                                                                                                                                           |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| auto_ping_interval              | Send a WebSocket ping every this many ms or 0 to disable. (default: 0)                                                                                                                                 |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| auto_ping_timeout               | Drop the connection if the peer did not respond to a previously sent ping in this many ms or 0 to disable. (default: 0)                                                                                |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| auto_ping_size                  | Payload size for pings sent, must be between 12 and 125 (default: 12)                                                                                                                                  |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| auto_ping_restart_on_any_traffic| Cancel a pending ping timeout already by having received a data frame. (default: true)                                                                                                                 |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| compression                     | enable WebSocket compression - see :doc:`WebSocket Compression  <WebSocket-Compression>`                                                                                                               |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| require_websocket_subprotocol   | Require WebSocket clients to properly announce the WAMP-WebSocket subprotocols it is able to speak                                                                                                     |
|                                 | This can be one or more from wamp.2.json, wamp.2.msgpack, wamp.2.json.batched and wamp.2.json.batched.                                                                                                 |
|                                 | Crossbar.io will by default require the client to announce the subprotocols it supports and select one of the announced subprotocols.                                                                  |
|                                 | If this option is set to false, Crossbar.io will no longer require the client to announce subprotocols and assume wamp.2.json when no WebSocket subprotocol is announced. (default: true)              |
+---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

Production Settings
-------------------

For example, here is a configuration for a production WebSocket service
with conservative settings:

.. code:: javascript

    {
       "type": "websocket",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "url": "ws://myserver.com:8080",
       "options": {
          "enable_webstatus": false,
          "max_frame_size": 1048576,
          "max_message_size": 1048576,
          "auto_fragment_size": 65536,
          "fail_by_drop": true,
          "open_handshake_timeout": 2500,
          "close_handshake_timeout": 1000,
          "auto_ping_interval": 10000,
          "auto_ping_timeout": 5000,
          "auto_ping_size": 12,
          "auto_ping_restart_on_any_traffic": true
       }
    }
