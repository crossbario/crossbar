Storage Setup
-------------

Do not use LMDB databases on remote filesystems, even between processes on the same host. This breaks flock() on some OSes,
possibly memory map sync, and certainly sync between programs on different hosts.



One simple, recommended approach to storage setup for hosting CrossbarFX and high performance
CFXDB is described.

CrossbarFX node storage (for high performance use cases) should reside on reliable enterprise
class storage devices optimized for *database workloads* with many small (4kB) random
read-write operations.

For the disks, choose for example:

* enterprise SSDs: flash drives (SATA/SAS/NVMe)
* cloud or enterprise SAN: Amazon EBS, Azure Managed Disks, OpenStack Cinder, ..

.. note::

    When selecting SSD hardware, considerations like consistent low IO latency,
    unrecoverable data error rate, powerloss protection, sustained write endurance and
    24/7 operation are important.
    In embedded and edge device deployments, extended temperature range, shock resistance
    and data retention can be of additional relevance.

Mount 2 block volumes (on AWS, Azure, ..) or attach 2 disk drives (SSDs)
with 10GB or bigger (same size for both) to a host.

Then, on the host:

1. create a **ZFS pool** mirrored over the 2 disks and
2. create a **ZFS filesystem** for *each* CrossbarFX node

or

1. create a **Linux MD device** mirrored over the 2 disks and
2. create a **XFS filesystem** for *all* CrossbarFX nodes

Both options provide for a production grade storage foundation for CrossbarFX nodes.
