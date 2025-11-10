:orphan:

Crossbar.io Personalities
==========================

.. note::

   This document is a **work-in-progress** documenting the Crossbar.io personality system architecture.

Overview
--------

Crossbar.io uses a "personality" system to support different deployment modes and feature sets. A personality is a policy class that configures which node type, web services, worker types, and features are available when running Crossbar.io.

The personality system allows Crossbar.io to operate in different modes by loading different ``Personality`` classes at startup, enabling the same codebase to support everything from simple standalone routers to complex multi-node distributed systems.

Available Personalities
-----------------------

Standalone
~~~~~~~~~~

**Module:** ``crossbar.personality.Personality``

**Command:** ``crossbar [command]`` (default) or ``crossbar standalone [command]``

The standalone personality is the base personality providing core WAMP router functionality.

**Key Characteristics:**

* **Node Type:** ``crossbar.node.node.Node``
* **Realm Stores:** Memory-only (``RealmStoreMemory``)
* **Web Services:** 20+ service types including:

  * ``static`` - Static file server
  * ``websocket`` - WAMP-WebSocket endpoint
  * ``rawsocket`` - WAMP-RawSocket endpoint
  * ``nodeinfo`` - Node information page
  * ``json`` - Generic JSON value web service
  * ``cgi`` - CGI script executor
  * ``wsgi`` - WSGI application host
  * ``longpoll`` - Long-poll fallback transport
  * ``mqtt`` - MQTT broker bridge
  * ``reverseproxy`` - HTTP reverse proxy
  * And many more...

* **Worker Types:**

  * ``RouterController`` - WAMP router worker
  * ``ContainerController`` - Application container worker
  * ``GuestController`` - Guest worker (external processes)
  * ``WebSocketTesteeController`` - WebSocket protocol tester

**Use Cases:**

* Development and testing
* Single-node WAMP router deployments
* Simple microservice architectures
* Getting started with Crossbar.io

Edge
~~~~

**Module:** ``crossbar.edge.personality.Personality``

**Command:** ``crossbar edge [command]``

The edge personality extends standalone with advanced features for distributed deployments, persistence, and XBR (Cross Blockchain Router) integration.

**Key Characteristics:**

* **Node Type:** ``FabricNode`` (enhanced capabilities)
* **Realm Stores:**

  * ``memory`` - In-memory storage
  * ``cfxdb`` - LMDB-backed persistent storage via zlmdb

* **Additional Web Services:**

  * ``pairme`` - Node pairing service for connecting to master nodes

* **Additional Features:**

  * Market maker support (XBR data markets)
  * LMDB-backed event history and persistence
  * Node pairing and registration capabilities
  * Enhanced monitoring and metrics

**Use Cases:**

* Production deployments requiring persistence
* Nodes that need to pair with a management/master node
* XBR data market participation
* High-availability configurations with persistent state

Master
~~~~~~

**Module:** ``crossbar.master.personality.Personality``

**Command:** ``crossbar master [command]``

The master personality extends edge functionality to enable centralized management and orchestration of multiple Crossbar.io nodes.

**Key Characteristics:**

* **Node Type:** ``FabricCenterNode`` (central management node)
* **Additional Web Services:**

  * ``registerme`` - Node registration service for managing edge nodes

* **Additional Features:**

  * Centralized configuration management
  * Multi-node orchestration
  * Dynamic node provisioning
  * Fleet management capabilities

**Use Cases:**

* Managing fleets of edge nodes
* Centralized configuration and deployment
* Multi-datacenter deployments
* Enterprise deployments requiring central control

Network
~~~~~~~

**Module:** ``crossbar.network.personality.Personality``

**Command:** ``crossbar network [command]``

The network personality provides advanced XBR network integration with blockchain-based features.

**Key Characteristics:**

* Full XBR network integration
* Blockchain-based coordination
* Network-wide resource management
* Advanced cryptographic features

**Use Cases:**

* XBR network participation
* Blockchain-integrated applications
* Decentralized data markets
* Network-wide coordination

Architecture Details
--------------------

