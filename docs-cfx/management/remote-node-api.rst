Remote Node API
===============

The remote node management API is a low-level internal API used by CFC itself
to manage CF nodes. It should not be used by user directly.

It provides remote access to the node management API of Crossbar.io Fabric
nodes currently connected.

.. contents:: :local:

---------


Nodes
-----

Nodes are instances of Crossbar.io (Fabric) running on host systems, and
running from a node directory. Most of the time, nodes run within Docker
containers or confined as snaps.

crossbarfabriccenter.remote.node.get_status
...........................................

.. automethod:: crossbar.node.controller.NodeController.get_status

crossbarfabriccenter.remote.node.shutdown
.........................................

.. automethod:: crossbar.node.controller.NodeController.shutdown

crossbarfabriccenter.remote.node.get_workers
............................................

.. automethod:: crossbar.node.controller.NodeController.get_workers

crossbarfabriccenter.remote.node.get_worker
...........................................

.. automethod:: crossbar.node.controller.NodeController.get_worker

crossbarfabriccenter.remote.node.start_worker
.............................................

.. automethod:: crossbar.node.controller.NodeController.start_worker

crossbarfabriccenter.remote.node.stop_worker
............................................

.. automethod:: crossbar.node.controller.NodeController.stop_worker

crossbarfabriccenter.remote.node.get_worker_log
...............................................

.. automethod:: crossbar.node.controller.NodeController.get_worker_log


Native Workers
--------------

Native workers are node worker processes of the types **router**,
**container** and **proxy**. The API here allows to retrieve worker
logs, control the worker CPU affinity and run code profilers in a live
running system.

crossbarfabriccenter.remote.worker.get_cpu_count
................................................

.. automethod:: crossbar.common.process.NativeProcess.get_cpu_count

crossbarfabriccenter.remote.worker.get_cpus
...........................................

.. automethod:: crossbar.common.process.NativeProcess.get_cpus

crossbarfabriccenter.remote.worker.get_cpu_affinity
...................................................

.. automethod:: crossbar.common.process.NativeProcess.get_cpu_affinity

crossbarfabriccenter.remote.worker.set_cpu_affinity
...................................................

.. automethod:: crossbar.common.process.NativeProcess.set_cpu_affinity

crossbarfabriccenter.remote.worker.get_process_info
...................................................

.. automethod:: crossbar.common.process.NativeProcess.get_process_info

crossbarfabriccenter.remote.worker.get_process_stats
....................................................

.. automethod:: crossbar.common.process.NativeProcess.get_process_stats

crossbarfabriccenter.remote.worker.get_process_monitor
......................................................

.. automethod:: crossbar.common.process.NativeProcess.get_process_monitor

crossbarfabriccenter.remote.worker.set_process_stats_monitoring
...............................................................

.. automethod:: crossbar.common.process.NativeProcess.set_process_stats_monitoring

crossbarfabriccenter.remote.worker.trigger_gc
.............................................

.. automethod:: crossbar.common.process.NativeProcess.trigger_gc

crossbarfabriccenter.remote.worker.start_manhole
................................................

.. automethod:: crossbar.common.process.NativeProcess.start_manhole

crossbarfabriccenter.remote.worker.stop_manhole
................................................

.. automethod:: crossbar.common.process.NativeProcess.stop_manhole

crossbarfabriccenter.remote.worker.get_manhole
..............................................

.. automethod:: crossbar.common.process.NativeProcess.get_manhole

crossbarfabriccenter.remote.worker.utcnow
.........................................

.. automethod:: crossbar.common.process.NativeProcess.utcnow

crossbarfabriccenter.remote.worker.started
..........................................

.. automethod:: crossbar.common.process.NativeProcess.started

crossbarfabriccenter.remote.worker.uptime
.........................................

.. automethod:: crossbar.common.process.NativeProcess.uptime

crossbarfabriccenter.remote.worker.set_node_id
..............................................

.. automethod:: crossbar.worker.controller.WorkerController.set_node_id

crossbarfabriccenter.remote.worker.get_node_id
..............................................

.. automethod:: crossbar.worker.controller.WorkerController.get_node_id

crossbarfabriccenter.remote.worker.get_profilers
................................................

.. automethod:: crossbar.worker.controller.WorkerController.get_profilers

crossbarfabriccenter.remote.worker.start_profiler
.................................................

.. automethod:: crossbar.worker.controller.WorkerController.start_profiler

crossbarfabriccenter.remote.worker.get_profile
..............................................

