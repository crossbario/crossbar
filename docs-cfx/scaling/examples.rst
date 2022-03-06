Examples
========

The following describes some common setups using Crossbar.io and
Web/Router Clusters for High-availability (HA), scale-up (utilizing multiple
CPU core on a single host) and scale-out (utilizing multiple hosts).

.. note::

    The examples here will work with all Crossbar.io binary flavors, that is
    Docker (CPython and PyPy), snap and EXE (single-file executable). However,
    The Docker/PyPy image of Crossbar.io is recommended for production, and
    should be used for any performance tests and benchmarking.

.. contents:: :local:

-----------

Prerequisites
-------------

CrossbarFX CLI
..............

Download and install the Crossbar.io single-file executable, which embeds
a command line inferface (CLI) to the master node:

.. code-block:: console

	curl https://download.crossbario.com/crossbarfx/linux-amd64/crossbarfx-latest -o /tmp/crossbarfx
	chmod +x /tmp/crossbarfx
	sudo cp /tmp/crossbarfx /usr/local/bin/

Now add the following to your ``~/.profile``

.. code-block:: bash

    CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub
    CROSSBAR_FABRIC_URL=ws://localhost:9000/ws

Make sure to refresh your current environment:

.. code-block:: console

    source ~/.profile

Initialize your default user profile for CLI usage:

.. code-block:: console

    crossbarfx shell init --yes

This will generate the following files:

.. code-block:: console

    $ find ~/.crossbarfx
    /home/oberstet/.crossbarfx
    /home/oberstet/.crossbarfx/config.ini
    /home/oberstet/.crossbarfx/default.pub
    /home/oberstet/.crossbarfx/default.priv
    $ cat ~/.crossbarfx/config.ini
    [default]

    url=ws://localhost:9000/ws
    privkey=default.priv
    pubkey=default.pub


CrossbarFX nodes setup
......................

The examples below all use 4 nodes in total:

* one master node
* three managed nodes

and

* the default management realm (automatically created)
* the three managed nodes auto-paired to the default management realm

The following describes how to start these 4 nodes using the Crossbar.io Docker image
all on the local machine, eg a developer notebook. Since all nodes are run on one host,
and to keep things simple, the nodes will listen on different ports:

* **TCP/8080** for the load-balancer
* **TCP/8081** for the managed node 1 (port TCP/8080 internally)
* **TCP/8082** for the managed node 2 (port TCP/8080 internally)
* **TCP/8082** for the managed node 3 (port TCP/8080 internally)
* **TCP/9000** for the master node

To get going, make sure to install Docker and docker-compose. Now create a ``docker-compose.yml``
file with this contents (eg in an otherwise empty directory):

.. code-block:: yaml

    version: '3'
    services:
        master:
            container_name: master
            image: crossbario/crossbarfx:pypy-slim-amd64
            ports:
                # TCP port mapping (HOST:CONTAINER port):
                - "9000:9000"
            tty: true
            environment:
                # mapped from host file ${HOME}/.crossbarfx/default.pub
                - CROSSBAR_FABRIC_SUPERUSER=../default.pub

                # both of these are required for auto-discovery & pairing of nodes
                - CROSSBAR_FABRIC_URL=ws://master:9000/ws
                - CROSSBAR_WATCH_TO_PAIR=/nodes
            volumes:
                # superuser public key
                - "${HOME}/.crossbarfx/default.pub:/default.pub:ro"

                # nodes parent directory (of all nodes) is mapped from host:
                - "${PWD}/.test/nodes:/nodes:rw"

                # node directory of master node
                - "${PWD}/.test/master:/master:rw"
            command:
                - master
                - start
                - --cbdir=/master

        # repeat this block for node2, node3, .. (adjusting container_name,
        # CROSSBAR_NODE_ID and host volume path)
        node1:
            container_name: node1
            image: crossbario/crossbarfx:pypy-slim-amd64
            ports:
                # TCP port mapping (HOST:CONTAINER port):
                - "8081:8080"
            tty: true
            environment:
                # auto-pairing configuration
                - CROSSBAR_FABRIC_URL=ws://master:9000/ws
                - CROSSBAR_NODE_ID=node1
            volumes:
                # node directory (of this node only!) is mapped from host:
                - "${PWD}/.test/nodes/node1:/node:rw"
            command:
                - edge
                - start
                - --cbdir=/node

