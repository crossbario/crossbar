# Crossbar.io

Open-source multi-protocol application router:

 * RPC and PubSub for distributed applications
 * Direct-to-database messaging
 * No application server needed


## What is that?

**Crossbar.io** is an application _router_: it can route remote procedure calls to endpoints and at the same time can act as a message broker to dispatch events in (soft) real-time to subscribers.

It provides application _infrastructure_ services to application components running in a distributed system and does so using two well-known, powerful messaging patterns:

 * **Remote Procedure Calls** where **Crossbar.io** acts as a *dealer* mediating between *callers* and *callees*
 * **Publish & Subscribe**, where **Crossbar.io** acts as a *broker* mediating between *publishers* and *subscribers*

For example, **Crossbar.io** allows you to

  * Call database stored procedures from JavaScript
  * Subscribe to topics and receive events in JavaScript
  * Publish events to topics from within database stored procedures or triggers

## Why?

### Less complexity

 * no application server required
 * logically 2-tier architecture
 * clean separation of frontend and backend code
 * fewer wheels to keep running and maintain
 * only JavaScript and PL/SQL know-how needed

### More power

 * create next-generation, single-page HTML5 frontends
 * create real-time enabled applications
 * push information from within the database
 * drive Web and Mobile frontends from the same backend API

## How does it work?

**Crossbar.io** is _multi-protocol_ - it speaks:

  * [The WebSocket Protocol](http://tools.ietf.org/html/rfc6455)
  * [The WebSocket Application Messaging Protocol (WAMP)](http://wamp.ws/)
  * Oracle database protocol
  * PostgreSQL database protocol
  * HTTP, FTP

**Crossbar.io** support *Oracle* today, with support for *PostgreSQL* upcoming.

**Crossbar.io** is written in Python, and builds on [Twisted](http://twistedmatrix.com/) and [Autobahn](http://autobahn.ws/).

It's fully asynchronous, high-performance with critical code paths accelerated in native code, and also able to run on [PyPy](http://pypy.org/), a [JITting](http://en.wikipedia.org/wiki/Just-in-time_compilation) Python implementation and competitive with e.g. NodeJS and Java based servers.

> As a first *indication*, you might have a look at the performance test section 9 in the reports [here](http://autobahn.ws/testsuite/reports/servers/index.html). The testing details are [here](https://github.com/tavendo/AutobahnTestSuite/tree/master/examples/publicreports). The usual caveats wrt any performance testing and benchmarking apply.

**Crossbar.io** can scale up on a 2 core/4GB Ram virtual machine to (at least == tested) 180k concurrently active connections. A scale out / cluster / federation architecture is currently under design.
