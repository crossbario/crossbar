Database Backup
===============

Backup and recovery of a nodes embedded databases.

Cold Backup
-----------

A node that is *not currently running* can be backed up by a simple filesystem level copy of
the node directory (``.crossbar`` usually). The node directory contains all node
database files (unless the default paths have been reconfigured).

Hot Backup
----------

**PLANNED FEATURE**

A node that is *currently running* can be backed up using the CrossbarFX shell:

.. code-block:: console

    crossbarfx shell --mrealm mrealm1 backup node node1 --output /backups

This will create a complete copy of all node databases in a new subdirectory in ``/backups``
while the node continues to run and while it is actively updating databases.

.. note::

    There is no need to stop the node while performing a backup. The difference in doing a hot
    backup vs cold backup (stopped node) is: with a hot backup, the active database size might
    grow significantly the longer the backup takes, as a consistent read view (MVCC) must be
    maintained during the complete backup which prohibits recycling dirty pages. This can be
    avoided by doing hot backups during lower load periods.

The path ``/backups`` must be writable from the node, and could eg come from a NFS share
to collect and archive the backups of different nodes.

To recover a node from a database backup, stop the node, move all existing databases in the
node directory to some other place, and copy over all files from the backup directory to the
node directory, and restart the node.

Each database backup is complete and functional in itself: it can be directly used to start
a node from (so there is no need for a ``restore`` command) and can be analyzed by direct-ZLMDB
access.
