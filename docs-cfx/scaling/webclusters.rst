Web Clusters
============

Managing Web clusters
---------------------

Create a new Web cluster
........................

To create a new webcluster named "cluster1" (in the management realm "default"):

.. code-block:: console

    crossbarfx shell --realm default create webcluster cluster1 \
        --config='{"tcp_port": 8080, "tcp_shared": true}'


List and show details about Web clusters
........................................

Show details about webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default show webcluster cluster1

List webclusters:

.. code-block:: console

    crossbarfx shell --realm default list webclusters


Start and stop Web clusters
...........................

Start the webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default start webcluster cluster1

Stop the webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default stop webcluster cluster1

Managing Cluster nodes
----------------------


Add nodes to Web clusters
.........................

Add all nodes (currently paired in the default management realm) to
the webcluster "cluster1", with a per-node parallel degree of two:

.. code-block:: console

    crossbarfx shell --realm default add webcluster-node cluster1 all \
        --config '{"parallel": 2}'


List and show details on Web cluster nodes
..........................................

List nodes currently added to webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default list webcluster-nodes cluster1


Show details about a node added to a cluster:

.. code-block:: console

    crossbarfx shell --realm default show webcluster-node cluster1 node-e907435a


Managing Cluster transports
---------------------------

Add a new Web transport to a Web cluster
........................................

FIXME

Start and stop Web transports
.............................

FIXME

List and show details on Web transports
.......................................

FIXME


Managing Transport services
---------------------------


Add a new Web service to a Web transport
........................................

Add a webservice serving static Web files to the webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default add webcluster-service cluster1 "/" \
        --config '{"type": "static", "directory": "..", "options": {"enable_directory_listing": true}}'

Add a webservice rendering a node info Web page to the webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default add webcluster-service cluster1 "info" \
        --config '{"type": "nodeinfo"}'

Add a webservice serving a arbitrary literal JSON value via HTTP to the webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default add webcluster-service cluster1 "settings" \
        --config '{"type": "json", "value": [1, 2, 3]}'

Add a webservice providing a WAMP-WebSocket endpoint to the webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default add webcluster-service cluster1 "ws" \
        --config '{"type": "websocket"}'


List and show details on Web services
.....................................

List webservices currently added to webcluster "cluster1":

.. code-block:: console

    crossbarfx shell --realm default list webcluster-services cluster1

Show details about a webservice added to a cluster:

.. code-block:: console

    crossbarfx shell --realm default show webcluster-service cluster1 "settings"
