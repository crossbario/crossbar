# Scaling Crossbar.io

The following discusses Crossbar.io scalability in terms of

* scale-up: utilizing faster and more cores on a single machine
* scale-out: utilizing multiple machines

and with regard to

* scaling WAMP application components
* scaling WAMP routing

## Scaling Application Components

Crossbar.io can host WAMP application components (which connect to WAMP routers) and supports scale-up and scale-out.

Application components are run in worker processes, and hence multiple cores on a single machine can be utilized by starting multiple, functionally different components or multiple instances of the same component.

Application components can also be spread across multiple machines, all connecting to the same router. Doing so allows you to scale-out and utilize the resources of multiple machines.

Above features already work today with the current Crossbar.io release.

## Scaling Routers

A Crossbar.io router worker process can manage multiple, independent realms and a single Crossbar.io node can run multiple router worker processes managing independent realms.

A *single* Crossbar.io router worker process already scales to 100-200k concurrently active connections.

You can utilize multiple cores on one machine for routing by starting *multiple* router worker processes, each managing *independent* realms.

The same works for scale-out, by running router workers on different machines, all managing different, independent realms.

Above features already work today with the current Crossbar.io release.

However, if you need to scale beyond 100-200k concurrently active connection on a *single realm*, this is not yet possible today.

For this, router workers will need to work together as a single logical router, managing the same realm. This feature is under development and currently scheduled for Q1/2016.
