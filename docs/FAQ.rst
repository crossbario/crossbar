:orphan:

FAQ
===

Frequently asked questions with Crossbar.io, Autobahn and WAMP.

-  `The WAMP ecosystem <#the-wamp-ecosystem>`__
-  `What is the relationship between WAMP, Autobahn and Crossbar.io? <#what-is-the-relationship-between-wamp,-autobahn-and-crossbar.io?>`__
-  `What is WAMP? <#what-is-wamp?>`__
-  `What is Autobahn? <#what-is-autobahn?>`__
-  `What is Crossbar.io? <#what-is-crossbar.io?>`__
-  `Licenses <#licenses>`__
-  `What does open-source license mean for me when I use it for a
   project? <#what-does-open-source-license-mean-for-me-when-i-use-it-for-a-project?>`__
-  `What is the license for the application
   templates? <#what-is-the-license-for-the-application-templates?>`__
-  `Modifying and contributing <#modifying-and-contributing>`__
-  `Can I hack Crossbar.io to fit my own
   needs? <#can-i-hack-crossbar.io-to-fit-my-own-needs?>`__
-  `I want to contribute to Crossbar.io - what do I need to
   do? <#i-want-to-contribute-to-crossbar.io---what-do-i-need-to-do?>`__
-  `Python runtime <#python-runtime>`__
-  `What is PyPy? <#what-is-pypy?>`__
-  `Should I run on CPython or
   PyPy? <#should-i-run-on-cpython-or-pypy?>`__
-  `Integration <#integration>`__
-  `Can I integrate a non-WAMP application into my WAMP
   application? <#can-i-integrate-a-non-wamp-application-into-my-wamp-application?>`__

The WAMP ecosystem
------------------

What is the relationship between WAMP, Autobahn and Crossbar.io?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`WAMP <https://wamp-proto.org>`__ is an open source protocol which provides RPC
and PubSub messaging patterns.

The `Autobahn project <https://crossbar.io/autobahn/>`__ provides WAMP
implementations in multiple languages.

**Crossbar.io** builds on Autobahn\|Python, one of the Autobahn
projects, and provides a much larger set of functionality to make it
into a powerful router for application messaging.

What is WAMP?
~~~~~~~~~~~~~

WAMP (Web Application Messaging Protocol) is a protocol which provides
both Remote Procedure Calls (RPC) and Publish & Subscribe (PubSub)
messaging patterns. All clients can be both publishers and subscribers,
callers of remote procedures and offer remote procedure endpoints. A
WAMP router connects the clients.

WAMP enables distributed, multi-client and server applications. It is an
open protocol, and several independent implementations exist.

WAMP has WebSocket as a preferred transport.

What is Autobahn?
~~~~~~~~~~~~~~~~~

The `Autobahn project <https://crossbar.io/autobahn/>`__ provides open-source
WebSocket and WAMP implementations for several programming languages.
WAMP implementations are for client roles implementations.

What is Crossbar.io?
~~~~~~~~~~~~~~~~~~~~

**Crossbar.io** builds on Autobahn\|Python. It adds the full set of
advanced WAMP router functionality, as well as things like an integrated
Web server, hosting of application components or support for various
authentication methods. Applications developed with Crossbar.io can use
any WAMP client library. This, obviously, includes the Autobahn
libraries.

Licenses
--------

What does open-source license mean for me when I use it for a project?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The license (`AGPL v3 <http://www.gnu.org/licenses/agpl-3.0.html>`__)
does not have any effect on your application. The APGL only affects code
which is joined to a AGPL licensed project's code.

When using Crossbar.io for an application, your application code just
sends and receives WAMP messages, which Crossbar.io routes. This does
not join your code to the code of Crossbar.io. This applies irrespective
of where you run your code. Using the possibility to host application
components with Crossbar.io does not join your code with Crossbar.io

Your code remains yours, and you can license it in whichever way you
want.

If you need further assurance, you can email us at
contact@crossbario.com for a signed letter asserting our view on the
license.

What is the license for the application templates?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We license all examples and other materials that you can use in creating
your own applications as liberally as possible.

In the case of the application templates, these are licensed either
under the BSD 2-clause license or the Apache 2.0 license. Both allow you
to use the code in your own applications, irrespective of which license
you are using. And yes, this includes commercial & closed source.

Modifying and Contributing
--------------------------

Can I hack Crossbar.io to fit my own needs?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Like all open source licenses, the AGPL gives you the right to modify
the code: to fix bugs, optimize things, add features, or anything else
you need or feel like doing.

When you modify Crossbar.io, then you need to provide access for others
to your modified code if

-  you distribute the modified code to any third party
-  you run the modified code on a server accessible to any third party

A 'third party' would usually be anybody else but you. An exception is
when you are working for a company - use purely inside the company does
not trigger the requirement to provide access to your code.

What this means is that you cannot use Crossbar.io as the basis for
developing closed source software (except for when you are its only
user).

I want to contribute to Crossbar.io - what do I need to do?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are `full
instructions <https://github.com/crossbario/crossbar/blob/master/CONTRIBUTING.md>`__
for how to contribute.

The short version:

Crossbar.io is hosted on GitHub, so you need to be familiar with the git
development model.

Additionally, before we can accept your first contribution, you need to
sign a Contributor Assignment Agreement (CAA) and mail this to us.

This is needed in order for the Crossbar.io project to have all
necessary rights to the code, e.g. to be able to switch licenses in the
future.

Integration
-----------

Can I integrate a non-WAMP application into my WAMP application?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to have a WAMP component which communicates with your
non-WAMP application (component) and does WAMP messaging based on this.
How complex this is depends on the specifics of the use case, e.g. the
protocol.

We do provide components for communicating with other applications over
HTTP/POST requests- see :doc:`the documentation <HTTP-Bridge>` , as well as
integration for MQTT clients via a :doc:`full MQTT broker <MQTT-Broker>` .
