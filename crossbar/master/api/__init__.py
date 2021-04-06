###############################################################################
#
# Crossbar.io FX Master
# Copyright (c) Crossbar.io Technologies GmbH. All rights reserved.
#
###############################################################################

from typing import List, Union  # noqa

from crossbarfx.master.api.remote import RemoteApi  # noqa
from crossbarfx.master.api.node import RemoteNodeApi
# from crossbarfx.master.api.nativeprocess import RemoteNativeProcessApi
from crossbarfx.master.api.worker import RemoteWorkerApi
from crossbarfx.master.api.router import RemoteRouterApi
from crossbarfx.master.api.container import RemoteContainerApi
from crossbarfx.master.api.proxy import RemoteProxyApi
from crossbarfx.master.api.tracing import RemoteTracingApi
from crossbarfx.master.api.docker import RemoteDockerApi
from crossbarfx.master.api.wamp import RemoteWampApi

APIS = []  # type: List[Union[RemoteApi, RemoteWampApi]]
APIS.append(RemoteNodeApi())
# APIS.append(RemoteNativeProcessApi())
APIS.append(RemoteWorkerApi())
APIS.append(RemoteRouterApi())
APIS.append(RemoteContainerApi())
APIS.append(RemoteProxyApi())
APIS.append(RemoteTracingApi())
APIS.append(RemoteDockerApi())
APIS.append(RemoteWampApi())