Personality Loading
~~~~~~~~~~~~~~~~~~~

Personalities are loaded dynamically at runtime based on the command used:

.. code-block:: python

   # From crossbar/__init__.py (line 305-327)
   if command == "standalone":
       from crossbar import personality as standalone
       personality = standalone.Personality
   elif command == "edge":
       from crossbar import edge
       personality = edge.Personality
   elif command == "network":
       from crossbar import network
       personality = network.Personality
   elif command == "master":
       from crossbar import master
       personality = master.Personality

The personality system is designed with conditional imports so that optional dependencies (e.g., for XBR features) are only required when using the corresponding personality.

Personality Class Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each personality class defines:

* ``NAME`` - Personality identifier (e.g., "standalone", "edge", "master")
* ``TITLE`` - Human-readable title
* ``BANNER`` - ASCII banner displayed at startup
* ``LICENSE`` - License file location tuple
* ``LICENSES_OSS`` - OSS licenses file location tuple
* ``WEB_SERVICE_CHECKERS`` - Dict mapping service names to config validation functions
* ``WEB_SERVICE_FACTORIES`` - Dict mapping service names to implementation classes
* ``REALM_STORES`` - Dict of available realm storage backends
* ``Node`` - Node class to instantiate
* ``NodeOptions`` - Node options class
* ``WorkerKlasses`` - List of available worker controller classes

Integration Levels
------------------

The personality system supports progressive complexity:

**Level 1: Single Router + WAMP Clients**

* Standalone personality
* Single router node
* Multiple WAMP client applications
* Suitable for: Development, simple deployments

**Level 2: Multiple Routers with R2R**

* Edge personality
* Multiple router nodes
* Router-to-Router (R2R) messaging
* Persistent state with cfxdb
* Suitable for: Production, high-availability

**Level 3: Managed Node Fleet**

* Master + Edge personalities
* Centralized management node
* Multiple edge nodes
* Dynamic provisioning
* Suitable for: Enterprise, multi-datacenter

**Level 4: XBR Network**

* Network personality
* Blockchain integration
* Decentralized coordination
* Data market participation
* Suitable for: XBR ecosystem applications

Crossbar Shell
--------------

The ``crossbar shell`` command provides an interactive management interface for working with master nodes and node fleets.

**Available Commands:**

* ``add`` - Add resources
* ``auth`` - Authenticate user with Crossbar.io
* ``clear`` - Clear screen
* ``create`` - Create resources
* ``current`` - Show currently selected resource
* ``delete`` - Delete resources
* ``export`` - Export resources
* ``help`` - General help
* ``import`` - Import resources
* ``init`` - Create a new user profile/key-pair
* ``list`` - List resources
* ``monitor`` - Monitor master node
* ``pair`` - Pair nodes and devices
* ``remove`` - Remove resources
* ``select`` - Change current resource
* ``set`` - Change shell settings
* ``shell`` - Run an interactive shell
* ``show`` - Show resources
* ``start`` - Start workers, components
* ``stop`` - Stop workers, components
* ``unpair`` - Unpair nodes and devices
* ``version`` - Print version information

**Usage:**

.. code-block:: bash

   # Interactive shell
   crossbar shell

   # Direct command execution
   crossbar shell list nodes
   crossbar shell show node <node-id>
   crossbar shell start worker <worker-id>

**Options:**

* ``--dotdir TEXT`` - Set the dot directory (with config and profile)
* ``--profile TEXT`` - Set the profile to be used
* ``--realm TEXT`` - Set the realm to join
* ``--role TEXT`` - Set the role requested to authenticate as
* ``--debug`` - Enable debug output

See Also
--------

* :doc:`Getting-Started` - Introduction to Crossbar.io
* :doc:`Installation` - Installing Crossbar.io
* :doc:`Node-Configuration` - Configuring Crossbar.io nodes
* :doc:`Administration` - Administrative tasks

.. note::

   This documentation will be expanded with more details on:

   * Personality-specific configuration examples
   * Migration guides between personalities
   * XBR network integration details
   * Master node management workflows
   * Router-to-Router (R2R) messaging patterns
