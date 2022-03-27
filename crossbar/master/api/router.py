###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ('RemoteRouterApi', )


class RemoteRouterApi(RemoteApi):

    # remote procedures and topics are exposed under this prefix
    PREFIX = u'crossbarfabriccenter.remote.router.'

    PROCS = {
        # these are worker level procedures
        u'worker': [
            u'get_router_realms',
            u'get_router_realm',
            u'get_router_realm_stats',
            u'get_router_realm_by_name',
            u'start_router_realm',
            u'stop_router_realm',
            u'get_router_realm_roles',
            u'get_router_realm_role',
            u'start_router_realm_role',
            u'stop_router_realm_role',
            u'get_router_transports',
            u'get_router_transport',
            u'start_router_transport',
            u'stop_router_transport',
            u'get_web_transport_services',
            u'get_web_transport_service',
            u'start_web_transport_service',
            u'stop_web_transport_service',
            u'get_router_components',
            u'get_router_component',
            u'start_router_component',
            u'stop_router_component',
            u'get_router_realm_links',
            u'get_router_realm_link',
            u'start_router_realm_link',
            u'stop_router_realm_link',
        ],
    }

    EVENTS = {
        # these are worker level topics
        u'worker': [
            u'on_router_realm_starting',
            u'on_router_realm_started',
            u'on_router_realm_stopping',
            u'on_router_realm_stopped',
            u'on_router_realm_role_starting',
            u'on_router_realm_role_started',
            u'on_router_realm_role_stopping',
            u'on_router_realm_role_stopped',
            u'on_router_transport_starting',
            u'on_router_transport_started',
            u'on_router_transport_stopping',
            u'on_router_transport_stopped',
            u'on_web_transport_service_starting',
            u'on_web_transport_service_started',
            u'on_web_transport_service_stopping',
            u'on_web_transport_service_stopped',
            u'on_router_component_starting',
            u'on_router_component_started',
            u'on_router_component_stopping',
            u'on_router_component_stopped',
        ]
    }
