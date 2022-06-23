###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

__all__ = ('BUILTIN_ROLES', )

BUILTIN_ROLES = {
    u'node-role': {
        u'name':
        u'node',
        u'permissions': [{
            u'uri': u'',
            u'match': u'prefix',
            u'allow': {
                u'call': True,
                u'register': True,
                u'publish': True,
                u'subscribe': True
            },
            u'disclose': {
                u'caller': True,
                u'publisher': True
            },
            u'cache': True
        }]
    },
    u'backend-role': {
        u'name':
        u'backend',
        u'permissions': [{
            u'uri': u'',
            u'match': u'prefix',
            u'allow': {
                u'call': True,
                u'register': True,
                u'publish': True,
                u'subscribe': True
            },
            u'disclose': {
                u'caller': True,
                u'publisher': True
            },
            u'cache': True
        }]
    },
    u'public-role': {
        u'name':
        u'public',
        u'permissions': [{
            u'uri': u'crossbarfabriccenter.mrealm.get_status',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.get_nodes',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.remote.node.get_workers',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.remote.node.get_worker',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.remote.router.get_router_realms',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.remote.realm.meta.wamp.session.list',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.remote.realm.meta.wamp.session.get',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.remote.realm.meta.wamp.session.on_join',
            u'allow': {
                u'subscribe': True
            }
        }, {
            u'uri': u'crossbarfabriccenter.remote.realm.meta.wamp.session.on_leave',
            u'allow': {
                u'subscribe': True
            }
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.get_traces',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.get_trace',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.get_trace_data',
            u'allow': {
                u'call': True
            },
            u'disclose': {
                u'caller': True,
            },
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.on_trace_data',
            u'allow': {
                u'subscribe': True
            }
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.on_trace_created',
            u'allow': {
                u'subscribe': True
            }
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.on_trace_starting',
            u'allow': {
                u'subscribe': True
            }
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.on_trace_started',
            u'allow': {
                u'subscribe': True
            }
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.on_trace_stopping',
            u'allow': {
                u'subscribe': True
            }
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.on_trace_stopped',
            u'allow': {
                u'subscribe': True
            }
        }, {
            u'uri': u'crossbarfabriccenter.mrealm.tracing.on_trace_deleted',
            u'allow': {
                u'subscribe': True
            }
        }]
    },
    u'owner-role': {
        u'name':
        u'owner',
        u'permissions': [{
            u'uri': u'',
            u'match': u'prefix',
            u'allow': {
                u'call': True,
                u'register': True,
                u'publish': True,
                u'subscribe': True
            },
            u'disclose': {
                u'caller': True,
                u'publisher': True
            },
            u'cache': True
        }]
    }
}
