# Crossbar.io

**Crossbar.io** - Unified application router.

**Join the [mailing list](http://groups.google.com/group/autobahnws), follow us on [Twitter](https://twitter.com/crossbario) and [Quick Start](https://github.com/crossbario/crossbar/wiki#quick-start) with Crossbar.io!**

___________
*This README:*

1. [What is Crossbar.io?](#what-is-crossbar-io)
2. [What can I do?](#what-can-i-do)
3. [Why should I care?](#why-should-i-care)


*Related articles:*

* [Is Crossbar.io the Future of Python Web Apps?](http://tavendo.com/blog/post/is-crossbar-the-future-of-python-web-apps/) - *A developer's blog post - good introduction!*
* [WebSocket - Why, what, and - can I use it?](http://tavendo.com/blog/post/websocket-why-what-can-i-use-it/) - *Background and motivation of WebSocket*
* [Why WAMP](http://wamp.ws/why/) - *Unified Routing and WAMP explained*

*More Resources:*

* [Project Homepage](http://crossbar.io)
* **[Quick Start](https://github.com/crossbario/crossbar/wiki#quick-start)**
* [Documentation](https://github.com/crossbario/crossbar/wiki)
* [Demos](https://demo.crossbar.io/)



## What is Crossbar.io?

Crossbar.io is an [open-source](https://github.com/crossbario/crossbar/blob/master/crossbar/LICENSE) server software that allows developers to create distributed systems, composed of application components which are loosely coupled, communicate in (soft) real-time and can be implemented in different languages:

![Crossbar.io clients overview - languages/environments: javascript/browser, javascript/node.js, Python, C++, under development: Java/Android, PL/SQL - PostgreSQL](docs/figures/gen/crossbar_integration.png)

At its core, Crossbar.io provides a flexible and scalable communication infrastructure for application components to talk to each other. This communication infrastructure is based on **Unified Routing** and **WAMP**:

>[**Unified Routing**](http://wamp.ws/why/#unified_routing) provides applications components with two communication patterns to use: **remote procedure calls** and **publish & subscribe**. In both patterns, the application components involved are fully decoupled by Crossbar.io which dynamically routes calls and events between them. [**WAMP**](http://wamp.ws) is an open, standardized protocol for Unified Routing that runs natively on WebSocket.

In addition to the core application routing service, Crossbar.io features:

 * **application component hosting**
 * **multi-process architecture**
 * **full-stack services**

Crossbar.io is a **component host** able to dynamically load, run and monitor **application components** written in different languages, and running under their native run-time.

Want to have component **A** written in JavaScript and running on NodeJS, component **B** written in Python and running on PyPy, and component **C** written and running on C++ natively? No problem - Crossbar.io has you covered.

>To get you started quickly, the command line tool of Crossbar.io is able to generate complete, ready-to-run application templates for different languages.

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

Here are a couple of demos and applications built with Crossbar.io

* [Next-gen Web](https://demo.crossbar.io/)
* [Internet-of-Things](http://tavendo.com/blog/post/arduino-yun-with-autobahn/)
* Connected Car
* [Real-time Collaboration](http://showroomdummy.com/)
* [Database-driven business applications](http://www.record-evolution.com/)
* [Messaging and chat](https://demo.crossbar.io/clandeck/)
* Multi-player online games

which can give you a hands-on impression of what you can do.

We can also take an example:

*Imagine you create a "Vote Game" web applications, where visitors can vote for one of three kinds of ice cream and the total number of votes for the different ice creams is displayed.*

Now, here is the catch: we want ot have the numbers shown to be correct - always, and instantly. Whenever someone votes on a ice cream, the displayed numbers of all visitors should update immediately.

In other words: we want a real-time enabled user interface.

From a developer point of view, what seems natural is having the frontend issue a remote procedure call to get the total number of votes initially. Then subscribe to a topic to get updates on the total number of votes. And finally issue a remote procedure call for actually voting. The backend should note each vote, and publish updated numbers for total votes. These patterns, remote procedure calls and publish & subscribe are exactly those provided by WAMP.

To summarize, above "Vote Game" app would be a good fit for Crossbar.io and is [easy to implement](https://github.com/tavendo/AutobahnPython/tree/master/examples/twisted/wamp/wamplet/votegame). 


## Why should I care?

We think that application developers and system operators should be freed from the burden and compexity of old architectures.

Crossbar.io is made for *DevOps*: it allows *developers* to easily **compose** a system from self-contained, independent services or application components and *operators* to **distribute** application components freely across system resources like nodes without breaking application communication.

We believe the above approach is scalable in terms of development and deployment, and in particular allows to create and operate more advanced systems with less complexity and in less time.


----------

Copyright (c) 2014 [Tavendo GmbH](http://www.tavendo.com). Licensed under the [Creative Commons CC-BY-SA license](http://creativecommons.org/licenses/by-sa/3.0/). "WAMP", "Crossbar.io" and "Tavendo" are trademarks of Tavendo GmbH.
