title: FAQ
toc: [Documentation, FAQ]

# FAQ

Frequently asked questions with Crossbar.io, Autobahn and WAMP.

* [The WAMP ecosystem](#the-wamp-ecosystem)
   + [What is the relationship between WAMP, Autobahn and Crossbar.io?](#what-is-the-relationship-between-wamp,-autobahn-and-crossbar.io?)
   + [What is WAMP?](#what-is-wamp?)
   + [What is Autobahn?](#what-is-autobahn?)
   + [What is Crossbar.io?](#what-is-crossbar.io?)
* [Licenses](#licenses)
   + [What does open-source license mean for me when I use it for a project?](#what-does-open-source-license-mean-for-me-when-i-use-it-for-a-project?)
   + [What is the license for the application templates?](#what-is-the-license-for-the-application-templates?)
* [Modifying and contributing](#modifying-and-contributing)
   + [Can I hack Crossbar.io to fit my own needs?](#can-i-hack-crossbar.io-to-fit-my-own-needs?)
   + [I want to contribute to Crossbar.io - what do I need to do?](#i-want-to-contribute-to-crossbar.io---what-do-i-need-to-do?)
* [Python runtime](#python-runtime)
   + [What is PyPy?](#what-is-pypy?)
   + [Should I run on CPython or PyPy?](#should-i-run-on-cpython-or-pypy?)
* [Integration](#integration)
   + [Can I integrate a non-WAMP application into my WAMP application?](#can-i-integrate-a-non-wamp-application-into-my-wamp-application?)


## The WAMP ecosystem

### What is the relationship between WAMP, Autobahn and Crossbar.io?

[WAMP](http://wamp.ws) is an open source protocol which provides RPC and PubSub messaging patterns.

The [Autobahn project](http://autobahn.ws/) provides WAMP implementations in multiple languages.

**Crossbar.io** builds on Autobahn|Python, one of the Autobahn projects, and provides a much larger set of functionality to make it into a powerful router for application messaging.

### What is WAMP?

WAMP (Web Application Messaging Protocol) is a protocol which provides both Remote Procedure Calls (RPC) and Publish & Subscribe (PubSub) messaging patterns. All clients can be both publishers and subscribers, callers of remote procedures and offer remote procedure endpoints. A WAMP router connects the clients.

WAMP enables distributed, multi-client and server applications. It is an open protocol, and several independent implementations exist.

WAMP has WebSocket as a preferred transport.

### What is Autobahn?

The [Autobahn project](http://autobahn.ws/) provides open-source WebSocket and WAMP implementations for several programming languages. WAMP implementations are for client roles implementations.

### What is Crossbar.io?

**Crossbar.io** builds on Autobahn|Python. It adds the full set of advanced WAMP router functionality, as well as things like an integrated Web server, hosting of application components or support for various authentication methods.
<br>
Applications developed with Crossbar.io can use any WAMP client library. This, obviously, includes the Autobahn libraries.

## Licenses

### What does open-source license mean for me when I use it for a project?

The license ([AGPL v3](http://www.gnu.org/licenses/agpl-3.0.html)) does not have any effect on your application. The APGL only affects code which is joined to a AGPL licensed project's code.

When using Crossbar.io for an application, your application code just sends and receives WAMP messages, which Crossbar.io routes. This does not join your code to the code of Crossbar.io. This applies irrespective of where you run your code. Using the possibility to host application components with Crossbar.io does not join your code with Crossbar.io

Your code remains yours, and you can license it in whichever way you want.

If you need further assurance, you can email us at contact@crossbario.com for a signed letter asserting our view on the license.

### What is the license for the application templates?

We license all examples and other materials that you can use in creating your own applications as liberally as possible.

In the case of the application templates, these are licensed either under the BSD 2-clause license or the Apache 2.0 license. Both allow you to use the code in your own applications, irrespective of which license you are using. And yes, this includes commercial & closed source.

## Modifying and Contributing

### Can I hack Crossbar.io to fit my own needs?

Like all open source licenses, the <a href="http://www.gnu.org/licenses/agpl-3.0.html">AGPL</a> gives you the right to modify the code: to fix bugs, optimize things, add features, or anything else you need or feel like doing.

When you modify Crossbar.io, then you need to provide access for others to your modified code if

* you distribute the modified code to any third party
* you run the modified code on a server accessible to any third party

A 'third party' would usually be anybody else but you. An exception is when you are working for a company - use purely inside the company does not trigger the requirement to provide access to your code.

What this means is that you cannot use Crossbar.io as the basis for developing closed source software (except for when you are its only user).

### I want to contribute to Crossbar.io - what do I need to do?

There are [full instructions](https://github.com/crossbario/crossbar/blob/master/CONTRIBUTING.md) for how to contribute.

The short version:

Crossbar.io is hosted on GitHub, so you need to be familiar with the git development model.

Additionally, before we can accept your first contribution, you need to sign a Contributor Assignment Agreement (CAA) and mail this to us.

This is needed in order for the Crossbar.io project to have all necessary rights to the code, e.g. to be able to switch licenses in the future.

## Python runtime

### What is PyPy?

[Python](https://www.python.org/) is a programming language that has multiple *implementations*. The original and default implementation is usually called *CPython*, since it is written in C.

Other implementations include:

* [PyPy](http://pypy.org/)
* [Jython](http://www.jython.org/)
* [IronPython](http://ironpython.net/)

Now, PyPy is a Python implementation specifically geared towards *high performance*.

Different from CPython, PyPy is not an interpreter, but compiling Python bytecode to native machine code - transparently and on the fly. It is a [JIT compiler](http://en.wikipedia.org/wiki/Just-in-time_compilation).

Also, PyPy [has](http://morepypy.blogspot.de/2013/10/incremental-garbage-collector-in-pypy.html) a powerful and *incremental garbage collector*. A [garbage collector](http://en.wikipedia.org/wiki/Garbage_collection_%28computer_science%29) is responsible for managing memory in a dynamic language such as Python.

### Should I run on CPython or PyPy?

Short answer: Using CPython is easier and quicker. If you don't need the highest possible performance, stick with CPython.

Running on PyPy will give you a *lot* more performance than CPython though. Of course there are some downsides as well:

* longer startup time compared to CPython (since the JIT compiler will need to do more initial work)
* it takes some time (seconds to minutes) until Crossbar.io reaches maximum performance (since the JIT compiler needs to warm up on the code hot-paths)
* it might have higher memory consumption than CPython

## Integration

### Can I integrate a non-WAMP application into my WAMP application?

It is possible to have a WAMP component which communicates with your non-WAMP application (component) and does WAMP messaging based on this. How complex this is depends on the specifics of the use case, e.g. the protocol.

We do provide components for communicating with other applications over HTTP/POST requests. For details see [the documentation](HTTP-Bridge).
