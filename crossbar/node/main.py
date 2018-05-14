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
from twisted.internet.defer import inlineCallbacks

from crossbar._util import hl, hlid, hltype, term_print, _add_debug_options, _add_cbdir_config, _add_log_arguments
from crossbar._logging import make_logfile_observer
from crossbar._logging import make_stdout_observer
from crossbar._logging import make_stderr_observer
from crossbar._logging import LogLevel
from crossbar.common.key import _maybe_generate_key

import crossbar

from autobahn.websocket.protocol import WebSocketProtocol
from autobahn.websocket.utf8validator import Utf8Validator
from autobahn.websocket.xormasker import XorMaskerNull

from crossbar.node.template import Templates
from crossbar.common.checkconfig import color_json, InvalidConfigException
from crossbar.worker import main as worker_main

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


def _run_command_legal(options, reactor, personality):
    """
    Subcommand "crossbar legal".
    """
    package, resource_name = personality.LEGAL
    filename = pkg_resources.resource_filename(package, resource_name)
    filepath = os.path.abspath(filename)
    with open(filepath) as f:
        legal = f.read()
        print(legal)


def _run_command_version(options, reactor, personality):
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

    # crossbarfx
    try:
        from crossbarfx._version import __version__ as crossbarfx_ver  # noqa
    except ImportError:
        crossbarfx_ver = '-'

    # txaio-etcd
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

    pad = " " * 22
    for line in personality.BANNER.splitlines():
        log.info(hl(line, color='yellow', bold=True))
    log.info("")
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
    if personality.NAME in (u'edge', u'master'):
        log.info(" Crossbar.io FX     : {ver}", ver=decorate(crossbarfx_ver))
    if personality.NAME in (u'master'):
        log.info("   txaioetcd        : {ver}", ver=decorate(txaioetcd_ver))
    log.info(" Frozen executable  : {py_is_frozen}", py_is_frozen=decorate('yes' if py_is_frozen else 'no'))
    log.info(" Operating system   : {ver}", ver=decorate(platform.platform()))
    log.info(" Host machine       : {ver}", ver=decorate(platform.machine()))
    log.info(" Release key        : {release_pubkey}", release_pubkey=decorate(release_pubkey[u'base64']))
    log.info("")


def _run_command_keys(options, reactor, personality):
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


def _run_command_init(options, reactor, personality):
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


def _run_command_status(options, reactor, personality):
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


def _run_command_stop(options, reactor, personality):
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


def _run_command_start(options, reactor, personality):
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
    node_options = personality.NodeOptions(debug_lifecycle=options.debug_lifecycle,
                                           debug_programflow=options.debug_programflow)

    node = personality.Node(personality,
                            options.cbdir,
                            reactor=reactor,
                            options=node_options)

    # print the banner, personality and node directory
    #
    for line in personality.BANNER.splitlines():
        log.info(hl(line, color='yellow', bold=True))
    log.info('')
    log.info('Initializing {node_personality} node from node directory {cbdir} {node_class}',
             node_personality=personality,
             cbdir=hlid(options.cbdir),
             node_class=hltype(personality.Node))

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

    # https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IReactorCore.html
    # Each "system event" in Twisted, such as 'startup', 'shutdown', and 'persist', has 3 phases:
    # 'before', 'during', and 'after' (in that order, of course). These events will be fired
    # internally by the Reactor.

    def before_reactor_started():
        term_print('CROSSBAR:REACTOR_STARTING')

    def after_reactor_started():
        term_print('CROSSBAR:REACTOR_STARTED')

    reactor.addSystemEventTrigger('before', 'startup', before_reactor_started)
    reactor.addSystemEventTrigger('after', 'startup', after_reactor_started)

    def before_reactor_stopped():
        term_print('CROSSBAR:REACTOR_STOPPING')

    def after_reactor_stopped():
        # FIXME: we are indeed reaching this line, however,
        # the log output does not work (it also doesnt work using
        # plain old print). Dunno why.

        # my theory about this issue is: by the time this line
        # is reached, Twisted has already closed the stdout/stderr
        # pipes. hence we do an evil trick: we directly write to
        # the process' controlling terminal
        # https://unix.stackexchange.com/a/91716/52500
        term_print('CROSSBAR:REACTOR_STOPPED')

    reactor.addSystemEventTrigger('before', 'shutdown', before_reactor_stopped)
    reactor.addSystemEventTrigger('after', 'shutdown', after_reactor_stopped)

    # now actually start the node ..
    #
    exit_info = {'was_clean': None}

    def start_crossbar():
        term_print('CROSSBAR:NODE_STARTING')

        #
        # ****** main entry point of node ******
        #
        d = node.start()

        # node started successfully, and later ..
        def on_startup_success(_shutdown_complete):
            term_print('CROSSBAR:NODE_STARTED')

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
            term_print('CROSSBAR:NODE_STARTUP_FAILED')
            exit_info['was_clean'] = False
            log.error("Could not start node: {tb}", tb=failure_format_traceback(err))
            if reactor.running:
                reactor.stop()

        d.addCallbacks(on_startup_success, on_startup_error)

    # Call a function when the reactor is running. If the reactor has not started, the callable
    # will be scheduled to run when it does start.
    reactor.callWhenRunning(start_crossbar)

    # Special feature to automatically shutdown the node after this many seconds
    if options.shutdownafter:

        @inlineCallbacks
        def _shutdown():
            term_print('CROSSBAR:SHUTDOWN_AFTER_FIRED')
            shutdown_info = yield node.stop()
            exit_info['was_clean'] = shutdown_info['was_clean']
            term_print('CROSSBAR:SHUTDOWN_AFTER_COMPLETE')

        reactor.callLater(options.shutdownafter, _shutdown)

    # now enter event loop ..
    #
    log.info(hl('Entering event reactor ...', color='cyan', bold=True))
    term_print('CROSSBAR:REACTOR_ENTERED')
    reactor.run()

    # once the reactor has finally stopped, we get here, and at that point,
    # exit_info['was_clean'] MUST have been set before - either to True or to False
    # (otherwise we are missing a code path to handle in above)

    # exit the program with exit code depending on whether the node has been cleanly shut down
    if exit_info['was_clean'] is True:
        term_print('CROSSBAR:EXIT_WITH_SUCCESS')
        sys.exit(0)

    elif exit_info['was_clean'] is False:
        term_print('CROSSBAR:EXIT_WITH_ERROR')
        sys.exit(1)

    else:
        term_print('CROSSBAR:EXIT_WITH_INTERNAL_ERROR')
        sys.exit(1)


