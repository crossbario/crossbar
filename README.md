# Crossbar.io

**Crossbar.io - Unified application router.**

*An Introduction*

1. [What is it?](#what-is-it)
2. [Why should I care?](#why-should-i-care)
3. [Where to go](#where-to-go)


*Other documents:*

* [Is Crossbar.io the Future of Python Web Apps?](http://tavendo.com/blog/post/is-crossbar-the-future-of-python-web-apps/) - *A developer's blog post about Crossbar.io - good introduction!*
* [Why WAMP](http://wamp.ws/why/) - *An introduction to Unified Routing and WAMP*
* [WebSocket - Why, what, and - can I use it?](http://tavendo.com/blog/post/websocket-why-what-can-i-use-it/) - *A good introduction and motivation for WebSocket*
* [Crossbar.io Quick Start](https://github.com/crossbario/crossbar/wiki#quick-start) - *Entry page in the Crossbar.io documentation Wiki*
* [Crossbar.io Project](https://github.com/crossbario/crossbar/wiki#quick-start) - *The project's homepage.*

## What is it?

Crossbar.io is an [open-source](https://github.com/crossbario/crossbar/blob/master/crossbar/LICENSE) server software that allows developers to create distributed systems composed of application components which are loosely coupled, communicate in (soft) real-time and can be implemented in different languages.

At it's core, Crossbar.io provides a flexible and scalable communication infrastructure for application components to talk to each other. This communication infrastructure is based on **Unified Routing** and **WAMP**:

>[**Unified Routing**](http://wamp.ws/why/#unified_routing) provides applications components with two communication patterns to use: remote procedure calls and publish & subscribe. In both patterns, the application components involved are fully decoupled by Crossbar.io which dynamically routes calls and events between the former. [**WAMP**](http://wamp.ws) is an open, standardized protocol that runs native on WebSocket.

**Unified Routing** allows Crossbar.io to provide developers with a powerful approach:

1. Composing a system from a set of self-contained, independent services or application components

2. Distributing application components freely across system resources like nodes, independent of the application communication paths

We think above approach is scalable in terms of developement and deployment, and in particular allows developers to create more advanced systems with less complexity and in less time.

Complementing the core application routing services, Crossbar.io features:

 * **polyglot component hosting**
 * **multi-process architecture**
 * **full-stack services**

Crossbar.io is a **polyglot component host** able to dynamically load, run and monitor application components written in different languages, and running under their native run-time. Want to have component **A** written in JavaScript and run on NodeJS, while component **B** written in Python and run on PyPy, and component **C** written and run on C++ natively? No problem. Crossbar.io will do with a little configuration.

>For quick start, the command line tool of Crossbar.io is able to generate complete, ready-to-run application templates for different languages.

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

## Why should I care?

Here are some things you can do with Crossbar.io - you can have

* all of your application frontends update in real-time as data changes on the backend or in other frontends
* write your application in JavaScript, from front- to backend

Hence, when you are creating apps or systems like

* [Next-gen Web](https://demo.crossbar.io/)
* [Internet-of-Things](http://tavendo.com/blog/post/arduino-yun-with-autobahn/)
* Connected Car
* [Real-time Collaboration](http://showroomdummy.com/)
* [Database-driven business applications](http://www.record-evolution.com/)
* [Messaging and chat](https://demo.crossbar.io/clandeck/)
* Multi-player online games

and are looking for a fresh, powerful developer experience, Crossbar.io might be made for you;)


## Where to go?

For further information, please checkout the [documentation](https://github.com/crossbario/crossbar/wiki) or get in touch on our [mailing list](https://groups.google.com/forum/#!forum/autobahnws).

----------

Copyright (c) 2014 [Tavendo GmbH](http://www.tavendo.com). Licensed under the [Creative Commons CC-BY-SA license](http://creativecommons.org/licenses/by-sa/3.0/). "WAMP", "Crossbar.io" and "Tavendo" are trademarks of Tavendo GmbH.