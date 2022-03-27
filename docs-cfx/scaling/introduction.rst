Introduction
============

Managed Multi-node Architecture
-------------------------------

Crossbar.io has a single-node, multi-process (worker) architecture.

Crossbar.io adds management and automation for multi-node cluster of nodes and allows
to scale up and out WAMP routing workloads and provides auto-managing of all resources
in a whole cluster from a single point of management.

.. figure:: /_static/crossbarfx-network-architecture.svg
    :align: center
    :alt: CrossbarFX network architecture
    :figclass: align-center

    Network architecture in a full setup

Web and Router Clusters
-----------------------

Crossbar.io enables scale-up and scale-out system architectures and high-availability deployments.

This is done by expanding from the single node, unmanaged mode that Crossbar.io OSS runs in
to many nodes all managed, orchestrated and controlled from a single pane of glass and center of
control, the master node.

The master node can orchestrate and control worker processes running on any of the nodes
under management, and uses worker processes in two categories:

* proxy workers running in **web clusters**, and
* router workers running **router clusters**

.. figure:: /_static/cfx-clustering-elements.svg
    :align: center
    :alt: Crossbar.io Clustering Elements
    :figclass: align-center

    Crossbar.io Clustering Elements (:download:`Crossbar.io Clustering Elements </_static/cfx-clustering-elements.pdf>`)

Web cluster are responsible for:

* accepting incoming WAMP connections from clients
* supporting multiple WAMP transports, including WebSocket and RawSocket
* supporting all WAMP serializers, including JSON, CBOR, MessagePack and Flatbuffers
* terminating TLS and off-loading encryption
* serving Web services, such as static files, redirects, HTML templates and so on

Further, Web clusters are responsible for WAMP authentication of the incoming clients,
and finally forwarding the connecting client to the right router cluster backend based on
WAMP role and realm of the authenticated client.

Router clusters are responsible for:

* routing WAMP messages within application realms
* multiplexing WAMP messages between sessions of clients
* maintaining point-of-truth for (client) authentication and authorization configuration
* managing consistent configuration of routing realms accross nodes
