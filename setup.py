#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

# IMPORTANT:
#
# This setup.py is kept for backwards compatibility with older pip versions.
# All package metadata and dependencies are now defined in pyproject.toml.
#
# Modern installation (pip >= 22.0.3):
#   pip install .
#   pip install -e .[dev]
#   pip install -e .[dev,dev-latest]
#

import os

from setuptools import setup


# enforce use of CFFI for LMDB
os.environ['LMDB_FORCE_CFFI'] = '1'

# enforce use of bundled libsodium
os.environ['SODIUM_INSTALL'] = 'bundled'

# enforce use of pure Python py-ubjson (no Cython)
os.environ['PYUBJSON_NO_EXTENSION'] = '1'

# All configuration is now in pyproject.toml
# setuptools will automatically read from pyproject.toml when using build backend
setup()
