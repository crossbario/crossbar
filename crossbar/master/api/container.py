###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ('RemoteContainerApi', )


class RemoteContainerApi(RemoteApi):

    # remote procedures and topics are exposed under this prefix
    PREFIX = u'crossbarfabriccenter.remote.container.'

    PROCS = {
        # these are worker level procedures
        u'worker': [
            (u'get_components', u'get_components'),
            (u'get_component', u'get_component'),
            (u'start_component', u'start_component'),
            (u'stop_component', u'stop_component'),
        ],
    }

    EVENTS = {
        # these are worker level topics
        u'worker': [
            u'on_container_component_starting',
            u'on_container_component_started',
            u'on_container_component_stopping',
            u'on_container_component_stopped',
        ]
    }
