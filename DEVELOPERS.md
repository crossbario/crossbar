# Developer Guide

This guide is for developers of the Crossbar.io code itself, not for application developers creating Crossbar.io based applications.

## Roadmap

### 0.11.0

[Milestone for 0.11.0](https://github.com/crossbario/crossbar/milestones/0.11.0)

* Python 3
* new logging
* various improvements in error handling
* File Upload service
* various bug fixes and enhancement

### 0.12.0

[Milestone for 0.12.0](https://github.com/crossbario/crossbar/milestones/0.12.0)

* **PostgreSQL integration** - This is about extending WAMP right into PostgreSQL procedural languages. The Publisher role needs some finishing touches. The Callee role we had in the past in WebMQ, and this needs to be rewritten. The Subscriber role would work similar to Callee, wheras the Caller role we can do using the HTTP bridge.
* **RawSocket ping/pong** - This is just a feature from the spec we are missing in the Autobahn implementation. And once we have it there, we need to expose the related ping/pong knobs in the config.
* **Reverse Proxy service** - This is a feature request for a Web service which can be configured on a path and provides reverse proxying of HTTP traffic to a backend server. Essentially, expose the Twisted Web resource that is available.
* **Web hook service** - This feature allows Crossbar.io receive Web hook requests from Web services like GitHub and inject WAMP events. The service would work generic enough to digest requests from various Web services.
* **various bug fixes and enhancement**

### 0.13.0

[Milestone for 0.13.0](https://github.com/crossbario/crossbar/milestones/0.13.0)

* Timeouts at different levels (WAMP action, ..)
* Various authentication features
* Reflection, API docs generation, payload validation

### 0.14.0

[Milestone for 0.14.0](https://github.com/crossbario/crossbar/milestones/0.14.0)

* Multi-core support for routers (part 1: transport/routing service processes)
