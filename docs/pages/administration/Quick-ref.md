[Documentation](.) > [Administration](Administration) > Quick Ref

# Quick Ref

A Crossbar.io node running in **local mode** reads a node configuration file upon startup and follows the configuration there to start services.

The configuration by default will be loaded from `CBDIR/config.json` (JSON format) or `CBDIR/config.yaml` (YAML format).

A Crossbar.io node always runs at least one process, the **node controller**. Here is a node configuration that merely changes the node ID via controller configuration:

```yaml
controller:
    # configuration of node controller process
    id: 'node301'
```

However, running a Crossbar.io node with only the controller process isn't of much use. All services that Crossbar.io provides are run in **worker processes**:

```yaml
controller:
    id: 'node301'

workers: [
  # list of worker processes
]
```

So we need to start up worker processes that provide useful services. The core service of Crossbar.io of course is to provide WAMP routing. Here is how to start up a **router worker**:

```yaml
controller:
    id: 'node301'

workers:
    # a router worker provides WAMP routing services
    - type: "router"
      realms: [
        # list of routing realms managed by this router worker
      ]
      transports: [
        # list of WAMP transports this router worker is listening on
      ]
```

A router worker, to do useful work will need two pieces of further configuration:

* a WAMP transport
* a routing realm

Transports are listening for incoming connections from WAMP clients. A router needs to have at least one listening transport configured, but can have multiple. Here is how to start up a **listening transport**:

```yaml
controller:
    id: 'node301'

workers:
    - type: "router"
      realms: []
      transports:
          # a WAMP-over-WebSocket transport listening on port TCP/9000
          - type: "websocket"
            endpoint:
                type: "tcp"
                port: 9000
```

In WAMP, realms are routing domains which are completely separate. Crossbar.io is able to serve multiple realms and allows to share listening transports across realms. A router needs to have at least one routing realm configured, but can have multiple. Here is how to start up a **routing realm**:

```yaml
controller:
    id: 'node301'

workers:
    - type: "router"
      realms:
          # a routing realm named "realm1" with everything allowed
          # for "anonymous" clients
          - name: "realm1"
            roles:
                - name: "anonymous"
                  allow-by-default: true
      transports:
          - type: "websocket"
            endpoint:
                type: "tcp"
                port: 9000
```

At this point, you have a fully functional WAMP router listening on TCP port 9000 for incoming WAMP-over-WebSocket connections that want to join realm "realm1"!

---

More topics to treat:

* Running and hosting WAMP application components:
  - using VMs (AWS EC2 etc)
  - using OS containers (Docker etc)
  - using OS processes (Crossbar.io **guest workers**)

* Advanced: hosting Python components inside Crossbar.io **native workers**

* WAMP component isolation: the "one process per component" approach
  (Processes are isolated regarding OS namespaces and resources, but generally
  share a filesystem; even more lightweight than OS containers. Recommended
  transport is WAMP-CBOR-RawSocket on top of Unix domain sockets.)


Crossbar.io promotes a "one process per component" approach.

An application might consist of dozens of components, but usually only of one or two,
maybe three different programming language stacks.

Running dozens of full OS containers with separate storage, or even multiple VMs with
a separate complete storage and installation for each results in a lot of complexity
and stuff to manage.

What we promote is running each component in a separate process, but let all processes
of one application share one storage, filesystem and installation stack.




* Using Crossbar.io with Docker

(I)

Docker (with custom installation stack + Crossbar.io)
  -> Crossbar.io
    -> Router workers
    -> Guest workers for components (can connect over TCP or UDS)

(II)

ROUTER 1
    Docker (with custom installation stack + Crossbar.io)
     -> Crossbar.io
       -> Router workers

COMPONENTS 1
    Docker (with custom installation stack + Crossbar.io)
     -> Crossbar.io
       -> Guest workers for components (connect over TCP)

COMPONENTS 2
    Docker (with custom installation stack + Crossbar.io)
     -> Crossbar.io
       -> Guest workers for components (connect over TCP)


* Similar for Atomic and Ubuntu Snappy
