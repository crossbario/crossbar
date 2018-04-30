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

from __future__ import absolute_import, print_function

import argparse
import click
import importlib
import json
import os
import platform
import signal
import sys
import six
import pkg_resources

import txaio
txaio.use_twisted()  # noqa
from txaio import make_logger, start_logging, set_global_log_level, failure_format_traceback

from twisted.python.reflect import qual
from twisted.logger import globalLogPublisher

from crossbar._util import hl, term_print
from crossbar._logging import make_logfile_observer
from crossbar._logging import make_stdout_observer
from crossbar._logging import make_stderr_observer
from crossbar._logging import LogLevel
from crossbar.common.key import _maybe_generate_key


def _get_personalities():
    """
    Return a map from personality names to actual available (=installed) Personality classes.
    """
    from crossbar.personality import Personality as StandalonePersonality

    default_personality = 'standalone'

    PKLASSES = {
        'standalone': StandalonePersonality,
    }

    try:
        from crossbarfabric.personality import Personality as FabricPersonality
        PKLASSES['fabric'] = FabricPersonality
        # default_personality = 'fabric'
    except ImportError:
        pass

    try:
        from crossbarfabriccenter.personality import Personality as FabricCenterPersonality
        PKLASSES['fabriccenter'] = FabricCenterPersonality
        # default_personality = 'fabriccenter'
    except ImportError:
        pass

    return PKLASSES, default_personality


_INSTALLED_PERSONALITIES, _DEFAULT_PERSONALITY = _get_personalities()
_DEFAULT_PERSONALITY_KLASS = _INSTALLED_PERSONALITIES[_DEFAULT_PERSONALITY]


import crossbar

from autobahn.twisted.choosereactor import install_reactor
from autobahn.websocket.protocol import WebSocketProtocol
from autobahn.websocket.utf8validator import Utf8Validator
from autobahn.websocket.xormasker import XorMaskerNull

from crossbar.controller.template import Templates
from crossbar.common.checkconfig import check_config_file, \
    color_json, convert_config_file, upgrade_config_file, InvalidConfigException
from crossbar.worker import process

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_HAS_COLOR_TERM = False
try:
    import colorama

    # https://github.com/tartley/colorama/issues/48
    term = None
    if sys.platform == 'win32' and 'TERM' in os.environ:
        term = os.environ.pop('TERM')

    colorama.init()
    _HAS_COLOR_TERM = True

    if term:
        os.environ['TERM'] = term

except ImportError:
    pass

__all__ = ('main',)

_PID_FILENAME = 'node.pid'


def _get_version(name_or_module):
    if isinstance(name_or_module, str):
        name_or_module = importlib.import_module(name_or_module)

    try:
        return name_or_module.__version__
    except AttributeError:
        return ''


def _check_pid_exists(pid):
    """
    Check if a process with given PID exists.

    :returns: ``True`` if a process exists.
    :rtype: bool
    """
    if sys.platform == 'win32':
        if _HAS_PSUTIL:
            # http://pythonhosted.org/psutil/#psutil.pid_exists
            return psutil.pid_exists(pid)
        else:
            # On Windows, this can only be done with native code (like via win32com, ctypes or psutil).
            # We use psutil.
            raise Exception("cannot check if process with PID exists - package psutil not installed")
    else:
        # Unix-like OS
        # http://stackoverflow.com/a/568285/884770
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True


def _is_crossbar_process(cmdline):
    """
    Returns True if the cmdline passed appears to really be a running
    crossbar instance.
    """
    if len(cmdline) > 1 and 'crossbar' in cmdline[1]:
        return True
    if len(cmdline) > 0 and cmdline[0] == 'crossbar-controller':
        return True
    return False


def _check_is_running(cbdir):
    """
    Check if a Crossbar.io node is already running on a Crossbar.io node directory.

    :param cbdir: The Crossbar.io node directory to check.
    :type cbdir: str

    :returns: The PID of the running Crossbar.io controller process or ``None``
    :rtype: int or None
    """
    log = make_logger()

    remove_PID_type = None
    remove_PID_reason = None

    fp = os.path.join(cbdir, _PID_FILENAME)

    if os.path.isfile(fp):
        with open(fp) as fd:
            pid_data_str = fd.read()
            try:
                pid_data = json.loads(pid_data_str)
                pid = int(pid_data['pid'])
            except ValueError:
                remove_PID_type = "corrupt"
                remove_PID_reason = "corrupt .pid file"
            else:
                if pid == os.getpid():
                    # the process ID is our own -- this happens often when the Docker container is
                    # shut down uncleanly
                    return None
                elif sys.platform == 'win32' and not _HAS_PSUTIL:
                    # when on Windows, and we can't actually determine if the PID exists,
                    # just assume it exists
                    return pid_data
                else:
                    pid_exists = _check_pid_exists(pid)
                    if pid_exists:
                        if _HAS_PSUTIL:
                            # additionally check this is actually a crossbar process
                            p = psutil.Process(pid)
                            cmdline = p.cmdline()
                            if not _is_crossbar_process(cmdline):
                                nicecmdline = ' '.join(cmdline)
                                if len(nicecmdline) > 76:
                                    nicecmdline = nicecmdline[:38] + ' ... ' + nicecmdline[-38:]
                                log.info('"{fp}" points to PID {pid} which is not a crossbar process:', fp=fp, pid=pid)
                                log.info('  {cmdline}', cmdline=nicecmdline)
                                log.info('Verify manually and either kill {pid} or delete {fp}', pid=pid, fp=fp)
                                return None
                        return pid_data
                    else:
                        remove_PID_type = "stale"
                        remove_PID_reason = "pointing to non-existing process with PID {}".format(pid)

    if remove_PID_type:
        # If we have to remove a PID, do it here.
        try:
            os.remove(fp)
        except:
            log.info(("Could not remove {pidtype} Crossbar.io PID file "
                      "({reason}) {fp} - {log_failure}"),
                     pidtype=remove_PID_type, reason=remove_PID_reason, fp=fp)
        else:
            log.info("{pidtype} Crossbar.io PID file ({reason}) {fp} removed",
                     pidtype=remove_PID_type.title(), reason=remove_PID_reason,
                     fp=fp)

    return None