def _run_command_check(options, reactor, personality):
    """
    Subcommand "crossbar check".
    """
    configfile = os.path.join(options.cbdir, options.config)

    verbose = False

    try:
        print("Checking local node configuration file: {}".format(configfile))
        config = personality.check_config_file(personality, configfile)
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


def _run_command_convert(options, reactor, personality):
    """
    Subcommand "crossbar convert".
    """
    configfile = os.path.join(options.cbdir, options.config)

    print("Converting local configuration file {}".format(configfile))

    try:
        personality.convert_config_file(personality, configfile)
    except Exception as e:
        print("\nError: {}\n".format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def _run_command_upgrade(options, reactor, personality):
    """
    Subcommand "crossbar upgrade".
    """
    configfile = os.path.join(options.cbdir, options.config)

    print("Upgrading local configuration file {}".format(configfile))

    try:
        personality.upgrade_config_file(personality, configfile)
    except Exception as e:
        print("\nError: {}\n".format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def _run_command_keygen(options, reactor, personality):
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


def _print_usage(prog, personality):
    print(hl(personality.BANNER, color='yellow', bold=True))
    print('Type "{} --help" to get help, or "{} <command> --help" to get help on a specific command.'.format(prog, prog))
    print('Type "{} legal" to read legal notices, terms of use and license and privacy information.'.format(prog))
    print('Type "{} version" to print detailed version information.'.format(prog))


def main(prog, args, reactor, personality):
    """
    Entry point of Crossbar.io CLI.
    """
    from crossbar import _util
    _util.set_flags_from_args(args)

    term_print('CROSSBAR:MAIN_ENTRY')

    # print banner and usage notes when started with empty args
    #
    if args is not None and '--help' not in args:
        # if all args are options (start with "-"), then we don't have a command,
        # but we need one! hence, print a usage message
        if not [x for x in args if not x.startswith('-')]:
            _print_usage(prog, personality)
            return

    # create the top-level parser
    #
    parser = argparse.ArgumentParser(prog=prog, description=personality.DESC)

    _add_debug_options(parser)

    # create subcommand parser
    #
    subparsers = parser.add_subparsers(dest='command',
                                       title='commands',
                                       help='Command to run (required)')
    subparsers.required = True

    # #############################################################

    # "init" command
    #
    parser_init = subparsers.add_parser('init',
                                        help='Initialize a new Crossbar.io node.')

    parser_init.add_argument('--appdir',
                             type=six.text_type,
                             default=None,
                             help="Application base directory where to create app and node from template.")

    parser_init.set_defaults(func=_run_command_init)

    # "start" command
    #
    parser_start = subparsers.add_parser('start',
                                         help='Start a Crossbar.io node.')

    _add_log_arguments(parser_start)
    _add_cbdir_config(parser_start)

    parser_start.add_argument('--shutdownafter',
                              type=int,
                              default=None,
                              help='Automatically shutdown node after this many seconds.')

    parser_start.set_defaults(func=_run_command_start)

    # "stop" command
    #
    parser_stop = subparsers.add_parser('stop',
                                        help='Stop a Crossbar.io node.')

    parser_stop.add_argument('--cbdir',
                             type=six.text_type,
                             default=None,
                             help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_stop.set_defaults(func=_run_command_stop)

    # "status" command
    #
    parser_status = subparsers.add_parser('status',
                                          help='Checks whether a Crossbar.io node is running.')

    parser_status.add_argument('--cbdir',
                               type=six.text_type,
                               default=None,
                               help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_status.add_argument('--assert',
                               type=six.text_type,
                               default=None,
                               choices=['running', 'stopped'],
                               help=("If given, assert the node is in this state, otherwise exit with error."))

    parser_status.set_defaults(func=_run_command_status)

    # "check" command
    #
    parser_check = subparsers.add_parser('check',
                                         help='Check a Crossbar.io node`s local configuration file.')

    _add_cbdir_config(parser_check)

    parser_check.set_defaults(func=_run_command_check)

    # "convert" command
    #
    parser_convert = subparsers.add_parser('convert',
                                           help='Convert a Crossbar.io node`s local configuration file from JSON to YAML or vice versa.')

    _add_cbdir_config(parser_convert)

    parser_convert.set_defaults(func=_run_command_convert)

    # "upgrade" command
    #
    parser_upgrade = subparsers.add_parser('upgrade',
                                           help='Upgrade a Crossbar.io node`s local configuration file to current configuration file format.')

    _add_cbdir_config(parser_upgrade)

    parser_upgrade.set_defaults(func=_run_command_upgrade)

    # "keygen" command
    #
    if False:
        parser_keygen = subparsers.add_parser(
            'keygen',
            help='Generate public/private keypairs for use with autobahn.wamp.cryptobox.KeyRing'
        )
        parser_keygen.set_defaults(func=_run_command_keygen)

    # "keys" command
    #
    parser_keys = subparsers.add_parser('keys',
                                        help='Print Crossbar.io release and node key (public key part by default).')

    parser_keys.add_argument('--cbdir',
                             type=six.text_type,
                             default=None,
                             help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser_keys.add_argument('--generate',
                             action='store_true',
                             help='Generate a new node key pair if none exists, or loads/checks existing.')

    parser_keys.add_argument('--private',
                             action='store_true',
                             help='Print the node private key instead of the public key.')

    parser_keys.set_defaults(func=_run_command_keys)

    # "version" command
    #
    parser_version = subparsers.add_parser('version',
                                           help='Print software versions.')

    parser_version.set_defaults(func=_run_command_version)

    # "legal" command
    #
    parser_legal = subparsers.add_parser('legal',
                                         help='Print legal and licensing information.')

    parser_legal.set_defaults(func=_run_command_legal)

    # INTERNAL USE! start a worker (this is used by the controller to start worker processes
    # but cannot be used outside that context.
    # argparse.SUPPRESS does not work here =( so we obfuscate the name to discourage use.
    #
    parser_worker = subparsers.add_parser('_exec_worker', help='Program internal use.')
    parser_worker = worker_main.get_argument_parser(parser_worker)

    parser_worker.set_defaults(func=worker_main._run_command_exec_worker)

    # #############################################################

    # parse cmd line args
    #
    options = parser.parse_args(args)
    options.argv = [prog] + args

    if hasattr(options, 'shutdownafter') and options.shutdownafter:
        options.shutdownafter = float(options.shutdownafter)

    # colored logging does not work on Windows, so overwrite it!
    # FIXME: however, printing the banner in color works at least now:
    # So maybe we can get the actual log output also working in color.
    if sys.platform == 'win32':
        options.color = False

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
    term_print('CROSSBAR:LOGGING_STARTED')

    # run the subcommand selected
    #
    try:
        options.func(options, reactor=reactor, personality=personality)
    except SystemExit as e:
        # SystemExit(0) is okay! Anything other than that is bad and should be
        # re-raised.
        if e.args[0] != 0:
            raise