.. automethod:: crossbar.worker.controller.WorkerController.get_profile

crossbarfabriccenter.remote.worker.get_pythonpath
.................................................

.. automethod:: crossbar.worker.controller.WorkerController.get_pythonpath

crossbarfabriccenter.remote.worker.add_pythonpath
.................................................

.. automethod:: crossbar.worker.controller.WorkerController.add_pythonpath


Router Workers
--------------

Routers are the core of Crossbar.io. They are native worker processes
that run the routing code of Crossbar.io as well as endpoint listeners,
Web services and other transports. The API here allows for remote and
dynamic management of router workers.

**Router Realms**
All routing of messages in Crossbar.io is isolated
in different routing confinements called realms. Realms, at the same time,
also provide namespace isolation, as URIs as always interpreted with respect
to the realm within they occur. URIs portable across realms - if required -
needs to be arranged for by the user.

**Realm Roles**
Roles are bundles of permissions defined on a realm. When a client
connects to the router and authenticates successfully, it is assigned a
**role**. This role will then determine the actual permissions the
client is granted by the router.

**Role Permissions**
Permissions specific which WAMP actions is allowed on which URI
(pattern) for the pair realm-role.

**Router Transports**
Routers will want to listen for incoming client connections on so-called
listening endpoints. The API here allows the dynamic startup and
shutdown of router listening endpoints in the form of transports.

**Transport Services**
Some router transports, such as Web transports, allow to configure
*transport services* attached to URL parts in a Web resource tree. The
API here allows to dynamically configure Web services, such as a static
Web or file download service on dynamic URL part in the Web resource
tree of Web transports.

**Router Components**
Router workers are native Crossbar.io processes that can host Python
user components. Restrictions: The user components must be written using
AutobahnPython and Twisted, and run under the same Python Crossbar.io
runs under. Further, running user components in the same OS process as
Crossbar.io routing code can lead to instability, and provides less
security isolation. Router components should only be used very
selectively for small amounts of code, such as dynamic authenticators or
authorizers.

---------

Router workers inherit all API from native workers, and additionally provide the following API.

crossbarfabriccenter.remote.router.get_router_realms
....................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_realms

crossbarfabriccenter.remote.router.get_router_realm
....................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_realm

crossbarfabriccenter.remote.router.get_router_realm_by_name
...........................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_realm_by_name

crossbarfabriccenter.remote.router.get_router_realm_stats
.........................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_realm_stats

crossbarfabriccenter.remote.router.start_router_realm
.....................................................

.. automethod:: crossbar.worker.router.RouterController.start_router_realm

crossbarfabriccenter.remote.router.stop_router_realm
....................................................

.. automethod:: crossbar.worker.router.RouterController.stop_router_realm

crossbarfabriccenter.remote.router.get_router_realm_roles
.........................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_realm_roles

crossbarfabriccenter.remote.router.get_router_realm_role
........................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_realm_role

crossbarfabriccenter.remote.router.start_router_realm_role
..........................................................

.. automethod:: crossbar.worker.router.RouterController.start_router_realm_role

crossbarfabriccenter.remote.router.stop_router_realm_role
.........................................................

.. automethod:: crossbar.worker.router.RouterController.stop_router_realm_role

crossbarfabriccenter.remote.router.get_router_components
........................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_components

crossbarfabriccenter.remote.router.get_router_component
.......................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_component

crossbarfabriccenter.remote.router.start_router_component
.........................................................

.. automethod:: crossbar.worker.router.RouterController.start_router_component

crossbarfabriccenter.remote.router.stop_router_component
........................................................

.. automethod:: crossbar.worker.router.RouterController.stop_router_component

crossbarfabriccenter.remote.router.get_router_transports
........................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_transports

crossbarfabriccenter.remote.router.get_router_transport
.......................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_transport

crossbarfabriccenter.remote.router.start_router_transport
.........................................................

.. automethod:: crossbar.worker.router.RouterController.start_router_transport

crossbarfabriccenter.remote.router.stop_router_transport
........................................................

.. automethod:: crossbar.worker.router.RouterController.stop_router_transport

crossbarfabriccenter.remote.router.start_web_transport_service
..............................................................

.. automethod:: crossbar.worker.router.RouterController.start_web_transport_service

crossbarfabriccenter.remote.router.stop_web_transport_service
.............................................................

.. automethod:: crossbar.worker.router.RouterController.stop_web_transport_service

crossbarfabriccenter.remote.router.get_web_transport_service
............................................................

