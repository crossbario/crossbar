#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################
"""Crossbar.io is a decentralized data plane for XBR/WAMP based application
service and data routing, built on Crossbar.io OSS."""

import os
import sys

import psutil

from crossbar._util import hl
from crossbar._version import __version__, __build__

import warnings

# prevent error in EXE building (pyinstaller):
# "pkg_resources.DistributionNotFound: The 'humanize' distribution was not found and is required by the application"
import humanize  # noqa

# monkey patch, see:
# https://github.com/ethereum/web3.py/issues/1201
# https://github.com/ethereum/eth-abi/pull/88
from eth_abi import abi

if not hasattr(abi, 'collapse_type'):

    def collapse_type(base, sub, arrlist):
        return base + sub + ''.join(map(repr, arrlist))

    abi.collapse_type = collapse_type

if not hasattr(abi, 'process_type'):
    from eth_abi.grammar import (
        TupleType,
        normalize,
        parse,
    )

    def process_type(type_str):
        normalized_type_str = normalize(type_str)
        abi_type = parse(normalized_type_str)

        type_str_repr = repr(type_str)
        if type_str != normalized_type_str:
            type_str_repr = '{} (normalized to {})'.format(
                type_str_repr,
                repr(normalized_type_str),
            )

        if isinstance(abi_type, TupleType):
            raise ValueError("Cannot process type {}: tuple types not supported".format(type_str_repr, ))

        abi_type.validate()

        sub = abi_type.sub
        if isinstance(sub, tuple):
            sub = 'x'.join(map(str, sub))
        elif isinstance(sub, int):
            sub = str(sub)
        else:
            sub = ''

        arrlist = abi_type.arrlist
        if isinstance(arrlist, tuple):
            arrlist = list(map(list, arrlist))
        else:
            arrlist = []

        return abi_type.base, sub, arrlist

    abi.process_type = process_type

# https://stackoverflow.com/a/40846742/884770
# https://github.com/numpy/numpy/pull/432/commits/170ed4e33d6196d724dc18ddcd42311c291b4587?diff=split
# https://docs.python.org/3/library/warnings.html
# /opt/pypy3/lib-python/3/importlib/_bootstrap.py:223: builtins.UserWarning: builtins.type size changed, may indicate binary incompatibility. Expected 872, got 416
warnings.filterwarnings("ignore", message="builtins.type size changed, may indicate binary incompatibility")

# https://peps.python.org/pep-0632/
# site-packages/_distutils_hack/__init__.py:30: builtins.UserWarning: Setuptools is replacing distutils.
warnings.filterwarnings("ignore", message="Setuptools is replacing distutils.")

__all__ = ('__version__', '__build__', 'run', 'personalities')

_DEFINED_REACTORS = ['select', 'poll', 'epoll', 'kqueue', 'iocp']

_DEFINED_PERSONALITIES = ['standalone', 'edge', 'master']

_TOP_COMMANDS = ['standalone', 'edge', 'network', 'master', 'shell', 'quickstart', 'legal', 'version']

_HELP_USAGE = """
Usage: {executable} <command>

    <command>:

    standalone       Run a Crossbar.io node (default when no command is given)
    edge             Run a crossbar Edge node
    master           Run a crossbar Master node
    network          Run a crossbar XBR Network node
    shell            Run a management shell command
    quickstart       Create a WAMP/XBR application skeleton
    version          Print crossbar software versions
    legal            Print crossbar license terms

Command help: {executable} <command> --help
"""


def run():
    """
    CLI entry point into crossbar.

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

    n.a.                **CROSSBAR_PERSONALITY**  Node personality:

                                                  * **standalone**
                                                  * **edge**
                                                  * **master**

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
    """
    #
    # check command line args
    #
    argv = sys.argv[:]
    if len(argv) < 2:
        print(_HELP_USAGE.format(executable=hl(os.path.basename(argv[0]), bold=True, color='yellow')))
        sys.exit(0)

    # XXX maybe we should Click here, too, since we're already depending on it?
    executable, command = argv[0:2]
    args = argv[2:]
    sys.argv = [executable] + argv[2:]

    # if no known top-level command was given, fallback to "edge" mode
    if command not in _TOP_COMMANDS:
        args = [command] + args
        command = 'standalone'

    # redirect a plain "crossbar legal" to "crossbar master legal"
    if command == 'legal':
        command = 'master'
        args = ['legal']

    # redirect a plain "crossbar version" to "crossbar master version"
    if command == 'version':
        command = 'master'
        args = ['version']

    # shell command (using asyncio)
    if command == 'shell':

        from crossbar.shell import main

        sys.exit(main.run())

    elif command == 'quickstart':
        from crossbar.quickstart import main

        sys.exit(main.run())

    elif command == 'quickstart-venv':
        from crossbar.quickstart.quickstartvenv import main

        sys.exit(main.run())

    # edge/master commands (using Twisted)
    elif command in ['standalone', 'edge', 'master', 'network']:

        # FIXME :: having FX drop out due to lack of entropy makes things a lot
        #          harder from a deployment / monitoring perspective. A retry with reporting
        #          would make life a lot easier.

        # on Linux, check that we start with sufficient system entropy
        if sys.platform.startswith('linux'):
            try:
                with open('/proc/sys/kernel/random/entropy_avail', 'r') as ent:
                    entropy_avail = int(ent.read())
                    if entropy_avail < 64:
                        print(
                            'FATAL: cannot start due to insufficient entropy ({} bytes) available - try installing rng-tools'
                            .format(entropy_avail))
                        sys.exit(1)
            except PermissionError:
                # this happens when packaged as a snap: the code prevented from reading a location
                # # that is not allowed to a confined snap package
                entropy_avail = -1

        mem_avail = psutil.virtual_memory().available // 2**20
        if mem_avail < 100:
            print('FATAL: cannot start due to insufficient available memory ({} MB free)'.format(mem_avail))
            sys.exit(1)

        from autobahn.twisted import install_reactor

        # IMPORTANT: keep the reactor install as early as possible to avoid importing
        # any Twisted module that comes with the side effect of installing a default
        # reactor (which might not be what we want!).
        reactor = install_reactor(explicit_reactor=os.environ.get('CROSSBAR_REACTOR', None),
                                  verbose=False,
                                  require_optimal_reactor=False)

        # get chosen personality class
        if command == 'standalone':
            from crossbar import personality as standalone

            personality = standalone.Personality

        elif command == 'edge':

            from crossbar import edge

            personality = edge.Personality

        elif command == 'network':

            from crossbar import network

            personality = network.Personality

        elif command == 'master':
            from crossbar import master

            personality = master.Personality

        else:
            # should not arrive here
            raise Exception('internal error')

        # do NOT move this import above *** (triggers reactor imports)
        from crossbar.node.main import main

        # and now actually enter here .. this never returns!
        sys.exit(main(executable, args, reactor, personality))

    else:
        assert False, 'should not arrive here'


def personalities():
    """
    Return a map from personality names to actual available (=installed) Personality classes.
    """
    #
    # do NOT move the imports here to the module level! (triggers reactor imports)
    #
    from crossbar import personality as standalone

    personality_classes = {'standalone': standalone.Personality}

    try:
        from crossbar import edge  # noqa
    except ImportError:
        pass
    else:
        personality_classes['edge'] = edge.Personality

    try:
        from crossbar import master  # noqa
    except ImportError:
        pass
    else:
        personality_classes['master'] = master.Personality

    return personality_classes


if __name__ == '__main__':
    run()
