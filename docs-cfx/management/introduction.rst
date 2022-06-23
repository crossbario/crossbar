Introduction
============

Control-/Data-plane Architecture
--------------------------------

Crossbar.io has a single-node, multi-process (worker) architecture. Crossbar.io adds management and automation for multi-node cluster of nodes and allows
to scale up and out WAMP routing workloads and provides auto-managing of all resources in a whole cluster from a single point of management.

All WAMP application routing Crossbar.io nodes that are managed in one administrative domain connect to a *master node*
via managment uplinks. The master node can then control the managed nodes via an API built into every node, an can coordinate
resource across nodes.

This lead to an architecture with a clear, secure separation of all application traffic (**data-plane**) and
management traffic (**control-plane**):

.. figure:: /_static/crossbarfx-central-control-plane.svg
    :align: center
    :alt: Crossbar.io central control plane
    :figclass: align-center

    Crossbar.io central control plane (:download:`Crossbar.io central control plane </_static/crossbarfx-central-control-plane.pdf>`)

Management Clients
------------------

Management Scopes
-----------------

* *Domain* wide Resources
* *Management Realm* wide Resources
* *Remote Node* wide Resources
