:orphan:

Proxy-Workers
=============

A worker of ``type = proxy`` allows for scaling across processes. Currently, a single "realm" must be run in a single "router worker" process (so that it may orchestrate all access, publications, etc). :doc:`Router Realms <Router-Realms>` can do a lot of work besides just the core work of the "dealer" and "broker" roles for a realm, and this is where Proxy workers come in. A proxy worker can do everything that a normal router worker does except for core WAMP things; a Proxy passes all this traffic off to a configured "backend" realm.

In concrete terms, a core router realm worker can accept only CBOR connections on Unix raw-socket connections and leave Proxy processes to terminate (possibly TLS) WebSocket connections, handle WAMP-level authentication, deserialize JSON, serve static Web content, serve "info" pages, etc. Using a Unix-domain backend connection leaves maximum CPU cycles for the single router worker.

A minimal example with one realm and two proxy workers is available `in the Crossbar "proxy" example <https://github.com/crossbario/crossbar-examples/tree/master/proxy>`_. You could of course have three or four (or more) Proxy workers if need be.

Proxy workers support all the same transports as :doc:`Router Transports <Router-Transports>`. It also supports a type called `websocket-proxy` which is the same as a `websocket` transport with the addition of a "backends" member, which tells the proxy how to connect to the backends. Currently, there must be exactly one backend.

+-----------+-----------------------------------------------------------------------------------------------------+
| parameter | description                                                                                         |
+===========+=====================================================================================================+
| backends  | List of dicts containing client-type endpoint information (must have exactly one) (**required**)    |
+-----------+-----------------------------------------------------------------------------------------------------+


Here is a complete example snippet (taken from the above example):

.. code::javascript

        {
            "type": "proxy",
            "options": {
            },
            "transports": [
                {
                    "type": "web",
                    "endpoint": {
                        "type": "tcp",
                        "port": 8443,
                        "shared": true,
                        "backlog": 1024
                    },
                    "paths": {
                        "/": {
                            "type": "static",
                            "directory": "../web",
                            "options": {
                                "enable_directory_listing": false
                            }
                        },
                        "autobahn": {
                            "type": "archive",
                            "archive": "autobahn-v20.1.1.zip",
                            "origin": "https://github.com/crossbario/autobahn-js-browser/archive/v20.1.1.zip",
                            "object_prefix": "autobahn-js-browser-20.1.1",
                            "default_object": "autobahn.min.js",
                            "download": true,
                            "cache": true,
                            "hashes": [
                                "a7e898a6a506c8bffe9a09d7e29b86a8adb90a15859024835df99cc7be82274a"
                            ],
                            "mime_types": {
                                ".min.js": "text/javascript",
                                ".jgz": "text/javascript"
                            }
                        },
                        "ws": {
                            "type": "websocket-proxy",
                            "serializers": [
                                "cbor", "msgpack", "json"
                            ],
                            "backends": [
                                {
                                    "type": "websocket",
                                    "endpoint": {
                                        "type": "unix",
                                        "path": "routerws.sock"
                                    },
                                    "url": "ws://localhost",
                                    "serializers": ["json"]
                                }
                            ],
                            "options": {
                                "allowed_origins": ["*"],
                                "allow_null_origin": true,
                                "enable_webstatus": true,
                                "max_frame_size": 1048576,
                                "max_message_size": 1048576,
                                "auto_fragment_size": 65536,
                                "fail_by_drop": true,
                                "open_handshake_timeout": 2500,
                                "close_handshake_timeout": 1000,
                                "auto_ping_interval": 10000,
                                "auto_ping_timeout": 5000,
                                "auto_ping_size": 12,
                                "auto_ping_restart_on_any_traffic": true,
                                "compression": {
                                    "deflate": {
                                        "request_no_context_takeover": false,
                                        "request_max_window_bits": 13,
                                        "no_context_takeover": false,
                                        "max_window_bits": 13,
                                        "memory_level": 5
                                    }
                                }
                            }
                        },
                        "info": {
                            "type": "nodeinfo"
                        }
                    }
                }
            ]
        }
