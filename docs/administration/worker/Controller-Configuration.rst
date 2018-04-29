Controller Configuration
========================

When a Crossbar.io node starts, initially only a single process is
started: the **node controller**.

The node controller is the master process of everything. At each time,
there is exactly one node controller process running. When the node
controller process has ended, the Crossbar.io node is down.

The node controller can be configured using the ``controller`` item in
the node's configuration:

.. code:: json

    {
       "controller": {
          "id": "mynode1",
          "options": {
             "title": "mycontroller"
          }
       }
    }

The available parameters in the ``controller`` dictionary are:

+-------------------+-----------------------------------------------------------------+
| option            | description                                                     |
+===================+=================================================================+
| **``id``**        | The ID of the node (default: **hostname** of machine)           |
+-------------------+-----------------------------------------------------------------+
| **``options``**   | Controller process options - see below (default: **``{}``**).   |
+-------------------+-----------------------------------------------------------------+
| **``manager``**   | Uplink Crossbar.io management application (**upcoming**).       |
+-------------------+-----------------------------------------------------------------+

The available ``options`` are:

+------------------+-----------------+
| option           | description     |
+==================+=================+
| **``title``**    | The controller  |
|                  | process title   |
|                  | (default:       |
|                  | **``"crossbar-c |
|                  | ontroller"``**) |
+------------------+-----------------+
| **``shutdown``** | Controls how    |
|                  | and when        |
|                  | crossbar shuts  |
|                  | down. Permitted |
|                  | values are:     |
|                  | ``shutdown_on_s |
|                  | hutdown_request |
|                  | ed``            |
|                  | (default for    |
|                  | "managed"       |
|                  | mode),          |
|                  | ``shutdown_on_w |
|                  | orker_exit``    |
|                  | (default),      |
|                  | ``shutdown_on_w |
|                  | orker_exit_with |
|                  | _error``,       |
|                  | ``shutdown_on_l |
|                  | ast_worker_exit |
|                  | ``.             |
+------------------+-----------------+

--------------
