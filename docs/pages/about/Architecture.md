[Documentation](.) > Architecture

# Architecture

> Note: This page describes the **planned architecture** of Crossbar.io. **Some parts** of this are **still being implemented**. Specifically: There is currently **no multi-node support**, and the API (and code) for the **management service** are only **partially** realized.  


## Introduction

Crossbar.io has a **multi-node** and **multi-process** architecture.

A Crossbar.io **node** is a single instance of the Crossbar.io software running on a single machine. This Crossbar.io node can form a cluster or federated network by connecting to other Crossbar.io nodes on the same, or, more often on other machines.

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_00.png)

Externally, the cluster will behave like a single instance.

>While application components connect to specific nodes or are directly hosted by specific nodes, this is transparent from an application point of view: application components are agnostic to how and where they are deployed.

## Nodes

A Crossbar.io node runs from a **node directory**, usually named `.crossbar`. This node directory contains the data the for the node, such as its local configuration, log files and server TLS keys/certificates. This means you can only run a single node per **node directory**:

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_00b.png)

## Processes

Crossbar.io has a **multi-process architecture**. A single, default node *controller process* spawns and monitors multiple *worker processes*. The multi-process architecture enables scaling up on multi-core systems and supports secure and robust operation.

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_00c.png)

There are two types of processes running within a Crossbar.io node:

 1. *Controller*
 2. *Workers*

The *Controller* manages, controls and monitors the Crossbar.io node.

>At any point, there is exactly one node *Controller* process running for a given node. The *Controller* is started when the node starts, and stops when the node stops. When a *Controller* exits, any *Worker* (see below) that had not been shut down earlier will also exit.

*Workers* are processes dynamically spawned by Crossbar.io to isolate functionality and scale up performance on multi-core systems. *Workers* come in the following flavors:

 * *Native Workers*
     * *Routers*
     * *Containers*
 * *Guest Workers*

*Native Workers* are WAMP *Routers* and WAMP *Containers*.

* *Routers* provide WAMP call and event routing services for applications and provide the core of Crossbar.io functionality.
* *Containers* can host application components written in Python (using [**Autobahn**](Python](https://github.com/tavendo/AutobahnPython) on [Twisted](http://twistedmatrix.com/)), i.e. what Crossbar.io is implemented on).

*Guest Workers* are arbitrary programs spawned and monitored by Crossbar.io, usually to run user defined application components written in languages other than Python (or running on asyncio, not Twisted). E.g. a *Guest* might be a program written in C++ using [**Autobahn**|Cpp](https://github.com/tavendo/AutobahnCpp) or JavaScript using [**Autobahn**|JS](https://github.com/tavendo/AutobahnJS), connecting back to a WAMP router running inside a *Native Worker*.


## Controller

A Crossbar.io node runs from a *node directory*, which contains (among other things) a node key, a local configuration file and log files.

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_01.png)

A node always runs a (single) node controller process. The node controller dynamically starts, monitors and stops worker processes. Node worker processes include *Routers*, *Containers* and *Guests*. These are described below.

A node may optionally connect to an uplink management service for remote management and monitoring. This is possible since Crossbar.io exposes all its services via WAMP. This API is private, however, and not stable. We are working on providing a management service which utilizes this.


## Routers

A Crossbar.io  node can run multiple types of workers, one of them being *Routers*. *Routers* provide Crossbar.io  WAMP routing services between WAMP clients.

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_02.png)

A *Router* can have multiple *Transports* configured such as WAMP over WebSocket/JSON over TCP, WAMP over RawSocket/MsgPack over Unix Domain sockets or WAMP over HTTP-Long-Poll.

Clients can connect to the same *Router* over different *Transports* and are still able to (transparently) talk to each other.

Clients can be any application component which speaks WAMP. These can run outside of the node, be it on the same machine or connected via network. A Router can also connect native Python application components that run inside the same worker process (Container) as the router ("side-by-side" connection), as well as application components that run outside the router's Container process - see below ("component hosts").


## Containers and Guests

Crossbar.io can work as a component host or component container for WAMP application components - regardless in which language they are written or under which run-time they run. You can host mixed language or run-time application component sets.

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_03.png)

Native Python application components are hosted in special worker processes called *Containers*.

Application components running under non-Python run-times are run and monitored in special worker processes called *Guests*.

In both cases the application components hosted will usally connect back to a locally running *Router* via fast IPC mechanisms (Unix domain sockets or loopback TCP).

## Scale-up on Multi-core

***Planned Feature***

Crossbar.io allows multiple router processes to form a single virtual router. This allows routing to be scaled-up for performance to multiple cores on a SMP machine.

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_04.png)

On Linux, this feature makes use of [TCP socket sharing](http://lwn.net/Articles/542629/) possible with newer Linux kernels. It works like this: multiple *Router* worker processes will all listen on the same TCP port. When a new client connection is coming in, the Linux kernel will determine the least loaded process that has the respective TCP port listened on. The kernel will then steer the incoming TCP connection *directly* to the determined process. This in-kernel load-balanacing ensures that there is no single bottleneck - not even for accepting TCP connections. The *Router* process that serves the newly connected client will also have *Links* to other *Routers* established. Those *Links* will carry the *Router-to-Router* traffic for routing calls and events across multiple *Routers*.

## Scale-out on Multi-node

***Planned Feature***

Crossbar.io allows router processes to *link* to other routers, including routers running on different hosts.

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_08.png)

This allows routing to be scaled-out for performance, scalability and fault-tolerance to multiple nodes in a cluster or federated system.

![Crossbar.io Node](/static/img/docs/gen/crossbar_deployment_05.png)

This feature leverages the same *Router-to-Router* communication as with multiple *Router* processes running on a single host. The only difference is: with local *Router-to-Router* traffic, the bytes will usually be shuffled over fast, local IPC mechanisms like Unix domain sockets, while for remote *Router-to-Router* traffic, the bytes will be carried over regular TCP connections.
