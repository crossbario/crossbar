###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import sys
import locale
import os
import time

import six
import click

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


def hl(text, bold=False):
    if not isinstance(text, six.text_type):
        text = '{}'.format(text)
    return click.style(text, fg='yellow', bold=bold)


def style_crossbar(text):
    if _HAS_COLOR_TERM:
        return click.style(text, fg='yellow', bold=True)
    else:
        return text


def style_finished_line(text):
    if _HAS_COLOR_TERM:
        return click.style(text, fg='yellow')
    else:
        return text


def style_error(text):
    if _HAS_COLOR_TERM:
        return click.style(text, fg='red', bold=True)
    else:
        return text


def style_ok(text):
    if _HAS_COLOR_TERM:
        return click.style(text, fg='green', bold=True)
    else:
        return text


def localnow():
    return time.strftime(locale.nl_langinfo(locale.D_T_FMT), time.localtime())
