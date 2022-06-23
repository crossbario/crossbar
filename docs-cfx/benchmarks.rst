Benchmarks
==========

Results
-------

WAMP message serialization
..........................

* **Intel Core i7**: `S3 hosted results <https://s3.eu-central-1.amazonaws.com/crossbario.com/docs/benchmarks/serialization/index.html>`__ | `Cloudfront hosted results <https://crossbario.com/docs/benchmarks/serialization/index.html>`__


RPC roundtrip, single CPU core
..............................

Measured is the WAMP RPC performance of CrossbarFX using a **single CPU core** for WAMP routing.

* **Intel Core i7**: `S3 hosted results <https://s3.eu-central-1.amazonaws.com/crossbario.com/docs/benchmarks/rpc_roundtrip/intel-nuci7.html>`__ | `Cloudfront hosted results <https://crossbario.com/docs/benchmarks/rpc_roundtrip/intel-nuci7.html>`__
* **Intel Xeon E3**: `S3 hosted results <https://s3.eu-central-1.amazonaws.com/crossbario.com/docs/benchmarks/rpc_roundtrip/brummer1.html>`__ | `Cloudfront hosted results <https://crossbario.com/docs/benchmarks/rpc_roundtrip/brummer1.html>`__
* **Intel Xeon D**: `S3 hosted results <https://s3.eu-central-1.amazonaws.com/crossbario.com/docs/benchmarks/rpc_roundtrip/matterhorn.html>`__ | `Cloudfront hosted results <https://crossbario.com/docs/benchmarks/rpc_roundtrip/matterhorn.html>`__

For issuing WAMP calls, we use 4 caller workers and on the receiving end, we use 2 callee workers.

The benchmark reports include Flamegraphs of CPU load profiles collected with VMprof (see below) and `this report </_static/router-worker-vmprof1.pdf>`_.

Typical load on on of the test hosts during the test, with the single router worker of the CrossbarFX node at full load:

.. thumbnail:: /_static/screenshots/benchmark_rpc_roundtrip_brummer1_load.png


PubSub throughput on router cluster, 8 core SMP
...............................................

FIXME: integrate benchmark into report CI


PubSub on HA cluster, 4 nodes
.............................

FIXME: integrate benchmark into report CI

------


Tools
-----

Flamegraphs
...........

* `Flamegraphs on GitHub <https://github.com/brendangregg/FlameGraph>`_
* `Flame Graphs <http://www.brendangregg.com/flamegraphs.html>`_
* `The Flame Graph <https://queue.acm.org/detail.cfm?id=2927301>`_
* `USENIX ATC 2017: Visualizing Performance with Flame Graphs <https://www.usenix.org/conference/atc17/program/presentation/gregg-flame>`_

vmprof
......

* `CrossbarFX report </_static/router-worker-vmprof1.pdf>`_
* `VMprof docs <https://vmprof.readthedocs.io/>`_
* `VMprof on GitHub <https://github.com/vmprof/vmprof-python>`_


*What is vmprof?*

.. note::

    Source of the following text is `this blog post on VMprof <https://morepypy.blogspot.com/2017/04/native-profiling-in-vmprof.html>`_

If you have already worked with vmprof you can skip the next two section. If not, here is a short introduction:

The goal of vmprof package is to give you more insight into your program. It is a statistical profiler. Another prominent
profiler you might already have worked with is cProfile. It is bundled with the Python standard library.

vmprof's distinct feature (from most other profilers) is that it does not significantly slow down your program execution.
The employed strategy is statistical, rather than deterministic. Not every function call is intercepted, but it samples stack
traces and memory usage at a configured sample rate (usually around 100hz). You can imagine that this creates a lot less
contention than doing work before and after each function call.

As mentioned earlier cProfile gives you a complete profile, but it needs to intercept every function call (it is a deterministic
profiler). Usually this means that you have to capture and record every function call, but this takes an significant amount time.

The overhead vmprof consumes is roughly 3-4% of your total program runtime or even less if you reduce the sampling frequency.
Indeed it lets you sample and inspect much larger programs. If you failed to profile a large application with cProfile,
please give vmprof a shot.


