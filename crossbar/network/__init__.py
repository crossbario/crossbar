##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import txaio

txaio.use_twisted()

from crossbar.network._authenticator import Authenticator as XbrNetworkAuthenticator
from crossbar.network._api import Network as XbrNetwork
from crossbar.network.personality import Personality

__doc__ = Personality.DESC

__all__ = (
    'Personality',
    'XbrNetwork',
    'XbrNetworkAuthenticator',
)
