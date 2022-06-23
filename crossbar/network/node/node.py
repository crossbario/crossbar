##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from crossbar.edge.node import FabricNode, FabricNodeControllerSession


class XbrNetworkNodeControllerSession(FabricNodeControllerSession):
    pass


class XbrNetworkNode(FabricNode):
    """
    Crossbar.io node personality.
    """
    DEFAULT_CONFIG_PATH = 'network/node/config.json'
    NODE_CONTROLLER = XbrNetworkNodeControllerSession
