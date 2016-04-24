[Documentation](.) > Roadmap

# Roadmap

Crossbar.io is under active development.

We're currently releasing 0.X versions. These mainly add features and bug-fixes, but may contain (minor) breaking changes.

For version 1.0 we're aiming for an API with long-term stability.

Starting with version 1.0, we'll be using [semantic versioning](http://semver.org/).

Since we are resource-constrained we cannot give a precise roadmap for any of the features listed below.

We try to consider user interest when prioritizing features. So please contact us if you need something - or better yet, help us in implementing it!

## Database Integration

Adds connectors for

* PostgreSQL
* Oracle

These allow databases to become WAMP clients. They offer all four WAMP client roles:

* *Publisher*
* *Subscriber*
* *Caller*
* *Callee*

(Note: Caller functionality may be limited due to lack of support for async operations in PL/SQL.)

## Features from the WAMP Advanced Profile

* forced subscriber unsubscribe
* call timeouts
* forced callee unregister
* cancelling calls

## Multi-core and Multi-node Support

Router-to-Router communication will allow clustering, federation and automatic failover.

## Partitioned Calls and Events

Partitioned calls enable using e.g. database sharding.

-
-

Additionally, Tavendo, the maintainers of the Crossbar.io project, are planning commercial offerings to be used with Crossbar:

## Cloud Management Service

Manage and monitor your Crossbar.io instances centrally on the Web. Your Crossbar.io instances establish a management connection with the DevOps cloud service, giving you the ability to monitor and manage them from anywhere. The data you route through your Crossbar.io instance doesn't touch the cloud service.

## Commercial Support

Tavendo are already offering commercial support (see their [website](http://tavendo.com) for contact details).
