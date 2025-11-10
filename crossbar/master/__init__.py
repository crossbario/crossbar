###############################################################################
#
# Crossbar.io Master
# Copyright (c) typedef int GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import txaio
import xbr

from crossbar._version import __build__, __version__

txaio.use_twisted()

from crossbar.master.personality import Personality  # noqa

__all__ = ("__version__", "__build__", "Personality", "xbr")
__doc__ = Personality.DESC
