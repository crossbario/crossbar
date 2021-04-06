Router Clusters
===============

Managing Router clusters
------------------------

Create a new Router cluster
...........................

Create a new router cluster named "cluster2" (in the management realm "default"):

.. code-block:: console

    crossbarfx shell --realm default create routercluster cluster2


List and show details about Router clusters
...........................................

Show details about router cluster "cluster2":

.. code-block:: console

    crossbarfx shell --realm default show routercluster cluster2

List Router clusters:

.. code-block:: console

    crossbarfx shell --realm default list routerclusters


Start and stop Router clusters
..............................

Start the router cluster "cluster2":

.. code-block:: console

    crossbarfx shell --realm default start routercluster cluster2

Stop the webcluster "cluster2":

.. code-block:: console

    crossbarfx shell --realm default stop routercluster cluster2


Managing Cluster nodes
----------------------


Add nodes to Router clusters
............................

Add all nodes (currently paired in the default management realm) to
the router cluster "cluster2", with given soft-/hardlimits per node:

.. code-block:: console

    crossbarfx shell --realm default add routercluster-node cluster2 all \
        --config '{"softlimit": 4, "hardlimit": 8}'

List and show details on Router cluster nodes
.............................................


List nodes currently added to webcluster "cluster2" (*NOT YET IMPLEMENTED*):

.. code-block:: console

    crossbarfx shell --realm default list routercluster-nodes cluster2

Show details about a node added to a cluster (*NOT YET IMPLEMENTED*):

.. code-block:: console

    crossbarfx shell --realm default show routercluster-node cluster2 node-e907435a


Managing Cluster worker groups
------------------------------

Add a new Router worker group to a Router cluster
.................................................

.. code-block:: console

    crossbarfx shell --realm default add routercluster-workergroup cluster2 mygroup1 \
        --config '{}'

List and show details on Web transports
.......................................

List worker groups currently added to router cluster "cluster2" (*NOT YET IMPLEMENTED*):

.. code-block:: console

    crossbarfx shell --realm default list routercluster-workergroups cluster2

Show details about a router worker group added to a router cluster:

.. code-block:: console

    crossbarfx shell --realm default show routercluster-workergroup cluster2 mygroup1
