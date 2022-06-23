#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import json

from io import StringIO as NativeStringIO

from io import StringIO

from mock import Mock

from twisted.logger import formatTime
from twisted.python.failure import Failure

from crossbar.test import TestCase
from crossbar._logging import (LogCapturer, make_stdout_observer, make_JSON_observer, record_separator,
                               make_stderr_observer)

from txaio import make_logger, get_global_log_level, set_global_log_level
from txaio.tx import Logger, LogLevel

_log = make_logger("info", logger=Mock)


def _makelog():
    log = make_logger("info", logger=Mock)
    return log


class _InitLoggerMaker(object):
    def __init__(self):
        self.log = make_logger("info", logger=Mock)


class _ClassDefLoggerMaker(object):
    log = make_logger("info", logger=Mock)


class LoggerModuleTests(TestCase):
    def setUp(self):
        self.existing_level = get_global_log_level()
        return super(LoggerModuleTests, self).setUp()

    def tearDown(self):
        set_global_log_level(self.existing_level)

    def test_set_global(self):
        """
        Setting the global log level via the function changes it.
        """
        set_global_log_level("warn")
        self.assertEqual(get_global_log_level(), "warn")

    def test_set_global_changes_loggers(self):
        """
        Setting the global log level changes the level of all loggers that were
        not instantiated with a level.
        """
        log = make_logger()
        self.assertEqual(log._log_level, "info")
        set_global_log_level("warn")
        self.assertEqual(log._log_level, "warn")

    def test_set_global_does_not_change_explicit_loggers(self):
        """
        Setting the global log level does not change loggers that have an
        explicit level set.
        """
        log = make_logger("info")
        self.assertEqual(log._log_level, "info")
        set_global_log_level("warn")
        self.assertEqual(log._log_level, "info")


class CrossbarLoggerTests(TestCase):
    def test_disallow_direct_instantiation(self):
        """
        The developer shouldn't call Logger directly, but use
        make_logger.
        """
        with self.assertRaises(AssertionError):
            Logger("warn")

    def test_set_level(self):
        """
        The log level needs to be one of the accepted log levels.
        """
        with self.assertRaises(ValueError):
            make_logger("not a suitable level")

    def test_logger_emits(self):
        """
        A Logger emits messages through to its child logger.
        """
        log = make_logger("trace", logger=Mock)

        log.error("Foo happened!!!")
        log._logger.emit.assert_called_with(LogLevel.error, "Foo happened!!!")

        log.warn("Stuff", foo="bar")
        log._logger.emit.assert_called_with(LogLevel.warn, "Stuff", foo="bar")

        log.trace("Stuff that's trace", foo="bar")
        log._logger.emit.assert_called_with(LogLevel.debug, "Stuff that's trace", foo="bar", txaio_trace=1)

    def test_logger_emits_if_higher(self):
        """
        A Logger that has a log level of a higher severity will not emit
        messages of a lower severity.
        """
        log = make_logger("info", logger=Mock)

        log.error("Error!")
        log.debug("Debug!")
        log.info("Info!")
        log.trace("Trace!")

        calls = {}

        for x in log._logger.emit.call_args_list:
            calls[x[0][0]] = calls.get(x[0][0], 0) + 1

        self.assertEqual(calls.get(LogLevel.critical, 0), 0)
        self.assertEqual(calls.get(LogLevel.error, 0), 1)
        self.assertEqual(calls.get(LogLevel.warn, 0), 0)
        self.assertEqual(calls.get(LogLevel.info, 0), 1)
        self.assertEqual(calls.get(LogLevel.debug, 0), 0)

    def test_logger_namespace_init(self):
        """
        The namespace of the Logger is of the creator when using __init__.
        """
        lm = _InitLoggerMaker()

        self.assertEqual(lm.log._logger.namespace, "crossbar.test.test_logger._InitLoggerMaker")

    def test_logger_namespace_classdef(self):
        """
        The namespace of the Logger is of the creator when using it in a class
        definition.
        """
        lm = _ClassDefLoggerMaker()

        self.assertEqual(lm.log._logger.namespace, "crossbar.test.test_logger._ClassDefLoggerMaker")

    def test_logger_namespace_moduledef(self):
        """
        The namespace of the Logger is the creator module when it is made in a
        module.
        """
        self.assertEqual(_log._logger.namespace, "crossbar.test.test_logger")

    def test_logger_namespace_function(self):
        """
        The namespace of the Logger is the creator function when it is made in
        a function outside of a class.
        """
        log = _makelog()
        self.assertEqual(log._logger.namespace, "crossbar.test.test_logger._makelog")

    def test_logger_failure(self):
        """
        The failure method catches the in-flight exception.
        """
        log = make_logger("info", logger=Mock)

        try:
            1 / 0
        except:
            log.failure("Failure happened!")

        self.assertEqual(log._logger.failure.call_count, 1)

    def test_logger_failure_not_called(self):
        """
        The failure method isn't called under 'none'.
        """
        log = make_logger("none", logger=Mock)

        try:
            1 / 0
        except:
            log.failure("Failure happened!")

        self.assertEqual(log._logger.failure.call_count, 0)


