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
import re
import six
import inspect
import json
import warnings

from json import JSONEncoder

from functools import partial

from zope.interface import provider

from twisted.logger import ILogObserver, formatEvent, Logger, globalLogPublisher
from twisted.logger import LogLevel, globalLogBeginner, formatTime

from twisted.python.constants import NamedConstant
from twisted.python.reflect import qual

from pygments import highlight, lexers, formatters

from weakref import WeakKeyDictionary

from ._log_categories import log_keys

record_separator = u"\x1e"
cb_logging_aware = u"CROSSBAR_RICH_LOGGING_ENABLE=True"

_loggers = WeakKeyDictionary()
_loglevel = "info"  # Default is "info"


def set_global_log_level(level):
    """
    Set the global log level on all the loggers that have the level not
    explicitly set.
    """
    for item in _loggers.keys():
        if not item._log_level_explicitly_set:
            item._log_level = level
    global _loglevel
    _loglevel = level


try:
    from colorama import Fore
except ImportError:
    # No colorama, so just mock it out.
    class _Fore(object):
        BLACK = ""
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        WHITE = ""
        RESET = ""
        LIGHTBLACK_EX = ""
        LIGHTRED_EX = ""
        LIGHTGREEN_EX = ""
        LIGHTYELLOW_EX = ""
        LIGHTBLUE_EX = ""
        LIGHTMAGENTA_EX = ""
        LIGHTCYAN_EX = ""
        LIGHTWHITE_EX = ""
    Fore = _Fore()

STANDARD_FORMAT = u"{startcolour}{time} [{system}]{endcolour} {text}"
SYSLOGD_FORMAT = u"{startcolour}[{system}]{endcolour} {text}"
NONE_FORMAT = u"{text}"

POSSIBLE_LEVELS = ["none", "critical", "error", "warn", "info", "debug",
                   "trace"]
REAL_LEVELS = ["critical", "error", "warn", "info", "debug"]

# Sanity check
assert set(REAL_LEVELS).issubset(set(POSSIBLE_LEVELS))

# A regex that matches ANSI escape sequences
# http://stackoverflow.com/a/33925425
_ansi_cleaner = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")


def strip_ansi(text):
    """
    Strip ANSI codes.
    """
    return _ansi_cleaner.sub('', text)


def escape_formatting(text):
    """
    Escape things that would otherwise confuse `.format`.
    """
    return text.replace(u"{", u"{{").replace(u"}", u"}}")


def make_stdout_observer(levels=(LogLevel.info, LogLevel.debug),
                         show_source=False, format="standard", trace=False,
                         colour=False, _file=None):
    """
    Create an observer which prints logs to L{sys.stdout}.
    """
    if _file is None:
        _file = sys.__stdout__

    @provider(ILogObserver)
    def StandardOutObserver(event):

        if event["log_level"] not in levels:
            return

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_namespace") is not None:
            logSystem += " " + event.get("cb_namespace", event.get("log_namespace", ''))

        if format == "standard":
            FORMAT_STRING = STANDARD_FORMAT
        elif format == "syslogd":
            FORMAT_STRING = SYSLOGD_FORMAT
        elif format == "none":
            FORMAT_STRING = NONE_FORMAT
        else:
            assert False

        if colour:
            # Choose a colour depending on where the log came from.
            if "Controller" in logSystem:
                fore = Fore.BLUE
            elif "Router" in logSystem:
                fore = Fore.YELLOW
            elif "Container" in logSystem:
                fore = Fore.GREEN
            else:
                fore = Fore.WHITE

            eventString = FORMAT_STRING.format(
                startcolour=fore, time=formatTime(event["log_time"]),
                system=logSystem, endcolour=Fore.RESET,
                text=formatEvent(event))
        else:
            eventString = strip_ansi(FORMAT_STRING.format(
                startcolour=u'', time=formatTime(event["log_time"]),
                system=logSystem, endcolour=u'',
                text=formatEvent(event)))

        print(eventString, file=_file)

    return StandardOutObserver


