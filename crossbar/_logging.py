#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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

from __future__ import absolute_import, division, print_function

import os
import sys
import json

from zope.interface import provider

from twisted.logger import ILogObserver, formatEvent, Logger, LogPublisher
from twisted.logger import LogLevel, globalLogBeginner, formatTime
from twisted.logger import FileLogObserver

from twisted.python.reflect import qual

log_publisher = LogPublisher()
log = Logger(observer=log_publisher)

record_separator = u"\x1e"
cb_logging_aware = u"CROSSBAR_RICH_LOGGING_ENABLE=True"

try:
    from colorama import Fore
except ImportError:
    # No colorama, so just mock it out.
    class Fore(object):
        BLUE = ""
        YELLOW = ""
        CYAN = ""
        WHITE = ""
        RED = ""
        RESET = ""
    Fore = Fore()

COLOUR_FORMAT = "{}{} [{}]{} {}"
NOCOLOUR_FORMAT = "{} [{}] {}"
SYSLOGD_FORMAT = "[{}] {}"

# Make our own copies of stdout and stderr, for printing to later
# When we start logging, the logger will capture all outputs to the *new*
# sys.stderr and sys.stdout. As we're printing to it, it'll get caught in an
# infinite loop -- which we don't want.
_stderr, _stdout = sys.stderr, sys.stdout


def escape_formatting(text):
    """
    Escape things that would otherwise confuse `.format`.
    """
    return text.replace(u"{", u"{{").replace(u"}", u"}}")


def make_stdout_observer(levels=(LogLevel.info, LogLevel.debug),
                         show_source=False, format="colour", trace=False):
    """
    Create an observer which prints logs to L{sys.stdout}.
    """
    @provider(ILogObserver)
    def StandardOutObserver(event):

        if not trace and event.get("cb_level") == "trace":
            # Don't output 'trace' output
            return

        if event["log_level"] not in levels:
            return

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_source") is not None:
            logSystem += " " + qual(event["log_source"].__class__)

        if format == "colour":
            # Choose a colour depending on where the log came from.
            if "Controller" in logSystem:
                fore = Fore.BLUE
            elif "Router" in logSystem:
                fore = Fore.YELLOW
            elif "Container" in logSystem:
                fore = Fore.CYAN
            else:
                fore = Fore.WHITE

            eventString = COLOUR_FORMAT.format(
                fore, formatTime(event["log_time"]), logSystem, Fore.RESET,
                formatEvent(event))
        elif format == "nocolour":
            eventString = NOCOLOUR_FORMAT.format(
                formatTime(event["log_time"]), logSystem, formatEvent(event))
        elif format == "syslogd":
            eventString = SYSLOGD_FORMAT.format(logSystem, formatEvent(event))

        print(eventString, file=_stdout)

    return StandardOutObserver


def make_stderr_observer(levels=(LogLevel.warn, LogLevel.error,
                                 LogLevel.critical),
                         show_source=False, format="colour"):
    """
    Create an observer which prints logs to L{sys.stderr}.
    """
    @provider(ILogObserver)
    def StandardErrorObserver(event):

        if event["log_level"] not in levels:
            return

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_source") is not None:
            logSystem += " " + qual(event["log_source"].__class__)

        if format == "colour":
            # Errors are always red, no matter the system they came from.
            eventString = COLOUR_FORMAT.format(
                Fore.RED, formatTime(event["log_time"]), logSystem, Fore.RESET,
                formatEvent(event))
        elif format == "nocolour":
            eventString = NOCOLOUR_FORMAT.format(
                formatTime(event["log_time"]), logSystem, formatEvent(event))
        elif format == "syslogd":
            eventString = SYSLOGD_FORMAT.format(logSystem, formatEvent(event))

        print(eventString, file=_stderr)

    return StandardErrorObserver


def make_JSON_observer(outFile):
    """
    Make an observer which writes JSON to C{outfile}.
    """
    def _make_json(event):

        return json.dumps({
            "text": escape_formatting(formatEvent(event)),
            "level": event.get("log_level", LogLevel.info).name})

    return FileLogObserver(
        outFile,
        lambda event: u"{0}{1}".format(_make_json(event), record_separator)
    )


def make_legacy_daily_logfile_observer(path, logoutputlevel):
    """
    Make a L{DefaultSystemFileLogObserver}.
    """
    from crossbar.twisted.processutil import DefaultSystemFileLogObserver
    from twisted.logger import LegacyLogObserverWrapper
    from twisted.python.logfile import DailyLogFile

    logfd = DailyLogFile.fromFullPath(os.path.join(path,
                                                   'node.log'))
    flo = LegacyLogObserverWrapper(
        DefaultSystemFileLogObserver(logfd,
                                     system="{:<10} {:>6}".format(
                                         "Controller", os.getpid())).emit)

    def _log(event):

        level = event["log_level"]

        if logoutputlevel == "none":
            return
        elif logoutputlevel == "quiet":
            # Quiet: Only print warnings and errors to stderr.
            if level not in (LogLevel.warn, LogLevel.error, LogLevel.critical):
                return
        elif logoutputlevel == "standard":
            # Standard: For users of Crossbar
            if level not in (LogLevel.info, LogLevel.warn, LogLevel.error,
                             LogLevel.critical):
                return
        elif logoutputlevel == "verbose":
            # Verbose: for developers
            # Adds the class source.
            if event.get("cb_level") == "trace":
                return
        elif logoutputlevel == "trace":
            # Verbose: for developers
            # Adds "trace" output
            pass
        else:
            assert False, "Shouldn't ever get here."

        # Forward the event
        flo(event)

    return _log


def make_logger():
    return Logger(observer=log_publisher)


def start_logging():
    """
    Start logging to the publishers.
    """
    globalLogBeginner.beginLoggingTo([log_publisher])
