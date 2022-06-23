Architecture
============

Crossbar.io has a multi-process (worker) architecture that allows to scale up (and out) of stateless
Web services (`full report <https://github.com/crossbario/crossbar-examples/tree/master/benchmark/web>`_):

.. figure:: /_static/webscaling_bigbox_results.png
    :align: center
    :alt: CrossbarFX Web scaling
    :figclass: align-center

    CrossbarFX: scaling Web worloads from 1-40 cores

However, this only allows to run stateless Web services, not full blown WAMP routers and realms,
and it is also hard to manage as keeping all the node configuration files in sync (to serve the same
scale-out set of Web services) and everything up and running manually is time consuming and error prone.

CrossbarFX addresses both problems, as it allows to scale up and out WAMP routing workloads and provides
auto-managing of all resources in a whole cluster from a single point of management.

.. figure:: /_static/crossbarfx-network-architecture.svg
    :align: center
    :alt: CrossbarFX network architecture
    :figclass: align-center

    Network architecture in a full setup


.. centered:: :download:`CrossbarFX Analytics Architectures </_static/crossbarfx-aggregator.pdf>`

