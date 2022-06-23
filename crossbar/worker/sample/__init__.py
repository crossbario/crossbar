#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

#
# the imports here are important (though not used in CB unless configured),
# because of single-exe packaging and pyinstaller otherwise missing deps
#

from crossbar.worker.sample._logging import LogTester  # noqa
