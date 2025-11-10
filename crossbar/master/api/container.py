###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from crossbar.master.api.remote import RemoteApi

__all__ = ("RemoteContainerApi",)


class RemoteContainerApi(RemoteApi):
    # remote procedures and topics are exposed under this prefix
    PREFIX = "crossbarfabriccenter.remote.container."

    PROCS = {
        # these are worker level procedures
        "worker": [
            ("get_components", "get_components"),
            ("get_component", "get_component"),
            ("start_component", "start_component"),
            ("stop_component", "stop_component"),
        ],
    }

    EVENTS = {
        # these are worker level topics
        "worker": [
            "on_container_component_starting",
            "on_container_component_started",
            "on_container_component_stopping",
            "on_container_component_stopped",
        ]
    }
