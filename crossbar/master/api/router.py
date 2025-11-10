###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ("RemoteRouterApi",)


class RemoteRouterApi(RemoteApi):
    # remote procedures and topics are exposed under this prefix
    PREFIX = "crossbarfabriccenter.remote.router."

    PROCS = {
        # these are worker level procedures
        "worker": [
            "get_router_realms",
            "get_router_realm",
            "get_router_realm_stats",
            "get_router_realm_by_name",
            "start_router_realm",
            "stop_router_realm",
            "get_router_realm_roles",
            "get_router_realm_role",
            "start_router_realm_role",
            "stop_router_realm_role",
            "get_router_transports",
            "get_router_transport",
            "start_router_transport",
            "stop_router_transport",
            "get_web_transport_services",
            "get_web_transport_service",
            "start_web_transport_service",
            "stop_web_transport_service",
            "get_router_components",
            "get_router_component",
            "start_router_component",
            "stop_router_component",
            "get_router_realm_links",
            "get_router_realm_link",
            "start_router_realm_link",
            "stop_router_realm_link",
        ],
    }

    EVENTS = {
        # these are worker level topics
        "worker": [
            "on_router_realm_starting",
            "on_router_realm_started",
            "on_router_realm_stopping",
            "on_router_realm_stopped",
            "on_router_realm_role_starting",
            "on_router_realm_role_started",
            "on_router_realm_role_stopping",
            "on_router_realm_role_stopped",
            "on_router_transport_starting",
            "on_router_transport_started",
            "on_router_transport_stopping",
            "on_router_transport_stopped",
            "on_web_transport_service_starting",
            "on_web_transport_service_started",
            "on_web_transport_service_stopping",
            "on_web_transport_service_stopped",
            "on_router_component_starting",
            "on_router_component_started",
            "on_router_component_stopping",
            "on_router_component_stopped",
        ]
    }
