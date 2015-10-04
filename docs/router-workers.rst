Router Workers
==============

Realms
------

.. automethod:: crossbar.worker.router.RouterWorkerSession.start_router_realm(id, config)

.. automethod:: crossbar.worker.router.RouterWorkerSession.stop_router_realm(id, close_sessions)

.. automethod:: crossbar.worker.router.RouterWorkerSession.get_router_realms()


Roles
-----

.. automethod:: crossbar.worker.router.RouterWorkerSession.start_router_realm_role(id, role_id, config)

.. automethod:: crossbar.worker.router.RouterWorkerSession.stop_router_realm_role(id, role_id)

.. automethod:: crossbar.worker.router.RouterWorkerSession.get_router_realm_roles(id)


Transports
----------

.. automethod:: crossbar.worker.router.RouterWorkerSession.start_router_transport(id, config)

.. automethod:: crossbar.worker.router.RouterWorkerSession.stop_router_transport(id)

.. automethod:: crossbar.worker.router.RouterWorkerSession.get_router_transports()


Components
----------

.. automethod:: crossbar.worker.router.RouterWorkerSession.start_router_component(id, config)

.. automethod:: crossbar.worker.router.RouterWorkerSession.stop_router_component(id)

.. automethod:: crossbar.worker.router.RouterWorkerSession.get_router_components()
