:orphan:

Processes
=========

Crossbar.io has a multi-process architecture. There is one node
controller process per node

-  `**Controller** Configuration <Controller%20Configuration>`__

and multiple worker processes of these types

-  `**Router** Configuration <Router%20Configuration>`__
-  `**Container** Configuration <Container%20Configuration>`__
-  `**Guest** Configuration <Guest%20Configuration>`__

Processes can be further configured with

-  `Process Environments <Process%20Environments>`__
-  `Native Worker Options <Native%20Worker%20Options>`__

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

-  ``"router"`` - see `Router Configuration <Router%20Configuration>`__
-  ``"container"`` - see `Container
   Configuration <Container%20Configuration>`__
-  ``"guest"`` - see `Guest Configuration <Guest%20Configuration>`__

--------------
