# Crossbar.io Master Node API Reference

The Crossbar.io Master Node exposes a comprehensive WAMP API on the management realm `com.crossbario.fabric`. This document provides a complete reference of all available API endpoints.

## Table of Contents

- [Connection Information](#connection-information)
- [Authentication](#authentication)
- [Global Realm APIs](#global-realm-apis)
- [Management Realm APIs](#management-realm-apis)
- [Application Realm API](#application-realm-api)
- [Remote Node Management API](#remote-node-management-api)
- [Remote Worker Management API](#remote-worker-management-api)
- [Remote Router Management API](#remote-router-management-api)
- [Remote Container Management API](#remote-container-management-api)
- [Remote Proxy Management API](#remote-proxy-management-api)
- [Remote Tracing API](#remote-tracing-api)
- [Remote WAMP Meta API](#remote-wamp-meta-api)
- [Usage Examples](#usage-examples)

---

## Connection Information

**WebSocket URL:**
- Local development: `ws://localhost:9000/ws`
- Production: `wss://master.xbr.network/ws`

**Realm:** `com.crossbario.fabric`

**Authentication Method:** WAMP-Cryptosign (Ed25519 public-key cryptography)

**Key Storage:** `~/.crossbar/default.priv`

**Transport:** WAMP-over-WebSocket with CBOR/MsgPack/JSON serializers

---

## Authentication

### Authenticator Procedure

- **`com.crossbario.fabric.authenticate`**
  - Dynamic cryptosign authentication
  - Validates Ed25519 signatures
  - Supports channel binding (tls-unique)
  - Database-backed user/node authentication

---

## Global Realm APIs

**Prefix:** `crossbar.`

These APIs manage the global Crossbar.io Fabric Center instance.

### Management Realm Lifecycle

- **`crossbar.activate_realm`** - Activate a management realm
  - Starts router workers and initializes realm infrastructure
  - Parameters: `mrealm_obj` (management realm configuration)
  
- **`crossbar.deactivate_realm`** - Deactivate a management realm
  - Stops all associated workers and cleans up resources
  - Parameters: `mrealm_obj` (management realm configuration)

---

## Management Realm APIs

**Prefix:** `crossbarfabriccenter.`

These APIs operate at the domain-global level for managing organizations, users, and management realms.

### User & Organization Management

**Prefix:** `crossbarfabriccenter.user.`

#### Organization Management

- **`list_organizations`** - List all organizations
  - Returns: List of organization OIDs or names
  - Parameters: `return_names` (optional bool)

- **`get_organization`** - Get organization details by OID
  - Parameters: `org_oid` (UUID string)
  - Returns: Organization object with metadata

- **`create_organization`** - Create new organization
  - Parameters: `organization` (dict with name, description, etc.)
  - Returns: Created organization object with OID

- **`modify_organization`** - Update organization
  - Parameters: `org_oid` (UUID), `org_delta` (changes dict)
  - Returns: Updated organization object

- **`delete_organization`** - Delete organization
  - Parameters: `org_oid` (UUID), `cascade` (optional bool)
  - Returns: Deletion confirmation

#### User Management

- **`list_users`** - List all users
  - Returns: List of user OIDs

- **`get_user`** - Get user by user ID
  - Parameters: `user_id` (UUID string)
  - Returns: User object with email, pubkeys, etc.

- **`get_user_by_pubkey`** - Get user by public key
  - Parameters: `pubkey` (hex-encoded Ed25519 pubkey)
  - Returns: User object

- **`get_user_by_email`** - Get user by email address
  - Parameters: `email` (string)
  - Returns: User object

- **`modify_user`** - Update user information
  - Parameters: `user_id` (UUID), `user_delta` (changes dict)
  - Returns: Updated user object

- **`list_users_by_organization`** - List users in an organization
  - Parameters: `org_id` (UUID)
  - Returns: List of user OIDs

- **`list_organizations_by_user`** - List organizations for a user
  - Parameters: `user_id` (UUID)
  - Returns: List of organization OIDs

- **`get_roles_on_organization_for_user`** - Get user's roles in an organization
  - Parameters: `org_id` (UUID), `user_id` (UUID)
  - Returns: List of role assignments

### Management Realm Management

**Prefix:** `crossbarfabriccenter.mrealm.`

#### Realm Operations

- **`list_mrealms`** - List all management realms
  - Parameters: `return_names` (optional bool)
  - Returns: List of management realm OIDs or names

- **`get_mrealm`** - Get management realm by OID
  - Parameters: `mrealm_oid` (UUID string)
  - Returns: Management realm object

- **`get_mrealm_by_name`** - Get management realm by name
  - Parameters: `mrealm_name` (string)
  - Returns: Management realm object

- **`create_mrealm`** - Create new management realm
  - Parameters: `mrealm` (dict with name, description, etc.)
  - Returns: Created management realm object with OID

- **`modify_mrealm`** - Update management realm
  - Parameters: `mrealm_oid` (UUID), `mrealm_diff` (changes dict)
  - Returns: Updated management realm object

- **`delete_mrealm`** - Delete management realm
  - Parameters: `mrealm_oid` (UUID), `cascade` (optional bool, default false)
  - Returns: Deletion confirmation

- **`delete_mrealm_by_name`** - Delete management realm by name
  - Parameters: `mrealm_name` (string), `cascade` (optional bool)
  - Returns: Deletion confirmation

#### Node Management

- **`list_nodes`** - List all nodes
  - Returns: List of node OIDs

- **`list_nodes_by_mrealm`** - List nodes in a management realm
  - Parameters: `mrealm_id` (UUID)
  - Returns: List of node OIDs

- **`list_nodes_by_mrealm_name`** - List nodes by realm name
  - Parameters: `mrealm_name` (string)
  - Returns: List of node OIDs

- **`get_node`** - Get node details
  - Parameters: `node_id` (UUID)
  - Returns: Node object with configuration

- **`get_node_by_name`** - Get node by management realm and node name
  - Parameters: `mrealm_name` (string), `node_name` (string)
  - Returns: Node object

- **`modify_node`** - Update node configuration
  - Parameters: `node_id` (UUID), `node_delta` (changes dict)
  - Returns: Updated node object

- **`delete_node`** - Delete node
  - Parameters: `node_id` (UUID)
  - Returns: Deletion confirmation

- **`pair_node`** - Pair a node to a management realm
  - Parameters: 
    - `pubkey` (hex-encoded Ed25519 public key)
    - `realm_name` (management realm name)
    - `authid` (node authentication ID)
    - `authextra` (optional dict)
  - Returns: Pairing confirmation with node OID

- **`unpair_node`** - Unpair node by OID
  - Parameters: `node_oid` (UUID)
  - Returns: Unpairing confirmation

- **`unpair_node_by_pubkey`** - Unpair node by public key
  - Parameters: `pubkey` (hex-encoded string)
  - Returns: Unpairing confirmation

- **`unpair_node_by_name`** - Unpair node by realm name and authid
  - Parameters: `realm_name` (string), `authid` (string)
  - Returns: Unpairing confirmation

#### Metadata Management

- **`get_docs`** - Get documentation for object type
  - Parameters: `otype` (object type), `oid` (object ID)
  - Returns: Documentation object

- **`delete_docs`** - Delete documentation
  - Parameters: `oid` (object ID)
  - Returns: Deletion confirmation

---

## Management Realm Controller API

**Prefix:** `crossbarfabriccenter.mrealm.<realm_name>.`

These APIs operate within a specific management realm for monitoring and tracing.

### Status & Monitoring

- **`get_status`** - Get realm status
  - Returns: Realm status with connected nodes, workers, etc.

- **`get_nodes`** - List nodes
  - Parameters: `status` (optional filter: 'online', 'offline')
  - Returns: List of node OIDs or authids

- **`get_node`** - Get node by OID
  - Parameters: `node_oid` (UUID)
  - Returns: Node details including connection status

- **`get_node_by_authid`** - Get node by authid
  - Parameters: `node_authid` (string)
  - Returns: Node details

### Distributed Tracing

- **`get_traces`** - List all traces
  - Returns: List of trace IDs

- **`get_trace`** - Get trace details
  - Parameters: `trace_id` (UUID)
  - Returns: Trace configuration and status

- **`get_trace_data`** - Get trace data
  - Parameters: `trace_id` (UUID), additional filters
  - Returns: Collected trace data

- **`create_trace`** - Create new trace
  - Parameters: Trace configuration dict
  - Returns: Created trace object with ID

- **`start_trace`** - Start tracing
  - Parameters: `trace_id` (UUID)
  - Returns: Deferred that resolves when trace starts

- **`stop_trace`** - Stop trace
  - Parameters: `trace_id` (UUID)
  - Returns: Deferred that resolves when trace stops

- **`delete_trace`** - Delete trace
  - Parameters: `trace_id` (UUID)
  - Returns: Deletion confirmation

---

## Application Realm API

**Prefix:** `crossbarfabriccenter.mrealm.arealm.`

These APIs manage application realms - the actual WAMP realms where end-user applications connect.

### Application Realm Management

- **`list_arealms`** - List all application realms
  - Parameters: `return_names` (optional bool)
  - Returns: List of application realm OIDs or names

- **`get_arealm`** - Get application realm by OID
  - Parameters: `arealm_oid` (UUID)
  - Returns: Application realm object

- **`get_arealm_by_name`** - Get application realm by name
  - Parameters: `arealm_name` (string)
  - Returns: Application realm object

- **`create_arealm`** - Create application realm
  - Parameters: `arealm` (dict with name, description, config)
  - Returns: Created application realm object

- **`delete_arealm`** - Delete application realm
  - Parameters: `arealm_oid` (UUID)
  - Returns: Deletion confirmation

- **`start_arealm`** - Start application realm on cluster
  - Parameters: `arealm_oid` (UUID), cluster configuration
  - Returns: Start confirmation with deployment details

- **`stop_arealm`** - Stop application realm
  - Parameters: `arealm_oid` (UUID)
  - Returns: Stop confirmation

- **`list_router_workers`** - List router workers for application realm
  - Parameters: `arealm_oid` (UUID)
  - Returns: List of worker identifiers

### Principal Management

Principals are authentication identities in application realms.

- **`list_principals`** - List principals in application realm
  - Parameters: `arealm_oid` (UUID), filters
  - Returns: List of principal OIDs

- **`get_principal`** - Get principal by OID
  - Parameters: `arealm_oid` (UUID), `principal_oid` (UUID)
  - Returns: Principal object with authid, authrole, etc.

- **`get_principal_by_name`** - Get principal by name
  - Parameters: `arealm_oid` (UUID), `principal_name` (string)
  - Returns: Principal object

- **`list_principal_credentials`** - List credentials for principal
  - Parameters: `arealm_oid` (UUID), `principal_oid` (UUID)
  - Returns: List of credential objects

- **`get_principal_credential`** - Get specific credential
  - Parameters: `arealm_oid` (UUID), `principal_oid` (UUID), `credential_oid` (UUID)
  - Returns: Credential details

### Role Management

Roles define authorization permissions in application realms.

- **`list_roles`** - List all roles
  - Parameters: `return_names` (optional bool)
  - Returns: List of role OIDs or names

- **`get_role`** - Get role by OID
  - Parameters: `role_oid` (UUID)
  - Returns: Role object with permissions

- **`get_role_by_name`** - Get role by name
  - Parameters: `role_name` (string)
  - Returns: Role object

- **`create_role`** - Create new role
  - Parameters: `role` (dict with name, permissions)
  - Returns: Created role object

- **`delete_role`** - Delete role
  - Parameters: `role_oid` (UUID)
  - Returns: Deletion confirmation

- **`list_role_permissions`** - List permissions for role
  - Parameters: `role_oid` (UUID)
  - Returns: List of permission objects

- **`get_role_permission`** - Get specific permission
  - Parameters: `role_oid` (UUID), `permission_oid` (UUID)
  - Returns: Permission details (URI, allow/deny, match type)

- **`get_role_permissions_by_uri`** - Get permissions by URI
  - Parameters: `role_oid` (UUID), `uri` (string)
  - Returns: Matching permissions

- **`list_arealm_roles`** - List roles in application realm
  - Parameters: `arealm_oid` (UUID)
  - Returns: List of role assignments

- **`get_arealm_role`** - Get specific arealm role
  - Parameters: `arealm_oid` (UUID), `role_oid` (UUID)
  - Returns: Role assignment details

---

## Remote Node Management API

**Prefix:** `crossbarfabriccenter.remote.node.`

These APIs forward management calls to remote Crossbar.io nodes. All procedures require `node_oid` as the first parameter.

### System Information

- **`get_cpu_count`** - Get CPU count
  - Parameters: `node_oid` (UUID)
  - Returns: Number of CPUs

- **`get_cpu_affinity`** - Get CPU affinity
  - Parameters: `node_oid` (UUID)
  - Returns: List of CPU cores process is bound to

- **`set_cpu_affinity`** - Set CPU affinity
  - Parameters: `node_oid` (UUID), `cpus` (list of core IDs)
  - Returns: Confirmation

- **`get_process_info`** - Get process information
  - Parameters: `node_oid` (UUID)
  - Returns: PID, executable, working directory, etc.

- **`get_process_stats`** - Get process statistics
  - Parameters: `node_oid` (UUID)
  - Returns: Memory usage, CPU time, open files, etc.

- **`set_process_stats_monitoring`** - Enable/disable process stats monitoring
  - Parameters: `node_oid` (UUID), `interval` (seconds)
  - Returns: Confirmation

- **`get_system_stats`** - Get system statistics
  - Parameters: `node_oid` (UUID)
  - Returns: System-wide CPU, memory, network, disk stats

- **`get_status`** - Get node status
  - Parameters: `node_oid` (UUID)
  - Returns: Node state, uptime, workers, etc.

### Debugging & Maintenance

- **`trigger_gc`** - Trigger garbage collection
  - Parameters: `node_oid` (UUID)
  - Returns: GC statistics

- **`start_manhole`** - Start manhole debugging
  - Parameters: `node_oid` (UUID), `port` (optional)
  - Returns: Manhole connection details

- **`stop_manhole`** - Stop manhole
  - Parameters: `node_oid` (UUID)
  - Returns: Confirmation

- **`get_manhole`** - Get manhole status
  - Parameters: `node_oid` (UUID)
  - Returns: Manhole configuration or null

- **`get_worker_log`** - Get worker log
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: Recent log entries

- **`shutdown`** - Shutdown node
  - Parameters: `node_oid` (UUID)
  - Returns: Shutdown acknowledgment

### Worker Management

- **`get_workers`** - List all workers
  - Parameters: `node_oid` (UUID)
  - Returns: List of worker IDs

- **`get_worker`** - Get worker details
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: Worker type, status, PID, etc.

- **`start_worker`** - Start new worker
  - Parameters: `node_oid` (UUID), `worker_id` (string), `worker_config` (dict)
  - Returns: Started worker details

- **`stop_worker`** - Stop worker
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: Stop confirmation

### Events

All events include `node_oid` as first parameter:

- **`on_node_starting`**, **`on_node_started`** - Node lifecycle
- **`on_node_heartbeat`** - Periodic node heartbeat
- **`on_node_stopping`**, **`on_node_stopped`** - Node shutdown
- **`on_router_starting`**, **`on_router_started`** - Router worker lifecycle
- **`on_container_starting`**, **`on_container_started`** - Container worker lifecycle
- **`on_guest_starting`**, **`on_guest_started`** - Guest worker lifecycle
- **`on_proxy_starting`**, **`on_proxy_started`** - Proxy worker lifecycle
- **`on_xbrmm_starting`**, **`on_xbrmm_started`** - XBR market maker lifecycle

---

## Remote Worker Management API

**Prefix:** `crossbarfabriccenter.remote.worker.`

These APIs manage individual workers on remote nodes. All procedures require `node_oid` and `worker_id` parameters.

### Worker Control

- **`shutdown`** - Shutdown worker
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: Shutdown acknowledgment

- **`get_status`** - Get worker status
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: Worker state, uptime, etc.

### Python Environment

- **`get_pythonpath`** - Get Python path
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: List of Python path entries

- **`add_pythonpath`** - Add to Python path
  - Parameters: `node_oid` (UUID), `worker_id` (string), `paths` (list)
  - Returns: Updated Python path

### Performance Monitoring

- **`get_cpu_affinity`** - Get CPU affinity
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: List of CPU cores

- **`set_cpu_affinity`** - Set CPU affinity
  - Parameters: `node_oid` (UUID), `worker_id` (string), `cpus` (list)
  - Returns: Confirmation

- **`get_process_info`** - Get process info
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: Worker process details

- **`get_process_stats`** - Get process stats
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: Memory, CPU, file descriptors, etc.

- **`set_process_stats_monitoring`** - Enable/disable monitoring
  - Parameters: `node_oid` (UUID), `worker_id` (string), `interval` (seconds)
  - Returns: Confirmation

### Profiling

- **`get_profilers`** - List available profilers
  - Parameters: `node_oid` (UUID), `worker_id` (string)
  - Returns: List of profiler names (vmprof, yappi, etc.)

- **`start_profiler`** - Start profiler
  - Parameters: `node_oid` (UUID), `worker_id` (string), `profiler` (string), `runtime` (seconds)
  - Returns: Profiler session ID

- **`get_profile`** - Get profiling data
  - Parameters: `node_oid` (UUID), `worker_id` (string), `profile_id` (UUID)
  - Returns: Profile data or download URL

### Events

- **`on_worker_log`** - Worker log messages
- **`on_profile_started`** - Profiling session started
- **`on_profile_finished`** - Profiling session finished

---

## Remote Router Management API

**Prefix:** `crossbarfabriccenter.remote.router.`

These APIs manage router workers on remote nodes. All procedures require `node_oid` and `worker_id` parameters.

### Realm Management

- **`get_router_realms`** - List router realms
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of realm IDs

- **`get_router_realm`** - Get realm details
  - Parameters: `node_oid`, `worker_id`, `realm_id`
  - Returns: Realm configuration

- **`get_router_realm_stats`** - Get realm statistics
  - Parameters: `node_oid`, `worker_id`, `realm_id`
  - Returns: Session count, message rates, etc.

- **`get_router_realm_by_name`** - Get realm by name
  - Parameters: `node_oid`, `worker_id`, `realm_name`
  - Returns: Realm details

- **`start_router_realm`** - Start router realm
  - Parameters: `node_oid`, `worker_id`, `realm_id`, `realm_config`
  - Returns: Started realm details

- **`stop_router_realm`** - Stop router realm
  - Parameters: `node_oid`, `worker_id`, `realm_id`
  - Returns: Stop confirmation

### Role Management

- **`get_router_realm_roles`** - List realm roles
  - Parameters: `node_oid`, `worker_id`, `realm_id`
  - Returns: List of role IDs

- **`get_router_realm_role`** - Get role details
  - Parameters: `node_oid`, `worker_id`, `realm_id`, `role_id`
  - Returns: Role configuration

- **`start_router_realm_role`** - Start realm role
  - Parameters: `node_oid`, `worker_id`, `realm_id`, `role_id`, `role_config`
  - Returns: Started role details

- **`stop_router_realm_role`** - Stop realm role
  - Parameters: `node_oid`, `worker_id`, `realm_id`, `role_id`
  - Returns: Stop confirmation

### Transport Management

- **`get_router_transports`** - List transports
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of transport IDs

- **`get_router_transport`** - Get transport details
  - Parameters: `node_oid`, `worker_id`, `transport_id`
  - Returns: Transport configuration

- **`start_router_transport`** - Start transport
  - Parameters: `node_oid`, `worker_id`, `transport_id`, `transport_config`
  - Returns: Started transport details (listening port, etc.)

- **`stop_router_transport`** - Stop transport
  - Parameters: `node_oid`, `worker_id`, `transport_id`
  - Returns: Stop confirmation

### Web Service Management

- **`get_web_transport_services`** - List web services
  - Parameters: `node_oid`, `worker_id`, `transport_id`
  - Returns: List of web service paths

- **`get_web_transport_service`** - Get web service details
  - Parameters: `node_oid`, `worker_id`, `transport_id`, `path`
  - Returns: Service type and configuration

- **`start_web_transport_service`** - Start web service
  - Parameters: `node_oid`, `worker_id`, `transport_id`, `path`, `service_config`
  - Returns: Started service details

- **`stop_web_transport_service`** - Stop web service
  - Parameters: `node_oid`, `worker_id`, `transport_id`, `path`
  - Returns: Stop confirmation

### Component Management

- **`get_router_components`** - List components
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of component IDs

- **`get_router_component`** - Get component details
  - Parameters: `node_oid`, `worker_id`, `component_id`
  - Returns: Component configuration

- **`start_router_component`** - Start component
  - Parameters: `node_oid`, `worker_id`, `component_id`, `component_config`
  - Returns: Started component details

- **`stop_router_component`** - Stop component
  - Parameters: `node_oid`, `worker_id`, `component_id`
  - Returns: Stop confirmation

### Realm Link Management

- **`get_router_realm_links`** - List realm links
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of realm link IDs

- **`get_router_realm_link`** - Get realm link details
  - Parameters: `node_oid`, `worker_id`, `link_id`
  - Returns: Realm link configuration

- **`start_router_realm_link`** - Start realm link
  - Parameters: `node_oid`, `worker_id`, `link_id`, `link_config`
  - Returns: Started realm link details

- **`stop_router_realm_link`** - Stop realm link
  - Parameters: `node_oid`, `worker_id`, `link_id`
  - Returns: Stop confirmation

### Events

- **`on_router_realm_starting`**, **`on_router_realm_started`**
- **`on_router_realm_stopping`**, **`on_router_realm_stopped`**
- **`on_router_realm_role_starting`**, **`on_router_realm_role_started`**
- **`on_router_realm_role_stopping`**, **`on_router_realm_role_stopped`**
- **`on_router_transport_starting`**, **`on_router_transport_started`**
- **`on_router_transport_stopping`**, **`on_router_transport_stopped`**
- **`on_web_transport_service_starting`**, **`on_web_transport_service_started`**
- **`on_web_transport_service_stopping`**, **`on_web_transport_service_stopped`**
- **`on_router_component_starting`**, **`on_router_component_started`**
- **`on_router_component_stopping`**, **`on_router_component_stopped`**

---

## Remote Container Management API

**Prefix:** `crossbarfabriccenter.remote.container.`

These APIs manage container workers on remote nodes. All procedures require `node_oid` and `worker_id` parameters.

### Component Management

- **`get_components`** - List container components
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of component IDs

- **`get_component`** - Get component details
  - Parameters: `node_oid`, `worker_id`, `component_id`
  - Returns: Component configuration

- **`start_component`** - Start component
  - Parameters: `node_oid`, `worker_id`, `component_id`, `component_config`
  - Returns: Started component details

- **`stop_component`** - Stop component
  - Parameters: `node_oid`, `worker_id`, `component_id`
  - Returns: Stop confirmation

### Events

- **`on_container_component_starting`**, **`on_container_component_started`**
- **`on_container_component_stopping`**, **`on_container_component_stopped`**

---

## Remote Proxy Management API

**Prefix:** `crossbarfabriccenter.remote.proxy.`

These APIs manage proxy workers on remote nodes. All procedures require `node_oid` and `worker_id` parameters.

### Transport Management

- **`get_proxy_transports`** - List proxy transports
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of transport IDs

- **`get_proxy_transport`** - Get transport details
  - Parameters: `node_oid`, `worker_id`, `transport_id`
  - Returns: Transport configuration

- **`start_proxy_transport`** - Start transport
  - Parameters: `node_oid`, `worker_id`, `transport_id`, `transport_config`
  - Returns: Started transport details

- **`stop_proxy_transport`** - Stop transport
  - Parameters: `node_oid`, `worker_id`, `transport_id`
  - Returns: Stop confirmation

### Web Service Management

- **`get_web_transport_services`** - List web services
  - Parameters: `node_oid`, `worker_id`, `transport_id`
  - Returns: List of service paths

- **`get_web_transport_service`** - Get service details
  - Parameters: `node_oid`, `worker_id`, `transport_id`, `path`
  - Returns: Service configuration

- **`start_web_transport_service`** - Start service
  - Parameters: `node_oid`, `worker_id`, `transport_id`, `path`, `service_config`
  - Returns: Started service details

- **`stop_web_transport_service`** - Stop service
  - Parameters: `node_oid`, `worker_id`, `transport_id`, `path`
  - Returns: Stop confirmation

### Route Management

- **`get_proxy_routes`** - List routes
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of route IDs

- **`get_proxy_realm_route`** - Get realm route
  - Parameters: `node_oid`, `worker_id`, `route_id`
  - Returns: Route configuration

- **`list_proxy_realm_routes`** - List realm routes
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of realm route IDs

- **`start_proxy_realm_route`** - Start route
  - Parameters: `node_oid`, `worker_id`, `route_id`, `route_config`
  - Returns: Started route details

- **`stop_proxy_realm_route`** - Stop route
  - Parameters: `node_oid`, `worker_id`, `route_id`
  - Returns: Stop confirmation

### Connection Management

- **`get_proxy_connections`** - List connections
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of connection IDs

- **`get_proxy_connection`** - Get connection details
  - Parameters: `node_oid`, `worker_id`, `connection_id`
  - Returns: Connection status and statistics

- **`start_proxy_connection`** - Start connection
  - Parameters: `node_oid`, `worker_id`, `connection_id`, `connection_config`
  - Returns: Started connection details

- **`stop_proxy_connection`** - Stop connection
  - Parameters: `node_oid`, `worker_id`, `connection_id`
  - Returns: Stop confirmation

### Events

- **`on_proxy_transport_starting`**, **`on_proxy_transport_started`**
- **`on_proxy_transport_stopping`**, **`on_proxy_transport_stopped`**

---

## Remote Tracing API

**Prefix:** `crossbarfabriccenter.remote.tracing.`

These APIs manage distributed tracing on remote nodes. All procedures require `node_oid` and `worker_id` parameters.

### Trace Management

- **`get_traces`** - List traces
  - Parameters: `node_oid`, `worker_id`
  - Returns: List of trace IDs

- **`get_trace`** - Get trace details
  - Parameters: `node_oid`, `worker_id`, `trace_id`
  - Returns: Trace configuration and status

- **`start_trace`** - Start trace
  - Parameters: `node_oid`, `worker_id`, `trace_id`, `trace_config`
  - Returns: Started trace details

- **`stop_trace`** - Stop trace
  - Parameters: `node_oid`, `worker_id`, `trace_id`
  - Returns: Stop confirmation with collected data summary

- **`get_trace_data`** - Get trace data
  - Parameters: `node_oid`, `worker_id`, `trace_id`, `limit` (optional)
  - Returns: Collected trace records

### Events

- **`on_trace_started`** - Trace session started
- **`on_trace_stopped`** - Trace session stopped
- **`on_trace_data`** - Trace data collected (streaming)

---

## Remote WAMP Meta API

**Prefix:** `crossbarfabriccenter.remote.realm.meta.`

This API forwards standard WAMP meta API calls to remote router realms. All procedures require `node_id`, `worker_id`, and `realm_id` parameters.

### Standard WAMP Meta API Procedures

**Session Management:**
- **`wamp.session.list`** - List all sessions
- **`wamp.session.get`** - Get session details
- **`wamp.session.count`** - Count active sessions

**Registration Management:**
- **`wamp.registration.list`** - List all registrations
- **`wamp.registration.get`** - Get registration details
- **`wamp.registration.lookup`** - Lookup registrations by URI
- **`wamp.registration.match`** - Match URI against registrations
- **`wamp.registration.list_callees`** - List callees for registration
- **`wamp.registration.count_callees`** - Count callees

**Subscription Management:**
- **`wamp.subscription.list`** - List all subscriptions
- **`wamp.subscription.get`** - Get subscription details
- **`wamp.subscription.lookup`** - Lookup subscriptions by URI
- **`wamp.subscription.match`** - Match URI against subscriptions
- **`wamp.subscription.list_subscribers`** - List subscribers
- **`wamp.subscription.count_subscribers`** - Count subscribers

### Standard WAMP Meta API Events

**Session Events:**
- **`wamp.session.on_join`** - Session joined realm
- **`wamp.session.on_leave`** - Session left realm

**Registration Events:**
- **`wamp.registration.on_create`** - Registration created
- **`wamp.registration.on_register`** - Callee registered
- **`wamp.registration.on_unregister`** - Callee unregistered
- **`wamp.registration.on_delete`** - Registration deleted

**Subscription Events:**
- **`wamp.subscription.on_create`** - Subscription created
- **`wamp.subscription.on_subscribe`** - Subscriber subscribed
- **`wamp.subscription.on_unsubscribe`** - Subscriber unsubscribed
- **`wamp.subscription.on_delete`** - Subscription deleted

---

## Usage Examples

### Connection Setup

```bash
# Set master node URL
export CROSSBAR_FABRIC_URL="ws://localhost:9000/ws"

# Authenticate with existing key
crossbar shell auth

# Or authenticate with specific key
crossbar shell auth --key ~/.crossbar/my-key.priv
```

### Python Client Example

```python
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.types import PublishOptions
from twisted.internet.defer import inlineCallbacks
import txaio

class MasterClient(ApplicationSession):
    
    @inlineCallbacks
    def onJoin(self, details):
        print(f"Connected to {details.realm}")
        
        # List all management realms
        mrealms = yield self.call('crossbarfabriccenter.mrealm.list_mrealms')
        print(f"Management realms: {mrealms}")
        
        # Get realm details
        realm = yield self.call('crossbarfabriccenter.mrealm.get_mrealm_by_name', 
                                'my-realm')
        print(f"Realm: {realm}")
        
        # List nodes in realm
        nodes = yield self.call('crossbarfabriccenter.mrealm.list_nodes_by_mrealm_name',
                               'my-realm')
        print(f"Nodes: {nodes}")
        
        self.leave()

# Connection configuration with cryptosign
from autobahn.wamp import cryptosign

key = cryptosign.CryptosignKey.from_file('~/.crossbar/default.priv')

config = ComponentConfig(
    realm='com.crossbario.fabric',
    extra={
        'key': key,
    }
)
```

### CLI Examples

```bash
# List management realms
crossbar shell call crossbarfabriccenter.mrealm.list_mrealms

# Pair a new node
crossbar shell call crossbarfabriccenter.mrealm.pair_node \
  --kwarg pubkey=a1b2c3... \
  --kwarg realm_name=my-realm \
  --kwarg authid=edge-node-1

# Get node status (requires node OID from pairing)
crossbar shell call crossbarfabriccenter.remote.node.get_status \
  --arg node_oid=550e8400-e29b-41d4-a716-446655440000

# List workers on node
crossbar shell call crossbarfabriccenter.remote.node.get_workers \
  --arg node_oid=550e8400-e29b-41d4-a716-446655440000

# Start router realm on remote node
crossbar shell call crossbarfabriccenter.remote.router.start_router_realm \
  --arg node_oid=550e8400-e29b-41d4-a716-446655440000 \
  --arg worker_id=router-001 \
  --arg realm_id=realm1 \
  --kwarg '{"name": "realm1", "roles": [...]}'

# Subscribe to node events
crossbar shell subscribe crossbarfabriccenter.remote.node.on_node_heartbeat
```

### JavaScript/TypeScript Example

```javascript
const autobahn = require('autobahn');
const cryptosign = require('autobahn-cryptosign');

// Load Ed25519 key
const key = cryptosign.load_key('~/.crossbar/default.priv');

const connection = new autobahn.Connection({
    url: 'ws://localhost:9000/ws',
    realm: 'com.crossbario.fabric',
    authmethods: ['cryptosign'],
    authid: 'user@example.com',
    authextra: {
        pubkey: key.pubkey,
    },
    onchallenge: (session, method, extra) => {
        return cryptosign.sign_challenge(key, extra.challenge);
    }
});

connection.onopen = async (session) => {
    console.log('Connected!');
    
    // List management realms
    const mrealms = await session.call('crossbarfabriccenter.mrealm.list_mrealms');
    console.log('Management realms:', mrealms);
    
    // Subscribe to node heartbeats
    await session.subscribe('crossbarfabriccenter.remote.node.on_node_heartbeat',
        (args, kwargs, details) => {
            console.log('Node heartbeat:', kwargs);
        }
    );
};

connection.open();
```

---

## Authentication Details

### Cryptosign Authentication Flow

1. **Client connects** to WebSocket endpoint
2. **Client sends HELLO** with:
   - `authmethod: 'cryptosign'`
   - `authextra.pubkey`: Ed25519 public key (hex)
   - `authextra.channel_binding`: 'tls-unique' (for TLS)

3. **Server responds with CHALLENGE** containing:
   - `challenge`: 32 random bytes (hex)
   - `channel_binding`: Requested binding type

4. **Client signs challenge**:
   - If channel binding: `signature = sign(challenge ⊕ channel_id)`
   - Else: `signature = sign(challenge)`
   - Concatenates: `signed_message = signature + challenge`

5. **Client sends AUTHENTICATE** with:
   - `signature`: Signed message (96 bytes hex)

6. **Server verifies signature** and:
   - Looks up user/node by pubkey in database
   - Assigns realm, authid, authrole
   - Returns WELCOME message

### Superuser Authentication

For development, you can bypass database authentication:

```bash
# Generate superuser key
crossbar keys --generate

# Set environment variable
export CROSSBAR_FABRIC_SUPERUSER=~/.crossbar/key.pub

# Restart master - superuser can authenticate instantly
crossbar start --config=master-config.json
```

---

## Error Codes

Common ApplicationError URIs returned by the API:

- `wamp.error.invalid_argument` - Invalid parameter type or value
- `wamp.error.no_such_procedure` - Procedure not registered
- `wamp.error.not_authorized` - Insufficient permissions
- `crossbar.error.no_such_object` - Object not found (by OID)
- `crossbar.error.already_exists` - Object with name/ID already exists
- `fabric.auth-failed.node-unpaired` - Node not paired with realm
- `fabric.auth-failed.new-user-auth-code-sent` - New user, activation code sent
- `fabric.auth-failed.registered-user-auth-code-sent` - Existing user, new activation

---

## Performance Considerations

### Database Authentication Delay

The master node uses LMDB database for user/node authentication. First-time lookups may take 5-30 seconds on slow disks. Solutions:

1. **Use superuser authentication** for development
2. **Enable SSD caching** for database directory
3. **Pre-warm database** with common queries
4. **Increase database maxsize** in config (default: 128 MB)

### Connection Pooling

For high-throughput management applications:

- Maintain persistent WAMP session (don't reconnect per operation)
- Use batched calls with `session.call_many()`
- Enable WAMP batching transport option
- Use CBOR or MsgPack serializers (faster than JSON)

### Remote Call Latency

Remote API calls add network round-trips:
- Master → Node: 1 RTT
- If node needs to query worker: +1 RTT
- Total latency typically 10-100ms depending on network

---

## See Also

- [Crossbar.io Documentation](https://crossbar.io/docs/)
- [WAMP Protocol Specification](https://wamp-proto.org/)
- [WAMP-Cryptosign Specification](https://wamp-proto.org/wamp_latest_ietf.html#name-cryptosign)
- [Autobahn WAMP Libraries](https://crossbar.io/autobahn/)

---

**Version:** Master Node API v24.10.1  
**Last Updated:** October 2025  
**License:** Crossbar.io is licensed under EUPL-1.2
