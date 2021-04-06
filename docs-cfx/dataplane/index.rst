Data-plane Analytics
====================

CrossbarFX has a high performance, in-memory database ("CFXDB") integrated and embedded into CrossbarFX.

CFXDB is used to persistently store, retrieve and query data like:

* persisted events and calls ("CrossbarFX usage data")
* market maker transactions and balances ("XBR transaction data")
* message and session tracing

For the CrossbarFX processes using ZLMDB, currently including

    master node database
    xbr market maker balance/transaction stores
    router workers event/call stores
    router worker authentication stores (eg cookies)


*High performance*

CFXDB itself is based on LMDB, an in-memory embedded transactional database, and
on `FlatBuffers <https://google.github.io/flatbuffers/>`__, a schema-based
zero-copy serialization format.

Combined with PyPy and its tracing JIT compiler, CFXDB achieves high performance with single-thread
scan (read) rates of over 5 million records per second.

*High integrity*

The performance comes with no compromise on robustness, and transactional database integrity.
LMDB was designed from the start to resist data loss in the face of system and application crashes.

Its copy-on-write approach never overwrites currently-in-use data. Avoiding overwrites means the
structure on disk/storage is always valid, so application or system crashes can never leave
the database in a corrupted state
(see `here <https://www.usenix.org/sites/default/files/conference/protected-files/osdi14_slides_zheng.pdf>`_).


**Contents**

.. toctree::
    :maxdepth: 2

    analytics-architectures.rst
    eventsdb/index
    zlmdb/index
