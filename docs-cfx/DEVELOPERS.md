# Crossbar.io Fabric Dev Docs

Some docs and hints for Crossbar.io Fabric developers.

## Master node controller components

The main controlling component on

* :class:`crossbarfx.master.node.node.FabricCenterNode`
* :class:`crossbarfx.master.node.node.FabricServiceNodeManager`
_initialize_mrealms

## Environment

```
export CROSSBAR_METERING_URL="https://metering.crossbario.com/submit"
export CROSSBAR_DISABLE_CE=1
```

## CE

```json
{
    "id": "change_engine",
    "type": "container",
    "options": {
        "disabled": "CROSSBAR_DISABLE_CE",
        "pythonpath": [".."],
        "expose_shared": true,
        "expose_controller": true
    },
    "components": [{
        "type": "class",
        "classname": "crossbarfx.master.change_engine.change_engine.ChangeEngine",
        "realm": "com.crossbario.fabric",
        "transport": {
            "type": "rawsocket",
            "serializer": "cbor",
            "endpoint": {
                "type": "unix",
                "path": "sock2"
            }
        }
    }]
}
```

```
2019-06-23T05:42:15+0200 [Controller  32657] Skip start of worker Container change_engine (disabled from config parameter)
```

```
export CROSSBAR_DISABLE_CE=1
```

```
2019-06-23T05:44:39+0200 [Controller    466] Skip start of worker Container change_engine (disabled from envvar CROSSBAR_DISABLE_CE)
```

## Databases

Default max sizes are:

* global database: 128M
* mrealm databases: 1G (per mrealm)


### Edge Nodes

Edge node configuration:

```json
{
    "version": 2,
    "controller": {
        "enable_docker": true,
        "fabric": {
            "transport": {
                "type": "websocket",
                "endpoint": {
                    "type": "tcp",
                    "host": "localhost",
                    "port": 9000
                },
                "url": "ws://localhost:9000/ws"
            },
            "heartbeat": {
                "startup_delay": 5,
                "heartbeat_period": 10,
                "include_system_stats": true,
                "send_workers_heartbeats": true,
                "aggregate_workers_heartbeats": true
            }
        }
    }
}
```

Configuration parameters:

* `startup_delay|int`: heartbeat sending initial delay in seconds (default: `5`)
* `heartbeat_period|int`: heartbeat sending period in seconds (default: `10`)
* `include_system_stats|bool`: include system statistics when sending node heartbeats (default: `true`)
* `send_workers_heartbeats|bool`: also send one heartbeat per worker with detailed information (default: `true`)
* `aggregate_workers_heartbeats|bool`: aggregate WAMP level statistics from router workers over realms run on those (default: `true`)

Code running in edge node:

1. `NodeManagementBridgeSession.attach_manager` - start sending heartbeats to master node after `startup_delay` seconds
2. `NodeManagementBridgeSession._send_heartbeat` - runs every `heartbeat_period` seconds:
    - calls `crossbar.get_status` and `crossbar.get_system_stats`
    - publishes heartbeat to `crossbarfabriccenter.node.on_heartbeat(node_id, worker_status)`
    - if `send_workers_heartbeats`, calls `crossbar.get_workers`,  `crossbar.get_process_monitor` and `crossbar.worker.{}.get_process_monitor` and ..
    - .. publishes heartbeat to `crossbarfabriccenter.node.on_worker_heartbeat(node_id, worker_id, worker_status)`

### Master Nodes

Write me.

### Metering Service

In the management realm databases of master node, heartbeats received from managed nodes
and managed workers (on those nodes) are persisted in:

* Database table `MNodeLog` (object `mschema.mnode_logs`): Heartbeat log record of managed nodes. Primary key: `(timestamp, node_id)`.
* Database table `MWorkerLog` (object `mschema.mworker_logs`): Heartbeat log record from managed node workers. Primary key: `(timestamp, node_id, worker_id)`.

In the global database of a master node, aggregate usage metering records are maintained:

* Database table `MasterNodeUsage` (object `gschema.usage`): Aggregate usage metering records for management realms. Primary key: `(timestamp, mrealm_id)`.

The records are aggregated as follows:

* `MNodeLog` (crossbarfx master): one record per **managed node** per **10 s** for tracking **node seconds** in management realms
* `MWorkerLog` (crossbarfx master): one record per **worker process** per **10 s** for tracking **worker seconds**, **session seconds** and **number of messages** in management realms
* `MasterNodeUsage` (crossbarfx master): one record per **master node** per **5 min** (30x time compression)
* `AwsMeterUsage` (part of the metering service): one record per **AWS customer** per **1 hour** (12x time compression, 360x total)

The DB write load on the master node from metering is:

- it inserts every received node/worker heartbeat record, which are sent from edge nodes every 10s
- it aggregates ^ and inserts one metering record per mrealm (found active) every 5min
- it updates ^ once the metering was submitted successfully

