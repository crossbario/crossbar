Database Format
===============

FIXME: document the CFXDB database format. Relevant topics: LMDB, Flatbuffers, ZLMDB, ..


The CFXDB consists of database tables stored as Flatbuffers in LMDB database files.
The specific database schema implemented by CrossbarFX can be found in an overview here:

.. centered:: :download:`CFXDB Database Schema </_static/cfxdb_database_schema.pdf>`

The tables are also documented in below.

.. contents:: :local:


Auxiliary Classes
-----------------

Persistent Maps
...............

.. autoclass:: zlmdb.MapOidCbor

.. autoclass:: zlmdb.MapOidFlatBuffers

.. autoclass:: zlmdb.MapOidOidFlatBuffers


FlatBuffers builders
....................

.. code-block:: python

    import flatbuffers

    builder = flatbuffers.Builder(0)


.. autoclass:: flatbuffers.Builder
    :members:
        StartVector,
        EndVector,
        CreateString,
        CreateByteVector,
        CreateNumpyVector


Datetime
........

.. code-block:: python

    import pandas as pd

    ts = pd.Timestamp(1540492454695212645, unit='ns')

    >>>> ts
    Timestamp('2018-10-25 18:34:14.695212645')

    >>>> ts.to_pydatetime()
    /home/oberstet/pypy3-v6.0.0-linux64/lib-python/3/code.py:91: UserWarning: Discarding nonzero nanoseconds in conversion
    exec(code, self.locals)
    datetime.datetime(2018, 10, 25, 18, 34, 14, 695212)

