# Crossbar.io Management API

This document lists calls which form part of the Crossbar.io management API.

It is provided as a convenience, and is not a definition of the API or intended as a documentation.

The management API is not intended for public use. It is used both internally for management of Crossbar.io when parsing a local config, and for remote management using a cloud service which we will provide.

For your rights regarding the use of this API see "LICENSE-FOR-API" in the root directory of this repository.

## Procedures

`crossbar.node.<node_id>.get_info`
`crossbar.node.<node_id>.shutdown`
`crossbar.node.<node_id>.utcnow`
`crossbar.node.<node_id>.started`
`crossbar.node.<node_id>.uptime`
`crossbar.node.<node_id>.trigger_gc`
`crossbar.node.<node_id>.get_workers`
`crossbar.node.<node_id>.get_worker_log`
`crossbar.node.<node_id>.start_router`
`crossbar.node.<node_id>.stop_router`
`crossbar.node.<node_id>.start_container`
`crossbar.node.<node_id>.stop_container`
`crossbar.node.<node_id>.start_guest`
`crossbar.node.<node_id>.stop_guest`
`crossbar.node.<node_id>.start_websocket_testee`
`crossbar.node.<node_id>.stop_websocket_testee`
`crossbar.node.<node_id>.get_process_info`
`crossbar.node.<node_id>.get_process_stats`
`crossbar.node.<node_id>.set_process_stats_monitoring`
`crossbar.node.<node_id>.start_manhole`
`crossbar.node.<node_id>.stop_manhole`
`crossbar.node.<node_id>.get_manhole`
`crossbar.node.<node_id>.worker.<worker_id>.utcnow`
`crossbar.node.<node_id>.worker.<worker_id>.utcnow`
`crossbar.node.<node_id>.worker.<worker_id>.started`
`crossbar.node.<node_id>.worker.<worker_id>.uptime`
`crossbar.node.<node_id>.worker.<worker_id>.trigger_gc`
`crossbar.node.<node_id>.worker.<worker_id>.get_pythonpath`
`crossbar.node.<node_id>.worker.<worker_id>.add_pythonpath`
`crossbar.node.<node_id>.worker.<worker_id>.get_profilers`
`crossbar.node.<node_id>.worker.<worker_id>.start_profiler`
`crossbar.node.<node_id>.worker.<worker_id>.get_profile`
`crossbar.node.<node_id>.worker.<worker_id>.get_process_info`
`crossbar.node.<node_id>.worker.<worker_id>.get_process_stats`
`crossbar.node.<node_id>.worker.<worker_id>.set_process_stats_monitoring`
`crossbar.node.<node_id>.worker.<worker_id>.get_cpu_count`
`crossbar.node.<node_id>.worker.<worker_id>.get_cpu_affinity`
`crossbar.node.<node_id>.worker.<worker_id>.set_cpu_affinity`
`crossbar.node.<node_id>.worker.<worker_id>.start_manhole`
`crossbar.node.<node_id>.worker.<worker_id>.stop_manhole`
`crossbar.node.<node_id>.worker.<worker_id>.get_manhole
`crossbar.node.<node_id>.worker.<worker_id>.get_router_realms`
`crossbar.node.<node_id>.worker.<worker_id>.start_router_realm`
`crossbar.node.<node_id>.worker.<worker_id>.stop_router_realm`
`crossbar.node.<node_id>.worker.<worker_id>.get_router_realm_roles`
`crossbar.node.<node_id>.worker.<worker_id>.start_router_realm_role`
`crossbar.node.<node_id>.worker.<worker_id>.stop_router_realm_role`
`crossbar.node.<node_id>.worker.<worker_id>.get_router_realm_uplinks`
`crossbar.node.<node_id>.worker.<worker_id>.start_router_realm_uplink`
`crossbar.node.<node_id>.worker.<worker_id>.stop_router_realm_uplink`
`crossbar.node.<node_id>.worker.<worker_id>.get_router_components`
`crossbar.node.<node_id>.worker.<worker_id>.start_router_component`
`crossbar.node.<node_id>.worker.<worker_id>.stop_router_component`
`crossbar.node.<node_id>.worker.<worker_id>.get_router_transports`
`crossbar.node.<node_id>.worker.<worker_id>.start_router_transport`
`crossbar.node.<node_id>.worker.<worker_id>.stop_router_transport`
`crossbar.node.<node_id>.worker.<worker_id>.get_container_components`
`crossbar.node.<node_id>.worker.<worker_id>.start_container_component`
`crossbar.node.<node_id>.worker.<worker_id>.stop_container_component`
`crossbar.node.<node_id>.worker.<worker_id>.restart_container_component`
`crossbar.node.<node_id>.worker.<worker_id>.stop_container`


## Events

`crossbar.on_node_ready`
`crossbar.node.<node_id>.on_process_stats_monitoring_set`
`crossbar.node.<node_id>.on_process_stats`
`crossbar.node.<node_id>.on_manhole_starting`
`crossbar.node.<node_id>.on_manhole_started`
`crossbar.node.<node_id>.on_manhole_stopping`
`crossbar.node.<node_id>.on_manhole_stopped`
`crossbar.node.<node_id>.on_worker_ready`
`crossbar.node.<node_id>.worker.<worker_id>.on_pythonpath_add`
`crossbar.node.<node_id>.worker.<worker_id>.on_cpu_affinity_set`
`crossbar.node.<node_id>.worker.<worker_id>.on_manhole_starting`
`crossbar.node.<node_id>.worker.<worker_id>.on_manhole_started`
`crossbar.node.<node_id>.worker.<worker_id>.on_manhole_stopping`
`crossbar.node.<node_id>.worker.<worker_id>.on_manhole_stopped





## Errors

`crossbar.error.feature_unavailable`
`crossbar.error.already_started`
`crossbar.error.invalid_configuration`
`crossbar.error.cannot_listen`
`crossbar.error.not_started`
`crossbar.error.invalid_argument`
`crossbar.error.runtime_error`
`crossbar.error.cannot_listen`




