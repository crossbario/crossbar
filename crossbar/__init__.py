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

from __future__ import absolute_import

import sys
import os

import txaio
from autobahn.twisted import install_reactor
from crossbar._version import __version__

"""Crossbar.io multi-protocol (WAMP/WebSocket, REST/HTTP, MQTT) application router for microservices."""

txaio.use_twisted()

__all__ = ('__version__', 'version', 'run')


def version():
    """
    Crossbar.io base package version, eg the string ``"18.4.1"``.

    :return: The base package version.
    :rtype: str
    """
    return __version__


def run(args=None, reactor=None):
    """
    Main entry point into Crossbar.io:

    * when called with no arguments, the arguments are read
      from the command line

    * when called with an explicit arguments list, use the same
      arguments in the list as on the command line, leaving out
      the initial `crossbar` command.


    twisted.internet.error.ReactorNotRestartable

    **Examples**

    To start Crossbar.io programmatically from a given node directory:

    .. code-block:: python

        import crossbar

        crossbar.run(['start', '--cbdir', '/tmp/mynode1/.crossbar'])

    To start Crossbar.io with log output at level "debug"

    .. code-block:: console

        $ crossbar start --loglevel=debug

    To chose a specific event reactor and print version information

    .. code-block:: console

        $ CROSSBAR_REACTOR="kqueue" crossbar version

    To start from a specified node directory (instead of the default `$CWD/.crossbar`):

    .. code-block:: console

        $ CROSSBAR_DIR="/tmp/test/.crossbar" crossbar start

    which is the same as

    .. code-block:: console

        $ crossbar start --cbdir=/tmp/test/.crossbar

   **Influential command line options and environment variables include:**

    ==================  ========================  ==============================================
    Command line arg:   Environment variable:     Description:
    ==================  ========================  ==============================================
    n.a.                **CROSSBAR_REACTOR**      Event reactor:

                                                  * **auto**
                                                  * **select**
                                                  * **poll**
                                                  * **epoll**
                                                  * **kqueue**
                                                  * **iocp**

    ``--personality``   **CROSSBAR_PERSONALITY**  Node personality:

                                                  * **standalone**
                                                  * **fabric**
                                                  * **fabricenter**

    ``--cbdir``         **CROSSBAR_DIR**          Node directory (local directory)
    ``--config``        **CROSSBAR_CONFIG**       Node configuration (local filename)
    ``--color``         n.a.                      Enable colored terminal output
    ``--loglevel``      n.a.                      Select log level
    ``--logformat``     n.a.                      Select log format
    ``--logdir``        n.a.                      Log to this local directory
    ``--logtofile``     n.a.                      Enable logging to file
    ==================  ========================  ==============================================

    .. seealso:: `TwistedMatrix: Choosing a Reactor and GUI Toolkit Integration <https://twistedmatrix.com/documents/current/core/howto/choosing-reactor.html>`_

    .. note:: The Twisted reactor to use can only be explicitly chosen via an environment
        variable, not a command line option.

    :param args: The (optional) program name .
    :type args: List[str]

    :param reactor: Optional Twisted reactor to use. If none is given, try to
        load the optimal reactor for Crossbar.io to run on the host platform.
    :type reactor: :class:`twisted.internet.reactor`
    """
    # use argument list from command line if none is given explicitly
    if args is None:
        args = sys.argv[1:]

    # IMPORTANT: keep the reactor install as early as possible to avoid importing
    # any Twisted module that comes with the side effect of installing a default
    # reactor (which might not be what we want!).
    if reactor is None:
        # we use an Autobahn utility to import the "best" available Twisted reactor
        reactor = install_reactor(explicit_reactor=os.environ.get('CROSSBAR_REACTOR', None),
                                  verbose=False,
                                  require_optimal_reactor=False)

    # Twisted reactor installed FROM HERE

    # Only _now_ import actual stuff, as this triggers lots of imports in turn,
    # somewhere down the line Twisted _will_ likely import its one and only reactor,
    # and if we haven't done before, Twisted will install whatever it deems right then.
    from crossbar.controller.cli import main

    # and now actually enter here .. this never returns!
    return main('crossbar', args, reactor)
