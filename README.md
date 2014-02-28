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


# Where to go

For further information including a getting started, please checkout the [Wiki](https://github.com/crossbario/crossbar/wiki).