def _run_command_legal(options, reactor=None, **kwargs):
    """
    Subcommand "crossbar legal".
    """
    Personality = _INSTALLED_PERSONALITIES[options.personality]
    package, resource_name = Personality.LEGAL
    filename = pkg_resources.resource_filename(package, resource_name)
    filepath = os.path.abspath(filename)
    with open(filepath) as f:
        legal = f.read()
        print(legal)


def _run_command_version(options, reactor=None, **kwargs):
    """
    Subcommand "crossbar version".
    """
    log = make_logger()

    # Python
    py_ver = '.'.join([str(x) for x in list(sys.version_info[:3])])
    py_ver_string = "[%s]" % sys.version.replace('\n', ' ')

    if 'pypy_version_info' in sys.__dict__:
        py_ver_detail = "{}-{}".format(platform.python_implementation(), '.'.join(str(x) for x in sys.pypy_version_info[:3]))
    else:
        py_ver_detail = platform.python_implementation()

    # Pyinstaller (frozen EXE)
    py_is_frozen = getattr(sys, 'frozen', False)

    # Twisted / Reactor
    tx_ver = "%s-%s" % (_get_version('twisted'), reactor.__class__.__name__)
    tx_loc = "[%s]" % qual(reactor.__class__)

    # txaio
    txaio_ver = _get_version('txaio')

    # Autobahn
    ab_ver = _get_version('autobahn')
    ab_loc = "[%s]" % qual(WebSocketProtocol)

    # UTF8 Validator
    s = qual(Utf8Validator)
    if 'wsaccel' in s:
        utf8_ver = 'wsaccel-%s' % _get_version('wsaccel')
    elif s.startswith('autobahn'):
        utf8_ver = 'autobahn'
    else:
        # could not detect UTF8 validator type/version
        utf8_ver = '?'
    utf8_loc = "[%s]" % qual(Utf8Validator)

    # XOR Masker
    s = qual(XorMaskerNull)
    if 'wsaccel' in s:
        xor_ver = 'wsaccel-%s' % _get_version('wsaccel')
    elif s.startswith('autobahn'):
        xor_ver = 'autobahn'
    else:
        # could not detect XOR masker type/version
        xor_ver = '?'
    xor_loc = "[%s]" % qual(XorMaskerNull)

    # JSON Serializer
    supported_serializers = ['JSON']
    from autobahn.wamp.serializer import JsonObjectSerializer
    json_ver = JsonObjectSerializer.JSON_MODULE.__name__

    # If it's just 'json' then it's the stdlib one...
    if json_ver == 'json':
        json_ver = 'stdlib'
    else:
        json_ver = (json_ver + "-%s") % _get_version(json_ver)

    # MsgPack Serializer
    try:
        import umsgpack  # noqa
        msgpack_ver = 'u-msgpack-python-%s' % _get_version(umsgpack)
        supported_serializers.append('MessagePack')
    except ImportError:
        msgpack_ver = '-'

    # CBOR Serializer
    try:
        import cbor  # noqa
        cbor_ver = 'cbor-%s' % _get_version(cbor)
        supported_serializers.append('CBOR')
    except ImportError:
        cbor_ver = '-'

    # UBJSON Serializer
    try:
        import ubjson  # noqa
        ubjson_ver = 'ubjson-%s' % _get_version(ubjson)
        supported_serializers.append('UBJSON')
    except ImportError:
        ubjson_ver = '-'

    # LMDB
    try:
        import lmdb  # noqa
        lmdb_lib_ver = '.'.join([str(x) for x in lmdb.version()])
        lmdb_ver = '{}/lmdb-{}'.format(_get_version(lmdb), lmdb_lib_ver)
    except ImportError:
        lmdb_ver = '-'

    # crossbarfabric (only Crossbar.io FABRIC)
    try:
        from crossbarfabric._version import __version__ as crossbarfabric_ver  # noqa
    except ImportError:
        crossbarfabric_ver = '-'

    # crossbarfabriccenter (only Crossbar.io FABRIC CENTER)
    try:
        from crossbarfabriccenter._version import __version__ as crossbarfabriccenter_ver  # noqa
    except ImportError:
        crossbarfabriccenter_ver = '-'

    # txaio-etcd (only Crossbar.io FABRIC CENTER)
    try:
        import txaioetcd  # noqa
        txaioetcd_ver = _get_version(txaioetcd)
    except ImportError:
        txaioetcd_ver = '-'

    # Release Public Key
    from crossbar.common.key import _read_release_key
    release_pubkey = _read_release_key()

    def decorate(text, fg='white', bg=None, bold=True):
        return click.style(text, fg=fg, bg=bg, bold=bold)

    Personality = _INSTALLED_PERSONALITIES[options.personality]

    log.info(hl(Personality.BANNER, color='yellow', bold=True))
    pad = " " * 22
    log.info(" Crossbar.io        : {ver}", ver=decorate(crossbar.__version__))
    log.info("   Autobahn         : {ver}", ver=decorate(ab_ver))
    log.trace("{pad}{debuginfo}", pad=pad, debuginfo=decorate(ab_loc))
    log.debug("     txaio          : {ver}", ver=decorate(txaio_ver))
    log.debug("     UTF8 Validator : {ver}", ver=decorate(utf8_ver))
    log.trace("{pad}{debuginfo}", pad=pad, debuginfo=decorate(utf8_loc))
    log.debug("     XOR Masker     : {ver}", ver=decorate(xor_ver))
    log.trace("{pad}{debuginfo}", pad=pad, debuginfo=decorate(xor_loc))
    log.debug("     JSON Codec     : {ver}", ver=decorate(json_ver))
    log.debug("     MsgPack Codec  : {ver}", ver=decorate(msgpack_ver))
    log.debug("     CBOR Codec     : {ver}", ver=decorate(cbor_ver))
    log.debug("     UBJSON Codec   : {ver}", ver=decorate(ubjson_ver))
    log.info("   Twisted          : {ver}", ver=decorate(tx_ver))
    log.trace("{pad}{debuginfo}", pad=pad, debuginfo=decorate(tx_loc))
    log.info("   LMDB             : {ver}", ver=decorate(lmdb_ver))
    log.info("   Python           : {ver}/{impl}", ver=decorate(py_ver), impl=decorate(py_ver_detail))
    log.trace("{pad}{debuginfo}", pad=pad, debuginfo=decorate(py_ver_string))
    if options.personality in (u'fabric', u'fabriccenter'):
        log.info(" Crossbar.io Fabric : {ver}", ver=decorate(crossbarfabric_ver))
    if options.personality == u'fabriccenter':
        log.info(" Crossbar.io FC     : {ver}", ver=decorate(crossbarfabriccenter_ver))
        log.debug("   txaioetcd        : {ver}", ver=decorate(txaioetcd_ver))
    log.info(" Frozen executable  : {py_is_frozen}", py_is_frozen=decorate('yes' if py_is_frozen else 'no'))
    log.info(" Operating system   : {ver}", ver=decorate(platform.platform()))
    log.info(" Host machine       : {ver}", ver=decorate(platform.machine()))
    log.info(" Release key        : {release_pubkey}", release_pubkey=decorate(release_pubkey[u'base64']))
    log.info("")


