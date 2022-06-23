###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ('RemoteProxyApi', )


class RemoteProxyApi(RemoteApi):

    PREFIX = 'crossbarfabriccenter.remote.proxy.'

    PROCS = {
        # these are worker level procedures
        'worker': [
            'get_proxy_transports',
            'get_proxy_transport',
            'start_proxy_transport',
            'stop_proxy_transport',
            'get_web_transport_services',
            'get_web_transport_service',
            'start_web_transport_service',
            'stop_web_transport_service',
            'get_proxy_routes',
            'get_proxy_realm_route',
            'list_proxy_realm_routes',
            'start_proxy_realm_route',
            'stop_proxy_realm_route',
            'get_proxy_connections',
            'get_proxy_connection',
            'start_proxy_connection',
            'stop_proxy_connection',
        ],
    }

    EVENTS = {
        # these are worker level topics
        'worker': [
            'on_proxy_transport_starting',
            'on_proxy_transport_started',
            'on_proxy_transport_stopping',
            'on_proxy_transport_stopped',
        ]
    }
