Node Controllers
================

Node
----

.. automethod:: crossbar.controller.process.NodeControllerSession.get_info()

.. automethod:: crossbar.controller.process.NodeControllerSession.shutdown(restart)


Workers
-------

.. automethod:: crossbar.controller.process.NodeControllerSession.get_workers()

.. automethod:: crossbar.controller.process.NodeControllerSession.get_worker_log(id, limit)

.. automethod:: crossbar.controller.process.NodeControllerSession.start_router(id, options)

.. automethod:: crossbar.controller.process.NodeControllerSession.stop_router(id, kill)

.. automethod:: crossbar.controller.process.NodeControllerSession.start_container(id, options)

.. automethod:: crossbar.controller.process.NodeControllerSession.stop_container(id, kill)

.. automethod:: crossbar.controller.process.NodeControllerSession.start_guest(id, config)

.. automethod:: crossbar.controller.process.NodeControllerSession.stop_guest(id, kill)