To **start** a Docker container with a **master node**:

.. code-block:: console

    docker-compose up master

You should see log output of the master node booting the first time. The master node should pick up the
public key of the default profile from your Crossbar.io shell (CLI) dotdir:

.. code-block:: console

    master    | 2020-07-30T19:38:20+0000 [Router         11] SUPERUSER public key c13ab830a27fbfc5b3a5c7f78c9a5c2d6da7464c83fa1745f0969c6442e1bf2c loaded from /default.pub

You should also see a default management realm be created (or found, after the first boot of the container):

.. code-block:: console

    master    | 2020-07-30T19:38:25+0000 [Container      18] Default management realm enabled
    master    | 2020-07-30T19:38:25+0000 [Container      18] Default management realm created [oid=a1e2c643-4355-473d-98ad-598c498499bc]

and finally "watch-to-pair" being active, so nodes can be paired automatically to the default
management realm:

.. code-block:: console

    master    | 2020-07-30T19:38:25+0000 [Container      17] Watch-to-pair enabled
    master    | 2020-07-30T19:38:25+0000 [Container      17] Configuration "auto_default_mrealm.watch_to_pair" set to "/nodes" from environment variable "$CROSSBAR_WATCH_TO_PAIR"

The last log line should read similar to

.. code-block:: console

    master    | 2020-07-30T19:38:30+0000 [Controller      1] <crossbarfx.master.node.node.FabricCenterNode.boot>::NODE_BOOT_COMPLETE

Open `http://localhost:9000/info <http://localhost:9000/info>`_ in a browser. This should render a HTML node
info page. You can also check the master node status from the CLI:

.. code-block:: console

    crossbarfx shell show status