def _run_command_keys(options, reactor=None, **kwargs):
    """
    Subcommand "crossbar keys".
    """
    log = make_logger()

    from crossbar.common.key import _read_node_key
    from crossbar.common.key import _read_release_key

    if options.generate:
        # Generate a new node key pair (2 files), load and check
        _maybe_generate_key(options.cbdir)
    else:
        # Print keys

        # Release (public) key
        release_pubkey = _read_release_key()

        # Node key
        node_key = _read_node_key(options.cbdir, private=options.private)

        if options.private:
            key_title = 'Crossbar.io Node PRIVATE Key'
        else:
            key_title = 'Crossbar.io Node PUBLIC Key'

        log.info('')
        log.info('{key_title}', key_title=hl('Crossbar Software Release Key', color='yellow', bold=True))
        log.info('base64: {release_pubkey}', release_pubkey=release_pubkey[u'base64'])
        log.info(release_pubkey[u'qrcode'].strip())
        log.info('')
        log.info('{key_title}', key_title=hl(key_title, color='yellow', bold=True))
        log.info('hex: {node_key}', node_key=node_key[u'hex'])
        log.info(node_key[u'qrcode'].strip())
        log.info('')


def _run_command_init(options, **kwargs):
    """
    Subcommand "crossbar init".
    """
    log = make_logger()

    template = 'default'
    templates = Templates()
    assert(template in templates)

    if options.appdir is None:
        options.appdir = '.'
    else:
        if os.path.exists(options.appdir):
            raise Exception("app directory '{}' already exists".format(options.appdir))

        try:
            os.mkdir(options.appdir)
        except Exception as e:
            raise Exception("could not create application directory '{}' ({})".format(options.appdir, e))
        else:
            log.info("Crossbar.io application directory '{options.appdir}' created",
                     options=options)

    options.appdir = os.path.abspath(options.appdir)

    log.info("Initializing node in directory '{options.appdir}'", options=options)
    get_started_hint = templates.init(options.appdir, template)

    log.info("Application template initialized")

    if get_started_hint:
        log.info("\n{hint}\n", hint=get_started_hint)
    else:
        log.info("\nTo start your node, run 'crossbar start --cbdir {cbdir}'\n",
                 cbdir=os.path.abspath(os.path.join(options.appdir, '.crossbar')))


