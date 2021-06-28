Using AWS
=========

On AWS, the info below of for chosing the optimal `instance type <https://aws.amazon.com/de/ec2/instance-types>`_
and size. Hosting XBR data markets means running a mix of worker types:

* router workers
* proxy workers (optional)
* market maker workers (required for XBR)

In general, CrossbarFX will run on most AWS EC2 instance types, from ``m5ad.large`` to ``i3en.24xlarge``.
Choose from these family types:

* best price: select latest generation of General Purpose Instances with at least one local NVMe disk
* best performance: select storage optimized instances with  at least two local NVMe disks

Specifically, we recommend the following instance sizes/type for running a CrossbarFX edge node including
scalable persistent storage for the XBR market maker:

* **SMALL**:
    - AWS EC2 ``m5ad.xlarge``
    - 2 vCPU, 8GB RAM, 1 x 75GB NVMe-SSD, up to 10GBit/s Network
* **MEDIUM**:
    - AWS EC2 ``m5ad.4xlarge``
    - 16 vCPU, 64GB RAM, 2 x 300GB NVMe-SSD, up to 10GBit/s Network
* **LARGE**:
    - AWS EC2 ``i3.8xlarge``
    - 32 vCPU, 244GB RAM, 4 x 1900GB NVMe-SSD, 10GBit/s Network
* ** XLARGE**:
    - AWS EC2 ``i3en.24xlarge``
    - 96 vCPU, 768GB RAM, 8 x 7500GB NVMe-SSD, 100GBit/s Network

-------

    Amazon EC2 M5 Instances are the next generation of the Amazon EC2 General Purpose compute instances.
    M5 instances offer a balance of compute, memory, and networking resources for a broad range of workloads.
    This includes web and application servers, back-end servers for enterprise applications, gaming servers,
    caching fleets, and app development environments.

    M5a and M5ad instances feature AMD EPYC 7000 series processors with an all core turbo clock speed of 2.5 GHz.
    The AMD-based instances provide additional options for customers that do not fully utilize the compute
    resources and can benefit from a cost savings of 10%.

* https://aws.amazon.com/ec2/instance-types/m5/?nc1=h_ls
* https://aws.amazon.com/blogs/aws/new-lower-cost-amd-powered-ec2-instances/
* https://aws.amazon.com/blogs/aws/new-amd-epyc-powered-amazon-ec2-m5ad-and-r5ad-instances/

    Amazon EC2 I3 instances include Non-Volatile Memory Express (NVMe) SSD-based instance storage
    optimized for low latency, very high random I/O performance, and high sequential read throughput,
    and deliver high IOPS at a low cost. I3 instances offer up to 25 Gbps of network bandwidth and up
    to 14 Gbps of dedicated bandwidth to Amazon Elastic Block Store (Amazon EBS).

* https://aws.amazon.com/ec2/instance-types/i3/?nc1=h_ls
