Native Processes
================

**Native Processes** in Crossbar.io are **Controller** and **Router** / **Container** workers and provide the following API.

.. note:: This API is *not* provided by **Guest** processes.


General
-------

.. automethod:: crossbar.common.process.NativeProcessSession.utcnow()

.. automethod:: crossbar.common.process.NativeProcessSession.started()

.. automethod:: crossbar.common.process.NativeProcessSession.uptime()


Garbage Collection
------------------

Crossbar.io runs on Python, and Python is running on a garbage-collected virtual machine.

.. automethod:: crossbar.common.process.NativeProcessSession.trigger_gc()


Manhole
-------

Crossbar.io supports `Twisted Manhole <http://twistedmatrix.com/documents/current/api/twisted.manhole.html>`__. Manhole allows to log into a native process on a live running Crossbar.io node and get an interactive Python interpreter shell. Using this allows to inspect and manipulate the live running system.

.. note:: This feature is intended for intended for internal use by
    Crossbar.io support engineers and developers.

.. automethod:: crossbar.common.process.NativeProcessSession.start_manhole(config)

.. automethod:: crossbar.common.process.NativeProcessSession.stop_manhole()

.. automethod:: crossbar.common.process.NativeProcessSession.get_manhole()


Monitoring
----------

.. automethod:: crossbar.common.process.NativeProcessSession.start_connection()

.. automethod:: crossbar.common.process.NativeProcessSession.stop_connection()

.. automethod:: crossbar.common.process.NativeProcessSession.get_connections()


Connections
-----------

.. automethod:: crossbar.common.process.NativeProcessSession.get_process_info()

.. automethod:: crossbar.common.process.NativeProcessSession.get_process_stats()

.. automethod:: crossbar.common.process.NativeProcessSession.set_process_stats_monitoring()
