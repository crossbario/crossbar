[Documentation](.) > Features

# Features

## WAMP Application Router

* realtime RPC and PubSub routing
* multiple [realms](Router Realms) per router (mutliple routing & authorization domains)
* Authentication via

    * [WAMP-Anonymous](Anonymous Authentication)
    * [WAMP-Ticket](Ticket Authentication)
    * [WAMP-CRA](Challenge-Response Authentication)
    * [WAMP-Cryptosign](Cryptosign Authentication)
    * [WAMP-Cookie](Cookie Authentication)
    * [WAMP-TLS](TLS Client Certificate Authentication)

* [Authorization](Authorization)
  * static for URI + role + realm combinations
  * dynamic via custom authorizations handlers - use any callable WAMP procedure for authorization


## WAMP Advanced Profile Features

+ [Subscriber Black- and Whitelisting](Subscriber Black and Whitelisting)
+ [Publisher Exclusion](Publisher Exclusion)
+ [Publisher Identification](Publisher Identification)
+ [Pattern-Based Subscriptions](Pattern Based Subscriptions)
+ [Subscription Meta-Events and Procedures](Subscription Meta Events and Procedures)
+ [Event History](Event History)
+ [Caller Identification](Caller Identification)
+ [Progressive Call Results](Progressive Call Results)
+ [Pattern-Based Registrations](Pattern Based Registrations)
+ [Shared Registrations](Shared Registrations)
+ [Registration Meta-Events and Procedures](Registration Meta Events and Procedures)


## Multi-Transport and Serialization

* [Serializations](https://github.com/tavendo/WAMP/blob/master/spec/basic.md#serializations):

  * JSON
  * msgpack

* Framings:

  * [WebSocket](WebSocket Transport) with [Flash fallback](Flash Policy Transport)
  * [RawSocket](RawSocket Transport)
  * [HTTP/long poll](Long-Poll Service)

* Transport

  * TCP/TLS
  * Unix Domain Socket
  * Unix pipes

## Polyglot Application Components

* Application components can be written in any language for which a WAMP library exists.
* Current WAMP libraries exist for ([full list](http://wamp-proto.org/implementations/)):

    * Python
    * JavaScript
    * PHP
    * Java
    * C++
    * Objective-C
    * C#
    * Erlang
    * Lua
    * Go
    * Haskell

## REST Bridge

* integrate services providing REST APIs into WAMP applications
* supports all four roles (subscriber, publisher, callee, caller)

## Component Host

* host WAMP application components in Crossbar
* **Native Worker** - native hosting and deep control for Python components
* **Guest Worker** - start, stop and monitoring for components in any runtime (e.g. NodeJS, PHP, Java)

## Embedded Web Server

* [static web server](Static Web Service)
* configurable paths

  * [Web redirection](Web Redirection Service)
  * [JSON value](JSON Value Service)
  * [CGI script](CGI Script Service)
  * [WSGI host](WSGI Host Service)


## Application Template Scaffolding for Quick Start

* [application templates](Application Templates) for multiple supported languages and platforms
* install from the command line
* offer a working basis to get you hacking

## JSON and YAML configuration

## Multi-Process Architecture


## Upcoming Features

* Database connectors - databases as WAMP components
* Multi-core and multi-node architecture
* full Python 3 support (some features not yet supported)

For more details about upcoming features, see the [Roadmap](Roadmap).
