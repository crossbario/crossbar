title: MQTT Broker
toc: [Documentation, Administration, MQTT Broker, MQTT Broker]

# MQTT Broker

Crossbar.io includes a MQTT bridge that not only makes it a full scale, great MQTT broker on its own, but also allows WAMP and MQTT publishers and subscribers talk to each other transparently.

This opens up whole new possibilities, eg immediately integrate MQTT client devices into a larger WAMP based application or system.

> The documentation for this feature is currently **very** sparse. We will be working on extending it soon. (A pull request adding docs would, of course, be highly appreciated!)

## Configuration

A MQTT transport is added to the Crossbar.io configuration like so:

```
"transports": [
    {
        "id": "mqtt_1",
        "type": "mqtt",
        "endpoint": {
            "type": "tcp",
            "port": 1883
        },
        "options": {
            "realm": "crossbardemo",
            "role": "mqtt_client"
        }
    }
]
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

## Example

There is a basic example for usage of the MQTT broker, and for trying things out as part of the [autobahn-python examples](https://github.com/crossbario/autobahn-python/tree/master/examples/twisted/wamp/mqtt).
