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

from functools import partial

from zope.interface import provider

from twisted.logger import ILogObserver, formatEvent, Logger, LogPublisher
from twisted.logger import LogLevel, globalLogBeginner, formatTime
from twisted.logger import FileLogObserver

from twisted.python.constants import NamedConstant
from twisted.python.compat import currentframe
from twisted.python.reflect import qual

from weakref import WeakKeyDictionary

log_publisher = LogPublisher()

record_separator = u"\x1e"
cb_logging_aware = u"CROSSBAR_RICH_LOGGING_ENABLE=True"

_loggers = WeakKeyDictionary()
_loglevel = "info"  # Default is "info"


def set_global_log_level(level):
    for item in _loggers.keys():
        item.log_level = level
    global _loglevel
    _loglevel = level


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

        if not trace and event.get("cb_trace") is True:
            # Don't output 'trace' output
            return

        if event["log_level"] not in levels:
            return

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_namespace") is not None:
            logSystem += " " + event.get("cb_namespace", event["log_namespace"])

        if format == "colour":
            # Choose a colour depending on where the log came from.
            if "Controller" in logSystem:
                fore = Fore.BLUE
            elif "Router" in logSystem:
                fore = Fore.YELLOW
            elif "Container" in logSystem:
                fore = Fore.GREEN
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

        if "log_failure" in event and event["log_format"] is None:
            # This is a traceback. Print it.
            print(event["log_failure"].getTraceback(), file=_stderr)
            return

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_namespace") is not None:
            logSystem += " " + event.get("cb_namespace", event["log_namespace"])

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
            "level": event.get("log_level", LogLevel.info).name,
            "namespace": event.get("log_namespace", '')
        })

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

POSSIBLE_LEVELS = ["none", "critical", "error", "warn", "info", "debug",
                   "trace"]
REAL_LEVELS = ["critical", "error", "warn", "info", "debug"]

# Sanity check
assert set(REAL_LEVELS).issubset(set(POSSIBLE_LEVELS))


class CrossbarLogger(object):
    """
    A logger that wraps a L{Logger} and no-ops messages that it doesn't want to
    listen to.
    """
    def __init__(self, log_level, namespace=None, logger=None, observer=None):

        assert logger is not None and \
            observer is not None and \
            namespace is not None, (
                "Don't make a CrossbarLogger directly, use makeLogger")

        self.log_level = log_level
        self.logger = logger(observer=observer, namespace=namespace)

        def _log(self, level, *args, **kwargs):
            """
            When this is called, it checks whether the index is higher than the
            current set level. If it is not, it is a no-op.
            """

            if isinstance(level, NamedConstant):
                level = level.name

            if POSSIBLE_LEVELS.index(level) <= POSSIBLE_LEVELS.index(self.log_level):
                getattr(self.logger, level)(*args, **kwargs)

        for item in REAL_LEVELS:
            # Set instances of _log which convert to no-ops.
            setattr(self, item, partial(_log, self, item))

        self.emit = partial(_log, self)

    def trace(self, *args, **kwargs):
        if POSSIBLE_LEVELS.index("trace") <= POSSIBLE_LEVELS.index(self.log_level):
            return self.debug(*args, cb_trace=True, **kwargs)

    @property
    def log_level(self):
        return self._log_level

    @log_level.setter
    def log_level(self, level):
        if level not in POSSIBLE_LEVELS:
            raise ValueError(
                "{level} not in {levels}".format(level=level,
                                                 levels=POSSIBLE_LEVELS))
        self._log_level = level


def make_logger(log_level=None, logger=Logger, observer=log_publisher):
    """
    Make a new logger (of the type set by the kwarg logger) that publishes to
    the observer set in the observer kwarg. If no explicit log_level is given,
    it uses the current global log level.
    """
    if log_level is None:
        # If an explicit log level isn't given, use the current global log
        # level
        log_level = _loglevel

    # Get the caller's frame
    cf = currentframe(1)

    if "self" in cf.f_locals:
        # We're probably in a class init or method
        namespace = qual(cf.f_locals["self"].__class__)

        logger = CrossbarLogger(log_level,
                                namespace=namespace,
                                logger=logger,
                                observer=observer)
    else:
        namespace = cf.f_globals["__name__"]

        if cf.f_code.co_name != "<module>":
            # If it's not the module, and not in a class instance, add the code
            # object's name.
            namespace = namespace + "." + cf.f_code.co_name

        logger = CrossbarLogger(log_level,
                                namespace=namespace,
                                logger=logger,
                                observer=observer)

    # Set up a weak ref, so that all loggers can be updated later
    _loggers[logger] = True
    return logger


def start_logging():
    """
    Start logging to the publisher.
    """
    globalLogBeginner.beginLoggingTo([log_publisher])
