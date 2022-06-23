#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import contextlib
import socket
import sys
import json
import os
import re
import inspect
import uuid
import copy
from collections.abc import Mapping

import click

from autobahn.wamp import CallDetails
from crossbar.common.checkconfig import InvalidConfigException

_ENVPAT_STR = r'^\$\{(.+)\}$'
_ENVPAT = re.compile(_ENVPAT_STR)

DEBUG_LIFECYCLE = False
DEBUG_PROGRAMFLOW = False


def set_flags_from_args(_args):
    global DEBUG_LIFECYCLE
    global DEBUG_PROGRAMFLOW

    for arg in _args:
        if arg.strip().lower() == '--debug-lifecycle':
            DEBUG_LIFECYCLE = True
        if arg.strip().lower() == '--debug-programflow':
            DEBUG_PROGRAMFLOW = True


# FS path to controlling terminal
_TERMINAL = None

# Linux, *BSD and MacOSX
if sys.platform.startswith('linux') or 'bsd' in sys.platform or sys.platform.startswith('darwin'):
    _TERMINAL = '/dev/tty' if os.path.exists('/dev/tty') else None
# Windows
elif sys.platform in ['win32']:
    pass
# Other OS
else:
    pass

# still, we might not be able to use TTY, so duck test it:
if _TERMINAL:
    try:
        with open('/dev/tty', 'w') as f:
            f.write('\n')
            f.flush()
    except:
        # under systemd: OSError: [Errno 6] No such device or address: '/dev/tty'
        _TERMINAL = None


def class_name(obj):
    """
    This returns a name like "module.Class" given either an instance, or a class.
    """

    if inspect.isclass(obj):
        cls = obj
    else:
        cls = obj.__class__
    return '{}.{}'.format(cls.__module__, cls.__name__)


def dump_json(obj, minified=True):
    """
    Dump JSON to a string, either pretty printed or not. Returns a Unicode
    string.
    """
    if minified:
        return json.dumps(obj, separators=(',', ':'), ensure_ascii=False)

    else:
        return json.dumps(obj, indent=4, separators=(',', ': '), sort_keys=False, ensure_ascii=False)


def hl(text, bold=False, color='yellow'):
    """
    Returns highlighted text.
    """
    if not isinstance(text, str):
        text = '{}'.format(text)
    return click.style(text, fg=color, bold=bold)


def _qn(obj):
    if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
        qn = '{}.{}'.format(obj.__module__, obj.__qualname__)
    else:
        qn = 'unknown'
    return qn


# def hltype(obj, render=DEBUG_PROGRAMFLOW):
def hltype(obj, render=True):

    if render:
        qn = _qn(obj).split('.')
        text = hl(qn[0], color='yellow', bold=True) + hl('.' + '.'.join(qn[1:]), color='yellow', bold=False)
        return '<' + text + '>'
    else:
        return ''


def hlflag(flag, true_txt='YES', false_txt='NO', null_txt='UNSET'):
    assert flag is None or type(flag) == bool
    if flag is None:
        return hl('{}'.format(null_txt), color='blue', bold=True)
    elif flag:
        return hl('{}'.format(true_txt), color='green', bold=True)
    else:
        return hl('{}'.format(false_txt), color='red', bold=True)


def hlid(oid):
    return hl('{}'.format(oid), color='blue', bold=True)


def hlval(val, color='white'):
    return hl('{}'.format(val), color=color, bold=True)


def hluserid(oid):
    """
    Returns highlighted text.
    """
    if not isinstance(oid, str):
        oid = '{}'.format(oid)
    return hl('"{}"'.format(oid), color='yellow', bold=True)


def hlfixme(msg, obj):
    return hl('FIXME: {} {}'.format(msg, _qn(obj)), color='green', bold=True)


def hlcontract(oid):
    if not isinstance(oid, str):
        oid = '{}'.format(oid)
    return hl('<{}>'.format(oid), color='magenta', bold=True)


