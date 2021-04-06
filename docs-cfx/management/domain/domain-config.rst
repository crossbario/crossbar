.. _DomainController:

Domain Controller Configuration
===============================

The CrossbarFX Domain Controller is the core piece of a CrossbarFX
domain and responsible for central management and monitoring of
a potentially large and distributed fleet of CrossbarFX nodes paired
with a management realm on the domain controller.


Management Uplink
-----------------

Every CrossbarFX (Edge and Core) node maintains an uplink (strictly outgoing
WAMP-over-WebSocket) connection to its domain controller.


The URL of the domain controller a CrossbarFX node will connect to can be

* the built-in default ``wss://fabric.crossbario.com/ws`` (future)
* set from an environment variable ``CROSSBAR_FABRIC_URL="ws://localhost:9000/ws"``

or via local node configuration:

.. code-block:: json

    {
        "version": 2,
        "controller": {
            "fabric": {
                "transport": {
                    "type": "websocket",
                    "endpoint": {
                        "type": "tcp",
                        "host": "localhost",
                        "port": 9000
                    },
                    "url": "ws://localhost:9000/ws"
                }
            }
        }
    }

To disable the domain controller uplink connection completely:

.. code-block:: json

    {
        "version": 2,
        "controller": {
            "fabric": {
                "transport": null
            }
        }
    }


Docker integration
------------------

.. code-block:: json

    {
        "version": 2,
        "controller": {
            "enable_docker": true
        }
    }


Node heartbeating
-----------------

.. code-block:: json

    {
        "version": 2,
        "controller": {
            "fabric": {
                "heartbeat": {
                    "startup_delay": 5,
                    "heartbeat_period": 10,
                    "include_system_stats": true,
                    "send_workers_heartbeats": true,
                    "aggregate_workers_heartbeats": true
                }
            }
        }
    }