#### Logs

Here is a master node submitting 2 usage metering records (for 2 mrealms):

```
2019-06-26T14:01:04+0200 [Container    3251]   Metering: submitting metering record
{'containers': 0,
 'controllers': 300,
 'count': 60,
 'guests': 0,
 'hostmonitors': 0,
 'marketmakers': 0,
 'metering_id': None,
 'mrealm_id': '9210d186-10f2-4175-aa2c-aeb67824f345',
 'msgs_call': 290,
 'msgs_error': 0,
 'msgs_event': 580,
 'msgs_invocation': 290,
 'msgs_publish': 290,
 'msgs_published': 290,
 'msgs_register': 0,
 'msgs_registered': 0,
 'msgs_result': 290,
 'msgs_subscribe': 0,
 'msgs_subscribed': 0,
 'msgs_yield': 290,
 'nodes': 300,
 'processed': 1561550464446683293,
 'proxies': 0,
 'pubkey': b'\xf4\x05\nxy\x94\xfc\xcaqQ\x03\xa852x]y\xea\xff>B\xd1\x8f\xd3'
           b'\xf6g\xfa+\xb4\xafC\x9e',
 'routers': 300,
 'sent': None,
 'seq': 110,
 'sessions': 900,
 'status': 1,
 'status_message': None,
 'timestamp': 1561550460000000000,
 'timestamp_from': 1561550160000000000,
 'total': 0}
2019-06-26T14:01:04+0200 [Container    3251]   Metering: metering record for "2019-06-26T12:01:00.000000000" processed with new status 2 [metering_id="8e8d5cac-8390-4488-a3b0-981e764674c1"].
2019-06-26T14:01:04+0200 [Container    3251]   Metering: submitting metering record
{'containers': 0,
 'controllers': 900,
 'count': 210,
 'guests': 0,
 'hostmonitors': 300,
 'marketmakers': 0,
 'metering_id': None,
 'mrealm_id': 'a75c1f1b-350d-41ab-9a9a-4841eda1e8fc',
 'msgs_call': 576,
 'msgs_error': 0,
 'msgs_event': 1152,
 'msgs_invocation': 576,
 'msgs_publish': 576,
 'msgs_published': 576,
 'msgs_register': 0,
 'msgs_registered': 0,
 'msgs_result': 576,
 'msgs_subscribe': 0,
 'msgs_subscribed': 0,
 'msgs_yield': 576,
 'nodes': 900,
 'processed': 1561550464490027781,
 'proxies': 0,
 'pubkey': b'\xf4\x05\nxy\x94\xfc\xcaqQ\x03\xa852x]y\xea\xff>B\xd1\x8f\xd3'
           b'\xf6g\xfa+\xb4\xafC\x9e',
 'routers': 900,
 'sent': None,
 'seq': 110,
 'sessions': 2100,
 'status': 1,
 'status_message': None,
 'timestamp': 1561550460000000000,
 'timestamp_from': 1561550160000000000,
 'total': 0}
2019-06-26T14:01:04+0200 [Container    3251]   Metering: metering record for "2019-06-26T12:01:00.000000000" processed with new status 2 [metering_id="21446294-31cc-4594-afc3-1cb12d08a408"].
```

And here is the regular base where a master node heartbeat loop iteration does not trigger an aggregation:

```
2019-06-26T14:06:14+0200 [Container    3251] Master heartbeat loop iteration 141 started .. (global database: 69.6 kB used, 99.95% free)
2019-06-26T14:06:14+0200 [Container    3251]   Metering: aggregating heartbeat records .. [started="2019-06-26T12:06:14.397871784", thread_id=140102424450560]
2019-06-26T14:06:14+0200 [Container    3251]   Metering: last metering timestamp stored is "2019-06-26T12:06:00.000000000"
2019-06-26T14:06:14+0200 [Container    3251]   Metering: no new intervals to aggregate.
2019-06-26T14:06:14+0200 [Container    3251]   Metering: finished aggregating [0 intervals]
2019-06-26T14:06:14+0200 [Container    3251] Master heartbeat loop iteration 141 finished: in 4 ms
```

#### Examples

To access heartbeat logs in the database of a management realm:

```python
import zlmdb

from crossbarfx.master.database.mrealmschema import MrealmSchema

DBFILE_MREALM = '.crossbar/.db-mrealm-4f266d60-f79c-4ef1-8e5f-f3acdd5660a3'

mdb = zlmdb.Database(DBFILE_MREALM, maxsize=2**30, readonly=False)

mschema = MrealmSchema.attach(mdb)

with mdb.begin() as txn:
    cnt = mschema.mnode_logs.count(txn)
    print('{} mnodelog records'.format(cnt))

    cnt = mschema.mworker_logs.count(txn)
    print('{} mworkerlog records'.format(cnt))
```