.. automethod:: crossbar.worker.router.RouterController.get_web_transport_service

crossbarfabriccenter.remote.router.get_web_transport_services
.............................................................

.. automethod:: crossbar.worker.router.RouterController.get_web_transport_services

crossbarfabriccenter.remote.router.kill_by_authid
.................................................

.. automethod:: crossbar.worker.router.RouterController.kill_by_authid

crossbarfabriccenter.remote.router.get_router_realm_links
.........................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_realm_links

crossbarfabriccenter.remote.router.get_router_realm_link
........................................................

.. automethod:: crossbar.worker.router.RouterController.get_router_realm_link

crossbarfabriccenter.remote.router.start_router_realm_link
..........................................................

.. automethod:: crossbar.worker.router.RouterController.start_router_realm_link

crossbarfabriccenter.remote.router.stop_router_realm_link
.........................................................

.. automethod:: crossbar.worker.router.RouterController.stop_router_realm_link


Proxy Workers
-------------

Proxy workers inherit all API from native workers, and additionally provide the following API.

crossbarfabriccenter.remote.proxy.get_proxy_transports
......................................................

.. automethod:: crossbar.worker.proxy.ProxyController.get_proxy_transports

crossbarfabriccenter.remote.proxy.get_proxy_transport
.....................................................

.. automethod:: crossbar.worker.proxy.ProxyController.get_proxy_transport

crossbarfabriccenter.remote.proxy.start_proxy_transport
.......................................................

.. automethod:: crossbar.worker.proxy.ProxyController.start_proxy_transport

crossbarfabriccenter.remote.proxy.stop_proxy_transport
......................................................

.. automethod:: crossbar.worker.proxy.ProxyController.stop_proxy_transport


crossbarfabriccenter.remote.proxy.start_web_transport_service
.............................................................

.. automethod:: crossbar.worker.proxy.ProxyController.start_web_transport_service

crossbarfabriccenter.remote.proxy.stop_web_transport_service
............................................................

.. automethod:: crossbar.worker.proxy.ProxyController.stop_web_transport_service

crossbarfabriccenter.remote.proxy.get_web_transport_service
...........................................................

.. automethod:: crossbar.worker.proxy.ProxyController.get_web_transport_service

crossbarfabriccenter.remote.proxy.get_web_transport_services
............................................................

.. automethod:: crossbar.worker.proxy.ProxyController.get_web_transport_services


crossbarfabriccenter.remote.proxy.get_proxy_routes
..................................................

.. automethod:: crossbar.worker.proxy.ProxyController.get_proxy_routes

crossbarfabriccenter.remote.proxy.get_proxy_realm_route
.......................................................

.. automethod:: crossbar.worker.proxy.ProxyController.get_proxy_realm_route

crossbarfabriccenter.remote.proxy.start_proxy_realm_route
.........................................................

.. automethod:: crossbar.worker.proxy.ProxyController.start_proxy_realm_route

crossbarfabriccenter.remote.proxy.stop_proxy_realm_route
........................................................

.. automethod:: crossbar.worker.proxy.ProxyController.stop_proxy_realm_route


crossbarfabriccenter.remote.proxy.get_proxy_connections
.......................................................

.. automethod:: crossbar.worker.proxy.ProxyController.get_proxy_connections

crossbarfabriccenter.remote.proxy.get_proxy_connection
......................................................

.. automethod:: crossbar.worker.proxy.ProxyController.get_proxy_connection

crossbarfabriccenter.remote.proxy.start_proxy_connection
........................................................

.. automethod:: crossbar.worker.proxy.ProxyController.start_proxy_connection

crossbarfabriccenter.remote.proxy.stop_proxy_connection
.......................................................

.. automethod:: crossbar.worker.proxy.ProxyController.stop_proxy_connection


Container Workers
-----------------

Container workers inherit all API from native workers, and additionally provide the following API.

crossbarfabriccenter.remote.container.get_components
....................................................

.. automethod:: crossbar.worker.container.ContainerController.get_components

crossbarfabriccenter.remote.container.get_component
...................................................

.. automethod:: crossbar.worker.container.ContainerController.get_component

crossbarfabriccenter.remote.container.start_component
.....................................................

.. automethod:: crossbar.worker.container.ContainerController.start_component

crossbarfabriccenter.remote.container.restart_component
.......................................................

.. automethod:: crossbar.worker.container.ContainerController.restart_component

crossbarfabriccenter.remote.container.stop_component
....................................................

.. automethod:: crossbar.worker.container.ContainerController.stop_component