Next, **pre-create node keys for 3 managed nodes** (which we'll start in the next step):

.. code-block:: console

    sudo mkdir -p ./.test/nodes
    sudo CROSSBAR_NODE_ID=node1 crossbarfx edge keys --cbdir=./.test/nodes/node1
    sudo CROSSBAR_NODE_ID=node2 crossbarfx edge keys --cbdir=./.test/nodes/node2
    sudo CROSSBAR_NODE_ID=node3 crossbarfx edge keys --cbdir=./.test/nodes/node3

Now, to **start** a Docker container with **managed nodes 1, 2 and 3**:

.. code-block:: console

    docker-compose up node1

Repeat the same for ``node2`` and ``node3`` in different shell sessions, while keeping the master node and all three managed nodes running in parallel.

**Congrats! You should now have 4 Docker containers running with master node and three managed nodes
that have been auto-paired to the default management realm.**

To stop and remove all (locally running) Docker containers:

.. code-block:: console

    docker stop $(docker ps -a -q)
    docker rm $(docker ps -a -q)

To show the status of all nodes:

.. code-block:: console

    crossbarfx shell --realm default show node

When everything is good, command output should look similar to:

.. code-block:: console

    $ crossbarfx shell --realm default show node

    [{'authextra': {'mrealm_oid': 'a1e2c643-4355-473d-98ad-598c498499bc',
                    'node_oid': '21413e8d-4629-42db-ae8d-7086fe8352cb'},
    'authid': 'node-21413e8d',
    'description': None,
    'heartbeat': 15,
    'label': None,
    'mrealm_oid': 'a1e2c643-4355-473d-98ad-598c498499bc',
    'oid': '21413e8d-4629-42db-ae8d-7086fe8352cb',
    'owner_oid': '99ec7304-98b2-4321-b567-f9169c049906',
    'pubkey': '95b4dfcb2a1fa9d8bd2a60ca2545a03f3f93c358487890f39f46c5191f11f73e',
    'status': 'online',
    'tags': None,
    'timestamp': 1596138672715645696},
    {'authextra': {'mrealm_oid': 'a1e2c643-4355-473d-98ad-598c498499bc',
                    'node_oid': 'a87b0cd2-7ec3-4885-9bb0-19b97fe500fc'},
    'authid': 'node-a87b0cd2',
    'description': None,
    'heartbeat': 4,
    'label': None,
    'mrealm_oid': 'a1e2c643-4355-473d-98ad-598c498499bc',
    'oid': 'a87b0cd2-7ec3-4885-9bb0-19b97fe500fc',
    'owner_oid': '99ec7304-98b2-4321-b567-f9169c049906',
    'pubkey': 'c0d4c1326df54c204c0b258bea7b447c950c35e2c2c7003913cbd2199d093b67',
    'status': 'online',
    'tags': None,
    'timestamp': 1596138668823008512},
    {'authextra': {'mrealm_oid': 'a1e2c643-4355-473d-98ad-598c498499bc',
                    'node_oid': 'd0ebbddc-79e7-45bf-a509-06adbda959d6'},
    'authid': 'node-d0ebbddc',
    'description': None,
    'heartbeat': 3,
    'label': None,
    'mrealm_oid': 'a1e2c643-4355-473d-98ad-598c498499bc',
    'oid': 'd0ebbddc-79e7-45bf-a509-06adbda959d6',
    'owner_oid': '99ec7304-98b2-4321-b567-f9169c049906',
    'pubkey': '7371f915f8ddfd6eb342af544b538b2c95e27afa90544092780a1ea8420e3e01',
    'status': 'online',
    'tags': None,
    'timestamp': 1596138670525071616}]

Once a managed node (that is paired) connects successfully to the master node, you will see a log
line similar to:

.. code-block:: console

    master_1  | 2020-07-30T15:30:12+0000 [Container      25] Success: managed node "node-21413e8d" is now online [oid=21413e8d-4629-42db-ae8d-7086fe8352cb, session=5576088267149225, status=online] <crossbarfx.master.mrealm.controller.MrealmController._on_session_startup>

You can also check the node directories of both the master node and the three managed
nodes on the host, eg:

.. code-block:: console

    $ find .test/
    .test/
    .test/nodes
    .test/nodes/node2
    .test/nodes/node2/key.priv
    .test/nodes/node2/key.pub
    .test/nodes/node2/key.activate
    .test/nodes/node2/node.pid
    .test/nodes/node3
    .test/nodes/node3/key.priv
    .test/nodes/node3/key.pub
    .test/nodes/node3/key.activate
    .test/nodes/node3/node.pid
    .test/nodes/node1
    .test/nodes/node1/key.priv
    .test/nodes/node1/key.pub
    .test/nodes/node1/key.activate
    .test/nodes/node1/node.pid
    .test/master
    .test/master/.db-controller
    .test/master/.db-controller/data.mdb
    .test/master/.db-controller/lock.mdb
    .test/master/key.priv
    .test/master/key.pub
    .test/master/autobahn-v20.2.1.zip
    .test/master/.db-mrealm-a1e2c643-4355-473d-98ad-598c498499bc
    .test/master/.db-mrealm-a1e2c643-4355-473d-98ad-598c498499bc/data.mdb
    .test/master/.db-mrealm-a1e2c643-4355-473d-98ad-598c498499bc/lock.mdb
    .test/master/node.pid
    .test/master/sock1
    .test/master/sock2

Here, some important files are:

* ``.test/master/.db-controller/data.mdb``: the domain-wide ("global") embedded database in the master node
* ``.test/master/.db-mrealm-a1e2c643-4355-473d-98ad-598c498499bc/data.mdb``: the default management realm embedded database in the master node
* ``.test/nodes/node1/key.activate``: the auto-activation file written by the master node, and read by the managed node 1 (in this case)

To monitor your managed nodes remotely, you can use:

.. code-block:: console

    crossbarfx shell monitor

.. thumbnail:: /_static/screenshots/cfx-shell-monitor-1.png

The process structure (from the host perspective) of the 4 nodes looks like (here, a web cluster with parallel=2 was already started):

.. thumbnail:: /_static/screenshots/cfx-process-structure-1.png

Here is the set of processes under load:

.. thumbnail:: /_static/screenshots/cfx-process-structure-2.png


wrk HTTP probe
..............

`wrk <https://github.com/wg/wrk>`_ is a modern HTTP benchmarking tool capable of generating
significant load when run on a single multi-core CPU.

To build and install from upstream sources (recommended):

.. code-block:: console

    git clone https://github.com/wg/wrk.git
    cd wrk
    make
    sudo cp wrk /usr/local/bin/

Basic usage:

.. code-block:: console

    wrk -t12 -c400 -d30s http://127.0.0.1:8080/mydata

This runs a benchmark for 30 seconds, using 12 threads, and keeping 400 HTTP connections open.


HAProxy HTTP load-balancer
..........................

`HAProxy <https://www.haproxy.org/>`_ is a reliable, high-performance TCP/HTTP load balancer.

To install from distro packages (recommended):

.. code-block:: console

    sudo apt update
    sudo apt install -y haproxy haproxyctl


Single-node scale-up
--------------------

Web- and Router-clusters can be used to scale-up Crossbar.io on a single machine
with multiple CPU cores by

* running at least one Web cluster with a parallel degree > 1 ("parallel web clusters")
* running multiple Router clusters with a scale == 1 each
* running at least one Router cluster with scale > 1 ("scaled router clusters")

on that machine (Crossbar.io node).

.. note::

    Obviously, you can also utilize multiple CPU core on a single host by running
    multiple Crossbar.io nodes (or even VMs) on that machine. We won't go any further
    into details about that approach here.


Parallel Web clusters
.....................

For single-node Web clusters, you can specify a **parallel degree > 1**
for the node you add to the cluster. This will start as many Crossbar.io proxy workers
as specified in the parallel degree on the node added.
Eg to make use of *all* CPU cores for processing TLS, WebSocket and JSON on incoming client
WAMP connections (which is what the proxy workers of a Web cluster provide), we recommend to
set **parallel degree == number of cores x 2**.

To **auto-select the parallel degree, specify a negative integer (-1)** when adding a node to
the web cluster. A parallel degree equal to double the number CPU cores on the added node
will be selected automatically (recommended).

Create a new Web cluster:

.. code-block:: console

    crossbarfx shell --realm default create webcluster cluster1 \
        --config='{"tcp_port": 8080, "tcp_shared": true}'

To show all nodes currently paired in the default management realm:

.. code-block:: console

    crossbarfx shell --realm default show node

Choose the node you want to use for your single-node Web cluster, say ``node-e462e059``).

