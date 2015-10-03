Native Workers
==============

**Native Workers** in Crossbar.io are **Router** and **Container** processes and provide the following API.

.. note:: This API is *not* provided by node **Controller** and **Guest** processes.


Module Search Path
------------------

**Native Workers** can run WAMP components written in Python and using AutobahnPython/Twisted in so called *side-by-side mode*, embedded inside the native worker process.

When doing so, the WAMP components need to be (dynamically) loaded by Crossbar.io. The procedures here allow to modify the Python module search path so user components can be found.

.. automethod:: crossbar.worker.worker.NativeWorkerSession.get_pythonpath

.. automethod:: crossbar.worker.worker.NativeWorkerSession.add_pythonpath


CPU Affinity
------------

Crossbar.io support the binding of running native workers to specific sets of CPU cores. Fixed binding to CPU cores can reduce cache trashing and increase performance.

.. automethod:: crossbar.worker.worker.NativeWorkerSession.get_cpu_count(logical)

.. automethod:: crossbar.worker.worker.NativeWorkerSession.get_cpu_affinity()

.. automethod:: crossbar.worker.worker.NativeWorkerSession.set_cpu_affinity(cpus)


Profiling
---------

Crossbar.io contains (optional) built-in **profiling** facilities to analyze run-time performance in a live running Crossbar.io node. Currently, this supports `vmprof <https://vmprof.readthedocs.org>`__ on PyPy.

.. automethod:: crossbar.worker.worker.NativeWorkerSession.get_profilers

.. automethod:: crossbar.worker.worker.NativeWorkerSession.start_profiler

.. automethod:: crossbar.worker.worker.NativeWorkerSession.get_profile
