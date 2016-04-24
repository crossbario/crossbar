[Documentation](.) > Introduction

# Introduction

Take a look at [the project homepage](http://crossbar.io/) if you haven't.

## Underlying concepts

Crossbar.io is an open source **unified application router** implementing the **WAMP protocol**, an open standard WebSocket subprotocol which enables **loosely coupled** application components/microservices to communicate in (soft) **real-time**. 

Crossbar.io directes and transmitts **messages** between these components, which are written with WAMP client libraries, existing for **multiple languages** (currently 9). Every application component can be written in any of these, and you can mix components written in multiple languages since all interaction is via WAMP. 

With Crossbar.io as a router, you can create applications which are **cross-platform**, and distribute the functionality in your applications as you want. This enables application architectures such as

![Crossbar.io Node](/static/img/docs/gen/crossbar_integration.png)

The WAMP protocol offers **two messaging patterns** to allow components communicate:

* **Routed Remote Procedure Calls** (RPCs) - components register procedures and any other component can call this via Crossbar.io, with Crossbario handling the registrations, call and result routing.
* **Publish & Subscribe** (PubSub) - components subscribe to topics and publish to these, with Crossbar.io handling the subscriptions and dispatching.

Read More:

* [WebSocket](http://wamp.ws/faq/#what_is_websocket)
* [RPC](http://wamp.ws/faq/#rpc)
* [PubSub](http://wamp.ws/faq/#pubsub)
* [Application Scenarios](Application Scenarios).
* [Reasoning behind the design of WAMP](http://wamp.ws/why/)

## Features

Crossbar.io is not just a WAMP router - it also provides and manages infrastructure for your application.

Features include:

* **Integrated Static Web Server** - serve your HTML5 frontends directly from Crossbar.io
* **Component Hosting** - start application components in any language together with Crossbar.io + manage their lifecycle
* **Authentication** and **Authorization** configurable in Crossbar.io
* hosting **WSGI** applications
* **HTTP Push Bridge** for integration with legacy applications

This will often make Crossbar.io all the infrastructure you need besides your database.

Crossbar.io is is high-performant, scalable, robust and secure, and distributed as Open Source under the AGPL v3 license.

It is Python software and runs on *nix, Windows and Mac OSX.

Read More:

* [Feature List](Features)
* [Local Installation](Local Installation)
* [Setup in the Cloud](Setup in the Cloud)


## Getting Started

We have instructions for installing Crossbar.io both locally and in the cloud:

* [Local Installation](Local Installation)
* [Setup in the Cloud](Setup in the Cloud)

Then pick your language or device of choice and get started with a ready-to-run application template which Crossbar.io can create.

* [Choose your Weapon](Choose your Weapon)

You could also try out some demos.

* [Try out some demos](https://demo.crossbar.io/)
