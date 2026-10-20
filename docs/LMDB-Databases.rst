:orphan:

LMDB Databases
==============

Crossbar.io keeps persistent data in embedded `LMDB <https://www.symas.com/lmdb>`__
databases, through `zLMDB <https://zlmdb.readthedocs.io/>`__:

-  the database-backed realm store (``"store": {"type": "cfxdb", "path": ...}``);
-  the database-backed cookie store (``"store": {"type": "database", "path": ...}``);
-  the databases of the XBR market maker and of the master node.

LMDB Format
-----------

From Crossbar.io 26.10.1 (zLMDB 26.10.1), two LMDB engines are bundled, and each
writes its own on-disk format:

.. list-table::
   :header-rows: 1

   * - LMDB format
     - LMDB engine
     - on-disk data format
   * - ``1.0``
     - LMDB 1.0.x
     - v3
   * - ``0.9``
     - LMDB 0.9.x
     - v1

Neither engine reads the other's format.

-  **A new database** is created in LMDB ``1.0`` format.
-  **An existing database** opens in its own format, with the matching engine. All
   databases created by Crossbar.io 26.7.1 and older are in LMDB ``0.9`` format,
   and keep working unchanged.
-  Crossbar.io **never converts** a database by itself.

There is no configuration option to choose the format.

.. warning::

    A database created by Crossbar.io 26.10.1 or later (LMDB ``1.0`` format)
    cannot be opened after a **downgrade** to Crossbar.io 26.7.1 or older, nor by
    tools built on LMDB 0.9, for example ``mdb_stat`` from LMDB 0.9 or py-lmdb
    before 3.0. Before downgrading, convert such a database to LMDB ``0.9`` format
    (see below), or start the older version with a new, empty database.

Which Format a Database Has
---------------------------

``crossbar version`` lists both bundled engines and marks the one used for new
databases:

.. code-block:: console

    $ crossbar version
    ...
       zLMDB                      : 26.10.1
         LMDB                     : 3.0.0/lmdb-1.0.2 (new databases), lmdb-0.9.36
    ...

When a node opens a database-backed realm store or cookie store, it logs the LMDB
format of the database and the engine servicing it, for example:

.. code-block:: text

    realm store initialized (type="cfxdb", dbpath="...", maxsize=134217728, readonly=False,
    sync=True, lmdb_format=0.9, lmdb_version=0.9.36)

To inspect a database without starting a node, use the ``zlmdb`` command, which is
installed with Crossbar.io:

.. code-block:: console

    $ zlmdb info .crossbar/realm1-db
    ...
    lib_version: 1.0
    lmdb_version: 1.0.2
    ...

Converting a Database
---------------------

To move a database to the other format, stop the node, copy the database into a
new database of the other format, check the copy with ``zlmdb info``, and point the
node configuration to the copy (or replace the original with it). Keep the
original until the node runs on the copy. The zLMDB documentation describes the
copy: `LMDB Formats (0.9 and 1.0) <https://zlmdb.readthedocs.io/en/latest/lmdb-formats.html>`__.
