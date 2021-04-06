WAMP Events Database
====================

Crossbar.io (OSS) includes *event history* which allows a WAMP client to retrieve a set of past
events for a subscription. Retrieval is by subscription ID, and for a set number of events.

CrossbarFX includes *event store* which allows events routed on selected topics to be persisted to disk
and queried over WAMP APIs or directly attaching the underlying *event store* to an application component
for data analysis on the persisted event history.

.. toctree::
    :maxdepth: 2

    overview
    analysis