def _run_command_status(options, **kwargs):
    """
    Subcommand "crossbar status".
    """
    log = make_logger()

    # https://docs.python.org/2/library/os.html#os.EX_UNAVAILABLE
    # https://www.freebsd.org/cgi/man.cgi?query=sysexits&sektion=3
    _EXIT_ERROR = getattr(os, 'EX_UNAVAILABLE', 1)

    # check if there is a Crossbar.io instance currently running from
    # the Crossbar.io node directory at all
    pid_data = _check_is_running(options.cbdir)

    # optional current state to assert
    _assert = options.__dict__['assert']
    if pid_data is None:
        if _assert == 'running':
            log.error('Assert status RUNNING failed: status is {}'.format(hl('STOPPED', color='red', bold=True)))
            sys.exit(_EXIT_ERROR)
        elif _assert == 'stopped':
            log.info('Assert status STOPPED succeeded: status is {}'.format(hl('STOPPED', color='green', bold=True)))
            sys.exit(0)
        else:
            log.info('Status is {}'.format(hl('STOPPED', color='white', bold=True)))
            sys.exit(0)
    else:
        if _assert == 'running':
            log.info('Assert status RUNNING succeeded: status is {}'.format(hl('RUNNING', color='green', bold=True)))
            sys.exit(0)
        elif _assert == 'stopped':
            log.error('Assert status STOPPED failed: status is {}'.format(hl('RUNNING', color='red', bold=True)))
            sys.exit(_EXIT_ERROR)
        else:
            log.info('Status is {}'.format(hl('RUNNING', color='white', bold=True)))
            sys.exit(0)


def _run_command_stop(options, exit=True, **kwargs):
    """
    Subcommand "crossbar stop".
    """
    # check if there is a Crossbar.io instance currently running from
    # the Crossbar.io node directory at all
    #
    pid_data = _check_is_running(options.cbdir)
    if pid_data:
        pid = pid_data['pid']
        print("Stopping Crossbar.io currently running from node directory {} (PID {}) ...".format(options.cbdir, pid))
        if not _HAS_PSUTIL:
            os.kill(pid, signal.SIGINT)
            print("SIGINT sent to process {}.".format(pid))
        else:
            p = psutil.Process(pid)
            try:
                # first try to interrupt (orderly shutdown)
                _INTERRUPT_TIMEOUT = 5
                p.send_signal(signal.SIGINT)
                print("SIGINT sent to process {} .. waiting for exit ({} seconds) ...".format(pid, _INTERRUPT_TIMEOUT))
                p.wait(timeout=_INTERRUPT_TIMEOUT)
            except psutil.TimeoutExpired:
                print("... process {} still alive - will _terminate_ now.".format(pid))
                try:
                    _TERMINATE_TIMEOUT = 5
                    p.terminate()
                    print("SIGTERM sent to process {} .. waiting for exit ({} seconds) ...".format(pid, _TERMINATE_TIMEOUT))
                    p.wait(timeout=_TERMINATE_TIMEOUT)
                except psutil.TimeoutExpired:
                    print("... process {} still alive - will KILL now.".format(pid))
                    p.kill()
                    print("SIGKILL sent to process {}.".format(pid))
                else:
                    print("Process {} terminated.".format(pid))
            else:
                print("Process {} has excited gracefully.".format(pid))
        if exit:
            sys.exit(0)
        else:
            return pid_data
    else:
        print("No Crossbar.io is currently running from node directory {}.".format(options.cbdir))
        sys.exit(getattr(os, 'EX_UNAVAILABLE', 1))


