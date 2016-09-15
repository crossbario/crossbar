title: CDC API Status
toc: [Documentation, CDC, CDC API Status]

# CDC API Status

## cdc.manage

**Procedures**

Users

* `[ ]` **`cdc.manage.create_user@1`**`(<user_name>, <user_email>, <user_pubkey>)`

Realms

* `[ ]` **`cdc.manage.create_realm@1`**`(<management_realm>, <owner_pubkey>)`
* `[ ]` **`cdc.manage.register_user@1`**`(<management_realm>, <user_pubkey>, <user_role>, <user_extra>)`
* `[ ]` **`cdc.manage.register_node@1`**`(<management_realm>, <node_pubkey>, <node_id>, <node_extra>)`

Verification

* `[ ]` **`cdc.manage.verify@1`**`(<verification_id>, <token>)`

**Events**

* `[ ]` **`cdc.manage.on_user_created@1`**
* `[ ]` **`cdc.manage.on_realm_created@1`**
* `[ ]` **`cdc.manage.on_user_registered@1`**
* `[ ]` **`cdc.manage.on_node_registered@1`**


## cdc.remote

**Procedures**

Global

* `[ ]` **`cdc.remote.status@1`**`()`

Nodes

* `[ ]` **`cdc.remote.list_nodes@1`**`()`
* `[ ]` **`cdc.remote.query_node@1`**`(<node_id>)`
* `[ ]` **`cdc.remote.stop_node@1`**`(<node_id>)`

Configs

* `[ ]` **`cdc.remote.save_config@1`**`(<node_id>)`
* `[ ]` **`cdc.remote.upload_config@1`**`(<node_id>, <node_config>)`
* `[ ]` **`cdc.remote.download_config@1`**`(<node_id>)`

Workers

* `[ ]` **`cdc.remote.list_workers@1`**`(<node_id>)`
* `[ ]` **`cdc.remote.query_worker@1`**`(<node_id>, <worker_id>)`
* `[ ]` **`cdc.remote.start_worker@1`**`(<node_id>, <worker_id>, <worker_config>)`
* `[ ]` **`cdc.remote.stop_worker@1`**`(<node_id>, <worker_id>)`

Logs

* `[ ]` **`cdc.remote.query_worker_log@1`**`(<node_id>, <worker_id>, <limit=50>)`
* `[ ]` **`cdc.remote.map_worker_log_topic@1`**`(<node_id>, <worker_id>)`

Limits

* `[ ]` **`cdc.remote.list_limits@1`**`(<node_id>, <worker_id>)`
* `[ ]` **`cdc.remote.get_limit@1`**`(<node_id>, <worker_id>, <limit_id>)`
* `[ ]` **`cdc.remote.set_limit@1`**`(<node_id>, <worker_id>, <limit_id>, <setting>)`

Profiles

* `[ ]` **`cdc.remote.list_profiles@1`**`(<node_id>, <worker_id>, <filter_running=False>)`
* `[ ]` **`cdc.remote.query_profile@1`**`(<node_id>, <worker_id>, <profile_id>)`
* `[ ]` **`cdc.remote.start_profile@1`**`(<node_id>, <worker_id>, <profile_id>, <profile_config>)`
* `[ ]` **`cdc.remote.stop_profile@1`**`(<node_id>, <worker_id>, <profile_id>)`

Realms

* `[ ]` **`cdc.remote.list_realms@1`**`(<node_id>, <worker_id>)`
* `[ ]` **`cdc.remote.query_realm@1`**`(<node_id>, <worker_id>, <realm_id>)`
* `[ ]` **`cdc.remote.start_realm@1`**`(<node_id>, <worker_id>, <realm_id>, <realm_config>)`
* `[ ]` **`cdc.remote.stop_realm@1`**`(<node_id>, <worker_id>, <realm_id>)`

Roles

* `[ ]` **`cdc.remote.list_roles@1`**`(<node_id>, <worker_id>, <realm_id>)`
* `[ ]` **`cdc.remote.query_role@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>)`
* `[ ]` **`cdc.remote.start_role@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>, <role_config>)`
* `[ ]` **`cdc.remote.stop_role@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>)`

Grants

* `[ ]` **`cdc.remote.list_grants@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>)`
* `[ ]` **`cdc.remote.query_grant@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>, <grant_id>)`
* `[ ]` **`cdc.remote.start_grant@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>, <grant_id>, <grant_config>)`
* `[ ]` **`cdc.remote.stop_grant@1`**`(<node_id>, <worker_id>, <realm_id>, <role_id>, <grant_id>)`

Transports

* `[ ]` **`cdc.remote.list_transports@1`**`(<node_id>, <worker_id>)`
* `[ ]` **`cdc.remote.query_transport@1`**`(<node_id>, <worker_id>, <transport_id>)`
* `[ ]` **`cdc.remote.start_transport@1`**`(<node_id>, <worker_id>, <transport_id>, <transport_config>)`
* `[ ]` **`cdc.remote.stop_transport@1`**`(<node_id>, <worker_id>, <transport_id>)`

Web Resources

* `[ ]` **`cdc.remote.list_web_resources@1`**`(<node_id>, <worker_id>, <transport_id>)`
* `[ ]` **`cdc.remote.query_web_resource@1`**`(<node_id>, <worker_id>, <transport_id>, <web_resource_id>)`
* `[ ]` **`cdc.remote.start_web_resource@1`**`(<node_id>, <worker_id>, <transport_id>, <web_resource_id>, <web_resource_config>)`
* `[ ]` **`cdc.remote.stop_web_resource@1`**`(<node_id>, <worker_id>, <transport_id>, <web_resource_id>)`

Components

* `[ ]` **`cdc.remote.list_components@1`**`(<node_id>, <worker_id>)`
* `[ ]` **`cdc.remote.query_component@1`**`(<node_id>, <worker_id>, <component_id>)`
* `[ ]` **`cdc.remote.start_component@1`**`(<node_id>, <worker_id>, <component_id>, <component_config>)`
* `[ ]` **`cdc.remote.stop_component@1`**`(<node_id>, <worker_id>, <component_id>)`

**Events**

* `[ ]` **`cdc.remote.on_node_status@1`**
* `[ ]` **`cdc.remote.on_worker_status@1`**
* `[ ]` **`cdc.remote.on_limit_set@1`**
* `[ ]` **`cdc.remote.on_profile_status@1`**
* `[ ]` **`cdc.remote.on_realm_status@1`**
* `[ ]` **`cdc.remote.on_role_status@1`**
* `[ ]` **`cdc.remote.on_grant_status@1`**
* `[ ]` **`cdc.remote.on_transport_status@1`**
* `[ ]` **`cdc.remote.on_web_resource_status@1`**
* `[ ]` **`cdc.remote.on_component_status@1`**