To add the node with (WAMP) ``authid`` ``node-e462e059`` to the cluster,
with a parallel degree of 8 for the node, run:

.. code-block:: console

    crossbarfx shell --realm default add webcluster-node cluster1 node-e462e059 \
        --config '{"parallel": 8}'

Next, since we want to quickly test already the Web cluster itself, let's add some
simple Web services to the cluster:

.. code-block:: console

    crossbarfx shell --realm default add webcluster-service cluster1 "mydata" \
        --config '{"type": "json", "value": {"msg": "Hello, world!", "codes": [1, 2, 3]}}'
    crossbarfx shell --realm default add webcluster-service cluster1 "info" \
        --config '{"type": "nodeinfo"}'

Now start the Web cluster:

.. code-block:: console

    crossbarfx shell --realm default start webcluster cluster1

Open in your browser:

* `http://localhost:8080/mydata <http://localhost:8080/mydata>`_ for the static JSON response value
* `http://localhost:8080/info <http://localhost:8080/info>`_ for the rendered node info HTML page

Congrats! You now have a parallel enabled, single-node Web cluster that will scale-up and fully
utilize a quad-core CPU.

To show details about your cluster:

.. code-block:: console

    crossbarfx shell --realm default show webcluster cluster1
    crossbarfx shell --realm default show webcluster-node cluster1 node-e462e059

and to show details about Web service currently running on your Web cluster:

.. code-block:: console

    crossbarfx shell --realm default list webcluster-services cluster1
    crossbarfx shell --realm default show webcluster-service cluster1 "mydata"

To benchmark the cluster, run:

.. code-block:: console

    wrk -t8 -c1000 -d30s http://127.0.0.1:8080/mydata

Above will start 1 process with 8 threads opening a total of 1000 concurrent
connections, and doing HTTP/GET requests to the specified URL.

.. note::

    Obviously, when testing with both the tested cluster, and the test probe (**wrk**)
    running on one machine over loopback TCP, the machine must have enough CPU cores
    for both workloads (the testee and the test load probe). With 100% CPU, the testee
    CPU core scalability will be distorted (by the load probe consuming CPU as well).


Router Clusters
...............

*Regular* router clusters run router groups with scale == 1 each. No router-to-router links
are involved. Frontend proxy workers route incoming WAMP traffic to the correct backend
router worker. The worker runs as the single worker in the router worker group responsible
for the respective application realm the incoming connecting should is authenticated and
joined to.