def _start_logging(options, reactor):
    """
    Start the logging in a way that all the subcommands can use it.
    """
    loglevel = getattr(options, "loglevel", "info")
    logformat = getattr(options, "logformat", "none")
    color = getattr(options, "color", "auto")

    set_global_log_level(loglevel)

    # The log observers (things that print to stderr, file, etc)
    observers = []

    if getattr(options, "logtofile", False):
        # We want to log to a file
        if not options.logdir:
            logdir = options.cbdir
        else:
            logdir = options.logdir

        logfile = os.path.join(logdir, "node.log")

        if loglevel in ["error", "warn", "info"]:
            show_source = False
        else:
            show_source = True

        observers.append(make_logfile_observer(logfile, show_source))
    else:
        # We want to log to stdout/stderr.

        if color == "auto":
            if sys.__stdout__.isatty():
                color = True
            else:
                color = False
        elif color == "true":
            color = True
        else:
            color = False

        if loglevel == "none":
            # Do no logging!
            pass
        elif loglevel in ["error", "warn", "info"]:
            # Print info to stdout, warn+ to stderr
            observers.append(make_stdout_observer(show_source=False,
                                                  format=logformat,
                                                  color=color))
            observers.append(make_stderr_observer(show_source=False,
                                                  format=logformat,
                                                  color=color))
        elif loglevel == "debug":
            # Print debug+info to stdout, warn+ to stderr, with the class
            # source
            observers.append(make_stdout_observer(show_source=True,
                                                  levels=(LogLevel.info,
                                                          LogLevel.debug),
                                                  format=logformat,
                                                  color=color))
            observers.append(make_stderr_observer(show_source=True,
                                                  format=logformat,
                                                  color=color))
        elif loglevel == "trace":
            # Print trace+, with the class source
            observers.append(make_stdout_observer(show_source=True,
                                                  levels=(LogLevel.info,
                                                          LogLevel.debug),
                                                  format=logformat,
                                                  trace=True,
                                                  color=color))
            observers.append(make_stderr_observer(show_source=True,
                                                  format=logformat,
                                                  color=color))
        else:
            assert False, "Shouldn't ever get here."

    for observer in observers:
        globalLogPublisher.addObserver(observer)

        # Make sure that it goes away
        reactor.addSystemEventTrigger('after', 'shutdown',
                                      globalLogPublisher.removeObserver, observer)

    # Actually start the logger.
    start_logging(None, loglevel)


def _run_command_start(options, reactor):
    """
    Subcommand "crossbar start".
    """
    # do not allow to run more than one Crossbar.io instance
    # from the same Crossbar.io node directory
    #
    pid_data = _check_is_running(options.cbdir)
    if pid_data:
        print("Crossbar.io is already running from node directory {} (PID {}).".format(options.cbdir, pid_data['pid']))
        sys.exit(1)
    else:
        fp = os.path.join(options.cbdir, _PID_FILENAME)
        with open(fp, 'wb') as fd:
            argv = options.argv
            options_dump = vars(options)
            pid_data = {
                'pid': os.getpid(),
                'argv': argv,
                'options': {x: y for x, y in options_dump.items()
                            if x not in ["func", "argv"]}
            }
            fd.write("{}\n".format(
                json.dumps(
                    pid_data,
                    sort_keys=False,
                    indent=4,
                    separators=(', ', ': '),
                    ensure_ascii=False
                )
            ).encode('utf8'))

    # remove node PID file when reactor exits
    #
    def remove_pid_file():
        fp = os.path.join(options.cbdir, _PID_FILENAME)
        if os.path.isfile(fp):
            os.remove(fp)
    reactor.addSystemEventTrigger('after', 'shutdown', remove_pid_file)

    log = make_logger()

    # represents the running Crossbar.io node
    #
    Personality = _INSTALLED_PERSONALITIES[options.personality]
    Node = Personality.NodeKlass
    node = Node(Personality, options.cbdir, reactor=reactor)

    # print the banner, personality and node directory
    #
    for line in Personality.BANNER.splitlines():
        log.info(hl(line, color='yellow', bold=True))
    log.info('')
    log.info('Node starting with personality "{node_personality}" [{node_class}]', node_personality=options.personality, node_class='{}.{}'.format(Node.__module__, Node.__name__))
    log.info('Running from node directory "{cbdir}"', cbdir=options.cbdir)

    # possibly generate new node key
    #
    node.load_keys(options.cbdir)

    # check and load the node configuration
    #
    try:
        node.load_config(options.config)
    except InvalidConfigException as e:
        log.failure()
        log.error("Invalid node configuration")
        log.error("{e!s}", e=e)
        sys.exit(1)
    except:
        raise

    log.info("Controller process starting [{python}-{reactor}] ..",
             python=platform.python_implementation(),
             reactor=qual(reactor.__class__).split('.')[-1])

    # https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IReactorCore.html
    # Each "system event" in Twisted, such as 'startup', 'shutdown', and 'persist', has 3 phases:
    # 'before', 'during', and 'after' (in that order, of course). These events will be fired
    # internally by the Reactor.

    def before_reactor_started():
        term_print('<CROSSBAR:REACTOR_STARTING>')

    def after_reactor_started():
        term_print('<CROSSBAR:REACTOR_STARTED>')

    reactor.addSystemEventTrigger('before', 'startup', before_reactor_started)
    reactor.addSystemEventTrigger('after', 'startup', after_reactor_started)

    def before_reactor_stopped():
        term_print('<CROSSBAR:REACTOR_STOPPING>')

    def after_reactor_stopped():
        # FIXME: we are indeed reaching this line, however,
        # the log output does not work (it also doesnt work using
        # plain old print). Dunno why.

        # my theory about this issue is: by the time this line
        # is reached, Twisted has already closed the stdout/stderr
        # pipes. hence we do an evil trick: we directly write to
        # the process' controlling terminal
        # https://unix.stackexchange.com/a/91716/52500
        term_print('<CROSSBAR:REACTOR_STOPPED>')

    reactor.addSystemEventTrigger('before', 'shutdown', before_reactor_stopped)
    reactor.addSystemEventTrigger('after', 'shutdown', after_reactor_stopped)

    # now actually start the node ..
    #
    exit_info = {'was_clean': None}

    def start_crossbar():
        term_print('<CROSSBAR:NODE_STARTING>')

        #
        # ****** main entry point of node ******
        #
        d = node.start()

        # node started successfully, and later ..
        def on_startup_success(_shutdown_complete):
            term_print('<CROSSBAR:NODE_STARTED>')

            shutdown_complete = _shutdown_complete['shutdown_complete']

            # .. exits, signaling exit status _inside_ the result returned
            def on_shutdown_success(shutdown_info):
                exit_info['was_clean'] = shutdown_info['was_clean']
                log.info('on_shutdown_success: was_clean={was_clean}', shutdown_info['was_clean'])

            # should not arrive here:
            def on_shutdown_error(err):
                exit_info['was_clean'] = False
                log.error("on_shutdown_error: {tb}", tb=failure_format_traceback(err))

            shutdown_complete.addCallbacks(on_shutdown_success, on_shutdown_error)

        # node could not even start
        def on_startup_error(err):
            term_print('<CROSSBAR:NODE_STARTUP_FAILED>')
            exit_info['was_clean'] = False
            log.error("Could not start node: {tb}", tb=failure_format_traceback(err))
            if reactor.running:
                reactor.stop()

        d.addCallbacks(on_startup_success, on_startup_error)

    # Call a function when the reactor is running. If the reactor has not started, the callable
    # will be scheduled to run when it does start.
    reactor.callWhenRunning(start_crossbar)

    # now enter event loop ..
    #
    term_print('<CROSSBAR:REACTOR_RUN>')
    reactor.run()

    # once the reactor has finally stopped, we get here, and at that point,
    # exit_info['was_clean'] MUST have been set before - either to True or to False
    # (otherwise we are missing a code path to handle in above)

    # exit the program with exit code depending on whether the node has been cleanly shut down
    if exit_info['was_clean'] is True:
        term_print('<CROSSBAR:EXIT_WITH_SUCCESS>')
        sys.exit(0)
    elif exit_info['was_clean'] is False:
        term_print('<CROSSBAR:EXIT_WITH_ERROR>')
        sys.exit(1)
    else:
        term_print('<CROSSBAR:EXIT_WITH_INTERNAL_ERROR>')
        sys.exit(1)


