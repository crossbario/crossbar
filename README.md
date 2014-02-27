# Crossbar.io

**Open-source polyglot application router**

*Remote Procedure Calls* and *Publish & Subscribe* for distributed applications, direct-to-database messaging and no application server needed.


## What is that?

[**Crossbar**.io](http://crossbar.io) is an application _router_: it can route remote procedure calls to endpoints and at the same time can act as a message broker to dispatch events in (soft) real-time to subscribers.

It provides application infrastructure services to application components running in a distributed system and does so using two well-known, powerful messaging patterns:

 * *Remote Procedure Calls*
 * *Publish & Subscribe*

For example, **Crossbar**.io allows you to

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

**Crossbar**.io provides routing services according to [The Web Application Messaging Protocol (WAMP)](http://wamp.ws/).

**Crossbar.io** is written in Python, and builds on [Twisted](http://twistedmatrix.com/) and [Autobahn](http://autobahn.ws/). It's fully asynchronous, high-performance with critical code paths accelerated in native code, and also able to run on [PyPy](http://pypy.org/), a [JITting](http://en.wikipedia.org/wiki/Just-in-time_compilation) Python implementation.

**Crossbar**.io supports direct integration of databases into WAMP based architectures. PostgreSQL and Oracle connectors under development.


## Sneak Preview

> Caution: **Crossbar**.io is currently under major refactoring, migrating to [WAMP v2](https://github.com/tavendo/WAMP/tree/master/spec). Functionality is only partially migrated (e.g. database connectors are still missing), and **Crossbar**.io is currently only tested on Linux.
> 

To install **Crossbar**.io:

	pip install crossbar

This will install the `crossbar` command. To get help on **Crossbar**.io, type:

	crossbar --help
 
**Crossbar**.io runs from a node data directory, which you can initialize

	crossbar init --cbdata ./test1

This will create a `test1` data directory, together with a configuration file `test1/config.json` (see below).

To start your **Crossbar**.io node:

	crossbar start --cbdata ./test1

**Crossbar**.io will log starting of the node:

	oberstet@corei7ub1310:~/tmp$ crossbar start --cbdata ./test1
	2014-02-25 18:45:46+0100 [-] Log opened.
	2014-02-25 18:45:46+0100 [-] Worker forked with PID 9053
	2014-02-25 18:45:46+0100 [-] Worker forked with PID 9054
	2014-02-25 18:45:46+0100 [-] Log opened.
	2014-02-25 18:45:46+0100 [-] Log opened.
	2014-02-25 18:45:47+0100 [-] Worker 9053: starting on EPollReactor ..
	2014-02-25 18:45:47+0100 [-] Worker 9054: starting on EPollReactor ..
	2014-02-25 18:45:47+0100 [-] Worker 9053: Router started.
	2014-02-25 18:45:47+0100 [-] Worker 9053: Class 'crossbar.demo.TimeService' (1) started in realm 'realm1'
	2014-02-25 18:45:47+0100 [-] WampWebSocketServerFactory starting on 9000
	2014-02-25 18:45:47+0100 [-] Starting factory <autobahn.twisted.websocket.WampWebSocketServerFactory instance at 0x3036d88>
	2014-02-25 18:45:47+0100 [-] Worker 9053: Transport websocket/tcp:9000 (1) started
	2014-02-25 18:45:47+0100 [-] WampWebSocketServerFactory starting on '/tmp/mysocket'
	2014-02-25 18:45:47+0100 [-] Starting factory <autobahn.twisted.websocket.WampWebSocketServerFactory instance at 0x3037908>
	2014-02-25 18:45:47+0100 [-] Worker 9053: Transport websocket/unix:/tmp/mysocket (2) started
	2014-02-25 18:45:47+0100 [-] Starting factory <autobahn.twisted.websocket.WampWebSocketClientFactory instance at 0x3485bd8>
	2014-02-25 18:45:47+0100 [-] Worker 9054: Component container started.
	2014-02-25 18:45:47+0100 [-] Worker 9054: Class 'crossbar.demo.TickService' started in realm 'realm1'
	...

The demo configuration of **Crossbar**.io will automatically start two demo application components, which you can test from the JavaScript frontends:

  * [Timeservice Frontend](https://github.com/tavendo/AutobahnPython/blob/master/examples/twisted/wamp/basic/rpc/timeservice/frontend.html)
  * [Ticker Frontend](https://github.com/tavendo/AutobahnPython/blob/master/examples/twisted/wamp/basic/pubsub/basic/frontend.html)

The demo configuration file `test1/config.json` created starts a WAMP router with two transports (TCP + Unix domain sockets).

It will also start the `crossbar.demo.TimeService` application component embedded in the router, and start the `crossbar.demo.TickService` application component in a separate worker, connected to the router via Unix domain sockets.

You can run any of the application components from [here](https://github.com/tavendo/AutobahnPython/tree/master/examples/twisted/wamp/basic).

If the application component isn't installed as a Python package, you need to provide a class path:

     "options": {
        "classpaths": [".", "/home/oberstet/scm/tavendo/autobahn/AutobahnPython/examples/twisted/wamp/basic"]
     },

and then the respective application components
	
	"classes": [
		"rpc.progress.backend.Component",
		"rpc.pubsub.backend.Component"
	]


## Where to go

The [Wiki](/wiki).