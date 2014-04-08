###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
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


import sys

if sys.platform.startswith('freebsd'):

   ## FreeBSD

   from freebsd.platform import PlatformService
   from freebsd.vmstat import VmstatService
   from freebsd.netstat import NetstatService
   SYSCMD_ZIP = '/usr/local/bin/zip'
   SYSCMD_SQLITE3 = '/usr/local/bin/sqlite3'

elif sys.platform.startswith('linux'):

   ## Amazon Linux

   from linux.platform import PlatformService
   from linux.vmstat import VmstatService
   from linux.netstat import NetstatService
   SYSCMD_ZIP = '/usr/bin/zip'
   SYSCMD_SQLITE3 = '/usr/bin/sqlite3'

else:

   ## Fake Platform
#   raise ImportError("my module doesn't support this system")
#   print "Using FakeOS platform module!"
   from fakeos.platform import PlatformService
   from fakeos.vmstat import VmstatService
   from fakeos.netstat import NetstatService
   SYSCMD_ZIP = 'zip'
   SYSCMD_SQLITE3 = 'sqlite3'
