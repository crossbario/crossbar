# coding=utf8

##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import os
import re
import inspect
import uuid

import click

from autobahn.wamp import CallDetails

_ENVPAT_STR = r'^\$\{(.+)\}$'
_ENVPAT = re.compile(_ENVPAT_STR)


def hl(text, bold=False, color='yellow'):
    if not isinstance(text, str):
        text = '{}'.format(text)
    return click.style(text, fg=color, bold=bold)


def _qn(obj):
    if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
        qn = '{}.{}'.format(obj.__module__, obj.__qualname__)
    else:
        qn = 'unknown'
    return qn


def hltype(obj):
    qn = _qn(obj).split('.')
    text = hl(qn[0], color='yellow', bold=True) + hl('.' + '.'.join(qn[1:]), color='white', bold=True)
    return '<' + text + '>'


def hlid(oid):
    return hl('{}'.format(oid), color='blue', bold=True)


def hluserid(oid):
    if not isinstance(oid, str):
        oid = '{}'.format(oid)
    return hl('"{}"'.format(oid), color='yellow', bold=True)


def hlval(val, color='white'):
    return hl('{}'.format(val), color=color, bold=True)


def hlcontract(oid):
    if not isinstance(oid, str):
        oid = '{}'.format(oid)
    return hl('<{}>'.format(oid), color='magenta', bold=True)


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
