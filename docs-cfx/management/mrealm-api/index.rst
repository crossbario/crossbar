Management Realm Controller API
===============================

Crossbar.io enables system architectures with multiple nodes, both in cloud and edge locations. This is done by
expanding from the single node, unmanaged mode that Crossbar.io OSS runs in to many nodes all managed, orchestrated
and controlled from a single pane of glass and center of control, the master node.

The master node can orchestrate and control worker processes running on any of the nodes under management, and
uses worker processes in two categories:

* proxy workers running in **web clusters**, and
* router workers running **router clusters**

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

.. figure:: /_static/cfx-clustering-elements.svg
    :align: center
    :alt: Crossbar.io Clustering Elements
    :figclass: align-center

    Crossbar.io Clustering Elements (:download:`Crossbar.io Clustering Elements </_static/cfx-clustering-elements.pdf>`)

Each management realm ``<MANAGEMENT-REALM-NAME>`` on the master node exposes the following
**Management Realm Controller API** to management clients.

The general procedure to run WAMP applications is by creating a new application realm
for the application (or for each tenant of the application):

* create an application realm (see :ref:`arealms`)

* create application roles (see :ref:`roles`) and permissions (see :ref:`permissions`) for authorization

* create pincipals (see :ref:`principals`) and authentication credentials (see :ref:`credentials`) for authentication

and finally starting the application realm on a router worker group (see :ref:`routercluster-workergroup`)
of a router cluster (see :ref:`routerclusters`) and a web cluster (see :ref:`webclusters`):

Here is a complete list of all procedures provided by the management realm controller for each
management realm created in the domain (the master node).

.. toctree::
    :maxdepth: 3

    arealms
    routerclusters
    webclusters