Storage
-------

Run against a XFS formatted filesystem on the local NVMe disk:

* read: IOPS=35.5k
* write: IOPS=17.2k
* read: IOPS=18.5k + write: IOPS=7907

Run against the raw local NVMe disk:

* read: IOPS=32.9k
* write: IOPS=14.8k
* read: IOPS=22.0k + write: IOPS=9847


.. code-block:: console

    sudo apt-get update
    sudo apt-get install -y nvme-cli xfsprogs fio

    sudo nvme smart-log /dev/nvme1n1
    sudo mkfs.xfs -f /dev/nvme1n1
    sudo mkdir /data

    sudo mount -t xfs /dev/nvme1n1 /data


.. code-block:: console

    ubuntu@ip-172-30-0-145:~$ cat test1.fio
    [global]
    group_reporting

    # put the dataset file on the fast storage
    filename=/data/test.dat

    # ideally dataset should be >=4x of physical RAM
    size=32G

    # LMDB does all IO 4k
    ioengine=sync
    #ioengine=libaio
    bs=4k
    iodepth=1

    # this should be at least #core/HTs (possibly higher, test)
    #numjobs=32
    numjobs=4

    time_based=1
    randrepeat=0
    norandommap=1

    # ideally, first burn for an hour to get the flash controller into steady state
    ramp_time=10
    runtime=60

    [randread]
    stonewall
    rw=randread

    [randwrite]
    stonewall
    rw=randwrite

    [randreadwrite7030]
    stonewall
    rw=randrw
    rwmixread=70


Run against a XFS formatted filesystem on the local NVMe disk:

* read: IOPS=35.5k
* write: IOPS=17.2k
* read: IOPS=18.5k + write: IOPS=7907