def term_print(text):
    """
    This directly prints to the process controlling terminal (if there is any).
    It bypasses any output redirections, or closes stdout/stderr pipes.

    This can be used eg for "admin messages", such as "node is shutting down now!"

    This currently only works on Unix like systems (tested only on Linux).
    When it cannot do so, it falls back to plain old print.
    """
    if DEBUG_LIFECYCLE:
        text = '{:<44}'.format(text)
        text = click.style(text, fg='blue', bold=True)
        if _TERMINAL:
            with open('/dev/tty', 'w') as f:
                f.write(text + '\n')
                f.flush()
        else:
            print(text)


def _add_debug_options(parser):
    parser.add_argument('--debug-lifecycle',
                        action='store_true',
                        help="This debug flag enables overall program lifecycle messages directly to terminal.")

    parser.add_argument(
        '--debug-programflow',
        action='store_true',
        help="This debug flag enables program flow log messages with fully qualified class/method names.")

    return parser


def _add_cbdir_config(parser):
    parser.add_argument('--cbdir',
                        type=str,
                        default=None,
                        help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser.add_argument('--config',
                        type=str,
                        default=None,
                        help="Crossbar.io configuration file (overrides default CBDIR/config.json)")

    return parser


def _add_log_arguments(parser):
    color_args = dict({
        "type": str,
        "default": "auto",
        "choices": ["true", "false", "auto"],
        "help": "If logging should be colored."
    })
    parser.add_argument('--color', **color_args)

    log_level_args = dict({
        "type": str,
        "default": 'info',
        "choices": ['none', 'error', 'warn', 'info', 'debug', 'trace'],
        "help": ("How much Crossbar.io should log to the terminal, in order of verbosity.")
    })
    parser.add_argument('--loglevel', **log_level_args)

    parser.add_argument('--logformat',
                        type=str,
                        default='standard',
                        choices=['syslogd', 'standard', 'none'],
                        help=("The format of the logs -- suitable for syslogd, not colored, or colored."))

    parser.add_argument('--logdir',
                        type=str,
                        default=None,
                        help="Crossbar.io log directory (default: <Crossbar Node Directory>/)")

    parser.add_argument('--logtofile', action='store_true', help="Whether or not to log to file")

    return parser


def get_free_tcp_port(host='127.0.0.1'):
    """
    Returns random, free listening port.

    .. note::

        This is _not_ completely race free, as a port returned as free is closed
        before returning, and might then be used by another process before the caller
        of this function can actually bind it. So watch out ..

    :param host: Host (interface) for which to return a free port for.
    :type host: str

    :return: Free TCP listening port.
    :rtype: int
    """
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def first_free_tcp_port(host='127.0.0.1', portrange=(1024, 65535)):
    """
    Returns the first free listening port within the given range.

    :param host: Host (interface) for which to return a free port for.
    :type host: str

    :param portrange: Pair of start and end port for port range to select free port within.
    :type portrange: tuple

    :return: Free TCP listening port.
    :rtype: int
    """
    port, max_port = portrange
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while port <= max_port:
        try:
            sock.bind((host, port))
            sock.close()
            return port
        except OSError:
            port += 1
    raise IOError('no free ports')


def get_free_tcp_address(host='127.0.0.1'):
    """
    Returns default local listening address with random port.

    Note: this is _not_ completely race free, as a port returned as free
    might be used by another process before the caller can bind it.

    :return: Default/free listening address:port.
    :rtype: str
    """
    # source: https://gist.github.com/gabrielfalcao/20e567e188f588b65ba2

    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind((host, 0))
    host, port = tcp.getsockname()
    tcp.close()
    address = 'tcp://{host}:{port}'.format(**locals())

    return address


def _deep_merge_map(a, b):
    """

    :param a:
    :param b:
    :return:
    """
    assert isinstance(a, Mapping)
    assert isinstance(b, Mapping)

    new_map = copy.deepcopy(a)

    for k, v in b.items():
        if v is None:
            if k in new_map and new_map[k]:
                del new_map[k]
        else:
            if k in new_map and isinstance(new_map[k], Mapping):
                assert isinstance(v, Mapping)
                new_map[k] = _deep_merge_map(new_map[k], v)

            # use list, not Sequence, since strings are also Sequences!
            # elif k in new_map and isinstance(new_map[k], Sequence):
            elif k in new_map and isinstance(new_map[k], list):
                # assert isinstance(v, Sequence)
                assert isinstance(v, list)

                new_map[k] = _deep_merge_list(new_map[k], v)

            else:
                new_map[k] = v

    return new_map


def _deep_merge_list(a, b):
    """
    Merges two lists. The list being merged must have length >= the
    list into which is merged.


    :param a: The list into which the other list is merged
    :param b: The list to be merged into the former
    :return: The merged list
    """
    # assert isinstance(a, Sequence)
    # assert isinstance(b, Sequence)
    assert isinstance(a, list)
    assert isinstance(b, list)

    assert len(b) >= len(a)
    if len(b) > len(a):
        for i in range(len(a), len(b)):
            assert b[i] is not None
            assert b[i] != 'COPY'

    new_list = []
    i = 0
    for item in b:
        if item is None:
            # drop the item from the target list
            pass
        elif item == 'COPY':
            # copy the item to the target list
            new_list.append(a[i])
        else:
            if i < len(a):
                # add merged item
                new_list.append(_deep_merge_object(a[i], item))
            else:
                # add new item
                new_list.append(item)
        i += 1
    return new_list


def _deep_merge_object(a, b):
    """

    :param a:
    :param b:
    :return:
    """
    # if isinstance(a, Sequence):
    if isinstance(a, list):
        return _deep_merge_list(a, b)
    elif isinstance(a, Mapping):
        return _deep_merge_map(a, b)
    else:
        return b


def merge_config(base_config, other_config):
    """

    :param base_config:
    :param other_config:
    :return:
    """
    if not isinstance(base_config, Mapping):
        raise InvalidConfigException('invalid type for configuration item - expected dict, got {}'.format(
            type(base_config).__name__))

    if not isinstance(other_config, Mapping):
        raise InvalidConfigException('invalid type for configuration item - expected dict, got {}'.format(
            type(other_config).__name__))

    merged_config = copy.deepcopy(base_config)

    if 'controller' in other_config:
        merged_config['controller'] = _deep_merge_map(merged_config.get('controller', {}), other_config['controller'])

    if 'workers' in other_config:
        merged_config['workers'] = _deep_merge_list(base_config.get('workers', []), other_config['workers'])

    return merged_config


def extract_member_oid(details: CallDetails) -> uuid.UUID:
    """
    Extract the XBR network member ID from the WAMP session authid (eg ``member_oid==72de3e0c-ca62-452f-8f09-2d3d30d1b511`` from ``authid=="member-72de3e0c-ca62-452f-8f09-2d3d30d1b511"``

    :param details: Call details.

    :return: Extracted XBR network member ID.
    """
    if details and details.caller_authrole == 'member' and details.caller_authid:
        return uuid.UUID(details.caller_authid[7:])
    else:
        raise RuntimeError('no XBR member identification in call details\n{}'.format(details))


def alternative_username(username):
    max_i = None
    for i in range(len(username) - 1, -1, -1):
        if username[i:].isdigit():
            max_i = i
    if max_i is not None:
        next = int(username[max_i:]) + 1
        alt_username = '{}{}'.format(username[:max_i], next)
    else:
        alt_username = '{}{}'.format(username, 1)
    return alt_username


def maybe_from_env(value):
    if isinstance(value, str):
        match = _ENVPAT.match(value)
        if match and match.groups():
            var = match.groups()[0]
            if var in os.environ:
                new_value = os.environ[var]
                return True, new_value
            else:
                print(
                    'WARNING: environment variable "{}" not set, but needed in XBR backend configuration'.format(var))
                return False, None
        else:
            return False, value
    else:
        return False, value
