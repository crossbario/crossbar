#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import sys
import re
import json
from io import StringIO

from json import JSONEncoder

from zope.interface import provider

from twisted.logger import ILogObserver, formatEvent, globalLogPublisher
from twisted.logger import LogLevel, formatTime

from pygments import highlight, lexers, formatters

from txaio import get_global_log_level, set_global_log_level
from txaio.tx import log_levels

from crossbar import _log_categories

record_separator = "\x1e"
cb_logging_aware = "CROSSBAR_RICH_LOGGING_ENABLE=True"

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

STANDARD_FORMAT = "{startcolor}{time} [{system}]{endcolor} {text}"
SYSLOGD_FORMAT = "{startcolor}[{system}]{endcolor} {text}"
NONE_FORMAT = "{text}"

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
    return text.replace("{", "{{").replace("}", "}}")


def make_stdout_observer(levels=(LogLevel.info, ),
                         show_source=False,
                         format="standard",
                         trace=False,
                         color=False,
                         _file=None,
                         _categories=None):
    """
    Create an observer which prints logs to L{sys.stdout}.
    """
    if _file is None:
        _file = sys.__stdout__

    if _categories is None:
        _categories = _log_categories.log_categories

    @provider(ILogObserver)
    def StandardOutObserver(event):

        if event["log_level"] not in levels:
            return

        if event["log_level"] == LogLevel.debug:
            if event.get("txaio_trace", False) and not trace:
                return

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_namespace") is not None:
            logSystem += " " + event.get("cb_namespace", event.get("log_namespace", ''))

        if event.get("log_category"):
            format_string = _categories.get(event['log_category'])
            if format_string:
                event = event.copy()
                event["log_format"] = format_string

        if format == "standard":
            FORMAT_STRING = STANDARD_FORMAT
        elif format == "syslogd":
            FORMAT_STRING = SYSLOGD_FORMAT
        elif format == "none":
            FORMAT_STRING = NONE_FORMAT
        else:
            assert False

        if color:
            # Choose a color depending on where the log came from.
            if "Controller" in logSystem:
                fore = Fore.BLUE
            elif "Router" in logSystem:
                fore = Fore.YELLOW
            elif "Container" in logSystem:
                fore = Fore.GREEN
            else:
                fore = Fore.WHITE

            eventString = FORMAT_STRING.format(startcolor=fore,
                                               time=formatTime(event["log_time"]),
                                               system=logSystem,
                                               endcolor=Fore.RESET,
                                               text=formatEvent(event))
        else:
            eventString = strip_ansi(
                FORMAT_STRING.format(startcolor='',
                                     time=formatTime(event["log_time"]),
                                     system=logSystem,
                                     endcolor='',
                                     text=formatEvent(event)))

        print(eventString, file=_file)

    return StandardOutObserver


def make_stderr_observer(levels=(LogLevel.warn, LogLevel.error, LogLevel.critical),
                         show_source=False,
                         format="standard",
                         color=False,
                         _file=None,
                         _categories=None):
    """
    Create an observer which prints logs to L{sys.stderr}.
    """
    if _file is None:
        _file = sys.__stderr__

    if _categories is None:
        _categories = _log_categories.log_categories

    @provider(ILogObserver)
    def StandardErrorObserver(event):

        if event["log_level"] not in levels:
            return

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_namespace") is not None:
            logSystem += " " + event.get("cb_namespace", event.get("log_namespace", ''))

        if event.get("log_category"):
            format_string = _categories.get(event['log_category'])
            if format_string:
                event = event.copy()
                event["log_format"] = format_string

        if event.get("log_format", None) is not None:
            eventText = formatEvent(event)
        else:
            eventText = ""

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

        if color:
            # Errors are always red.
            fore = Fore.RED

            eventString = FORMAT_STRING.format(startcolor=fore,
                                               time=formatTime(event["log_time"]),
                                               system=logSystem,
                                               endcolor=Fore.RESET,
                                               text=eventText)
        else:
            eventString = strip_ansi(
                FORMAT_STRING.format(startcolor='',
                                     time=formatTime(event["log_time"]),
                                     system=logSystem,
                                     endcolor='',
                                     text=eventText))

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
        if log_levels.index(level) > log_levels.index(get_global_log_level()):
            return

        done_json = {"level": level, "namespace": event.pop("log_namespace", '')}

        eventText = formatEvent(event)

        if "log_failure" in event:
            # This is a traceback. Print it.
            traceback = event["log_failure"].getTraceback()

            eventText = eventText + os.linesep + traceback

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
            text = encoder.encode({"text": done_json["text"], "level": "error", "namespace": "crossbar._logging"})

        if not isinstance(text, str):
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

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if show_source and event.get("log_namespace") is not None:
            logSystem += " " + event.get("cb_namespace", event.get("log_namespace", ''))

        if event.get("log_format", None) is not None:
            eventText = formatEvent(event)
        else:
            eventText = ""

        if "log_failure" in event:
            # This is a traceback. Print it.
            eventText = eventText + event["log_failure"].getTraceback()

        eventString = strip_ansi(
            STANDARD_FORMAT.format(
                startcolor='', time=formatTime(
                    event["log_time"]), system=logSystem, endcolor='', text=eventText)) + os.linesep

        return eventString

    return FileLogObserver(f, _render)


def color_json(json_str):
    """
    Given an already formatted JSON string, return a colored variant which will
    produce colored output on terminals.
    """
    assert (type(json_str) == str)
    return highlight(json_str, lexers.JsonLexer(), formatters.TerminalFormatter())


class JSON(object):
    """
    An object which encapsulates a JSON-dumpable item, and will colorise it
    when it is __str__'d.
    """
    def __init__(self, item):
        self._item = item

    def __str__(self):
        json_str = json.dumps(self._item, separators=(', ', ': '), sort_keys=False, indent=3, ensure_ascii=False)
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
        self._old_log_level = get_global_log_level()
        self.desired_level = level
        self.log_text = StringIO()

        self._out_observer = make_stdout_observer(levels=(LogLevel.debug, LogLevel.info, LogLevel.warn,
                                                          LogLevel.error),
                                                  _file=self.log_text,
                                                  trace=True)

    def get_category(self, identifier):
        """
        Get logs captured with the given log category.
        """
        return [x for x in self.logs if x.get("log_category") == identifier]

    def _got_log(self, log):
        self.logs.append(log)

        # Render them, to make sure there are no "can't format" errors
        self._out_observer(log)

    def __enter__(self):
        set_global_log_level(self.desired_level)
        globalLogPublisher.addObserver(self._got_log)
        return self

    def __exit__(self, type, value, traceback):
        globalLogPublisher.removeObserver(self._got_log)
        set_global_log_level(self._old_log_level)