.. code-block:: console

    ubuntu@ip-172-30-0-145:~$ fio test1.fio
    randread: (g=0): rw=randread, bs=(R) 4096B-4096B, (W) 4096B-4096B, (T) 4096B-4096B, ioengine=sync, iodepth=1
    ...
    randwrite: (g=1): rw=randwrite, bs=(R) 4096B-4096B, (W) 4096B-4096B, (T) 4096B-4096B, ioengine=sync, iodepth=1
    ...
    randreadwrite7030: (g=2): rw=randrw, bs=(R) 4096B-4096B, (W) 4096B-4096B, (T) 4096B-4096B, ioengine=sync, iodepth=1
    ...
    fio-3.1
    Starting 12 processes
    Jobs: 4 (f=4): [_(8),m(4)][31.7%][r=76.0MiB/s,w=33.5MiB/s][r=19.5k,w=8567 IOPS][eta 08m:00s]
    randread: (groupid=0, jobs=4): err= 0: pid=5481: Mon Sep 30 16:40:12 2019
    read: IOPS=35.5k, BW=139MiB/s (145MB/s)(8320MiB/60001msec)
        clat (nsec): min=731, max=13887k, avg=111496.26, stdev=87961.74
        lat (nsec): min=758, max=13887k, avg=111579.16, stdev=87961.58
        clat percentiles (nsec):
        |  1.00th=[   1624],  5.00th=[   1864], 10.00th=[   2064],
        | 20.00th=[ 100864], 30.00th=[ 114176], 40.00th=[ 119296],
        | 50.00th=[ 128512], 60.00th=[ 132096], 70.00th=[ 134144],
        | 80.00th=[ 142336], 90.00th=[ 146432], 95.00th=[ 152576],
        | 99.00th=[ 179200], 99.50th=[ 187392], 99.90th=[ 301056],
        | 99.95th=[1236992], 99.99th=[3981312]
    bw (  KiB/s): min=19665, max=39812, per=24.62%, avg=34954.35, stdev=3392.66, samples=479
    iops        : min= 4916, max= 9953, avg=8738.25, stdev=848.16, samples=479
    lat (nsec)   : 750=0.01%, 1000=0.01%
    lat (usec)   : 2=8.97%, 4=5.57%, 10=0.87%, 20=0.04%, 50=0.01%
    lat (usec)   : 100=4.17%, 250=80.25%, 500=0.04%, 750=0.01%, 1000=0.01%
    lat (msec)   : 2=0.02%, 4=0.02%, 10=0.01%, 20=0.01%
    cpu          : usr=1.73%, sys=5.97%, ctx=1801145, majf=0, minf=11
    IO depths    : 1=115.1%, 2=0.0%, 4=0.0%, 8=0.0%, 16=0.0%, 32=0.0%, >=64=0.0%
        submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        issued rwt: total=2129969,0,0, short=0,0,0, dropped=0,0,0
        latency   : target=0, window=0, percentile=100.00%, depth=1
    randwrite: (groupid=1, jobs=4): err= 0: pid=5561: Mon Sep 30 16:40:12 2019
    write: IOPS=17.2k, BW=67.1MiB/s (70.3MB/s)(4026MiB/60036msec)
        clat (usec): min=2, max=119102, avg=231.65, stdev=2979.35
        lat (usec): min=2, max=119102, avg=231.75, stdev=2979.41
        clat percentiles (usec):
        |  1.00th=[    4],  5.00th=[    5], 10.00th=[    6], 20.00th=[    6],
        | 30.00th=[    6], 40.00th=[    6], 50.00th=[    6], 60.00th=[    6],
        | 70.00th=[    7], 80.00th=[    7], 90.00th=[    9], 95.00th=[   11],
        | 99.00th=[   21], 99.50th=[17433], 99.90th=[47449], 99.95th=[62653],
        | 99.99th=[70779]
    bw (  KiB/s): min= 3837, max=41501, per=23.51%, avg=16141.85, stdev=7137.16, samples=477
    iops        : min=  959, max=10375, avg=4035.09, stdev=1784.30, samples=477
    lat (usec)   : 4=2.91%, 10=89.66%, 20=6.42%, 50=0.12%, 100=0.01%
    lat (usec)   : 250=0.12%, 500=0.01%, 750=0.01%, 1000=0.01%
    lat (msec)   : 2=0.01%, 4=0.01%, 10=0.02%, 20=0.29%, 50=0.37%
    lat (msec)   : 100=0.07%, 250=0.01%
    cpu          : usr=0.40%, sys=2.87%, ctx=35737, majf=0, minf=12
    IO depths    : 1=144.9%, 2=0.0%, 4=0.0%, 8=0.0%, 16=0.0%, 32=0.0%, >=64=0.0%
        submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        issued rwt: total=0,1030656,0, short=0,0,0, dropped=0,0,0
        latency   : target=0, window=0, percentile=100.00%, depth=1
    randreadwrite7030: (groupid=2, jobs=4): err= 0: pid=5648: Mon Sep 30 16:40:12 2019
    read: IOPS=18.5k, BW=72.1MiB/s (75.6MB/s)(4326MiB/60001msec)
        clat (nsec): min=1208, max=15115k, avg=169234.82, stdev=400160.94
        lat (nsec): min=1254, max=15116k, avg=169351.44, stdev=400162.46
        clat percentiles (nsec):
        |  1.00th=[   1912],  5.00th=[   2832], 10.00th=[  41216],
        | 20.00th=[ 101888], 30.00th=[ 111104], 40.00th=[ 121344],
        | 50.00th=[ 132096], 60.00th=[ 142336], 70.00th=[ 158720],
        | 80.00th=[ 183296], 90.00th=[ 226304], 95.00th=[ 252928],
        | 99.00th=[ 610304], 99.50th=[2768896], 99.90th=[6717440],
        | 99.95th=[7503872], 99.99th=[9764864]
    bw (  KiB/s): min=  653, max=25032, per=25.18%, avg=18590.28, stdev=7156.62, samples=476
    iops        : min=  163, max= 6258, avg=4647.32, stdev=1789.21, samples=476
    write: IOPS=7907, BW=30.9MiB/s (32.4MB/s)(1853MiB/60001msec)
        clat (usec): min=2, max=12835, avg=105.96, stdev=304.68
        lat (usec): min=2, max=12836, avg=106.13, stdev=304.69
        clat percentiles (usec):
        |  1.00th=[    5],  5.00th=[    6], 10.00th=[    6], 20.00th=[    9],
        | 30.00th=[   24], 40.00th=[   59], 50.00th=[   92], 60.00th=[  117],
        | 70.00th=[  129], 80.00th=[  141], 90.00th=[  167], 95.00th=[  198],
        | 99.00th=[  281], 99.50th=[ 1745], 99.90th=[ 5342], 99.95th=[ 6456],
        | 99.99th=[ 7898]
    bw (  KiB/s): min=  177, max=10888, per=25.18%, avg=7965.53, stdev=3063.91, samples=476
    iops        : min=   44, max= 2722, avg=1991.09, stdev=766.04, samples=476
    lat (usec)   : 2=1.13%, 4=2.80%, 10=8.15%, 20=1.36%, 50=5.20%
    lat (usec)   : 100=10.74%, 250=66.32%, 500=3.35%, 750=0.08%, 1000=0.04%
    lat (msec)   : 2=0.21%, 4=0.31%, 10=0.30%, 20=0.01%
    cpu          : usr=1.64%, sys=7.19%, ctx=2044364, majf=0, minf=16
    IO depths    : 1=100.0%, 2=0.0%, 4=0.0%, 8=0.0%, 16=0.0%, 32=0.0%, >=64=0.0%
        submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        issued rwt: total=1107371,474471,0, short=0,0,0, dropped=0,0,0
        latency   : target=0, window=0, percentile=100.00%, depth=1

    Run status group 0 (all jobs):
    READ: bw=139MiB/s (145MB/s), 139MiB/s-139MiB/s (145MB/s-145MB/s), io=8320MiB (8724MB), run=60001-60001msec

    Run status group 1 (all jobs):
    WRITE: bw=67.1MiB/s (70.3MB/s), 67.1MiB/s-67.1MiB/s (70.3MB/s-70.3MB/s), io=4026MiB (4222MB), run=60036-60036msec

    Run status group 2 (all jobs):
    READ: bw=72.1MiB/s (75.6MB/s), 72.1MiB/s-72.1MiB/s (75.6MB/s-75.6MB/s), io=4326MiB (4536MB), run=60001-60001msec
    WRITE: bw=30.9MiB/s (32.4MB/s), 30.9MiB/s-30.9MiB/s (32.4MB/s-32.4MB/s), io=1853MiB (1943MB), run=60001-60001msec

    Disk stats (read/write):
    nvme1n1: ios=3071320/1652731, merge=0/11, ticks=382284/4749384, in_queue=4940980, util=90.11%
    ubuntu@ip-172-30-0-145:~$


