##############################################################################
#
#                        Crossbar.io FX
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import txaio
txaio.use_twisted()  # noqa

from autobahn import xbr
from crossbarfx._version import __version__, __build__
from crossbarfx.edge.personality import Personality

__all__ = ('__version__', '__build__', 'Personality', 'xbr')
__doc__ = Personality.DESC
