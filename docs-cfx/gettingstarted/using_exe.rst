Using the EXE
=============

CrossbarFX is currently published and available as

* `Single file executable <https://download.crossbario.com/>`_
* `Docker image <https://hub.docker.com/r/crossbario/>`_

.. note::

    The single file executable is a fully statically linked binary for the respective CPU architecture
    that does not depend on any installed libraries or software other than the OS kernel and the C run-time.

    .. code-block:: console

        oberstet@intel-nuci7:$ ldd crossbarfx-linux-amd64-20190108-9553865
            linux-vdso.so.1 (0x00007ffc4abeb000)
            libdl.so.2 => /lib/x86_64-linux-gnu/libdl.so.2 (0x00007f2778d35000)
            libz.so.1 => /lib/x86_64-linux-gnu/libz.so.1 (0x00007f2778b18000)
            libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f2778727000)
            /lib64/ld-linux-x86-64.so.2 (0x00007f2778f39000)


For Linux
.........

The CrossbarFX single-file executable should run on any Linux distribution
with a Linux kernel 3.10+ (glibc 2.17+) and x86 64 bit CPU architecture.

E.g. the executable has been tested on the following Linux distributions and works
on any of those (or later):

=================================    ================   =============   ====================
OS                                   Linux              libc            tested
=================================    ================   =============   ====================
RHEL/CentOS 7                        3.10               glibc 2.17      works
SLES 12                              3.12               glibc 2.19      not tested
Ubuntu 14.04 LTS "Trusty Tahr"       3.13               eglibc 2.19     works
Debian 8 "Jessie"                    3.16               glibc 2.19      works
=================================    ================   =============   ====================

Download the latest release from `here <https://download.crossbario.com/?prefix=crossbarfx/linux-amd64/>`_, make the file executable, and place it somewhere convenient:

.. code-block:: console

    cd /tmp
    curl -o crossbarfx https://download.crossbario.com/crossbarfx/linux-amd64/crossbarfx-latest
    chmod +x crossbarfx
    sudo cp ./crossbarfx /usr/local/bin/crossbarfx
    crossbarfx edge version

Here is a log of above:

.. code-block:: console

    oberstet@intel-nuci7:~$ curl -o crossbarfx https://download.crossbario.com/crossbarfx/linux-amd64/crossbarfx-linux-amd64-20190201-dfe263a  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                     Dload  Upload   Total   Spent    Left  Speed
    100 43.4M  100 43.4M    0     0  2232k      0  0:00:19  0:00:19 --:--:-- 2492k
    oberstet@intel-nuci7:~$ chmod +x crossbarfx
    oberstet@intel-nuci7:~$ sudo cp crossbarfx /usr/local/bin/
    [sudo] Passwort für oberstet:
    oberstet@intel-nuci7:~$ crossbarfx master version

        :::::::::::::::::
              :::::          _____                 __              _____  _______
        :::::   :   :::::   / ___/______  ___ ___ / /  ___ _____  / __/ |/_/ ___/
        :::::::   :::::::  / /__/ __/ _ \(_-<(_-</ _ \/ _ `/ __/ / _/_>  </ /__
        :::::   :   :::::  \___/_/  \___/___/___/_.__/\_,_/_/   /_/ /_/|_|\___/
              :::::
        :::::::::::::::::   Crossbar.io Fabric XBR Center v19.1.1 [20190201-dfe263a]

        Copyright (c) 2013-2019 Crossbar.io Technologies GmbH. All rights reserved.

     Crossbar.io        : 19.1.2
       txaio            : 18.8.1
       Autobahn         : 19.1.1
       Twisted          : 18.9.0-EPollReactor
       LMDB             : 0.94/lmdb-0.9.22
       Python           : 3.7.1/CPython
     Crossbar.io     : 19.1.1
       txaio-etcd       : -
       XBR              : 18.12.2
       zLMDB            : 19.1.1
     Frozen executable  : yes
     Operating system   : Linux-4.15.0-44-generic-x86_64-with-debian-buster-sid
     Host machine       : x86_64
     Release key        : RWSYMhkKjlumkHKD93y/IDruNCLAbAgcBYW551mEk1qtv0KkTapYBfmc

    oberstet@intel-nuci7:~$


For Windows
...........

The CrossbarFX single-file executable should run on any Windows since Windows XP,
and on x86 32 bit and 64 bit. CrossbarFX for Windows does not require anything
to install (like from MSIs packages or such),  and it does not require Administrator
rights to run.

Download the latest release from

* `Windows x86, 64 bit <https://download.crossbario.com/?prefix=crossbarfx/windows-amd64/>`_
* `Windows x86, 32 bit <https://download.crossbario.com/?prefix=crossbarfx/windows-x86/>`_

and place it somewhere convenient like your desktop.

Now open a command shell, change to your desktop, and run:

.. code-block:: console

    crossbarfx.exe edge version


Starting your first node
........................

.. code-block:: bash

    #!/bin/sh

    CROSSBAR_FABRIC_URL=ws://localhost:9000/ws
    CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub

    echo "Using CROSSBAR_FABRIC_URL=${CROSSBAR_FABRIC_URL}"
    echo "Using CROSSBAR_FABRIC_SUPERUSER=${CROSSBAR_FABRIC_SUPERUSER}"

    # this will create ~/.crossbarfx/* if it doesn't yet exist
    crossbarfx shell init --yes
    crossbarfx master version

    # test from scratch
    rm -rf ./test

    # start CFC node
    mkdir -p ./test/cfc
    crossbarfx master start --cbdir ./test/cfc/.crossbar &
    sleep 5

    # initialize 3 CF nodes
    crossbarfx edge init --appdir ./test/cf1
    crossbarfx edge init --appdir ./test/cf2
    crossbarfx edge init --appdir ./test/cf3
    sleep 5

    # authenticate, create new management realm and pair the 3 CF nodes
    crossbarfx shell init --yes
    crossbarfx shell create mrealm mrealm1
    crossbarfx shell list mrealms
    crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
    crossbarfx shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
    crossbarfx shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3
    sleep 5

    # start the 3 CF nodes
    crossbarfx edge start --cbdir ./test/cf1/.crossbar &
    crossbarfx edge start --cbdir ./test/cf2/.crossbar &
    crossbarfx edge start --cbdir ./test/cf3/.crossbar &
    crossbarfx shell --realm mrealm1 list nodes
    sleep 5

    # create a web cluster
    crossbarfx shell --realm mrealm1 create webcluster cluster1 \
        --config '{"tcp_port": 8080, "tcp_shared": true}'
    crossbarfx shell --realm mrealm1 list webclusters
    crossbarfx shell --realm mrealm1 list webcluster-nodes cluster1

    crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node1
    crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node2
    crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node3
    crossbarfx shell --realm mrealm1 list webcluster-nodes cluster1

    crossbarfx shell --realm mrealm1 add webcluster-service cluster1 info \
        --config '{"type": "nodeinfo"}'
    crossbarfx shell --realm mrealm1 list webcluster-services cluster1

    crossbarfx shell --realm mrealm1 start webcluster cluster1
    sleep 5

    # stop and remove everything again
    crossbarfx shell --realm mrealm1 stop webcluster cluster1
    crossbarfx shell --realm mrealm1 remove webcluster-service cluster1 info
    crossbarfx shell --realm mrealm1 remove webcluster-transport cluster1 transport1
    crossbarfx shell --realm mrealm1 remove webcluster-node cluster1 node1
    crossbarfx shell --realm mrealm1 remove webcluster-node cluster1 node2
    crossbarfx shell --realm mrealm1 remove webcluster-node cluster1 node3
    crossbarfx shell --realm mrealm1 delete webcluster cluster1

    crossbarfx shell --realm mrealm1 list nodes
    crossbarfx edge stop --cbdir ./test/cf1/.crossbar
    crossbarfx edge stop --cbdir ./test/cf2/.crossbar
    crossbarfx edge stop --cbdir ./test/cf3/.crossbar
    crossbarfx shell --realm mrealm1 list nodes

    crossbarfx shell list mrealms
    crossbarfx shell delete mrealm mrealm1
    crossbarfx shell list mrealms

    crossbarfx master stop --cbdir ./test/cfc/.crossbar


Starting a cluster
..................

Assume you have created a management realm ``mrealm1`` and paired three nodes:


.. code-block:: console

    crossbarfx shell create mrealm mrealm1
    crossbarfx shell pair node ./test/cf1/.crossbar/key.pub mrealm1 node1
    crossbarfx shell pair node ./test/cf2/.crossbar/key.pub mrealm1 node2
    crossbarfx shell pair node ./test/cf3/.crossbar/key.pub mrealm1 node3

and have all nodes running

.. code-block:: console

    crossbarfx edge start --cbdir ./test/cf1/.crossbar &
    crossbarfx edge start --cbdir ./test/cf2/.crossbar &
    crossbarfx edge start --cbdir ./test/cf3/.crossbar &

Then you can create a web cluster:

.. code-block:: console

    crossbarfx shell --realm mrealm1 create webcluster cluster1 --config '{"tcp_port": 8080, "tcp_shared": true}'
    crossbarfx shell --realm mrealm1 list webclusters
    crossbarfx shell --realm mrealm1 show webcluster cluster1

add nodes to the webcluster

.. code-block:: console

    crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node1 --config '{"parallel": 4}'
    crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node2 --config '{"parallel": 4}'
    crossbarfx shell --realm mrealm1 add webcluster-node cluster1 node3 --config '{"parallel": 4}'
    crossbarfx shell --realm mrealm1 list webcluster-nodes cluster1
    crossbarfx shell --realm mrealm1 show webcluster-node cluster1 node1

add services to the webcluster

.. code-block:: console

    crossbarfx shell --realm mrealm1 add webcluster-service cluster1 '/' \
        --config '{"type": "static", "directory": "/tmp", "options": {"enable-directory-listing": true}}'
    crossbarfx shell --realm mrealm1 add webcluster-service cluster1 'hello' \
        --config '{"type": "json", "value": "Hello, world!"}'
    crossbarfx shell --realm mrealm1 add webcluster-service cluster1 'info' --config '{"type": "nodeinfo"}'
    crossbarfx shell --realm mrealm1 list webcluster-services cluster1
    crossbarfx shell --realm mrealm1 show webcluster-service cluster1 "/"

and finally start the cluster:

.. code-block:: console

    crossbarfx shell --realm mrealm1 start webcluster cluster1
    crossbarfx shell --realm mrealm1 show webcluster cluster1

The web cluster will run four workers on each of the three nodes with a transport on
each and with three web services defined.

Incoming requests will be served by all of the 12 worker processes. To check, run the following in a shell script:

.. code-block:: bash

    for i in `seq 1 100`;
    do
        sh -c 'curl -s http://localhost:8080/info | grep "with PID"'
    done

You should be able to find 12 PIDs in the log

.. code-block:: console

      Served for 127.0.0.1:55476 from Crossbar.io router worker with PID 20946.
      Served for 127.0.0.1:55478 from Crossbar.io router worker with PID 20807.
      Served for 127.0.0.1:55480 from Crossbar.io router worker with PID 20934.
      Served for 127.0.0.1:55482 from Crossbar.io router worker with PID 20832.
      Served for 127.0.0.1:55484 from Crossbar.io router worker with PID 20849.
      Served for 127.0.0.1:55486 from Crossbar.io router worker with PID 20934.
      Served for 127.0.0.1:55488 from Crossbar.io router worker with PID 20897.
      ...

The following Web services can be run in Web clusters:

* ``path``
* ``static``
* ``json``
* ``nodeinfo``
* ``redirect``
* ``reverseproxy``
* ``websocket-reverseproxy``
* ``cgi``
* ``wsgi``

.. note::

    The following Web services cannot be run in Web clusters currently:
    ``resource``, ``websocket``, ``longpoll``, ``caller``, ``publisher``, ``webhook``

Using a real performance benchmarking tool (https://github.com/wg/wrk/wiki/Installing-Wrk-on-Linux) for
measuring HTTP performance:

.. code-block:: console

    (pypy3_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ wrk -c 500 -t 4 -d 60 --latency http://127.0.0.1:8080/hello
    Running 1m test @ http://127.0.0.1:8080/hello
      4 threads and 500 connections
      Thread Stats   Avg      Stdev     Max   +/- Stdev
        Latency     4.04ms    4.56ms  68.64ms   87.28%
        Req/Sec    40.09k     5.87k   77.28k    75.41%
      Latency Distribution
         50%    2.19ms
         75%    4.55ms
         90%   10.13ms
         99%   21.35ms
      9574688 requests in 1.00m, 2.89GB read
    Requests/sec: 159367.32
    Transfer/sec:     49.24MB
    (pypy3_1) oberstet@intel-nuci7:~/scm/crossbario/crossbarfx$ wrk -c 1 -t 1 -d 60 --latency http://127.0.0.1:8080/hello
    Running 1m test @ http://127.0.0.1:8080/hello
      1 threads and 1 connections
      Thread Stats   Avg      Stdev     Max   +/- Stdev
        Latency    41.24us  107.14us   5.98ms   99.03%
        Req/Sec    27.09k     1.28k   29.92k    78.37%
      Latency Distribution
         50%   33.00us
         75%   35.00us
         90%   45.00us
         99%  141.00us
      1619989 requests in 1.00m, 500.56MB read
    Requests/sec:  26955.16
    Transfer/sec:      8.33MB

The top run is optimized towards throughput, wheras the bottom one is optimized for latency.

.. code-block:: console

    (pypy3_1) oberstet@matterhorn:~/scm/crossbario/crossbarfx$ wrk -c 256 -d 60 -t 8 --latency http://127.0.0.1:8080/hello
    Running 1m test @ http://127.0.0.1:8080/hello
      8 threads and 256 connections
      Thread Stats   Avg      Stdev     Max   +/- Stdev
        Latency     1.70ms    3.69ms 125.89ms   91.44%
        Req/Sec    38.45k     9.27k   57.62k    58.78%
      Latency Distribution
         50%  598.00us
         75%    1.03ms
         90%    4.48ms
         99%   15.49ms
      18349001 requests in 1.00m, 5.54GB read
    Requests/sec: 305378.19
    Transfer/sec:     94.36MB
    (pypy3_1) oberstet@matterhorn:~/scm/crossbario/crossbarfx$ wrk -c 1 -d 60 -t 1 --latency http://127.0.0.1:8080/hello
    Running 1m test @ http://127.0.0.1:8080/hello
      1 threads and 1 connections
      Thread Stats   Avg      Stdev     Max   +/- Stdev
        Latency    84.37us  583.59us  33.10ms   99.84%
        Req/Sec    14.45k   628.23    15.32k    92.50%
      Latency Distribution
         50%   66.00us
         75%   67.00us
         90%   68.00us
         99%   93.00us
      862901 requests in 1.00m, 266.63MB read
    Requests/sec:  14381.63
    Transfer/sec:      4.44MB
