###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from typing import List, Union  # noqa

from crossbar.master.api.remote import RemoteApi  # noqa
from crossbar.master.api.node import RemoteNodeApi
# from crossbar.master.api.nativeprocess import RemoteNativeProcessApi
from crossbar.master.api.worker import RemoteWorkerApi
from crossbar.master.api.router import RemoteRouterApi
from crossbar.master.api.container import RemoteContainerApi
from crossbar.master.api.proxy import RemoteProxyApi
from crossbar.master.api.tracing import RemoteTracingApi
from crossbar.master.api.docker import RemoteDockerApi
from crossbar.master.api.wamp import RemoteWampApi

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
