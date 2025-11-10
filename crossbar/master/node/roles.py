###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

__all__ = ("BUILTIN_ROLES",)

BUILTIN_ROLES = {
    "node-role": {
        "name": "node",
        "permissions": [
            {
                "uri": "",
                "match": "prefix",
                "allow": {"call": True, "register": True, "publish": True, "subscribe": True},
                "disclose": {"caller": True, "publisher": True},
                "cache": True,
            }
        ],
    },
    "backend-role": {
        "name": "backend",
        "permissions": [
            {
                "uri": "",
                "match": "prefix",
                "allow": {"call": True, "register": True, "publish": True, "subscribe": True},
                "disclose": {"caller": True, "publisher": True},
                "cache": True,
            }
        ],
    },
    "public-role": {
        "name": "public",
        "permissions": [
            {
                "uri": "crossbarfabriccenter.mrealm.get_status",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {
                "uri": "crossbarfabriccenter.mrealm.get_nodes",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {
                "uri": "crossbarfabriccenter.remote.node.get_workers",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {
                "uri": "crossbarfabriccenter.remote.node.get_worker",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {
                "uri": "crossbarfabriccenter.remote.router.get_router_realms",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {
                "uri": "crossbarfabriccenter.remote.realm.meta.wamp.session.list",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {
                "uri": "crossbarfabriccenter.remote.realm.meta.wamp.session.get",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {"uri": "crossbarfabriccenter.remote.realm.meta.wamp.session.on_join", "allow": {"subscribe": True}},
            {"uri": "crossbarfabriccenter.remote.realm.meta.wamp.session.on_leave", "allow": {"subscribe": True}},
            {
                "uri": "crossbarfabriccenter.mrealm.tracing.get_traces",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {
                "uri": "crossbarfabriccenter.mrealm.tracing.get_trace",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {
                "uri": "crossbarfabriccenter.mrealm.tracing.get_trace_data",
                "allow": {"call": True},
                "disclose": {
                    "caller": True,
                },
            },
            {"uri": "crossbarfabriccenter.mrealm.tracing.on_trace_data", "allow": {"subscribe": True}},
            {"uri": "crossbarfabriccenter.mrealm.tracing.on_trace_created", "allow": {"subscribe": True}},
            {"uri": "crossbarfabriccenter.mrealm.tracing.on_trace_starting", "allow": {"subscribe": True}},
            {"uri": "crossbarfabriccenter.mrealm.tracing.on_trace_started", "allow": {"subscribe": True}},
            {"uri": "crossbarfabriccenter.mrealm.tracing.on_trace_stopping", "allow": {"subscribe": True}},
            {"uri": "crossbarfabriccenter.mrealm.tracing.on_trace_stopped", "allow": {"subscribe": True}},
            {"uri": "crossbarfabriccenter.mrealm.tracing.on_trace_deleted", "allow": {"subscribe": True}},
        ],
    },
    "owner-role": {
        "name": "owner",
        "permissions": [
            {
                "uri": "",
                "match": "prefix",
                "allow": {"call": True, "register": True, "publish": True, "subscribe": True},
                "disclose": {"caller": True, "publisher": True},
                "cache": True,
            }
        ],
    },
}
