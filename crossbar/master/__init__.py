###############################################################################
#
# Crossbar.io FX Master
# Copyright (c) Crossbar.io Technologies GmbH. All rights reserved.
#
###############################################################################

from autobahn import xbr
from crossbar._version import __version__, __build__

import txaio
txaio.use_twisted()

from crossbar.master.personality import Personality  # noqa

__all__ = ('__version__', '__build__', 'Personality', 'xbr')
__doc__ = Personality.DESC
