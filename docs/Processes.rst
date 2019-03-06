:orphan:

Processes
=========

Crossbar.io has a multi-process architecture. There is one node
controller process per node

-  :doc:`Controller Configuration <Controller-Configuration>`

and multiple worker processes of these types

-  :doc:`Router Configuration <Router-Configuration>`
-  :doc:`Container Configuration <Container-Configuration>`
-  :doc:`Guest Configuration <Guest-Configuration>`

Processes can be further configured with

-  :doc:`Process Environments <Process-Environments>`
-  :doc:`Native Worker Options <Native-Worker-Options>`

Configuration
-------------

The **controller** is configured in the node's configuration like here

.. code:: javascript

    {
        "controller": {
            // controller configuration
        }
    }

Read more in `**Controller**
Configuration <Controller%20Configuration>`__.

**Workers** are configured in a node's local configuration like this

.. code:: javascript

    {
        "workers": [
            {
                "type": "..."
            }
        ]
    }

There are valid values for the ``type`` of worker:

-  ``"router"`` - see :doc:`Router Configuration <Router-Configuration>`
-  ``"container"`` - see :doc:`Container
   Configuration <Container-Configuration>`
-  ``"guest"`` - see :doc:`Guest Configuration <Guest-Configuration>`