To access usage data in the global database:

```python
from crossbarfx.master.database.globalschema import GlobalSchema

DBFILE_GLOBAL = '.crossbar/.db-controller'

gdb = zlmdb.Database(DBFILE_GLOBAL, maxsize=2**30, readonly=False)

gschema = GlobalSchema.attach(gdb)

with gdb.begin() as txn:
    cnt = gschema.usage.count(txn)
    print('{} usage records'.format(cnt))
```

## Database tables

* [ ] `crossbario/crossbarfx/cfxdb/cfxdb/common.fbs`: common types
* [ ] `crossbario/crossbarfx/cfxdb/cfxdb/log.fbs`: CrossbarFX master: log tables
* [ ] `crossbario/crossbarfx/cfxdb/cfxdb/eventstore.fbs`: WAMP sessions, publications and events tables
* [ ] `crossbario/crossbarfx/cfxdb/cfxdb/xbr.fbs`: XBR market maker tables
* [ ] `crossbario/crossbarfx/crossbarfx/shell/idl/reflection.fbs`: FIXME - duplicate (use cfxdb)
* [ ] `crossbario/crossbarfx/crossbarfx/master/database/common.fbs`: FIXME - refactor into cfxdb.common
* [ ] `crossbario/crossbarfx/crossbarfx/master/database/user.fbs`: CrossbarFX master: global authentication
* [ ] `crossbario/crossbarfx/crossbarfx/master/database/mrealm.fbs`: CrossbarFX master: management realms
* [ ] `crossbario/crossbarfx/crossbarfx/master/database/meta.fbs`: FIXME - refactor/expand/use
* [ ] `crossbario/crossbarfx/crossbarfx/master/database/application.fbs`: FIXME - empty, remove for now
* [ ] `crossbario/crossbarfx/crossbarfx/master/database/xbr.fbs`: FIXME - refactor into cfxdb.xbr
* [ ] `crossbario/crossbarfx/crossbarfx/master/database/reflection.fbs`: FIXME - move to cfxdb.reflection

## Class hierarchy