.. code-block:: console

	crossbarfx shell --realm default create routercluster cluster2
	crossbarfx shell --realm default add routercluster-node cluster2 all --config '{"softlimit": 4, "hardlimit": 8}'
	crossbarfx shell --realm default add routercluster-workergroup cluster2 mygroup1 --config '{"scale": 1}'
	crossbarfx shell --realm default add routercluster-workergroup cluster2 mygroup2 --config '{"scale": 1}'
	crossbarfx shell --realm default add routercluster-workergroup cluster2 mygroup3 --config '{"scale": 1}'
	crossbarfx shell --realm default add routercluster-workergroup cluster2 mygroup4 --config '{"scale": 1}'

.. code-block:: console

	crossbarfx shell --realm default create arealm myrealm1 --config='{}'
	crossbarfx shell --realm default create arealm myrealm2 --config='{}'
	crossbarfx shell --realm default create arealm myrealm3 --config='{}'
	crossbarfx shell --realm default create arealm myrealm4 --config='{}'

.. code-block:: console

	crossbarfx shell --realm default create role myrole1 --config='{}'
	crossbarfx shell --realm default add role-permission myrole1 "" --config='{"match": "prefix", "allow_call": true, "allow_register": true, "allow_publish": true, "allow_subscribe": true, "disclose_caller": true, "disclose_publisher": true, "cache": true}'
	crossbarfx shell --realm default add arealm-role myrealm1 myrole1 --config='{"authmethod": "anonymous"}'
	crossbarfx shell --realm default add arealm-role myrealm2 myrole1 --config='{"authmethod": "anonymous"}'
	crossbarfx shell --realm default add arealm-role myrealm3 myrole1 --config='{"authmethod": "anonymous"}'
	crossbarfx shell --realm default add arealm-role myrealm4 myrole1 --config='{"authmethod": "anonymous"}'

.. code-block:: console

	crossbarfx shell --realm default start routercluster cluster2
	crossbarfx shell --realm default start arealm myrealm1 cluster2 mygroup1 cluster1
	crossbarfx shell --realm default start arealm myrealm2 cluster2 mygroup2 cluster1
	crossbarfx shell --realm default start arealm myrealm3 cluster2 mygroup3 cluster1
	crossbarfx shell --realm default start arealm myrealm4 cluster2 mygroup3 cluster1

.. code-block:: console

	crossbarfx shell --realm default add webcluster-service cluster1 "ws" --config '{"type": "websocket"}'
	crossbarfx shell --realm default start webcluster cluster1


Scaled Router Clusters
......................

**Still under development!**

*Scaled* router clusters run at least one router group with scale > 1. Running more than
one worker in a router worker group requires router-to-router links (between the router
workers of a group).


Multi-node scale-out with HAProxy
---------------------------------

Create a HAProxy configuration file ``haproxy.conf`` with the following contents:

.. code-block:: console

    global
       log 127.0.0.1 local2
       maxconn 200000

    defaults
       log global
       timeout connect 2000
       timeout client 2000
       timeout server 2000

    listen stats
       bind 127.0.0.1:1936
       mode http
       stats enable
       stats hide-version
       stats realm Haproxy\ Statistics
       stats uri /

    frontend crossbar
        bind *:8080
        mode tcp
        option tcplog
        default_backend crossbar_nodes
        timeout client 1m

    backend crossbar_nodes
        mode tcp
        option log-health-checks
        log global
        # balance roundrobin
        balance leastconn
        server node1 127.0.0.1:8081 check fall 3 rise 2
        server node2 127.0.0.1:8082 check fall 3 rise 2
        server node3 127.0.0.1:8083 check fall 3 rise 2
        server node4 127.0.0.1:8084 check fall 3 rise 2
        timeout connect 10s
        timeout server 1m

Start HAProxy by running:

.. code-block:: console

    haproxy -f haproxy.conf

You should see logs lines similar to:

.. code-block:: console

    $ haproxy -f haproxy.conf
    [WARNING] 212/004409 (4017) : Health check for server crossbar_nodes/node1 succeeded, reason: Layer4 check passed, check duration: 0ms, status: 3/3 UP.
    [WARNING] 212/004410 (4017) : Health check for server crossbar_nodes/node2 succeeded, reason: Layer4 check passed, check duration: 0ms, status: 3/3 UP.
    [WARNING] 212/004410 (4017) : Health check for server crossbar_nodes/node3 succeeded, reason: Layer4 check passed, check duration: 0ms, status: 3/3 UP.