Run against the raw local NVMe disk:

* read: IOPS=32.9k
* write: IOPS=14.8k
* read: IOPS=22.0k + write: IOPS=9847

.. code-block:: console

    ubuntu@ip-172-30-0-145:~$ sudo fio test1.fio
    randread: (g=0): rw=randread, bs=(R) 4096B-4096B, (W) 4096B-4096B, (T) 4096B-4096B, ioengine=sync, iodepth=1
    ...
    randwrite: (g=1): rw=randwrite, bs=(R) 4096B-4096B, (W) 4096B-4096B, (T) 4096B-4096B, ioengine=sync, iodepth=1
    ...
    randreadwrite7030: (g=2): rw=randrw, bs=(R) 4096B-4096B, (W) 4096B-4096B, (T) 4096B-4096B, ioengine=sync, iodepth=1
    ...
    fio-3.1
    Starting 12 processes
    Jobs: 1 (f=1): [_(9),f(1),_(2)][100.0%][r=2124KiB/s,w=812KiB/s][r=531,w=203 IOPS][eta 00m:00s]
    randread: (groupid=0, jobs=4): err= 0: pid=6733: Mon Sep 30 17:11:57 2019
    read: IOPS=32.9k, BW=129MiB/s (135MB/s)(7713MiB/60001msec)
        clat (nsec): min=929, max=10532k, avg=120410.17, stdev=93043.60
        lat (nsec): min=955, max=10532k, avg=120493.58, stdev=93043.25
        clat percentiles (nsec):
        |  1.00th=[   1720],  5.00th=[   1992], 10.00th=[  61696],
        | 20.00th=[ 107008], 30.00th=[ 117248], 40.00th=[ 122368],
        | 50.00th=[ 130560], 60.00th=[ 132096], 70.00th=[ 136192],
        | 80.00th=[ 146432], 90.00th=[ 152576], 95.00th=[ 164864],
        | 99.00th=[ 185344], 99.50th=[ 197632], 99.90th=[ 382976],
        | 99.95th=[1646592], 99.99th=[4292608]
    bw (  KiB/s): min=21891, max=34504, per=22.77%, avg=29970.17, stdev=4899.76, samples=476
    iops        : min= 5472, max= 8626, avg=7492.19, stdev=1224.95, samples=476
    lat (nsec)   : 1000=0.01%
    lat (usec)   : 2=5.08%, 4=3.16%, 10=0.54%, 20=0.03%, 50=0.51%
    lat (usec)   : 100=7.21%, 250=83.34%, 500=0.06%, 750=0.01%, 1000=0.01%
    lat (msec)   : 2=0.02%, 4=0.03%, 10=0.01%, 20=0.01%
    cpu          : usr=1.69%, sys=5.66%, ctx=1801153, majf=0, minf=10
    IO depths    : 1=117.1%, 2=0.0%, 4=0.0%, 8=0.0%, 16=0.0%, 32=0.0%, >=64=0.0%
        submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        issued rwt: total=1974454,0,0, short=0,0,0, dropped=0,0,0
        latency   : target=0, window=0, percentile=100.00%, depth=1
    randwrite: (groupid=1, jobs=4): err= 0: pid=6820: Mon Sep 30 17:11:57 2019
    write: IOPS=14.8k, BW=57.9MiB/s (60.7MB/s)(3477MiB/60026msec)
        clat (nsec): min=1222, max=39192k, avg=268800.33, stdev=2346955.84
        lat (nsec): min=1276, max=39192k, avg=268874.56, stdev=2346954.90
        clat percentiles (usec):
        |  1.00th=[    3],  5.00th=[    3], 10.00th=[    4], 20.00th=[    4],
        | 30.00th=[    4], 40.00th=[    4], 50.00th=[    4], 60.00th=[    5],
        | 70.00th=[    5], 80.00th=[    5], 90.00th=[    6], 95.00th=[    8],
        | 99.00th=[15664], 99.50th=[23462], 99.90th=[23725], 99.95th=[27657],
        | 99.99th=[27657]
    bw (  KiB/s): min=10230, max=16186, per=24.35%, avg=14444.87, stdev=1351.84, samples=479
    iops        : min= 2557, max= 4046, avg=3610.85, stdev=337.98, samples=479
    lat (usec)   : 2=0.01%, 4=53.94%, 10=43.04%, 20=1.69%, 50=0.02%
    lat (usec)   : 100=0.01%, 250=0.01%, 500=0.01%, 750=0.01%, 1000=0.01%
    lat (msec)   : 4=0.01%, 10=0.01%, 20=0.67%, 50=0.64%
    cpu          : usr=0.33%, sys=1.59%, ctx=11705, majf=0, minf=13
    IO depths    : 1=140.7%, 2=0.0%, 4=0.0%, 8=0.0%, 16=0.0%, 32=0.0%, >=64=0.0%
        submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        issued rwt: total=0,890123,0, short=0,0,0, dropped=0,0,0
        latency   : target=0, window=0, percentile=100.00%, depth=1
    randreadwrite7030: (groupid=2, jobs=4): err= 0: pid=6897: Mon Sep 30 17:11:57 2019
    read: IOPS=22.0k, BW=89.7MiB/s (94.1MB/s)(5384MiB/60001msec)
        clat (nsec): min=972, max=15194k, avg=170148.21, stdev=536912.29
        lat (nsec): min=1000, max=15194k, avg=170233.41, stdev=536915.36
        clat percentiles (nsec):
        |  1.00th=[   1688],  5.00th=[   2064], 10.00th=[  46336],
        | 20.00th=[  92672], 30.00th=[ 100864], 40.00th=[ 104960],
        | 50.00th=[ 108032], 60.00th=[ 112128], 70.00th=[ 118272],
        | 80.00th=[ 128512], 90.00th=[ 148480], 95.00th=[ 173056],
        | 99.00th=[2670592], 99.50th=[4751360], 99.90th=[7241728],
        | 99.95th=[7831552], 99.99th=[9502720]
    bw (  KiB/s): min= 2384, max=39576, per=25.04%, avg=23010.51, stdev=12267.21, samples=476
    iops        : min=  596, max= 9894, avg=5752.36, stdev=3066.76, samples=476
    write: IOPS=9847, BW=38.5MiB/s (40.3MB/s)(2308MiB/60001msec)
        clat (nsec): min=1700, max=7497.0k, avg=5064.87, stdev=33877.08
        lat (nsec): min=1793, max=7497.1k, avg=5206.70, stdev=33946.84
        clat percentiles (nsec):
        |  1.00th=[ 2928],  5.00th=[ 3120], 10.00th=[ 3344], 20.00th=[ 3600],
        | 30.00th=[ 3856], 40.00th=[ 4128], 50.00th=[ 4384], 60.00th=[ 4640],
        | 70.00th=[ 4896], 80.00th=[ 5280], 90.00th=[ 5920], 95.00th=[ 7392],
        | 99.00th=[13760], 99.50th=[16192], 99.90th=[28544], 99.95th=[35072],
        | 99.99th=[98816]
    bw (  KiB/s): min= 1008, max=17362, per=25.05%, avg=9867.42, stdev=5278.63, samples=476
    iops        : min=  252, max= 4340, avg=2466.59, stdev=1319.62, samples=476
    lat (nsec)   : 1000=0.01%
    lat (usec)   : 2=3.00%, 4=13.26%, 10=18.51%, 20=1.24%, 50=1.12%
    lat (usec)   : 100=13.08%, 250=47.94%, 500=0.42%, 750=0.09%, 1000=0.06%
    lat (msec)   : 2=0.32%, 4=0.50%, 10=0.46%, 20=0.01%
    cpu          : usr=1.74%, sys=5.37%, ctx=1260119, majf=1, minf=18
    IO depths    : 1=122.7%, 2=0.0%, 4=0.0%, 8=0.0%, 16=0.0%, 32=0.0%, >=64=0.0%
        submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
        issued rwt: total=1378197,590874,0, short=0,0,0, dropped=0,0,0
        latency   : target=0, window=0, percentile=100.00%, depth=1

    Run status group 0 (all jobs):
    READ: bw=129MiB/s (135MB/s), 129MiB/s-129MiB/s (135MB/s-135MB/s), io=7713MiB (8087MB), run=60001-60001msec

    Run status group 1 (all jobs):
    WRITE: bw=57.9MiB/s (60.7MB/s), 57.9MiB/s-57.9MiB/s (60.7MB/s-60.7MB/s), io=3477MiB (3646MB), run=60026-60026msec

    Run status group 2 (all jobs):
    READ: bw=89.7MiB/s (94.1MB/s), 89.7MiB/s-89.7MiB/s (94.1MB/s-94.1MB/s), io=5384MiB (5645MB), run=60001-60001msec
    WRITE: bw=38.5MiB/s (40.3MB/s), 38.5MiB/s-38.5MiB/s (40.3MB/s-40.3MB/s), io=2308MiB (2420MB), run=60001-60001msec

    Disk stats (read/write):
    nvme1n1: ios=3694742/1876986, merge=0/13511166, ticks=503032/5806404, in_queue=6118792, util=98.77%
    ubuntu@ip-172-30-0-145:~$
