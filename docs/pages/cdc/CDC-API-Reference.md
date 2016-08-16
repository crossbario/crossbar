title: CDC API Reference
toc: [Documentation, CDC, CDC API Reference]

# CDC API Reference

This is a complete reference of the public API of Crossbar.io DevOps Center (CDC). This API is intended to be used by Crossbar.io users for management of Crossbar.io based solutions directly from within applications and from user tools for automation.

> **WARNING** CDC is currently in pre-alpha phase - a lot of stuff does not work yet and is still in flux. Read the **[API Status](CDC API Status)**.

* [Top](#cdc-api-reference)
    * [Notation](#notation)
    * [Names and IDs](#names-and-ids)
    * [API Versioning](#api-versioning)
* [User and Realm Management](#user-and-realm-management)
    * [Creating Users](#creating-users)
    * [Creating Realms](#creating-realms)
    * [Registering Users](#registering-users)
    * [Pairing Nodes](#pairing-nodes)
* [Remote Node API](#remote-node-api)
    * [Managing Nodes](#nodes)
        * [Configuration Files](#configuration-files)
    * [Managing Workers](#workers)
        * [Remote Log Access](#remote-log-access)
        * [Resource Limits](#resource-limits)
        * [Profiling Workers](#profiling)
    * [Managing Routers](#routers)
        * [Router Realms](#realms)
            * [Roles](#roles)
            * [Role Grants](#grants)
        * [Router Transports](#transports)
            * [Web Resources](#web-resources)
        * [Router Components](#components)

---

### Notation

We use the following notation to denote the URI of a procedure or topic:

* **`cdc.remote.query_node@1`**

The URI in this case is the string `cdc.remote.query_node@1` (including the `@1` at the end).

When denoting procedure parameters, we use the following notation:

* **`cdc.remote.query_node@1`**`(<node_id>)`

This denotes a procedure that takes a single, mandatory, positional parameter named `node_id`. The further meaning and allowed types and values are described in the procedure documentation block.

### Names and IDs

When not otherwise mentioned, IDs and names in the CDC API must match the following regular expressions:

* IDs of nodes, workers, transports, ..: `^[a-z][a-z0-9_]{2,11}$`
* Names of users, realms: `^[A-Za-z][A-Za-z0-9_\-@\.]{2,254}$`

### API Versioning

We are using the following scheme for **versioning** in the API

* `cdc.some_proc@1()` - Original procedure signature
* `cdc.some_proc@2(<filter_status>)` - Revised procedure signature or semantics.
* `cdc.some_proc@3(<filter_type>, <filter_status>)` - Third revision of the procedure.

> Every time the signature or the semantics of a procedure changes, the *revision* of the procedure is increased. CDC will try to make reasonable efforts to provide backward compatible procedure revisions. Thus, a procedure may be available in multiple revisions in parallel. This provides backward compatibility for CDC clients.

---

## User and Realm Management

With API based pairing, the owner of a management realm will be able to call CDC procedures which add, provision and configure Crossbar.io node public keys and CDC API client public keys allowed access to that management realm.

The management realm owner's key pair should be protected well, and only used to create day to day key pairs for administrators of the management realm itself.

### Creating Users

New users can be created using this procedure:

* **`cdc.manage.create_user@1`**`(<user_name>, <user_email>, <user_pubkey>)`

Create a new user and return a `<verification_id>`.

This initiates registration of a new user providing a user name, email and first public key. The user name is checked that is does not yet exist and meets the requirements for user names. When these conditions are met, a challenge in form of a graphical captcha with an embedded, token/PIN is sent via email to the email address provided.

The user will need to read the token/PIN from the captcha and enter that allowing to make the call to

* **`cdc.manage.verify@1`**`(<verification_id>, <token>)`

Verify a token/PIN code reveived for a pending user registration.

> **Security note.** Any client can call this. A successful call will make both the `<verification_id>` and the `token` be consumed, and the values cannot be reused. Upon an unsucessful call, the number of retries is limited per `<verification_id>` and per `<token>`.

When this call returns successfully, the user is created.

To register more public keys for the user, calls above procedure again with different public keys. This will send a challenge as well and proceed exactly like above.

### Creating Realms

To **create a new management realm**:

* **`cdc.manage.create_realm@1`**`(<management_realm>, <owner_pubkey>)`

Register a new management realm and return a `<verification_id>`.

The user with the given `<owner_pubkey>` will be sent a verification token/PIN and upon successful verification, become owner of the new realm.

The public key must have been registered before for a user, and the management realm must be valid and still be available. The registering owner's email address is already known, and used for sending a captcha with a PIN like above to the owner.

To verify the token/PIN code received and finalize the realm creation, call

* **`cdc.manage.verify@1`**`(<verification_id>, <token>)`

Verify a token/PIN code received for a pending realm creation.

> **Security note.** Any client can call this. A successful call will make both the `<verification_id>` and the `token` be consumed, and the values cannot be reused. Upon an unsucessful call, the number of retries is limited per `<verification_id>` and per `<token>`.

When this call returns successfully, the management realm is created. The owner of the management realm can manage the realm by allowing new Crossbar.io node public keys and CDC API client public keys access to the management realm under respective roles.

---

### Registering Users

To **register an CDC user with a management realm**:

* **`cdc.manage.register_user@1`**`(<management_realm>, <user_pubkey>, <user_role>, <user_extra>)`

Register a user on a management realm under a role and return a `<verification_id>`.

The user is granted rights on the management realm depending on `<user_role>`:

* `"guest"`
* `"devops"`
* `"admin"`

Optionally, custom extra information can be provided which is forwarded to the client during authentication.

> **Security note.** Only the owner of the respective management realm is authorized to call this procedure.

The owner of the management realm will be sent a verification token/PIN for the registration. To verify the token/PIN code received and finalize the node registration, call

* **`cdc.manage.verify@1`**`(<verification_id>, <token>)`

Verify a token/PIN code received for a pending user registration.

When this call returns successfully, the user is registered with the respective realm.


### Registering Nodes

To **register a Crossbar.io node with a management realm**:

* **`cdc.manage.register_node@1`**`(<management_realm>, <node_pubkey>, <node_id>, <node_extra>)`

Registers a Crossbar.io node and return a `<verification_id>`.

The `<node_id>` must be unique within the given management realm and must conform to the regular expression for names (see [here](#names-and-ids)).

Optionally, custom extra information can be provided which is forwarded to the node during authentication.

> **Security note.** Only the owner of the respective management realm is authorized to call this procedure.

The owner of the management realm will be sent a verification PIN for the node registration. To verify the PIN code received and finalize the node registration, call

* **`cdc.manage.verify@1`**`(<verification_id>, <token>)`

Verify a PIN code received for a pending node registration.

When this call returns successfully, the node is registered with the respective realm. The node will have `<node_id>` assigned and joined on the management realm under the role `"node"`.

---


## Remote Node API

### Global

**Procedures**

* **`cdc.remote.status@1`**`()`

Returns Crossbar.io management & monitoring API remoting service status information.

*Example (see [here](https://github.com/crossbario/crossbarexamples/blob/master/cdc/tut1.py)).*

```python
@inlineCallbacks
def main(session):
    try:
        status = yield session.call(u'cdc.remote.status@1')
    except:
        session.log.failure()
    else:
        realm = status[u'realm']
        now = status[u'now']
        print('Connected to CDC realm "{}", time is {}'.format(realm, now))
```

### Node Management

Crossbar.io nodes connected to CDC can be managed remotely. Provisioned nodes can be listed and queried:

**Procedures**

* **`cdc.remote.list_nodes@1`**`()`

Returns a list of ID of Crossbar.io nodes attached to this management realm.

* **`cdc.remote.query_node@1`**`(<node_id>)`

Get detailed info on a node provisioned on this management realm and remotely accessible.

* **`cdc.remote.stop_node@1`**`(<node_id>)`

Remotely shut down a node.

> Note that there is no way to remotely *start* a node (there is no `cdc.remote.start_node` procedure) - this should be done by the OS service startup system. The latter will (when configured correctly) automatically restart the Crossbar.io (as it does when the machine hosting the node boots).

**Events**

* **`cdc.remote.on_node_status@1`**

Fires when the status of a node changes (with a tuple `(node_id, old_status, new_status)` as event payload).

*Example (see [here](https://github.com/crossbario/crossbarexamples/blob/master/cdc/tut2.py)).*

```python
@inlineCallbacks
def main(session):
    try:
        # get list of provisioned nodes
        nodes = yield session.call(u'cdc.remote.list_nodes@1')

        for node_id in nodes:
            # get node status given node_id
            node_status = yield session.call(u'cdc.management.query_node@1',
                                             node_id)
            print('node "{}" is in status "{}"'.format(node_id, node_status))

        # our handler that will be called when a node changes status
        def on_node_status(node_id, old_status, new_status):
            print('node "{}"" changed state: "{}"" to "{}"'.format(node_id,
                                                                   old_status,
                                                                   new_status))

        yield session.subscribe(on_node_status,
                                u'cdc.remote.on_node_status@1')

        yield sleep(60)
    except:
        session.log.failure()
```

---

#### Configuration Files

To promote operational independence even when no uplink CDC connection is available, the complete current node configuration can be written to the local node configuration file. Doing so allows the node to recover into the same state even when restarting without a CDC connection.

**Procedures**

* **`cdc.remote.save_config@1`**`(<node_id>)`

Save the live node configuration to the current node configuration file (in an atomic operation).

* **`cdc.remote.upload_config@1`**`(<node_id>, <node_config>)`

Upload the given configuration to the current node configuration file.

* **`cdc.remote.download_config@1`**`(<node_id>)`

Download the current node configuration file. Note that the live node configuration may differ from the current node configuration file

> When the current configuration file has been modified via `cdc.remote.upload_config`, the live node configuration might be out of sync with the former. In this case the node must be shut down and restarted to bring both in sync.

---

### Worker Management

Crossbar.io nodes provide services via worker processes, of which there are three types:

* router workers
* container workers
* guest workers

Workers on nodes can be managed remotely:

**Procedures**

* **`cdc.remote.list_workers@1`**`(<node_id>)`

Returns a list of IDs of workers currently running on the given node.

* **`cdc.remote.query_worker@1`**`(<node_id>, <worker_id>)`

Get detailed info on a worker running on a node.

* **`cdc.remote.start_worker@1`**`(<node_id>, <worker_id>, <worker_config>)`

Remotely start a new worker on the node. A worker can be a router, container or guest worker.

* **`cdc.remote.stop_worker@1`**`(<node_id>, <worker_id>)`

Stop a worker currently running on the given node.

**Events**

* **`cdc.remote.on_worker_status@1`**

Fires when the status of a worker changes (with a tuple `(node_id, worker_id, old_status, new_status)` as event payload).

*Example (see [here](https://github.com/crossbario/crossbarexamples/blob/master/cdc/tut3.py)).*

```python
@inlineCallbacks
def main(session):
    try:
        # get all nodes in state "online"
        node_ids = yield session.call(u'cdc.remote.list_nodes@1',
                                      filter_status=u'online')

        for node_id in node_ids:
            # get workers for each node
            worker_ids = yield session.call(u'cdc.remote.list_workers@1',
                                            node_id)

            for worker_id in worker_ids:
                # query each worker found ..
                worker = yield session.call(u'cdc.remote.query_worker@1',
                                            node_id, worker_id)

                worker_type = worker[u'type']
                print('worker "{}"-"{}": "{}"'.format(node_id,
                                                      worker_id,
                                                      worker_type))
    except:
        session.log.failure()
```

---

#### Remote Log Access

The log output from any worker process started on any node can be remotely accessed.

**Procedures**

* **`cdc.remote.query_worker_log@1`**`(<node_id>, <worker_id>, <limit=50>)`

Get the last N lines of log output from the specified worker.

* **`cdc.remote.map_worker_log_topic@1`**`(<node_id>, <worker_id>)`

Get the (selective) topic on which the worker publishes log events. Subscribing to the returned topic will allow to selectively receive log events from only the single respective worker.

**Events**

* **`<worker_log_topic>`**

Fires when a worker writes a new log line.

*Example (see [here](https://github.com/crossbario/crossbarexamples/blob/master/cdc/tut5.py)).*

```python
@inlineCallbacks
def main(session):
    try:
        # retrieve log history of worker
        log = yield session.call(u'cdc.remote.query_worker_log@1',
                                 node_id, worker_id, 30)

        for log_rec in log:
            print(log_rec)

        # subscribe to live log stream from worker
        def on_worker_log(*args, **kwargs):
            print(args, kwargs)

        log_topic = yield session.call(u'cdc.remote.map_worker_log_topic@1',
                                       node_id, worker_id, 30)

        sub = yield session.subscribe(on_worker_log, log_topic)
        print('Listening to live log output ..')
    except:
        session.log.failure()
    else:
        yield sleep(15)
```

#### Resource Limits

Currently the only implemented worker resource control is *CPU affinity*.

**Procedures**

* **`cdc.remote.list_limits@1`**`(<node_id>, <worker_id>)`

Return list of IDs of resource limits for the given worker process.

* **`cdc.remote.get_limit@1`**`(<node_id>, <worker_id>, <limit_id>)`

Get detailed status of a resource limit in a given worker process.

* **`cdc.remote.set_limit@1`**`(<node_id>, <worker_id>, <limit_id>, <setting>)`

Set a resource limit on a worker resource limit. When `setting == null`, the resource limit is removed.

**Events**

* **`cdc.remote.on_limit_set@1`**

Fires when a limit on a worker changes (with a tuple `(node_id, worker_id, limit_id, old_setting, new_setting)` as event payload).


#### Profiling

Native workers such as routers and containers, with or without running user app components can be profiled using the builtin vmprof profiler.

**Procedures**

* **`cdc.remote.list_profiles@1`**`(<node_id>, <worker_id>, <filter_running=False>)`

Returns a list of tuples `<profile_id>, <profile_status>, <profile_ended>` of profiles previously run (or currently running) for the given worker process.

* **`cdc.remote.query_profile@1`**`(<profile_id>)`

Returns data from a previously run profile

* **`cdc.remote.start_profile@1`**`(<node_id>, <worker_id>, <profiler="vmprof">, <run_secs=10>, <run_async=True>)`

Start the specified profiler on the given worker returning a `<profile_id>`. The run-time must also be given. When the profile is done, it can be retrieved.

* **`cdc.remote.stop_profile@1`**`(<node_id>, <worker_id>, <profiler_id>)`

Stop a currently running profile.

**Events**

* **`cdc.remote.on_profile_status@1`**

Fires when a profile is started or ended (with a tuple `(node_id, worker_id, profile_id, profile_status)` as event payload).

---

### Routers

Crossbar.io **router workers** listen on **transports** providing routing for **realms**. The different features of router workers can be grouped into:

* [Realms](#realms), [Roles](#roles) and [Grants](#grants)
* [Transports](#transports) and [Web Resources](#web-resources)
* [Components](#router-and-container-components)

### Realms

A **realm** is a separate namespace and isolated routing domain.

**Procedures**

* **`cdc.remote.list_realms@1`**`(<node_id>, <worker_id>)`

Get list of IDs of realms started on a router worker on a node.

* **`cdc.remote.query_realm@1`**`(<node_id>, <worker_id>, <realm_id>)`

Get detailed info on a realm started on a router worker.

* **`cdc.remote.start_realm@1`**`(<node_id>, <worker_id>, <realm_id>, <realm_config>)`

Start a new routing realm on a router worker on a node.

* **`cdc.remote.stop_realm@1`**`(<node_id>, <worker_id>, <realm_id>)`

Stop a realm currently started on a router worker on some node.

**Events**

* **`cdc.remote.on_realm_status@1`**

Fires when the status of a realm changes (with a tuple `(node_id, worker_id, realm_id, old_status, new_status)` an event payload).

#### Roles

Clients connecting are authenicated under **roles** on **realms**.

**Procedures**

* **`cdc.remote.list_roles@1`**`(<node_id>, <worker_id>, <realm_id>)`

Get list of IDs of roles started on a realm on a router worker on a node.

* **`cdc.remote.query_role@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>)`

Get detailed info on a role started on a routing realm.

* **`cdc.remote.start_role@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>, <role_config>)`

Start a new role on a routing realm.

* **`cdc.remote.stop_role@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>)`

Stop a role running on a routing realm.

**Events**

* **`cdc.remote.on_role_status@1`**

Fires when the status of a role changes (with a tuple `(node_id, worker_id, realm_id, role_id, old_status, new_status)`.

#### Grants

A **role** on a **realm** provides **grants** to clients.

**Procedures**

* **`cdc.remote.list_grants@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>)`

Get list of IDs of grants started on the respective realm role.

* **`cdc.remote.query_grant@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>, <grant_id>)`

Get detailed status information on the respective grant.

* **`cdc.remote.start_grant@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>, <grant_id>, <grant_config>)`

Start a new grant on the respective role.

* **`cdc.remote.stop_role@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>, <grant_id>)`

Stop a currently running grant on a role.

**Events**

* **`cdc.remote.on_grant_status@1`**

Fires when the status of a grant changes (with a tuple `(node_id, worker_id, realm_id, role_id, old_status, new_status)`).

---

### Transports

Routers run listening **transports** for clients to connect. Transports can be remotely managed using the following API:

**Procedures**

* **`cdc.remote.list_transports@1`**`(<node_id>, <worker_id>)`

Get list of IDs of transports currently running in the specified router worker.

* **`cdc.remote.query_transport@1`**`(<node_id>, <worker_id>, <transport_id>)`

Get detailed status information on a transport running in a router worker.

* **`cdc.remote.start_transport@1`**`(<node_id>, <worker_id>, <transport_id>, <transport_config>)`

Start a new transport on a router worker.

* **`cdc.remote.stop_transport@1`**`(<node_id>, <worker_id>, <transport_id>)`

Stop the given transport currently running in a router worker.

**Events**

* **`cdc.remote.on_transport_status@1`**

Fires when the status of a transport changes (with a tuple `(node_id, worker_id, transport_id, old_status, new_status)`).

#### Web Resources

Certain transports like Web transports, or the Web transport subservice of a Unisocket transport can host **resources**, eg a static Web resource serving static files from a directory.

**Procedures**

* **`cdc.remote.list_web_resources@1`**`(<node_id>, <worker_id>, <transport_id>)`

Get list of IDs of Web resources running on the given Web or Unisocket transport.

* **`cdc.remote.query_web_resource@1`**`(<node_id>, <worker_id>, <transport_id>, <resource_id>)`

Get detailed status information on a Web resource running on a Web or Unisocket transport.

* **`cdc.remote.start_web_resource@1`**`(<node_id>, <worker_id>, <transport_id>, <resource_id>, <resource_config>)`

Start a new Web resource on the given Web or Unisocket transport.

* **`cdc.remote.stop_web_resource@1`**`(<node_id>, <worker_id>, <transport_id>, <resource_id>)`

Stop the specified Web resource currently running on the Web transport given.

**Events**

* **`cdc.remote.on_web_resource_status@1`**

Fires when the status of a Web resource changes (with a tuple `(node_id, worker_id, transport_id, resource_id, old_status, new_status)`).

---

### Router and Container Components

Router and container workers can optionally host WAMP application **components**. This feature allows to dynamically and remotely start and stop application components in Crossbar.io (native) workers:

**Procedures**

* **`cdc.remote.list_components@1`**`(<node_id>, <worker_id>)`

Get list of IDs of components currently running in the given router/container worker.

* **`cdc.remote.query_component@1`**`(<node_id>, <worker_id>, <component_id>)`

Get detailed status of a component currently running the the given router/container worker.

* **`cdc.remote.start_component@1`**`(<node_id>, <worker_id>, <component_id>, <component_config>)`

Start a new component in the given router/container worker.

* **`cdc.remote.stop_component@1`**`(<node_id>, <worker_id>, <component_id>)`

Stop a component currently running in the given router/container worker.

**Events**

* **`cdc.remote.on_component_status@1`**

Fires when the status of a component changes (with a tuple `(node_id, worker_id, component_id, old_status, new_status)` as event payload).

---
