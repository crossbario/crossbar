###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

__all__ = [
   'HAS_FSNOTIFY',
   'DirWatcher'
]


import sys

HAS_FSNOTIFY = False
DirWatcher = None

if sys.platform.startswith('linux'):
   try:
      from crossbar.platform.linux.fsnotify import DirWatcher
      HAS_FSNOTIFY = True
   except ImportError:
      pass
