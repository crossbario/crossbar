##############################################################################
#
#                        Crossbar.io FX
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import txaio
txaio.use_twisted()

from crossbarfx.network._authenticator import Authenticator as XbrNetworkAuthenticator
from crossbarfx.network._api import Network as XbrNetwork
from crossbarfx.network.personality import Personality

__doc__ = Personality.DESC

__all__ = (
    'Personality',
    'XbrNetwork',
    'XbrNetworkAuthenticator',
)
