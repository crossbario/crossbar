# Crossbar.io

**Crossbar.io - Unified application router.**

*An Introduction*

1. [What is it?](#what-is-it)
2. [What can I do?](#what-can-i-do)
3. [Why should I care?](#why-should-i-care)
4. [Where to go?](#where-to-go)


*Other documents:*

* [Is Crossbar.io the Future of Python Web Apps?](http://tavendo.com/blog/post/is-crossbar-the-future-of-python-web-apps/) - *A developer's blog post - good introduction!*
* [Why WAMP](http://wamp.ws/why/) - *Unified Routing and WAMP explained*
* [WebSocket - Why, what, and - can I use it?](http://tavendo.com/blog/post/websocket-why-what-can-i-use-it/) - *Background and motivation of WebSocket*
* [Crossbar.io Quick Start](https://github.com/crossbario/crossbar/wiki#quick-start) - *Documentation Wiki Entry page*
* [Crossbar.io Project](https://github.com/crossbario/crossbar/wiki#quick-start) - *The project's homepage.*

## What is it?

Crossbar.io is an [open-source](https://github.com/crossbario/crossbar/blob/master/crossbar/LICENSE) server software that allows developers to create distributed systems, composed of application components which are loosely coupled, communicate in (soft) real-time and can be implemented in different languages.

At its core, Crossbar.io provides a flexible and scalable communication infrastructure for application components to talk to each other.

![Crossbar.io clients overview - languages/environments: javascript/browser, javascript/node.js, Python, C++, under development: Java/Android, PL/SQL - PostgreSQL](docs/figures/crossbar_clients_optimized.svg)

This communication infrastructure is based on **Unified Routing** and **WAMP**:

>[**Unified Routing**](http://wamp.ws/why/#unified_routing) provides applications components with two communication patterns to use: **remote procedure calls** and **publish & subscribe**. In both patterns, the application components involved are fully decoupled by Crossbar.io which dynamically routes calls and events between them. [**WAMP**](http://wamp.ws) is an open, standardized protocol that runs natively on WebSocket.

In addition to the core application routing services, Crossbar.io features:

 * **polyglot component hosting**
 * **multi-process architecture**
 * **full-stack services**

Crossbar.io is a **polyglot component host** able to dynamically load, run and monitor application components written in different languages, and running under their native run-time.

Want to have component **A** written in JavaScript and running on NodeJS, component **B** written in Python and running on PyPy, and component **C** written and running on C++ natively? No problem - Crossbar.io has you covered.

>For a quick start, the command line tool of Crossbar.io is able to generate complete, ready-to-run application templates for different languages.

Crossbar.io has a **multi-process architecture** where a node controller process spawns and monitors worker processes. Worker types include router, application component host and arbitrary guest processes. *The multi-process architecture enables scaling up on multi-core systems and supports secure and robust operation.*

Crossbar.io also includes a whole set of **full-stack services**, such as authentication and authorization, serving static Web files, HTTP long-poll fallback, HTTP push bridge, CGI scripts and hosting WSGI applications. This will often make Crossbar.io all the infrastructure you need besides your database.

<!--
*Unified Routing*


instrastructure
unified routing


Application components talk to each other over [WAMP](http://wamp.ws) - an open communication protocol that runs native on the Web (via [WebSocket](http://tavendo.com/blog/post/websocket-why-what-can-i-use-it/)) and *unifies two simple, yet powerful messaging patterns in one protocol*:

* calling remote procedures (*Remote Procedure Calls*) and
* publishing events (*Publish & Subscribe*)

At it's core, what Crossbar.io provides is the **dynamic routing of calls and events between application components**. In a robust, secure and scalable way. And application components can be deployed to and span multiple systems.

Finally, Crossbar.io is *polyglot*, which means application components can be written in [different languages](http://wamp.ws/implementations/), e.g. [Python](http://autobahn.ws/python), [JavaScript](http://autobahn.ws/js) or [C++](http://autobahn.ws/cpp). Not only that, but each application component can run under it's *native* run-time system!

We think Crossbar.io is a big step forward, bringing **more power** and **less complexity** to developers.
-->

## What can I do?

Checkout some Crossbar.io powered demos and apps

* [Next-gen Web](https://demo.crossbar.io/)
* [Internet-of-Things](http://tavendo.com/blog/post/arduino-yun-with-autobahn/)
<!-- * Connected Car -->
* [Real-time Collaboration](http://showroomdummy.com/)
* [Database-driven business applications](http://www.record-evolution.com/)
* [Messaging and chat](https://demo.crossbar.io/clandeck/)
<!-- * Multi-player online games -->


## Why should I care?

Crossbar.io is made for *DevOps* - it allows *developers* to

**compose** a system from self-contained, independent services or application components

and *operators* to

**distribute** application components freely across system resources like nodes without breaking application communication

We believe the above approach is scalable in terms of development and deployment, and in particular allows to create and operate more advanced systems with less complexity and in less time.


## Where to go?

For further information, please checkout the [documentation](https://github.com/crossbario/crossbar/wiki) or get in touch on our [mailing list](https://groups.google.com/forum/#!forum/autobahnws).

----------

Copyright (c) 2014 [Tavendo GmbH](http://www.tavendo.com). Licensed under the [Creative Commons CC-BY-SA license](http://creativecommons.org/licenses/by-sa/3.0/). "WAMP", "Crossbar.io" and "Tavendo" are trademarks of Tavendo GmbH.