def _run_command_check(options, **kwargs):
    """
    Subcommand "crossbar check".
    """
    from crossbar.personality import default_native_workers

    configfile = os.path.join(options.cbdir, options.config)

    verbose = False

    try:
        print("Checking local node configuration file: {}".format(configfile))
        config = check_config_file(configfile, default_native_workers())
    except Exception as e:
        print("Error: {}".format(e))
        sys.exit(1)
    else:
        print("Ok, node configuration looks good!")

        if verbose:
            config_content = json.dumps(
                config,
                skipkeys=False,
                sort_keys=False,
                ensure_ascii=False,
                separators=(',', ': '),
                indent=4,
            )
            print(color_json(config_content))

        sys.exit(0)


def _run_command_convert(options, **kwargs):
    """
    Subcommand "crossbar convert".
    """
    configfile = os.path.join(options.cbdir, options.config)

    print("Converting local configuration file {}".format(configfile))

    try:
        convert_config_file(configfile)
    except Exception as e:
        print("\nError: {}\n".format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def _run_command_upgrade(options, **kwargs):
    """
    Subcommand "crossbar upgrade".
    """
    configfile = os.path.join(options.cbdir, options.config)

    print("Upgrading local configuration file {}".format(configfile))

    try:
        upgrade_config_file(configfile)
    except Exception as e:
        print("\nError: {}\n".format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def _run_command_keygen(options, **kwargs):
    """
    Subcommand "crossbar keygen".
    """

    try:
        from autobahn.wamp.cryptobox import KeyRing
    except ImportError:
        print("You should install 'autobahn[encryption]'")
        sys.exit(1)

    priv, pub = KeyRing().generate_key()
    print('  private: {}'.format(priv))
    print('   public: {}'.format(pub))


_HELP_DESCRIPTION = _DEFAULT_PERSONALITY_KLASS.DESC


_HELP_PERSONALITIES = """Software personality to use:
 "standalone" (Crossbar.io single node, AGPL),
 "fabric" (Crossbar.io mesh node, license required),
 "fabriccenter" (Crossbar.io mesh controller, license required)
"""


def _add_personality_argument(parser):
    parser.add_argument('--personality',
                        type=six.text_type,
                        default=_DEFAULT_PERSONALITY,
                        choices=sorted(_INSTALLED_PERSONALITIES.keys()) + ['community'],
                        help=(_HELP_PERSONALITIES))


def main(prog, args, reactor):
    """
    Entry point of Crossbar.io CLI.
    """
    # print banner and usage notes when started with empty args
    #
    if args is not None:
        if not args:
            print(hl(_DEFAULT_PERSONALITY_KLASS.BANNER, color='yellow', bold=True))
            print('Type "crossbar --help to get help, or "crossbar <command> --help" to get help on a specific command.')
            print('Type "crossbar legal" to read legal notices, terms of use and license and privacy information.')
            print('Type "crossbar version" to print detailed version information.')
            return

    # create the top-level parser
    #
    parser = argparse.ArgumentParser(prog=prog or 'crossbar', description=_HELP_DESCRIPTION)

    _add_personality_argument(parser)

    # create subcommand parser
    #
    subparsers = parser.add_subparsers(dest='command',
                                       title='commands',
                                       help='Command to run (required)')
    subparsers.required = True

    # #############################################################

    # some shared arguments
    #
    log_level_args = {
        "type": str,
        "default": 'info',
        "choices": ['none', 'error', 'warn', 'info', 'debug', 'trace'],
        "help": ("How much Crossbar.io should log to the terminal, in order "
                 "of verbosity.")
    }

    color_args = {
        "type": str,
        "default": "auto",
        "choices": ["true", "false", "auto"],
        "help": "If logging should be colored."
    }

    # "init" command
    #
    parser_init = subparsers.add_parser('init',
                                        help='Initialize a new Crossbar.io node.')

    parser_init.set_defaults(func=_run_command_init)

    _add_personality_argument(parser_init)

    parser_init.add_argument('--appdir',
                             type=six.text_type,
                             default=None,
                             help="Application base directory where to create app and node from template.")

    # "start" command
    #
    parser_start = subparsers.add_parser('start',
                                         help='Start a Crossbar.io node.')

    parser_start.set_defaults(func=_run_command_start)

    _add_personality_argument(parser_start)

    parser_start.add_argument('--cbdir',
                              type=six.text_type,
                              default=None,
                              help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_start.add_argument('--config',
                              type=six.text_type,
                              default=None,
                              help="Crossbar.io configuration file (overrides default CBDIR/config.json)")

    parser_start.add_argument('--logdir',
                              type=six.text_type,
                              default=None,
                              help="Crossbar.io log directory (default: <Crossbar Node Directory>/)")

    parser_start.add_argument('--logtofile',
                              action='store_true',
                              help="Whether or not to log to file")

    parser_start.add_argument('--loglevel',
                              **log_level_args)

    parser_start.add_argument('--color',
                              **color_args)

    parser_start.add_argument('--logformat',
                              type=six.text_type,
                              default='standard',
                              choices=['syslogd', 'standard', 'none'],
                              help=("The format of the logs -- suitable for "
                                    "syslogd, not colored, or colored."))

    # "stop" command
    #
    parser_stop = subparsers.add_parser('stop',
                                        help='Stop a Crossbar.io node.')

    parser_stop.set_defaults(func=_run_command_stop)

    _add_personality_argument(parser_stop)

    parser_stop.add_argument('--cbdir',
                             type=six.text_type,
                             default=None,
                             help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    # "status" command
    #
    parser_status = subparsers.add_parser('status',
                                          help='Checks whether a Crossbar.io node is running.')

    parser_status.set_defaults(func=_run_command_status)

    _add_personality_argument(parser_status)

    parser_status.add_argument('--cbdir',
                               type=six.text_type,
                               default=None,
                               help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_status.add_argument('--assert',
                               type=six.text_type,
                               default=None,
                               choices=['running', 'stopped'],
                               help=("If given, assert the node is in this state, otherwise exit with error."))

    # "check" command
    #
    parser_check = subparsers.add_parser('check',
                                         help='Check a Crossbar.io node`s local configuration file.')

    parser_check.set_defaults(func=_run_command_check)

    _add_personality_argument(parser_check)

    parser_check.add_argument('--loglevel',
                              **log_level_args)

    parser_check.add_argument('--color',
                              **color_args)

    parser_check.add_argument('--cbdir',
                              type=six.text_type,
                              default=None,
                              help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_check.add_argument('--config',
                              type=six.text_type,
                              default=None,
                              help="Crossbar.io configuration file (overrides default CBDIR/config.json)")

    # "convert" command
    #
    parser_convert = subparsers.add_parser('convert',
                                           help='Convert a Crossbar.io node`s local configuration file from JSON to YAML or vice versa.')

    parser_convert.set_defaults(func=_run_command_convert)

    _add_personality_argument(parser_convert)

    parser_convert.add_argument('--cbdir',
                                type=six.text_type,
                                default=None,
                                help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_convert.add_argument('--config',
                                type=six.text_type,
                                default=None,
                                help="Crossbar.io configuration file (overrides default CBDIR/config.json)")

    # "upgrade" command
    #
    parser_upgrade = subparsers.add_parser('upgrade',
                                           help='Upgrade a Crossbar.io node`s local configuration file to current configuration file format.')

    parser_upgrade.set_defaults(func=_run_command_upgrade)

    _add_personality_argument(parser_upgrade)

    parser_upgrade.add_argument('--cbdir',
                                type=six.text_type,
                                default=None,
                                help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_upgrade.add_argument('--config',
                                type=six.text_type,
                                default=None,
                                help="Crossbar.io configuration file (overrides default CBDIR/config.json)")

    # "keygen" command
    #
    if False:
        parser_keygen = subparsers.add_parser(
            'keygen',
            help='Generate public/private keypairs for use with autobahn.wamp.cryptobox.KeyRing'
        )

        parser_keygen.set_defaults(func=_run_command_keygen)

        _add_personality_argument(parser_keygen)

    # "keys" command
    #
    parser_keys = subparsers.add_parser('keys',
                                        help='Print Crossbar.io release and node key (public key part by default).')

    parser_keys.add_argument('--generate',
                             '-g',
                             action='store_true',
                             help='Generate a new node key pair if none exists, or loads/checks existing.')

    parser_keys.add_argument('--private',
                             '-p',
                             action='store_true',
                             help='Print the node private key instead of the public key.')

    parser_keys.set_defaults(func=_run_command_keys)

    _add_personality_argument(parser_keys)

    parser_keys.add_argument('--cbdir',
                             type=six.text_type,
                             default=None,
                             help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_keys.add_argument('--loglevel',
                             **log_level_args)
    parser_keys.add_argument('--color',
                             **color_args)

    # "version" command
    #
    parser_version = subparsers.add_parser('version',
                                           help='Print software versions.')

    parser_version.set_defaults(func=_run_command_version)

    _add_personality_argument(parser_version)

    parser_version.add_argument('--loglevel',
                                **log_level_args)
    parser_version.add_argument('--color',
                                **color_args)

    # "legal" command
    #
    parser_legal = subparsers.add_parser('legal',
                                         help='Print legal and licensing information.')

    parser_legal.set_defaults(func=_run_command_legal)

    _add_personality_argument(parser_legal)

    # INTERNAL USE! start a worker (this is used by the controller to start worker processes
    # but cannot be used outside that context.
    # argparse.SUPPRESS does not work here =( so we obfuscate the name to discourage use.
    #
    parser_worker = subparsers.add_parser('_exec_worker', help='Program internal use.')
    parser_worker = process.get_argument_parser(parser_worker)
    parser_worker.set_defaults(func=process.run)

    # #############################################################

    # parse cmd line args
    #
    options = parser.parse_args(args)
    if args:
        options.argv = [prog] + args
    else:
        options.argv = sys.argv

    # backward compat for personality name "community": renamed to "standalone"
    #
    if options.personality == 'community':
        options.personality = 'standalone'
        print('Personality name "community" deprecated: please use "standalone" (automatically selected now)')

    # colored logging does not work on Windows, so overwrite it!
    #
    if sys.platform == 'win32':
        options.color = False

    # IMPORTANT: keep the reactor install as early as possible to
    # avoid importing any Twisted module that comes with the side effect
    # of installing a default reactor (which might not be what we want!).
    if not reactor:
        # we use an Autobahn utility to import the "best" available Twisted reactor
        reactor = install_reactor(explicit_reactor=options.reactor,
                                  verbose=False,
                                  require_optimal_reactor=False)

    # ################## Twisted reactor installed FROM HERE ##################

    # Crossbar.io node directory
    #
    if hasattr(options, 'cbdir'):
        if not options.cbdir:
            if "CROSSBAR_DIR" in os.environ:
                options.cbdir = os.environ['CROSSBAR_DIR']
            elif os.path.isdir('.crossbar'):
                options.cbdir = '.crossbar'
            else:
                options.cbdir = '.'

        options.cbdir = os.path.abspath(options.cbdir)

        # convenience: if --cbdir points to a config file, take
        # the config file's base dirname as node directory
        if os.path.isfile(options.cbdir):
            options.cbdir = os.path.dirname(options.cbdir)

        # convenience: auto-create directory if not existing
        if not os.path.isdir(options.cbdir):
            try:
                os.mkdir(options.cbdir)
            except Exception as e:
                print("Could not create node directory: {}".format(e))
                sys.exit(1)
            else:
                print("Auto-created node directory {}".format(options.cbdir))

    # Crossbar.io node configuration file
    #
    if hasattr(options, 'config'):
        # if not explicit config filename is given, try to auto-detect .
        if not options.config:
            for f in ['config.yaml', 'config.json']:
                fn = os.path.join(options.cbdir, f)
                if os.path.isfile(fn) and os.access(fn, os.R_OK):
                    options.config = f
                    break

    # Log directory
    #
    if hasattr(options, 'logdir'):
        if options.logdir:
            options.logdir = os.path.abspath(os.path.join(options.cbdir, options.logdir))
            if not os.path.isdir(options.logdir):
                try:
                    os.mkdir(options.logdir)
                except Exception as e:
                    print("Could not create log directory: {}".format(e))
                    sys.exit(1)
                else:
                    print("Auto-created log directory {}".format(options.logdir))

    # Start the logger
    #
    _start_logging(options, reactor)

    # run the subcommand selected
    #
    try:
        options.func(options, reactor=reactor)
    except SystemExit as e:
        # SystemExit(0) is okay! Anything other than that is bad and should be
        # re-raised.
        if e.args[0] != 0:
            raise
