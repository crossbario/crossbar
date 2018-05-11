#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

import sys
import socket
import platform

from twisted.internet import fdesc, tcp, ssl
from twisted.python.runtime import platformType

# Flag indiciating support for creating shared sockets with in-kernel
# load-balancing (!). Note that while FreeBSD had SO_REUSEPORT for ages,
# it does NOT (currently) implement load-balancing. Linux >= 3.9 and
# DragonFly BSD does.
_HAS_SHARED_LOADBALANCED_SOCKET = False

if sys.platform.startswith('linux'):
    try:
        # get Linux kernel version, like: (3, 19)
        _LINUX_KERNEL_VERSION = [int(x) for x in tuple(platform.uname()[2].split('.')[:2])]

        # SO_REUSEPORT only supported for Linux kernels >= 3.9
        if (_LINUX_KERNEL_VERSION[0] == 3 and _LINUX_KERNEL_VERSION[1] >= 9) or _LINUX_KERNEL_VERSION[0] >= 4:
            _HAS_SHARED_LOADBALANCED_SOCKET = True

            # monkey patch missing constant if needed
            if not hasattr(socket, 'SO_REUSEPORT'):
                socket.SO_REUSEPORT = 15
    except:
        pass

elif sys.platform == 'win32':
    # http://stackoverflow.com/questions/14388706/socket-options-so-reuseaddr-and-so-reuseport-how-do-they-differ-do-they-mean-t/14388707#14388707
    _HAS_SHARED_LOADBALANCED_SOCKET = True

# FIXME: DragonFly BSD claims support: http://lists.dragonflybsd.org/pipermail/commits/2013-May/130083.html

__all__ = ('create_stream_socket', 'SharedPort', 'SharedTLSPort')


def create_stream_socket(addressFamily, shared=False):
    """
    Create a new socket for use with Twisted's IReactor.adoptStreamPort.

    :param addressFamily: The socket address family.
    :type addressFamily: One of socket.AF_INET, socket.AF_INET6, socket.AF_UNIX
    :param shared: If `True`, request to create a shared, load-balanced socket.
                   When this feature is not available, throw an exception.
    :type shared: bool
    :returns obj -- A socket.
    """
    s = socket.socket(addressFamily, socket.SOCK_STREAM)
    s.setblocking(0)
    fdesc._setCloseOnExec(s.fileno())

    if platformType == "posix" and sys.platform != "cygwin":
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if shared:
        if addressFamily not in [socket.AF_INET, socket.AF_INET6]:
            raise Exception("shared sockets are only supported for IPv4 and IPv6")

        if _HAS_SHARED_LOADBALANCED_SOCKET:
            if sys.platform.startswith('linux'):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            elif sys.platform == 'win32':
                # http://stackoverflow.com/questions/14388706/socket-options-so-reuseaddr-and-so-reuseport-how-do-they-differ-do-they-mean-t/14388707#14388707
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                raise Exception("logic error")
        else:
            raise Exception("shared sockets unsupported on this system")

    return s


class SharedPort(tcp.Port):
    """
    A custom TCP port which allows to set socket options for sharing TCP ports between multiple processes.
    """

    def __init__(self, port, factory, backlog=50, interface='', reactor=None, shared=False):
        if shared and not _HAS_SHARED_LOADBALANCED_SOCKET:
            raise Exception("shared sockets unsupported on this system")
        else:
            self._shared = shared

        tcp.Port.__init__(self, port, factory, backlog, interface, reactor)

    def createInternetSocket(self):
        s = tcp.Port.createInternetSocket(self)
        if self._shared:
            if _HAS_SHARED_LOADBALANCED_SOCKET:
                if sys.platform.startswith('linux'):
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                elif sys.platform == 'win32':
                    # http://stackoverflow.com/questions/14388706/socket-options-so-reuseaddr-and-so-reuseport-how-do-they-differ-do-they-mean-t/14388707#14388707
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    # s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                else:
                    raise Exception("logic error")
            else:
                raise Exception("shared sockets unsupported on this system")
        return s


class SharedTLSPort(SharedPort, ssl.Port):
    """
    A custom TLS port which allows to set socket options for sharing (the underlying) TCP ports between multiple processes.
    """

    def __init__(self, port, factory, ctxFactory, backlog=50, interface='', reactor=None, shared=False):
        if shared and not _HAS_SHARED_LOADBALANCED_SOCKET:
            raise Exception("shared sockets unsupported on this system")
        else:
            self._shared = shared

        ssl.Port.__init__(self, port, factory, ctxFactory, backlog, interface, reactor)