def make_stderr_observer(levels=(LogLevel.warn, LogLevel.error,
                                 LogLevel.critical),
                         show_source=False, format="standard",
                         colour=False, _file=None):
    """
    Create an observer which prints logs to L{sys.stderr}.
    """
    if _file is None:
        _file = sys.__stderr__

    @provider(ILogObserver)
    def StandardErrorObserver(event):

        if event["log_level"] not in levels:
            return

        if event.get("log_system", u"-") == u"-":
            logSystem = u"{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_namespace") is not None:
            logSystem += " " + event.get("cb_namespace", event.get("log_namespace", ''))

        if event.get("log_format", None) is not None:
            eventText = formatEvent(event)
        else:
            eventText = u""

        if "log_failure" in event:
            # This is a traceback. Print it.
            eventText = eventText + event["log_failure"].getTraceback()

        if format == "standard":
            FORMAT_STRING = STANDARD_FORMAT
        elif format == "syslogd":
            FORMAT_STRING = SYSLOGD_FORMAT
        elif format == "none":
            FORMAT_STRING = NONE_FORMAT
        else:
            assert False

        if colour:
            # Errors are always red.
            fore = Fore.RED

            eventString = FORMAT_STRING.format(
                startcolour=fore, time=formatTime(event["log_time"]),
                system=logSystem, endcolour=Fore.RESET,
                text=formatEvent(event))
        else:
            eventString = strip_ansi(FORMAT_STRING.format(
                startcolour=u'', time=formatTime(event["log_time"]),
                system=logSystem, endcolour=u'',
                text=formatEvent(event)))

        print(eventString, file=_file)

    return StandardErrorObserver


def make_JSON_observer(outFile):
    """
    Make an observer which writes JSON to C{outfile}.
    """
    class CrossbarEncoder(JSONEncoder):
        def default(self, o):
            return escape_formatting(repr(o))
    encoder = CrossbarEncoder()

    @provider(ILogObserver)
    def _make_json(_event):
        event = dict(_event)
        level = event.pop("log_level", LogLevel.info).name

        # as soon as possible, we wish to give up if this event is
        # outside our target log-level; this is to prevent
        # (de-)serializing all the debug() messages (for example) from
        # workers to the controller.
        if POSSIBLE_LEVELS.index(level) > POSSIBLE_LEVELS.index(_loglevel):
            return

        done_json = {
            "level": level,
            "namespace": event.pop("log_namespace", '')
        }

        eventText = formatEvent(event)

        if "log_failure" in event:
            # This is a traceback. Print it.
            traceback = event["log_failure"].getTraceback()

            if not six.PY3:
                traceback = traceback.decode('utf-8')
                linesep = os.linesep.decode('utf-8')
            else:
                linesep = os.linesep

            eventText = eventText + linesep + traceback

        done_json["text"] = escape_formatting(eventText)

        try:
            event.pop("log_logger", "")
            event.pop("log_format", "")
            event.pop("log_source", "")
            event.pop("log_system", "")
            event.pop("log_failure", "")
            event.pop("failure", "")
            event.update(done_json)

            text = encoder.encode(event)

        except Exception:
            text = encoder.encode({
                "text": done_json["text"],
                "level": "error",
                "namespace": "crossbar._logging"})

        if not isinstance(text, six.text_type):
            text = text.decode('utf8')

        print(text, end=record_separator, file=outFile)
        outFile.flush()

    return _make_json


def make_logfile_observer(path, show_source=False):
    """
    Make an observer that writes out to C{path}.
    """
    from twisted.logger import FileLogObserver
    from twisted.python.logfile import DailyLogFile

    f = DailyLogFile.fromFullPath(path)

    def _render(event):

        if event.get("log_system", u"-") == u"-":
            logSystem = u"{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_namespace") is not None:
            logSystem += " " + event.get("cb_namespace", event.get("log_namespace", ''))

        if event.get("log_format", None) is not None:
            eventText = formatEvent(event)
        else:
            eventText = u""

        if "log_failure" in event:
            # This is a traceback. Print it.
            eventText = eventText + event["log_failure"].getTraceback()

        eventString = strip_ansi(STANDARD_FORMAT.format(
            startcolour=u'', time=formatTime(event["log_time"]),
            system=logSystem, endcolour=u'',
            text=eventText)) + os.linesep

        return eventString

    return FileLogObserver(f, _render)


