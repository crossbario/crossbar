Using Docker
============

`CrossbarFX on DockerHub <https://hub.docker.com/r/crossbario/crossbarfx>`_:

.. thumbnail:: /_static/screenshots/crossbarfx_on_dockerhub.png

.. thumbnail:: /_static/screenshots/crossbarfx_on_dockerhub_tags.png

To pull the latest CrossbarFX image while automatically selecting the
right/best image for your CPU architecture:

::

    docker pull crossbario/crossbarfx:latest

Manually select the architecture and flavor:

-  **AMD64**: ``docker pull  crossbario/crossbarfx:pypy-amd64``
-  **i386**: ``docker pull  crossbario/crossbarfx:pypy-i386``
-  **ARM64**: ``docker pull  crossbario/crossbarfx:cpy-slim-arm64``
-  **ARM32**: ``docker pull  crossbario/crossbarfx:cpy-slim-arm32``

To test CrossbarFX and print version information:

::

    docker run -it --rm crossbario/crossbarfx:cpy-slim-amd64 master version

This should look like:

::

    oberstet@matterhorn:~$ docker run -it --rm crossbario/crossbarfx:cpy-slim-amd64 master version

        :::::::::::::::::
              :::::          _____                 __              _____  _______
        :::::   :   :::::   / ___/______  ___ ___ / /  ___ _____  / __/ |/_/ ___/
        :::::::   :::::::  / /__/ __/ _ \(_-<(_-</ _ \/ _ `/ __/ / _/_>  </ /__
        :::::   :   :::::  \___/_/  \___/___/___/_.__/\_,_/_/   /_/ /_/|_|\___/
              :::::
        :::::::::::::::::   Crossbar.io Fabric XBR Center v19.2.2 [00000]

        Copyright (c) 2013-2019 Crossbar.io Technologies GmbH. All rights reserved.

     Crossbar.io        : 19.2.1
       txaio            : 18.8.1
       Autobahn         : 19.2.1
       Twisted          : 18.9.0-EPollReactor
       LMDB             : 0.94/lmdb-0.9.22
       Python           : 3.7.2/CPython
     Crossbar.io     : 19.2.2
       NumPy            : 1.15.4
       zLMDB            : 19.2.2
       XBR              : 19.2.2
     Frozen executable  : no
     Operating system   : Linux-4.15.0-43-generic-x86_64-with-debian-9.7
     Host machine       : x86_64
     Release key        : RWR2yD4qEkDnHAOwcTx6qTqaTT55n+J5pWez5jXUFT89fwlfVO77nFaV


Selecting an image
------------------

All images are tagged according to the following scheme

::

    crossbario/crossbarfx:<python>[-slim]-<arch>

where ``<python>`` can take

-  ``pypy``: for a **PyPy 3 based CrossbarFX stack**: CrossbarFX runs
   **5-20x faster** on `PyPy <http://pypy.org/>`__, a tracing JIT
   compiler for Python
-  ``cpy``: for a **CPython 3 based CrossbarFX stack**: standard
   `CPython <https://www.python.org/>`__ based, available on more CPU
   architectures, quicker startup, potentially less memory consumption

and ``<arch>`` can take

-  ``amd64``: x86 64-bit CPUs
-  ``i386``: x86 32-bit CPUs
-  ``arm64``: ARMv8 64-bit CPUs
-  ``arm32``: ARMv7 32-bit CPUs

The **-slim** PyPy images are built from `PyPy Docker Official
Images <https://hub.docker.com/_/pypy>`__ while the non-slim PyPy images
are built directly from the `PyPy project binary
releases <http://pypy.org/download.html>`__ and
``buildpack-deps:bionic`` base images.

    Not all combinations of above are currently available.

Here is the currently available list of images:

::

    REPOSITORY              TAG                 IMAGE ID            CREATED             SIZE
    crossbario/crossbarfx   pypy-amd64          94879ab8fee3        6 hours ago         937MB
    crossbario/crossbarfx   pypy-i386           96a93f6096ed        6 hours ago         906MB
    crossbario/crossbarfx   pypy-slim-amd64     8dba32911b06        5 hours ago         498MB
    crossbario/crossbarfx   pypy-slim-i386      d1530a6a5467        5 hours ago         492MB
    crossbario/crossbarfx   cpy-slim-amd64      fbd8aa8852de        5 hours ago         540MB
    crossbario/crossbarfx   cpy-slim-i386       f7a28f354839        4 hours ago         504MB
    crossbario/crossbarfx   cpy-slim-arm64      acc7f5826f38        3 hours ago         480MB
    crossbario/crossbarfx   cpy-slim-arm32      8662282adf07        4 hours ago         401MB

To inspect the set of images referred to in the
``crossbario/crossbarfx`` multi-arch image:

::

    docker pull crossbario/crossbarfx:latest
    export DOCKER_CLI_EXPERIMENTAL=enabled
    docker manifest inspect crossbario/crossbarfx:latest

    Note: PyPy based images for ARM32 and ARM64 are not yet available.

Running a standalone node
-------------------------

CrossbarFX can be run as an **edge node** either standalone or
optionally connected to and managed by a CrossbarFX master node. Here is
how to create and run a standalone/unmanaged CrossbarFX *edge node*.

Create a new node application directory on the host:

::

    cd $HOME
    mkdir -p nodes/standalone1

Initialize the application directory:

::

    docker run -it --rm \
        -v ${HOME}/nodes/standalone1:/node \
        crossbario/crossbarfx:cpy-slim-amd64 \
        edge init --appdir /node

Start the CrossbarFX edge node from the directory:

::

    docker run -it --rm \
        -p 8080:8080 \
        -p 8081:8081 \
        -v ${HOME}/nodes/standalone1:/node \
        crossbario/crossbarfx:cpy-slim-amd64 \
        edge start --cbdir=/node/.crossbar

And open the nodes' info page at http://localhost:8080/info. You should
see some basic information rendered by the running node.

Running managed nodes
---------------------

CrossbarFX can be run as an **edge node** connected to and managed by a
CrossbarFX master node. Here is how to create and run a managed
CrossbarFX *edge node*.

Master node
...........

A master node is responsible of managing edge nodes and required for the
full feature set. Here is how to run a CrossbarFX *master node*.

Create a new node application directory on the host:

::

    cd $HOME
    mkdir -p nodes/master1

Initialize a superuser profile within the container by running:

::

    docker run -it --rm \
        -v ${HOME}/nodes/master1:/node \
        -e CROSSBAR_FABRIC_URL="ws://localhost:9000/ws" \
        crossbario/crossbarfx:cpy-slim-amd64 \
        shell auth --yes

and start the master node:

::

    docker run -d --name cfxmaster \
        -p 9000:9000 \
        -v ${HOME}/nodes/master1:/node \
        -v ${HOME}/nodes/:/nodes \
        -e CROSSBAR_FABRIC_URL="ws://localhost:9000/ws" \
        -e CROSSBAR_FABRIC_SUPERUSER=/node/.crossbarfx/default.pub \
        crossbario/crossbarfx:cpy-slim-amd64 \
        master start --cbdir=/nodes/master1/.crossbar

You can now login into the running container and administer the
CrossbarFX master node using the CLI from with (using the superuser
profile created above for authentication):

::

    docker exec -it cfxmaster bash

Here are a couple of CLI commands

::

    crossbarfx shell show status
    crossbarfx shell list mrealms
    crossbarfx shell create mrealm mrealm1
    crossbarfx shell show mrealm mrealm1

executed inside the running container:

.. code:: console

    oberstet@intel-nuci7:~$ docker exec -it cfxmaster bash
    root@7a75f56f5d13:/# crossbarfx shell show status
    {'now': '2019-02-24T14:27:59.616Z',
     'realm': 'com.crossbario.fabric',
     'started': '2019-02-24T14:26:25.679Z',
     'tick': 20,
     'type': 'domain',
     'uptime': 'a minute'}
    root@7a75f56f5d13:/# crossbarfx shell list mrealms
    []
    root@7a75f56f5d13:/# crossbarfx shell create mrealm mrealm1
    {'cf_container_worker': '00000000-0000-0000-0000-000000000000',
     'cf_node': '00000000-0000-0000-0000-000000000000',
     'cf_router_worker': '00000000-0000-0000-0000-000000000000',
     'created': 1551018503094144,
     'name': 'mrealm1',
     'oid': 'edac2a4a-fa70-48e8-9f09-b1ddb162ea24',
     'owner': '3e30230c-3a48-4ff6-94af-2107f1370891'}
    root@7a75f56f5d13:/# crossbarfx shell list mrealms
    ['edac2a4a-fa70-48e8-9f09-b1ddb162ea24']
    root@7a75f56f5d13:/# crossbarfx shell show mrealm mrealm1
    {'cf_container_worker': '00000000-0000-0000-0000-000000000000',
     'cf_node': '00000000-0000-0000-0000-000000000000',
     'cf_router_worker': '00000000-0000-0000-0000-000000000000',
     'created': 1551018503094144,
     'name': 'mrealm1',
     'oid': 'edac2a4a-fa70-48e8-9f09-b1ddb162ea24',
     'owner': '3e30230c-3a48-4ff6-94af-2107f1370891'}
    root@7a75f56f5d13:/#

Managed nodes
.............

Create a new node application directory on the host:

::

    cd $HOME
    mkdir -p nodes/edge1

Start the CrossbarFX edge node from the directory:

::

    docker run -it --rm \
        --link cfxmaster \
        -p 8080:8080 \
        -p 8081:8081 \
        -v ${HOME}/nodes/edge1:/node \
        -e CROSSBAR_FABRIC_URL="ws://cfxmaster:9000/ws" \
        crossbario/crossbarfx:cpy-slim-amd64 \
        edge start --cbdir=/node/.crossbar

CrossbarFX will start and exit again with log output similar to:

::

    ...
    2019-02-24T14:54:34+0000 [Controller      1] Node key files exist and are valid. Node public key is 0x5678a ..
    ...
    2019-02-24T14:54:34+0000 [Controller      1] Connecting to Crossbar.io Fabric Center at ws://cfxmaster:9000/ws ..
    2019-02-24T14:54:34+0000 [Controller      1] FABRIC.AUTH-FAILED.NODE-UNPAIRED: THIS NODE IS UNPAIRED. PLEASE PAIR ..
    ...

This is fine! The node has connected to the master node, but the master
node does not know the node (it is "unpaired") and the connection is
denied.

Go to the *terminal attached to the running master node container* and
pair the node:

::

    crossbarfx shell pair node /nodes/edge1/.crossbar/key.pub mrealm1 edge1

Here is log output:

::

    (cpy372_7) oberstet@intel-nuci7:~$ docker exec -it cfxmaster bash
    root@d18cf797a22a:/# crossbarfx shell list mrealms
    ['af3fabcf-34bb-4b7e-a739-2546d1715f37']
    root@d18cf797a22a:/# crossbarfx shell pair node /nodes/edge1/.crossbar/key.pub mrealm1 edge1
    {'authextra': None,
     'authid': 'edge1',
     'mrealm_oid': 'af3fabcf-34bb-4b7e-a739-2546d1715f37',
     'oid': 'e716f3ae-6053-4c1b-a511-9914ad9a94fe',
     'owner_oid': '68460374-8ab3-4d6d-b547-7791d45dec1b',
     'pubkey': '5678aa0a3528d1c0148e7ad93a9ff071c877ea98b8757c3f7a0bdec49c64b331'}

Now start the edge node again, you should see output like:

.. code:: console

    (cpy372_1) oberstet@intel-nuci7:~$ docker run -it --rm     --link cfxmaster     -p 8080:8080     -p 8081:8081     -v ${HOME}/nodes/edge1:/node     -e CROSSBAR_FABRIC_URL="ws://cfxmaster:9000/ws"     crossbario/crossbarfx:cpy-slim-amd64     edge start --cbdir=/node/.crossbar
    2019-03-01T12:06:10+0000 [Controller      1]
    2019-03-01T12:06:10+0000 [Controller      1]     :::::::::::::::::
    2019-03-01T12:06:10+0000 [Controller      1]           :::::          _____                 __              _____  __
    2019-03-01T12:06:10+0000 [Controller      1]     :::::   :   :::::   / ___/______  ___ ___ / /  ___ _____  / __/ |/_/
    2019-03-01T12:06:10+0000 [Controller      1]     :::::::   :::::::  / /__/ __/ _ \(_-<(_-</ _ \/ _ `/ __/ / _/_>  <
    2019-03-01T12:06:10+0000 [Controller      1]     :::::   :   :::::  \___/_/  \___/___/___/_.__/\_,_/_/   /_/ /_/|_|
    2019-03-01T12:06:10+0000 [Controller      1]           :::::
    2019-03-01T12:06:10+0000 [Controller      1]     :::::::::::::::::   Crossbar Fabric XBR v19.2.2 [00000]
    2019-03-01T12:06:10+0000 [Controller      1]
    2019-03-01T12:06:10+0000 [Controller      1]     Copyright (c) 2013-2019 Crossbar.io Technologies GmbH. All rights reserved.
    2019-03-01T12:06:10+0000 [Controller      1]
    2019-03-01T12:06:10+0000 [Controller      1] Initializing <crossbarfx.edge.node.node.FabricNode> as node [realm=crossbar, cbdir=/node/.crossbar]
    2019-03-01T12:06:10+0000 [Controller      1] Node key files exist and are valid. Node public key is 0xcf8c2ea74058a47ec2c90d8aa0c8e0508d823444003ed60243ddd6887a946c63
    2019-03-01T12:06:10+0000 [Controller      1] Node key loaded from /node/.crossbar/key.priv
    2019-03-01T12:06:10+0000 [Controller      1] Node configuration loaded [config_source=default, config_path=None]
    2019-03-01T12:06:10+0000 [Controller      1] Entering event reactor ...
    2019-03-01T12:06:10+0000 [Controller      1] Starting edge node <crossbar.node.node.Node.start>
    2019-03-01T12:06:10+0000 [Controller      1] Node ID 90bb13f6ea1a set from hostname
    2019-03-01T12:06:10+0000 [Controller      1] RouterServiceAgent ready (realm_name="crossbar", on_ready=None)
    2019-03-01T12:06:10+0000 [Controller      1] Docker daemon integration disabled
    2019-03-01T12:06:10+0000 [Controller      1] Registered 48 procedures
    2019-03-01T12:06:10+0000 [Controller      1] Signal handler installed on process 1 thread 139930718757888
    2019-03-01T12:06:10+0000 [Controller      1] Using default node shutdown triggers ['shutdown_on_shutdown_requested']
    2019-03-01T12:06:10+0000 [Controller      1] Booting node <crossbarfx.edge.node.node.FabricNode.boot>
    2019-03-01T12:06:10+0000 [Controller      1] Using custom fabric controller at URL "ws://cfxmaster:9000/ws" (from envvar)
    2019-03-01T12:06:10+0000 [Controller      1] Connecting to Crossbar.io Fabric Center at ws://cfxmaster:9000/ws ..
    2019-03-01T12:06:10+0000 [Controller      1] NodeManagementBridgeSession.attach_manager: manager attached as node "c82b34ee-fc5a-4de3-a484-b07720b5db02" on management realm "mrealm1")
    2019-03-01T12:06:10+0000 [Controller      1] Connected to Crossbar.io Fabric Center at management realm "mrealm1", set node ID "c82b34ee-fc5a-4de3-a484-b07720b5db02" (extra={'x_cb_node_id': None, 'x_cb_peer': 'tcp4:172.17.0.3:41034', 'x_cb_pid': 17}, session_id=5936774736058267)
    2019-03-01T12:06:10+0000 [Controller      1] Applying local node configuration (on_start_apply_config is enabled)
    2019-03-01T12:06:10+0000 [Controller      1] Booting node from local configuration .. <crossbar.node.node.Node.boot_from_config>
    2019-03-01T12:06:10+0000 [Controller      1] Will start 1 worker ..
    2019-03-01T12:06:10+0000 [Controller      1] Order node to start Router worker001
    2019-03-01T12:06:10+0000 [Controller      1] Starting router worker worker001 <crossbar.node.controller.NodeController.start_worker>
    2019-03-01T12:06:11+0000 [Router         18] Starting worker "worker001" for node "c82b34ee-fc5a-4de3-a484-b07720b5db02" on realm "crossbar" with personality "edge" <crossbarfx.edge.worker.router.ExtRouterController>
    2019-03-01T12:06:11+0000 [Router         18] Running as PID 18 on CPython-EPollReactor
    2019-03-01T12:06:11+0000 [Router         18] Entering event reactor ...
    2019-03-01T12:06:11+0000 [Router         18] Router worker session for "worker001" joined realm "crossbar" on node router <crossbar.worker.router.RouterController.onJoin>
    2019-03-01T12:06:11+0000 [Router         18] Registered 53 procedures
    2019-03-01T12:06:11+0000 [Router         18] Router worker session for "worker001" ready
    2019-03-01T12:06:11+0000 [Controller      1] Ok, node has started Router worker001
    2019-03-01T12:06:11+0000 [Controller      1] Configuring Router worker001 ..
    2019-03-01T12:06:11+0000 [Controller      1] Order Router worker001 to start Transport transport001
    2019-03-01T12:06:11+0000 [Router         18] Starting router transport "transport001" <crossbar.worker.router.RouterController.start_router_transport>
    2019-03-01T12:06:11+0000 [Router         18] Creating router transport for "transport001" <crossbar.worker.transport.create_router_transport>
    2019-03-01T12:06:11+0000 [Router         18] Router transport created for "transport001" <crossbar.worker.transport.RouterWebTransport>
    2019-03-01T12:06:11+0000 [Router         18] Created "pairme" Web service on root path "/" of Web transport "transport001"
    2019-03-01T12:06:11+0000 [Router         18] Site starting on 8080
    2019-03-01T12:06:11+0000 [Controller      1] Ok, Router worker001 has started Transport transport001
    2019-03-01T12:06:11+0000 [Controller      1] Order Transport transport001 to start Web Service webservice001
    2019-03-01T12:06:11+0000 [Router         18] Starting "websocket" Web service on path "ws" of transport "transport001" <crossbar.worker.router.RouterController.start_web_transport_service>
    2019-03-01T12:06:11+0000 [Controller      1] Ok, Transport transport001 has started Web Service webservice001
    2019-03-01T12:06:11+0000 [Controller      1] Ok, Router worker001 configured
    2019-03-01T12:06:11+0000 [Controller      1] Ok, local node configuration booted successfully!
    2019-03-01T12:06:15+0000 [Controller      1] Starting management heartbeat .. [interval=10.0]
