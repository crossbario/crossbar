Mesh Links
==========

Tested with `this build <https://download.crossbario.com/crossbarfx/linux-amd64/crossbarfx-linux-amd64-20181028-fc87e59>`_ (Linux 64 bit executable).


.. code-block:: console

    crossbarfx-linux-amd64-20181028-fc87e59 edge start --cbdir=./node1/.crossbar


.. code-block:: json

    {
        "version": 2,
        "controller": {
            "id": "node002",
            "fabric": {
                "transport": null
            }
        },
        "workers": [
            {
                "type": "router",
                "realms": [
                    {
                        "name": "realm1",
                        "roles": [
                        ],
                        "uplinks": [
                            {
                                "id": "uplink_2_1",
                                "realm": "realm1",
                                "transport": {
                                    "type": "websocket",
                                    "endpoint": {
                                        "type": "tcp",
                                        "host": "localhost",
                                        "port": 8001
                                    },
                                    "url": "ws://localhost:8001/ws"
                                }
                            }
                        ]
                    }
                ],
                "transports": [
                ]
            }
        ]
    }



----------


Publishing from a client connected to router **node1**:

.. thumbnail:: /_static/screenshots/tree-routing-from-node1.png

----------


Publishing from a client connected to router **node2**:

.. thumbnail:: /_static/screenshots/tree-routing-from-node2.png

----------


Publishing from a client connected to router **node3**:

.. thumbnail:: /_static/screenshots/tree-routing-from-node3.png

----------


Publishing from a client connected to router **node4**:

.. thumbnail:: /_static/screenshots/tree-routing-from-node4.png

----------


Publishing from a client connected to router **node5**:

.. thumbnail:: /_static/screenshots/tree-routing-from-node5.png
