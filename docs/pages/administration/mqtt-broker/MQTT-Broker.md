title: MQTT Broker and Bridge
toc: [Documentation, Administration, MQTT Broker, MQTT Broker]

# MQTT Broker and Bridge

> *WARNING: this feature is still in beta and configuration and functionality can change*

Crossbar.io is a multi-protocol router with support for MQTT Version 3.1.1.

You can use Crossbar.io both as a **standalone MQTT broker**, and to integrate MQTT clients with a WAMP based system.

The latter is possible as Crossbar.io **includes a MQTT-to-WAMP bridge** that allows WAMP and MQTT publishers and subscribers talk to each other transparently.

This opens up whole new possibilities, eg immediately integrate MQTT client devices into a larger WAMP based application, add native remote procedure call functionality to an MQTT based system or gradually migrating an existing MQTT system towards WAMP.


## Payload Mapping

MQTT is completely agnostic to application payload. Application payload in MQTT is a (single) binary string.

In WAMP, application payload is carried in structured form (args, kwargs), and auxiliary information for the interaction (call, invocation, publish, event) is exposed as well to enable rich, standard and custom semantics.

So there is an impedance mismatch, and part of what is required is a mapping or transformation between application payloads.

In general, application payload between MQTT and WAMP can be transformed in three layers:

* within the WAMP client library or WAMP app code (**"passthrough mode"**)
* within the MQTT client library or MQTT app code (**"native mode"**)
* within the router (**"dynamic mode"**)

Crossbar.io supports all three modes, and the modes are configurable in an URI tree to operate new code along legacy code which enables a gradual migration path for app code.


## Examples

Complete working examples can be found here:

* [Using MQTT with Crossbar.io](https://github.com/crossbario/crossbar-examples/tree/master/mqtt/basic)

In **[passthrough mode](https://github.com/crossbario/crossbar-examples/tree/master/mqtt/basic/passthrough)**, MQTT payloads are transmitted in *payload transparency mode* on the wire, which means, Crossbar.io will not touch the (arbitrary binary) MQTT payload at all.

In **[native mode](https://github.com/crossbario/crossbar-examples/tree/master/mqtt/basic/native)**, MQTT payloads are converted between WAMP structured application payload and MQTT binary payload using a statically configured serializer such as JSON, CBOR, MessagePack or UBJSON.

In **[dynamic mode](https://github.com/crossbario/crossbar-examples/tree/master/mqtt/basic/dynamic)**, MQTT payloads are converted between arbitrary binary and WAMP structured application payload by calling into a user provided *payload transformer function*, which can be implemented in any WAMP supported language.


## Configuration

Crossbar.io can run MQTT transports either as a *dedicated MQTT transport* or as part of a *universal transport*.

To configure a *dedicated MQTT transport** in Crossbar.io, add a transport configuration item like below:

```json
{
    "transports": [
        {
            "id": "mqtt-001",
            "type": "mqtt",
            "endpoint": {
                "type": "tcp",
                "port": 1883
            },
            "options": {
                "realm": "realm1",
                "role": "anonymous",
                "payload_mapping": {
                    "": {
                        "type": "passthrough"
                    }
                }
            }
        }
    ]
}
```

parameter | description
---|---
**`id`** | The (optional) transport ID - this must be unique within the router this transport runs in (default: **`"transportN"`** where **N** is numbered starting with **1**)
**`type`** | Type of transport - must be `"mqtt"`.
**`endpoint`** | A network connection for data transmission - see connecting [Transport Endpoints](Transport Endpoints) (**required**)
**`options`** | see below (**required**)

Two options can be set here:

parameter | description
---|---
**`realm`** | The routing realm the MQTT transport will be connected to. (**required**)
**`role`** | The authentication role that MQTT clients connecting to the MQTT transport will be authenticated as (optional)
**`payload_mapping`** | The payload mapping configuration. This is a required dictionary mapping WAMP URI prefixes to a payload format.

Payload formats come in the flavors down below (see the examples for details).

The MQTT transport can also be configured as part of a **universal transport**, like for example:

```json
{
    "type": "universal",
    "endpoint": {
        "type": "tcp",
        "port": 8080
    },
    "mqtt": {
        "options": {
            "realm": "realm1",
            "role": "anonymous",
            "payload_mapping": {
                "": {
                    "type": "dynamic",
                    "realm": "codec",
                    "encoder": "com.example.mqtt.encode",
                    "decoder": "com.example.mqtt.decode"
                }
            }
        }
    },
    "rawsocket": {
        "serializers": [
            "cbor", "msgpack", "ubjson", "json"
        ]
    },
    "websocket": {
        "ws": {
            "type": "websocket",
            "serializers": [
                "cbor", "msgpack", "ubjson", "json"
            ]
        }
    },
    "web": {
        "paths": {
            "/": {
                "type": "static",
                "directory": "..",
                "options": {
                    "enable_directory_listing": true
                }
            }
        }
    }
}
```


### Passthrough Payload Format

**[Complete Example](https://github.com/crossbario/crossbar-examples/tree/master/mqtt/basic/passthrough)**

Crossbar.io can be configured to forward MQTT without touching in **passthrough mode**, which can be set on WAMP URI prefixes:

```json
{
    "realm": "realm1",
    "role": "anonymous",
    "payload_mapping": {
        "": {
            "type": "passthrough"
        }
    }
}
```

In **passthrough-mode**, MQTT payloads are transmitted in *payload transparency mode* on the wire, which means, Crossbar.io will not touch the (arbitrary binary) MQTT payload at all.


### Native Payload Format

**[Complete Example](https://github.com/crossbario/crossbar-examples/tree/master/mqtt/basic/native)**

Crossbar.io can be configured to transform MQTT payload using a specified serializer in **native mode**, which can be set on WAMP URI prefixes:

```json
{
    "realm": "realm1",
    "role": "anonymous",
    "payload_mapping": {
        "": {
            "type": "native",
            "serializer": "cbor"
        }
    }
}
```

In **native mode**, MQTT payloads are converted between WAMP structured application payload and MQTT binary payload using a statically configured serializer such as JSON, CBOR, MessagePack or UBJSON.


### Dynamic Payload Format

**[Complete Example](https://github.com/crossbario/crossbar-examples/tree/master/mqtt/basic/dynamic)**

Crossbar.io can be configured to transform MQTT payload by calling user supplied payload codec procedures in **dynamic mode**, which can be set on WAMP URI prefixes:

```json
{
    "realm": "realm1",
    "role": "anonymous",
    "payload_mapping": {
        "": {
            "type": "dynamic",
            "realm": "codec",
            "encoder": "com.example.mqtt.encode",
            "decoder": "com.example.mqtt.decode"
        }
    }
}
```

In **dynamic**, MQTT payloads are converted between arbitrary binary and WAMP structured application payload by calling into a user provided *payload transformer function*, which can be implemented in any WAMP supported language.
