##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import txaio

from crossbar.network.node.node import XbrNetworkNode
from crossbar.edge.personality import Personality as _Personality


class Personality(_Personality):

    log = txaio.make_logger()

    NAME = 'network'

    Node = XbrNetworkNode

    def check_config(self, personality):
        res = _Personality.check_config(self, personality)
        return res

    def check_config_file(self, personality, config_path):
        res = _Personality.check_config_file(self, personality, config_path)
        return res