class CrossbarLogger(object):
    """
    A logger that wraps a L{Logger} and no-ops messages that it doesn't want to
    listen to.
    """
    def __init__(self, log_level=None, namespace=None, logger=None, observer=None):

        assert logger is not None and \
            observer is not None and \
            namespace is not None, (
                "Don't make a CrossbarLogger directly, use makeLogger")

        if log_level is None:
            # If an explicit log level isn't given, use the current global log
            # level
            self._setlog_level = _loglevel
            self._log_level_explicitly_set = False
        else:
            self.set_log_level(log_level)

        self.logger = logger(observer=observer, namespace=namespace)

        def _log(self, level, *args, **kwargs):
            """
            When this is called, it checks whether the index is higher than the
            current set level. If it is not, it is a no-op.
            """
            if isinstance(level, NamedConstant):
                level = level.name

            if "log_category" in kwargs:
                if kwargs["log_category"] not in log_keys:
                    warnings.warn("Invalid log ID")

            if POSSIBLE_LEVELS.index(level) <= POSSIBLE_LEVELS.index(self._log_level):
                getattr(self.logger, level)(*args, **kwargs)

        for item in REAL_LEVELS:
            # Set instances of _log which convert to no-ops.
            setattr(self, item, partial(_log, self, item))

        self.emit = partial(_log, self)

    def failure(self, *args, **kwargs):
        if POSSIBLE_LEVELS.index("critical") <= POSSIBLE_LEVELS.index(self._log_level):
            return self.logger.failure(*args, **kwargs)

    def trace(self, *args, **kwargs):
        if POSSIBLE_LEVELS.index("trace") <= POSSIBLE_LEVELS.index(self._log_level):
            return self.debug(*args, cb_trace=True, **kwargs)

    def set_log_level(self, level):
        """
        Explicitly change the log level.
        """
        self._log_level_explicitly_set = True
        self._log_level = level

    @property
    def _log_level(self):
        return self._setlog_level

    @_log_level.setter
    def _log_level(self, level):
        if level not in POSSIBLE_LEVELS:
            raise ValueError(
                "{level} not in {levels}".format(level=level,
                                                 levels=POSSIBLE_LEVELS))
        self._setlog_level = level


def make_logger(log_level=None, logger=Logger, observer=None):
    """
    Make a new logger (of the type set by the kwarg logger) that publishes to
    the observer set in the observer kwarg. If no explicit log_level is given,
    it uses the current global log level.
    """
    if observer is None:
        observer = globalLogPublisher

    # Get the caller's frame
    cf = inspect.currentframe().f_back

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
    globalLogBeginner.beginLoggingTo([])


def color_json(json_str):
    """
    Given an already formatted JSON string, return a colored variant which will
    produce colored output on terminals.
    """
    assert(type(json_str) == six.text_type)
    return highlight(json_str, lexers.JsonLexer(), formatters.TerminalFormatter())


class JSON(object):
    """
    An object which encapsulates a JSON-dumpable item, and will colourise it
    when it is __str__'d.
    """
    def __init__(self, item):
        self._item = item

    def __str__(self):
        json_str = json.dumps(self._item, separators=(', ', ': '),
                              sort_keys=False, indent=3, ensure_ascii=False)
        output_str = os.linesep + color_json(json_str)

        if bytes == str:
            # In case json.dumps returns a not-str on Py2, we will encode
            output_str = output_str.encode('utf8')

        return output_str


class LogCapturer(object):
    """
    A context manager that captures logs inside of it, and makes it available
    through the logs attribute, or the get_category method.
    """
    def __init__(self, level="debug"):
        self.logs = []
        self._old_log_level = _loglevel
        self.desired_level = level

    def get_category(self, identifier):
        """
        Get logs captured with the given log category.
        """
        return [x for x in self.logs if x.get("log_category") == identifier]

    def __enter__(self):
        set_global_log_level(self.desired_level)
        globalLogPublisher.addObserver(self.logs.append)
        return self

    def __exit__(self, type, value, traceback):
        globalLogPublisher.removeObserver(self.logs.append)
        set_global_log_level(self._old_log_level)