class JSONObserverTests(TestCase):
    def test_basic(self):
        """
        The JSON observer outputs a stream of log events.
        """
        stream = StringIO()
        observer = make_JSON_observer(stream)
        log = make_logger(observer=observer)

        log.info("Hello")

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], record_separator)
        self.assertEqual(len(log_entry.keys()), 4)
        self.assertEqual(log_entry["level"], "info")
        self.assertEqual(log_entry["text"], "Hello")

    def test_failure(self):
        """
        Failures include the stacktrace.
        """
        stream = StringIO()
        observer = make_JSON_observer(stream)
        log = make_logger(observer=observer)

        try:
            1 / 0
        except:
            log.failure("Oh no {0}".format("!"))

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], record_separator)
        self.assertEqual(len(log_entry.keys()), 4)
        self.assertIn("ZeroDivisionError", log_entry["text"])
        self.assertIn("Oh no !", log_entry["text"])
        self.assertEqual(log_entry["level"], "critical")

    def test_not_json_serialisable(self):
        """
        Non-JSON-serialisable parameters are repr()'d.
        """
        stream = StringIO()
        observer = make_JSON_observer(stream)
        log = make_logger(observer=observer)

        try:
            1 / 0
        except:
            log.failure("Oh no", obj=observer)

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], record_separator)
        self.assertEqual(len(log_entry.keys()), 5)
        self.assertIn("ZeroDivisionError", log_entry["text"])
        self.assertIn("Oh no", log_entry["text"])
        self.assertIn("<function ", log_entry["obj"])
        self.assertEqual(log_entry["level"], "critical")

    def test_repr_formatting(self):
        """
        Non-JSON-serialisable parameters are repr()'d, and any curly brackets
        in the result are escaped.
        """
        stream = StringIO()
        observer = make_JSON_observer(stream)
        log = make_logger(observer=observer)

        class BracketThing(object):
            def __repr__(self):
                return "<BracketThing kwargs={}>"

        log.info("hi {obj}", obj=BracketThing())

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], record_separator)
        self.assertEqual(len(log_entry.keys()), 5)
        self.assertEqual("hi <BracketThing kwargs={{}}>", log_entry["text"])
        self.assertEqual(log_entry["level"], "info")

    def test_raising_during_encoding(self):
        """
        Non-JSON-serialisable parameters are repr()'d, and if that's impossible
        then the message is lost.
        """
        stream = StringIO()
        observer = make_JSON_observer(stream)
        log = make_logger(observer=observer)

        class BadThing(object):
            def __repr__(self):
                raise Exception()

        log.info("hi {obj}", obj=BadThing())

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], record_separator)
        self.assertEqual(len(log_entry.keys()), 3)
        self.assertIn("MESSAGE LOST", log_entry["text"])
        self.assertEqual(log_entry["level"], "error")

    def test_unicode_logs(self):
        """
        Unicode is JSON serialised correctly.
        """
        stream = StringIO()
        observer = make_JSON_observer(stream)
        log = make_logger(observer=observer)

        try:
            raise Exception("\u2603")
        except:
            log.failure("Oh no")

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], record_separator)
        self.assertEqual(len(log_entry.keys()), 4)
        self.assertIn("\u2603", log_entry["text"])
        self.assertEqual(log_entry["level"], "critical")