The Crossbar.io (and CrossbarFX) node controller spawns new managed worker processes from [here](https://github.com/crossbario/crossbar/blob/a735923a877804bae3062cf74deb49282486dc4b/crossbar/node/controller.py#L693) running down this line of code (or along this class hierarchy):

```
crossbar.common.twisted.processutil.WorkerProcessEndpoint.connect()
|
.. OS spawns process ..
    |
    crossbar.worker.main
    |   -> _run_command_exec_worker()
    |
    +-- autobahn.twisted.wamp.ApplicationSession
        |   -> onJoin()
        |
        +-- crossbar.common.process.NativeProcess
            |   -> e.g. get_process_stats()
            |
            +-- crossbar.worker.controller.WorkerController
                |   -> e.g. start_profiler()
                |
                +-- crossbar.worker.router.RouterController
                    |   -> e.g. start_router_realm()
                    |     -> crossbar.router.router.RouterFactory.start_realm()
                    |       -> new crossbar.router.router.Router instance
                    |
                    +-- crossbarfx.edge.worker.router.ExtRouterController
                            -> e.g. start_router_realm_link()


autobahn.util.ObservableMixin
|
+-- autobahn.wamp.protocol.BaseSession
    |
    +-- autobahn.wamp.protocol.ApplicationSession
        |
        +-- autobahn.twisted.wamp.ApplicationSession
```

the new clustering capabilities (still pubsub only at the moment) are anchored in `ExtRouterController.start_router_realm_link()` which is a management API entry point of edge nodes and makes the respective router establish a router-to-router link to another router.

the router-to-router links _can_ be configured manually via `config.json` (for example, see [here](https://github.com/crossbario/crossbarfx/blob/master/test/benchmark/router_cluster/ha_setup/edge1/.crossbar/config.json) )

however, the way this is designed to be used it programmatically, from CFC backend code. as in, from a abstract "router cluster" definition in the master database, CFC will programmatically call into CF nodes (above `start_router_realm_link` et al) to wire up and maintain a cluster at run-time based on this definition

## Building

### Building a venv

> Note: the following builds CPython from source, and with CPython as a shared library enabled, which is needed for the EXE (pyinstaller). Last verified: 2020/12/21 on Ubuntu 18.04.5 LTS (Bionic).

Here is a complete recipe that worked for me on an AWS Graviton (a1.xlarge) / ARM64 instance:

Install build dependencies:

```
sudo apt update
sudo apt -y dist-upgrade
sudo apt-get -y install build-essential libssl-dev libffi-dev libunwind-dev \
   libreadline-dev zlib1g-dev libbz2-dev libsqlite3-dev libncurses5-dev libsnappy-dev
```

Build Python from source:

```
cd ~
wget https://www.python.org/ftp/python/3.9.2/Python-3.9.2.tar.xz
tar xvf Python-3.9.2.tar.xz
cd Python-3.9.2
./configure --prefix=$HOME/cpy392 --enable-shared
make -j4
make install
```

Run the following:

```
sudo sh -c 'echo /home/oberstet/cpy392/lib >> /etc/ld.so.conf.d/cpy392.conf'
sudo ldconfig
```

> Alternatively to the last, add this to `${HOME}/.bashrc`: `export LD_LIBRARY_PATH=${HOME}/cpy392/lib:${LD_LIBRARY_PATH}`

Update pip, and install wheel:

```
${HOME}/cpy392/bin/pip3 install -U "pip<20" wheel twine
${HOME}/cpy392/bin/pip3 --version
```

Create a virtual env:

```
${HOME}/cpy392/bin/python3 -m venv ~/cpy392_1
```

Add the following to `${HOME}/.bashrc`:

```
alias cpy392_1='source ${HOME}/cpy392_1/bin/activate'
```

Add the following to `${HOME}/.profile`:

```
export PATH=${HOME}/cpy392/bin:${PATH}
```

### Installing from Wheels

Run [this script](https://github.com/crossbario/crossbarfx/blob/master/docs/_static/crossbarfx-install-from-wheels.sh) to install Crossbar.io from wheels (x86-64):

```
cd ~
rm -f ./crossbarfx-install-from-wheels.sh
wget https://s3.eu-central-1.amazonaws.com/crossbario.com/docs/crossbarfx/_static/crossbarfx-install-from-wheels.sh
chmod +x crossbarfx-install-from-wheels.sh
./crossbarfx-install-from-wheels.sh
```

### Building from Sources

Now:

```
cd ~
mkdir -p scm/crossbario
cd scm/crossbario
git clone git@github.com:crossbario/txaio.git
git clone git@github.com:crossbario/txaio-etcd.git
git clone git@github.com:crossbario/zlmdb.git
git clone git@github.com:crossbario/autobahn-python.git
git clone git@github.com:crossbario/crossbar.git
git clone git@github.com:crossbario/crossbarfx.git

cd ~
mkdir scm/xbr
cd scm/xbr
git clone git@github.com:xbr/xbr-protocol.git

~/cpy392/bin/python3 -m venv ~/cpy392_1
source ~/cpy392_1/bin/activate

pip install twine wheel

cd ~
cd scm/crossbario/crossbarfx
make build_wheels
make install_wheels
```

### Building the EXE

Here is how to build the EXE on Linux from sources. This was tested on Ubuntu 18.

Install build tools and libraries:

```
sudo apt-get -y install build-essential libssl-dev libffi-dev libunwind-dev \
   libreadline-dev zlib1g-dev libbz2-dev libsqlite3-dev libncurses5-dev libsnappy-dev
```

Build Python:

```
cd ~
wget https://www.python.org/ftp/python/3.7.0/Python-3.7.0.tar.xz
tar xvf Python-3.7.0.tar.xz
cd Python-3.7.0
./configure --prefix=${HOME}/cpy370 --enable-shared
make -j4
make install
cd ..
```

and add this to your `$HOME/.profile`:

```
export PATH=${HOME}/cpy370/bin:${PATH}
export LD_LIBRARY_PATH=${HOME}/cpy370/lib:${LD_LIBRARY_PATH}
```

Build crossbarfx executable in a new Python virtualenv:

```
~/cpy370/bin/python3 -m venv ~/cpy370_1
source ~/cpy370_1/bin/activate
pip install -U pip
```

Install development requirements:

```
cd scm/crossbario/crossbarfx
pip install -r requirements-dev.txt
```

Build the single-file executable

```
tox -e buildexe
```

This should give you:

```
(cpy370_1) oberstet@thinkpad-t430s:~/scm/crossbario/crossbarfx$ ll dist/
insgesamt 22392
drwxrwxr-x  2 oberstet oberstet     4096 Sep 10 12:52 ./
drwxrwxr-x 14 oberstet oberstet     4096 Sep 10 12:51 ../
-rwxr-xr-x  1 oberstet oberstet 22919184 Sep 10 12:52 crossbarfx*
(cpy370_1) oberstet@thinkpad-t430s:~/scm/crossbario/crossbarfx$ ldd dist/crossbarfx
	linux-vdso.so.1 =>  (0x00007ffe1d5f1000)
	libdl.so.2 => /lib/x86_64-linux-gnu/libdl.so.2 (0x00007f29c0990000)
	libz.so.1 => /lib/x86_64-linux-gnu/libz.so.1 (0x00007f29c0776000)
	libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f29c03ac000)
	/lib64/ld-linux-x86-64.so.2 (0x00007f29c0b94000)
(cpy370_1) oberstet@thinkpad-t430s:~/scm/crossbario/crossbarfx$ file dist/crossbarfx
dist/crossbarfx: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 2.6.32, BuildID[sha1]=28ba79c778f7402713aec6af319ee0fbaf3a8014, stripped
(cpy370_1) oberstet@thinkpad-t430s:~/scm/crossbario/crossbarfx$ ./dist/crossbarfx version
invalid command
(cpy370_1) oberstet@thinkpad-t430s:~/scm/crossbario/crossbarfx$ ./dist/crossbarfx

Usage: crossbarfx <command>

    <command> :

    quickstart       Create a WAMP/XBR application skeleton using Docker
    quickstart-venv  Create a WAMP/XBR application skeleton using "virtual environments"
    shell            Run an interactive management shell
    edge             Run a CrossbarFX edge node
    master           Run a CrossbarFX master node

(cpy370_1) oberstet@thinkpad-t430s:~/scm/crossbario/crossbarfx$ ./dist/crossbarfx edge version

    :::::::::::::::::
          :::::          _____                 __              _____  __
    :::::   :   :::::   / ___/______  ___ ___ / /  ___ _____  / __/ |/_/
    :::::::   :::::::  / /__/ __/ _ \(_-<(_-</ _ \/ _ `/ __/ / _/_>  <
    :::::   :   :::::  \___/_/  \___/___/___/_.__/\_,_/_/   /_/ /_/|_|
          :::::
    :::::::::::::::::   Crossbar Fabric XBR v18.9.1 [00000]

    Copyright (c) 2013-2018 Crossbar.io Technologies GmbH. All rights reserved.

 Crossbar.io        : 18.9.2
   Autobahn         : 18.9.2
   Twisted          : 18.7.0-EPollReactor
   LMDB             : 0.94/lmdb-0.9.22
   Python           : 3.7.0/CPython
 Crossbar.io     : 18.9.1
 Frozen executable  : yes
 Operating system   : Linux-4.4.0-134-generic-x86_64-with-debian-stretch-sid
 Host machine       : x86_64
 Release key        : RWSDSZzMhv9utm/rhC+IL0t74bE6vQpI/gZuztT6MciW0/mzmijWMt9f

(cpy370_1) oberstet@thinkpad-t430s:~/scm/crossbario/crossbarfx$
```

## Codebase

### Overview

The three main work areas in Crossbar.io in the code base can the summarized as follows:

* **Router**: core WAMP routing code, uses mainly `autobahn` and `twisted.internet`
    * [crossbar/router](https://github.com/crossbario/crossbar/tree/master/crossbar/router)
        * [crossbar/router/auth](https://github.com/crossbario/crossbar/tree/master/crossbar/router/auth)
    * [crossbar/bridge](https://github.com/crossbario/crossbar/tree/master/crossbar/bridge)
        * [crossbar/bridge/mqtt](https://github.com/crossbario/crossbar/tree/master/crossbar/bridge/mqtt)
* **Web**: all Web service related features, uses mainly `twisted.web` and `txrequests`
    * [crossbar/bridge](https://github.com/crossbario/crossbar/tree/master/crossbar/bridge)
        * [crossbar/bridge/rest](https://github.com/crossbario/crossbar/tree/master/crossbar/bridge/rest)
    * [crossbar/webservice](https://github.com/crossbario/crossbar/tree/master/crossbar/webservice)
        * [crossbar/webservice/templates](https://github.com/crossbario/crossbar/tree/master/crossbar/webservice/templates)
* **Core**: core node, uses mainly `twisted.internet` and `autobahn`
    * [crossbar/common](https://github.com/crossbario/crossbar/tree/master/crossbar/common)
        * [crossbar/common/keys](https://github.com/crossbario/crossbar/tree/master/crossbar/common/keys)
        * [crossbar/common/twisted](https://github.com/crossbario/crossbar/tree/master/crossbar/common/twisted)
    * [crossbar/node](https://github.com/crossbario/crossbar/tree/master/crossbar/node)
        * [crossbar/node/templates](https://github.com/crossbario/crossbar/tree/master/crossbar/node/templates)
    * [crossbar/worker](https://github.com/crossbario/crossbar/tree/master/crossbar/worker)
        * [crossbar/worker/sample](https://github.com/crossbario/crossbar/tree/master/crossbar/worker/sample)

**This directory structure is mirrored in the [Crossbar.io Fabric](https://github.com/crossbario/crossbar-fabric/tree/master/crossbarfabric)
and [Crossbar.io Fabric Center](https://github.com/crossbario/crossbar-fabric-center/tree/master/crossbarfabriccenter) code repositories.
Doing so allow quick navigation and location of code is canonical in most cases.**

---

### Node Booting

**The following describes how a Crossbar.io node boots, and where Crossbar.io Fabric extends the former in this area.**

---

The `crossbar` Python package defines the CLI entrypoint in [crossbar/setup.py](https://github.com/crossbario/crossbar/blob/master/setup.py):

```python
entry_points={
    # CLI entry function
    'console_scripts': [
        'crossbar = crossbar:run'
    ]
}
```

**crossbar:run** resolves to [crossbar/__init__.py](https://github.com/crossbario/crossbar/blob/master/crossbar/__init__.py).

This file contains the complete public (user level) Python API of Crossbar.io:

* `crossbar.version()`
* `crossbar.run(args, reactor)`
* `crossbar.personalities()`

**crossbar.run** installs the Twisted reactor selected or automatically chosen, and then calls
`crossbar.node.cli.main('crossbar', args, reactor)`.

[crossbar/node/cli.py](https://github.com/crossbario/crossbar/blob/master/crossbar/node/cli.py)
checks the arguments list given, and runs the respective command.

E.g. for `crossbar start` the function run is **_run_command_start(options, reactor)**.

This will do a couple of checks, and then *instantiate* a new Crossbar.io node

```python
personality = crossbar.personalities()[options.personality]

node_options = personality.NodeOptions(debug_lifecycle=options.debug_lifecycle,
                                       debug_programflow=options.debug_programflow)

node = personality.Node(personality,
                        options.cbdir,
                        reactor=reactor,
                        options=node_options)
```

At this point, first the

1. node key is checked and loaded (or possibly a new one automatically generated), then
2. the node configuration is checked and loaded, and then
3. the node is started

This is using the following main `Node` methods:

* `Node.load_keys`: loads (and auto-generates new) node key
* `Node.load_config`: loads the local node configuration filke
* `Node.start`: starts the node (set node ID, start local node management router, ..)
* `Node.stop`: stops the node
* `Node.boot`: called during start of a node, and overidden in CF and CFC
* `Node.boot_from_config`: start workers as defined in local config

When `Node.start()` runs, it will create the **local node management router**:

```python
# local node management router
self._router_factory = None

# session factory for node management router
self._router_session_factory = None

# the node controller realm
self._realm = u'crossbar'
```

The local node management router allows the Crossbar.io node controller process communicate with
worker processes over WAMP, using pipes as a transport.

This router is always running, but does not open any network or UDS listening endpoints. Further, all sessions use
the following transports:

* function-call transport (for built-in node controller and service sessions - see below)
* stdio transport (over pipes) for communicating with workers

> Note: one feature that CF will add above CB is starting actual listening endpoints on the node
management router, such as on a UDS. This will allow applications to control themself (locally).
So it provides dynamic managability, but not remote management (as CFC does), but can provide the
former with no uplink connectivity at all.

The node management router however uses the standard classes of CB:

* `crossbar.router.router.RouterFactory`
* `crossbar.router.session.RouterSessionFactory`
* `crossbar.worker.types.RouterRealm`

The primary feature that makes the node controller router "different" from a plain vanilla
CB router is that it comes with two special sessions attached

* **crossbar.node.controller.NodeController**
* **crossbar.router.service.RouterServiceAgent**

These two are describe in the next sections.

To conclude the boot process, after everything is wired up as above, the Twisted reactor is
finally started `reactor.run()` in **run_command_start**.

---

### Node Controller

> "node controller" can refer to two things: the node controller _process_ (which always runs)
and the node controller _session_, which lives on the local node management router, and which
provides the main entry point into managing the node. In this section, the latter is the topic.

The node controller session **crossbar.node.controller.NodeController** lives on the local
node management router as a regular WAMP session, but embedded/side-by-side with the router.

That is, it uses an internal function-call based transport with essentially zero overhead
(well, other than one or two function calls).

The `NodeController` (session) registers a couple of node top-level WAMP procedures:

* **crossbar.get_status**
* **crossbar.shutdown**
* **crossbar.get_workers**
* **crossbar.get_worker**
* **crossbar.start_worker**: start a new worker: router, container or guest
* **crossbar.stop_worker**
* **crossbar.get_worker_log**

> It is important to note that both the local management realm and the URI prefix for node
top-level things (procedures/topics) is "crossbar".

These WAMP procedures are then called by the `Node.boot_from_config()` function which runs through
the local node configuration issueing calls into above, and analog procedures for worker management.

The most important node top-level function is **crossbar.start_worker**, which starts a new
Crossbar.io worker process: a router worker, a container worker or guest worker for Crossbar.io OSS,
and new worker types in CF/CFC (eg proxy workers).

`NodeController.start_worker` uses two private methods:

* `_start_guest_worker`
* `_start_native_worker`

to do all the actual work. The latter is what is of most interest.

`_start_native_worker` will start a new worker process by:

* `python -u -m crossbar.worker.main ...` (by default)
* or using `crossbar exec_worker ...` when running a frozen/one-file executable

It will also setup WAMP communication so that the spawned worker can join the node management
router as a WAMP session (on realm "crossbar") and register WAMP procedures that in turn allow the
spawned worker to be controlled, possibly from any other session on the node management router.

Notable lines from the code:

```python
transport_factory = create_native_worker_client_factory(self._node._router_session_factory, ...)

childFDs = {0: "w", 1: "r", 2: "r", 3: "r"}

transport_endpoint = WorkerProcessEndpoint(reactor, exe, args, env, childFDs)

d = transport_endpoint.connect(transport_factory)
```

This communication over pipes using Twisted machinery is provided via:

* **create_native_worker_client_factory**
* **WorkerProcessEndpoint**

Also note the control session being added to the node management router (`self._node._router_session_factory` in above).

That means, in addition to the two always attached `NodeController` and `RouterServiceAgent`, the node management router
will have one WAMP session joined _per worker_.

> CF/CFC adds more sessions, eg the uplink connection to CFC is another session on the node management router (as well
as on the uplink CFC router - that is, it is a dual-homed bridge).

---

### Worker Controllers

Similar to like the node has a node controller, a (native) worker has a worker controller which allows to
control the worker from outside (that is, other session joined on the node management router).

* **crossbar.worker.controller.WorkerController**: controller base class for all native worker types
* **crossbar.worker.router.RouterController**: controller for router workers
* **crossbar.worker.container.ContainerController**: controller for container workers

Lets have a look at the [RouterController](https://github.com/crossbario/crossbar/blob/master/crossbar/worker/router.py).

* **get_router_realms**
* **get_router_realm**
* **start_router_realm**: start a new realm, eg "realm1" on the router
* **stop_router_realm**
* **get_router_realm_roles**
* **start_router_realm_role**: start a new role on a realm, eg "anonymous" or "user"
* **stop_router_realm_role**
* **get_router_transports**
* **start_router_transport**: start a new router (listening) transport, eg WebSocket, Web, RawSocket or Universal
* **stop_router_transport**
* **start_web_transport_service**: for Web transports, starts a new Web service on a path, eg "static" or "nodeinfo"
* **stop_web_transport_service**
* **get_router_components**
* **start_router_component**: start a new Python component embedded in the router (this is discouraged in general)
* **stop_router_component**

We will quickly discuss the most important of above methods, those needed to start a node from a local node
configuration.

**RouterController.start_router_realm** does two primary things:

1. creates a new router for the realm `self._router_factory.start_realm(rlm)`
2. populates the new (empty) realm with a new router service agent session `rlm.session = RouterServiceAgent(cfg, router)`

> Note: 2. in above can be an extension point where CF/CFC adds functionality: pre-populate more special sessions.

**RouterController.start_router_realm_role** adds a new WAMP authentiation roles with its permissions to the router.

> Note: currently it is not possible to operate at the permissions level, only role level. We should have the permission
level granularity supported though.

**RouterController.start_router_transport** will create a new router (listening) transport via the `Personality` class
and start the transport:

```python
# create a transport and parse the transport configuration
router_transport = self.personality.create_router_transport(self, transport_id, config)

# start listening ..
d = router_transport.start(create_paths)
```

**personality.create_router_transport** resolves to one of these:

* **crossbar**.worker.transport.create_router_transport
* **crossbarfabric**.worker.transport.create_router_transport
* **crossbarfabriccenter**.worker.transport.create_router_transport

which will create a Web transport **crossbar.worker.transport.RouterWebTransport**, which will use a slightly
modified Twisted Web `Site` instance (`crossbar.common.twisted.web.Site`) as Twisted transport factory.

On this `Site` instance, individual Web services can be added and removed. The types of Web services available
depends on the node personality and is available as a map **Personality.WEB_SERVICE_FACTORIES**.

All Web services must derive from **crossbar.webservice.base.RouterWebService**, for example serving static files
from a directory is provided by **crossbar.webservice.static.RouterWebServiceStatic**.

---

### Crossbar.io Pluggability Overview

Crossbar.io Fabric XBR extends Crossbar.io OSS in features. To realize that from a common code base that builds
on the OSS code base, we need appropriate extension points within CB to add new:

* Web Transport Services (e.g. for XBR API Hubs)
* Worker Types (e.g. for WAMP proxy/frontend workers)
* Router Transports (e.g. for multiplexed/vectored WAMP transports proxy->router worker traffic)
* ...

Core to the pluggability design are the classes:

* [crossbar.Personality](https://github.com/crossbario/crossbar/blob/master/crossbar/personality.py)
* [crossbarfabric.Personality](https://github.com/crossbario/crossbar-fabric/blob/master/crossbarfabric/personality.py)
* [crossbarfabriccenter.Personality](https://github.com/crossbario/crossbar-fabric-center/blob/master/crossbarfabriccenter/personality.py)

These act like central switchboards to *indirectly* access all pluggable functionality.

That is, all code implementing features must reference and call functions supposed to be pluggable via those `Personality` classes.

This allows the following: code in CF can add a new feature, and that is referenced and used by code in CB (OSS) - even
though the latter code doesn't (statically) know the former even exists. IOW: new code in CF can plug into code in CB.

The `Personality` classes also provide a perfect overview and entry point into the code base, and to split up work
between developers using clearly defined and narrow (internal) interfaces.

---

### Crossbar.io Extension Points

The following lists the steps required to implement a new CF/CFC feature that adds extends CB as one of the
planned CB extension points.

#### Adding new Web Service Types

New Web service types can be added to CF/CFC like this:

1. Create a new configuration checker function in the existing file `crossbarfabric.common.checkconfig.py`
2. Add the function to the map `crossbarfabric.personality.Personality.WEB_SERVICE_CHECKERS`
3. Create a new file `crossbarfabric/webservice/example.py` with a new class `RouterWebServiceExample` deriving
from `crossbar.webservice.base.RouterWebService`
4. Add the class to the map `crossbarfabric.personality.Personality.WEB_SERVICE_FACTORIES`

#### Adding new Worker Types

Write me.

#### Adding new Router Transport Types

Write me.

#### Adding new Router Cookie and Session Store Types

Write me.

#### Adding new Router Authentication Methods

Write me.

#### Adding new Node Management Router Service Sessions

Write me.

#### Overriding existing Node Management Router Service Sessions

Write me.

#### Adding new Application Router Service Sessions

Write me.

#### Overriding existing Application Router Service Sessions

Write me.

---

### Management Events

Management events are published by Crossbar.io native workers via router/container controller sessions and by the node itself via the node controller session. These sessions are all connected to the node management router (inside the node controller process) and joined to the `crossbar` realm there. The transports used to connect the sessions is function-call based for the node controller session, and runs over stdio pipes for native workers.

Besides above controller sessions, the management bridge uplink session is also joined on the node management realm (`crossbar`) *subscribing to all management events* and republishing those events on the CFC uplink router, under a translated URI.

Lets look at an example and follow the code, and the translation of the event URI when forwarding to the uplink CFC.

A new realm can be started in a running router worker from CFC with the call ultimately being handled by

* [crossbar.worker.router.RouterController.start_router_realm](https://github.com/crossbario/crossbar/blob/master/crossbar/worker/router.py#L200)

This code will start the realm, and before returing to the caller, it will publish a management event with information on the newly started realm:

```python
self.publish(u'{}.on_realm_started'.format(self._uri_prefix), ...)
```

The URI prefix used in above comes from the `WorkerController` base class:

```python
self._uri_prefix = u'crossbar.worker.{}'.format(self._worker_id)
```

That means, the event will be published to the URI

* `crossbar.worker.<worker_id>.on_realm_started`

This event will be received in the bridge session, the event topic URI will be translated to

* `crossbarfabriccenter.node.<node_id>.worker.<worker_id>.on_realm_started`

and the event will be [published](https://github.com/crossbario/crossbarfx/blob/master/crossbarfx/edge/node/management.py#L300) (with that new topic) on the uplink CFC router, on the management realm the node is connected to.

The event forwarded by the management bridge session in the node is then received in the backend for the management realm **crossbarfx.master.mrealm.management.ManagementRealmBackend**.

Within this backend, a representation of the current configuration and state of all run-time elements of a node such as workers or router realms etc is held.

This representation of the (last known) configuration or state is kept current by updating from receiving management events from the nodes. The state is initially filled when the backend starts by actively querying all nodes.

This representation of the current configuration/state of nodes and their elements within the management backend is in-memory and transient, and the source for CFC frontends (UI, console, API). That is, node management events are (normally) only received in the backend, and the backend then in turn might publish consolidated or filtered events to be received by CFC frontends.

---

### RLinks

RLinks ("router-to-router links").

#### Message and code flow

Relevant Autobahn types/classes:

* [autobahn.wamp.types](https://github.com/crossbario/autobahn-python/blob/master/autobahn/wamp/types.py)
* [autobahn.wamp.message](https://github.com/crossbario/autobahn-python/blob/master/autobahn/wamp/message.py)
* [autobahn.wamp.protocol](https://github.com/crossbario/autobahn-python/blob/master/autobahn/wamp/protocol.py)
* [autobahn.wamp.exception](https://github.com/crossbario/autobahn-python/blob/master/autobahn/wamp/exception.py)


`forward_for`:

* `autobahn.wamp.types.EventDetails`
* `autobahn.wamp.types.CallResult`
* `autobahn.wamp.message.Yield`


Relevant Crossbar.io types/classes:

* [crossbar.worker.rlink](https://github.com/crossbario/crossbar/blob/master/crossbar/worker/rlink.py)
* [crossbar.router.dealer](https://github.com/crossbario/crossbar/blob/master/crossbar/router/dealer.py)
* [crossbar.router.broker](https://github.com/crossbario/crossbar/blob/master/crossbar/router/broker.py)