Open in your browser:

* `http://localhost:8080/mydata <http://localhost:8080/mydata>`_ (for the static JSON response value)
* `http://localhost:8080/info <http://localhost:8080/info>`_ (for the rendered node info HTML page)

To check that HAProxy is actually forwarding HTTP request (on port 8080), to the three nodes
(running on ports 8081, 8082, 8083 on one host for demonstration purposes), run the following
command a couple of times and notice the changing node ID:

.. code-block:: console

    curl -s http://localhost:8080/info | grep "node-"

To check statistics and backend node health from HAProxy, open the `HAProxy page <http://localhost:1936>`_ in your browser.

When you kill one of the nodes, HAProxy will notice:

.. code-block:: console

    [WARNING] 212/005229 (4017) : Health check for server crossbar_nodes/node1 failed, reason: Layer4 connection problem, info: "Connection refused", check duration: 0ms, status: 2/3 UP.

as well as the master node:

.. code-block:: console

    master    | 2020-07-30T22:52:29+0000 [Container      23] Warning: managed node "node-21413e8d" became offline [oid=21413e8d-4629-42db-ae8d-7086fe8352cb, session=1197540987905435, status=offline] <crossbarfx.master.mrealm.controller.MrealmController._on_session_shutdown>

When the node is started again, HAProxy will take notice

.. code-block:: console

    [WARNING] 212/005416 (4017) : Server crossbar_nodes/node1 is UP. 3 active and 0 backup servers online. 0 sessions requeued, 0 total in queue.

and again the master node as well

.. code-block:: console

    master    | 2020-07-30T22:54:20+0000 [Container      23] Ok, managed node "21413e8d-4629-42db-ae8d-7086fe8352cb" became healthy (again) [status=offline -> "online"] <crossbarfx.master.mrealm.controller.MrealmController._initialize.<locals>.on_check_nodes>

You can also verify that the HTTP services are still working while at least one node remains
healthy. Further, once a node is alive again, it will become active and fed with (new) incoming
connections by the load balancer. This demonstrates node-level HA.

Going on, you can also crash and kill individual processes (workers) within a single node,
and the master node will automatically restart and configure a new worker replacing the gap
in the desired state of the cluster.


Login into one of the containers running a managed node:

.. code-block:: console

    docker exec -it node1 bash

Determine the PID of one of the proxy workers running in the node:

.. code-block:: console

    ps -Af | grep proxy

and kill one of the workers:

.. code-block:: console

    kill -9 59

In the managed node logs, you should see something like:

.. code-block:: console

    node1     | 2020-07-30T22:57:45+0000 [Controller      1] Node worker cpw-66e4d4e2-7 ended with error ([Failure instance: Traceback (failure with no frames): <class 'twisted.internet.error.ProcessTerminated'>: A process has ended with a probable error condition: process ended by signal 9.
    ...
    node1     | 2020-07-30T22:57:46+0000 [Controller      1] Starting proxy-worker "cpw-66e4d4e2-7" .. <crossbar.node.controller.NodeController.start_worker>

while in the master node log lines like these should appear:

.. code-block:: console

    master    | 2020-07-30T22:57:46+0000 [Container      23] No Web cluster worker cpw-66e4d4e2-7 currently running on node 21413e8d-4629-42db-ae8d-7086fe8352cb: starting worker ..
    ...
    master    | 2020-07-30T22:57:51+0000 [Container      23] <crossbarfx.master.cluster.webcluster.WebClusterMonitor.check_and_apply> Web cluster worker cpw-66e4d4e2-7 started on node 21413e8d-4629-42db-ae8d-7086fe8352cb [{'id': 'cpw-66e4d4e2-7', 'status': 'started', 'started': '2020-07-30T22:57:51.887Z', 'who': 6492096218143899, 'pid': 78, 'startup_time': 5.59393}]

What has happened is the master node detecting the missing worker on the node, and then starting and configuring
a new worker. The cluster will be automatically completed again ("self-healed"), thus demonstrating HA on a process
or per-worker basis, rather than only per-node.

.. thumbnail:: /_static/screenshots/cfx-webcluster-haproxy.png


Multi-node scale-out with AWS-NLB
---------------------------------

Write me.