class StdoutObserverTests(TestCase):
    def test_basic(self):

        stream = NativeStringIO()
        observer = make_stdout_observer(_file=stream)
        log = make_logger(observer=observer)

        log.info("Hi!", log_system="foo")

        result = stream.getvalue()
        self.assertIn("[foo]", result)

    def test_output_standard(self):
        """
        The output format is the time, the system in square brackets, and the
        message.
        """
        stream = NativeStringIO()
        observer = make_stdout_observer(_file=stream, format="standard")
        event = {
            'log_level': LogLevel.info,
            'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
            'log_source': None,
            'log_format': 'Hi there!',
            'log_system': 'foo',
            'log_time': 1434099813.77449
        }

        observer(event)

        result = stream.getvalue()
        self.assertEqual(result[:-1], formatTime(event["log_time"]) + " [foo] Hi there!")

    def test_output_syslogd(self):
        """
        The syslogd output format is the system in square brackets, and the
        message.
        """
        stream = NativeStringIO()
        observer = make_stdout_observer(_file=stream, format="syslogd")
        event = {
            'log_level': LogLevel.info,
            'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
            'log_source': None,
            'log_format': 'Hi there!',
            'log_system': 'foo',
            'log_time': 1434099813.77449
        }

        observer(event)

        result = stream.getvalue()
        self.assertEqual(result[:-1], "[foo] Hi there!")

    def test_format_log_category(self):
        """
        A log category in the event will mean the format is replaced with the
        format string referencing it.
        """
        stream = NativeStringIO()
        observer = make_stdout_observer(_file=stream, format="syslogd")

        event = {
            'log_level': LogLevel.info,
            'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
            'log_category': "DBG100",
            'x': 'x~',
            'y': 'z',
            'z': 'a',
            'log_source': None,
            'log_system': 'foo',
            'log_time': 1434099813.77449
        }

        observer(event)

        result = stream.getvalue()
        self.assertEqual(result[:-1], "[foo] DEBUG x~ z a")


class StderrObserverTests(TestCase):
    def test_basic(self):

        stream = NativeStringIO()
        observer = make_stderr_observer(_file=stream)
        log = make_logger(observer=observer)

        log.error("Hi!", log_system="foo")

        result = stream.getvalue()
        self.assertIn("[foo]", result)

    def test_output_standard(self):
        """
        The output format is the time, the system in square brackets, and the
        message.
        """
        stream = NativeStringIO()
        observer = make_stderr_observer(_file=stream, format="standard")
        event = {
            'log_level': LogLevel.error,
            'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
            'log_source': None,
            'log_format': 'Hi there!',
            'log_system': 'foo',
            'log_time': 1434099813.77449
        }

        observer(event)

        result = stream.getvalue()
        self.assertEqual(result[:-1], formatTime(event["log_time"]) + " [foo] Hi there!")

    def test_output_syslogd(self):
        """
        The syslogd output format is the system in square brackets, and the
        message.
        """
        stream = NativeStringIO()
        observer = make_stderr_observer(_file=stream, format="syslogd")
        event = {
            'log_level': LogLevel.error,
            'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
            'log_source': None,
            'log_format': 'Hi there!',
            'log_system': 'foo',
            'log_time': 1434099813.77449
        }

        observer(event)

        result = stream.getvalue()
        self.assertEqual(result[:-1], "[foo] Hi there!")

    def test_format_log_category(self):
        """
        A log category in the event will mean the format is replaced with the
        format string referencing it.
        """
        stream = NativeStringIO()
        observer = make_stderr_observer(_file=stream, format="syslogd")

        event = {
            'log_level': LogLevel.error,
            'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
            'log_category': "DBG100",
            'x': 'x~',
            'y': 'z',
            'z': 'a',
            'log_source': None,
            'log_system': 'foo',
            'log_time': 1434099813.77449
        }

        observer(event)

        result = stream.getvalue()
        self.assertEqual(result[:-1], "[foo] DEBUG x~ z a")

    def test_format_failure(self):
        """
        A traceback will print.
        """
        stream = NativeStringIO()
        observer = make_stderr_observer(_file=stream, format="syslogd")

        try:
            raise ValueError("noooo {0}".format("!!"))
        except:
            err = Failure()

        event = {
            'log_level': LogLevel.error,
            'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
            'log_format': None,
            'log_source': None,
            'log_failure': err,
            'log_system': 'foo',
            'log_time': 1434099813.77449
        }

        observer(event)

        result = stream.getvalue()
        self.assertIn("noooo {0}", result)


class LogCapturerTests(TestCase):
    def test_capturer(self):
        """
        The log capturer is a context manager that captures the logs emitted
        inside it.
        """
        log = make_logger("info")

        with LogCapturer() as l:
            log.info("Whee!", log_category="CB500", foo="bar")

        self.assertEqual(len(l.get_category("CB500")), 1)
        self.assertEqual(l.get_category("CB500")[0]["foo"], "bar")
