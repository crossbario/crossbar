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

from __future__ import absolute_import, division

import sys
import inspect
import json

import six
import click

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

# *BSD and MacOSX
if 'bsd' in sys.platform or sys.platform.startswith('darwin'):
    _TERMINAL = '/dev/tty'
# Windows
elif sys.platform in ['win32']:
    pass
# Linux
elif sys.platform.startswith('linux'):
    _TERMINAL = '/dev/tty'
# Other OS
else:
    pass


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
        return json.dumps(obj, indent=4, separators=(',', ': '),
                          sort_keys=True, ensure_ascii=False)


def hl(text, bold=False, color='yellow'):
    """
    Returns highlighted text.
    """
    if not isinstance(text, six.text_type):
        text = '{}'.format(text)
    return click.style(text, fg=color, bold=bold)


def _qn(obj):
    if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
        qn = '{}.{}'.format(obj.__module__, obj.__qualname__)
    else:
        qn = 'unknown'
    return qn


def hltype(obj, render=DEBUG_PROGRAMFLOW):

    if render:
        qn = _qn(obj).split('.')
        text = hl(qn[0], color='yellow', bold=True) + hl('.' + '.'.join(qn[1:]), color='white', bold=True)
        return '<' + text + '>'
    else:
        return ''


def hlid(oid):
    return hl('{}'.format(oid), color='blue', bold=True)


def hluserid(oid):
    """
    Returns highlighted text.
    """
    if not isinstance(oid, six.text_type):
        oid = '{}'.format(oid)
    return hl('"{}"'.format(oid), color='yellow', bold=True)


def hlfixme(msg, obj):
    return hl('FIXME: {} {}'.format(msg, _qn(obj)), color='green', bold=True)


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

    parser.add_argument('--debug-programflow',
                        action='store_true',
                        help="This debug flag enables program flow log messages with fully qualified class/method names.")

    return parser


def _add_cbdir_config(parser):
    parser.add_argument('--cbdir',
                        type=six.text_type,
                        default=None,
                        help="Crossbar.io node directory (overrides ${CROSSBAR_DIR} and the default ./.crossbar)")

    parser.add_argument('--config',
                        type=six.text_type,
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
                        type=six.text_type,
                        default='standard',
                        choices=['syslogd', 'standard', 'none'],
                        help=("The format of the logs -- suitable for syslogd, not colored, or colored."))

    parser.add_argument('--logdir',
                        type=six.text_type,
                        default=None,
                        help="Crossbar.io log directory (default: <Crossbar Node Directory>/)")

    parser.add_argument('--logtofile',
                        action='store_true',
                        help="Whether or not to log to file")

    return parser
