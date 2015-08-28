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

import json

from six import StringIO as NativeStringIO, PY3

from twisted.trial.unittest import TestCase

from io import StringIO

from mock import Mock

from twisted.logger import formatTime

from crossbar._logging import make_logger, CrossbarLogger, LogLevel
from crossbar import _logging


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
        self.existing_level = _logging._loglevel

    def tearDown(self):
        _logging.set_global_log_level(self.existing_level)

    def test_set_global(self):
        """
        Setting the global log level via the function changes it.
        """
        _logging.set_global_log_level("warn")
        self.assertEqual(_logging._loglevel, "warn")

    def test_set_global_changes_loggers(self):
        """
        Setting the global log level changes the level of all loggers that were
        not instantiated with a level.
        """
        log = make_logger()
        self.assertEqual(log._log_level, "info")
        _logging.set_global_log_level("warn")
        self.assertEqual(log._log_level, "warn")

    def test_set_global_does_not_change_explicit_loggers(self):
        """
        Setting the global log level does not change loggers that have an
        explicit level set.
        """
        log = make_logger("info")
        self.assertEqual(log._log_level, "info")
        _logging.set_global_log_level("warn")
        self.assertEqual(log._log_level, "info")


class CrossbarLoggerTests(TestCase):

    def test_disallow_direct_instantiation(self):
        """
        The developer shouldn't call CrossbarLogger directly, but use
        make_logger.
        """
        with self.assertRaises(AssertionError):
            CrossbarLogger("warn")

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
        log.logger.error.assert_called_with("Foo happened!!!")

        log.warn("Stuff", foo="bar")
        log.logger.warn.assert_called_with("Stuff", foo="bar")

        log.trace("Stuff that's trace", foo="bar")
        log.logger.debug.assert_called_with("Stuff that's trace",
                                            foo="bar", cb_trace=1)

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
        log.emit(LogLevel.info, "Infoooo!")

        self.assertEqual(log.logger.failure.call_count, 0)
        self.assertEqual(log.logger.critical.call_count, 0)
        self.assertEqual(log.logger.error.call_count, 1)
        self.assertEqual(log.logger.warn.call_count, 0)
        self.assertEqual(log.logger.info.call_count, 2)
        self.assertEqual(log.logger.debug.call_count, 0)
        self.assertEqual(log.logger.trace.call_count, 0)

    def test_logger_namespace_init(self):
        """
        The namespace of the Logger is of the creator when using __init__.
        """
        lm = _InitLoggerMaker()

        self.assertEqual(lm.log.logger.namespace,
                         "crossbar.test.test_logger._InitLoggerMaker")

    def test_logger_namespace_classdef(self):
        """
        The namespace of the Logger is of the creator when using it in a class
        definition.
        """
        lm = _ClassDefLoggerMaker()

        self.assertEqual(lm.log.logger.namespace,
                         "crossbar.test.test_logger._ClassDefLoggerMaker")

    def test_logger_namespace_moduledef(self):
        """
        The namespace of the Logger is the creator module when it is made in a
        module.
        """
        self.assertEqual(_log.logger.namespace,
                         "crossbar.test.test_logger")

    def test_logger_namespace_function(self):
        """
        The namespace of the Logger is the creator function when it is made in
        a function outside of a class.
        """
        log = _makelog()
        self.assertEqual(log.logger.namespace,
                         "crossbar.test.test_logger._makelog")

    def test_logger_failure(self):
        """
        The failure method catches the in-flight exception.
        """
        log = make_logger("info", logger=Mock)

        try:
            1 / 0
        except:
            log.failure("Failure happened!")

        self.assertEqual(log.logger.failure.call_count, 1)

    def test_logger_failure_not_called(self):
        """
        The failure method isn't called under 'none'.
        """
        log = make_logger("none", logger=Mock)

        try:
            1 / 0
        except:
            log.failure("Failure happened!")

        self.assertEqual(log.logger.failure.call_count, 0)


class JSONObserverTests(TestCase):

    def test_basic(self):
        """
        The JSON observer outputs a stream of log events.
        """
        stream = StringIO()
        observer = _logging.make_JSON_observer(stream)
        log = make_logger(observer=observer)

        log.info("Hello")

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], _logging.record_separator)
        self.assertEqual(len(log_entry.keys()), 4)
        self.assertEqual(log_entry["level"], u"info")
        self.assertEqual(log_entry["text"], u"Hello")

    def test_failure(self):
        """
        Failures include the stacktrace.
        """
        stream = StringIO()
        observer = _logging.make_JSON_observer(stream)
        log = make_logger(observer=observer)

        try:
            1 / 0
        except:
            log.failure("Oh no")

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], _logging.record_separator)
        self.assertEqual(len(log_entry.keys()), 4)
        self.assertIn(u"ZeroDivisionError", log_entry["text"])
        self.assertIn(u"Oh no", log_entry["text"])
        self.assertEqual(log_entry["level"], u"critical")

    def test_not_json_serialisable(self):
        """
        Non-JSON-serialisable parameters are repr()'d.
        """
        stream = StringIO()
        observer = _logging.make_JSON_observer(stream)
        log = make_logger(observer=observer)

        try:
            1 / 0
        except:
            log.failure("Oh no", obj=observer)

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], _logging.record_separator)
        self.assertEqual(len(log_entry.keys()), 5)
        self.assertIn(u"ZeroDivisionError", log_entry["text"])
        self.assertIn(u"Oh no", log_entry["text"])
        self.assertIn(u"<function ", log_entry["obj"])
        self.assertEqual(log_entry["level"], u"critical")

    def test_repr_formatting(self):
        """
        Non-JSON-serialisable parameters are repr()'d, and any curly brackets
        in the result are escaped.
        """
        stream = StringIO()
        observer = _logging.make_JSON_observer(stream)
        log = make_logger(observer=observer)

        class BracketThing(object):
            def __repr__(self):
                return "<BracketThing kwargs={}>"

        log.info("hi {obj}", obj=BracketThing())

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], _logging.record_separator)
        self.assertEqual(len(log_entry.keys()), 5)
        self.assertEqual(u"hi <BracketThing kwargs={{}}>", log_entry["text"])
        self.assertEqual(log_entry["level"], u"info")

    def test_raising_during_encoding(self):
        """
        Non-JSON-serialisable parameters are repr()'d, and if that's impossible
        then the message is lost.
        """
        stream = StringIO()
        observer = _logging.make_JSON_observer(stream)
        log = make_logger(observer=observer)

        class BadThing(object):
            def __repr__(self):
                raise Exception()

        log.info("hi {obj}", obj=BadThing())

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], _logging.record_separator)
        self.assertEqual(len(log_entry.keys()), 3)
        self.assertIn(u"MESSAGE LOST", log_entry["text"])
        self.assertEqual(log_entry["level"], u"error")

    def test_unicode_logs(self):
        """
        Unicode is JSON serialised correctly.
        """
        stream = StringIO()
        observer = _logging.make_JSON_observer(stream)
        log = make_logger(observer=observer)

        try:
            if PY3:
                raise Exception(u"\u2603")
            else:
                raise Exception(u"\u2603".encode('utf-8'))
        except:
            log.failure("Oh no")

        result = stream.getvalue()
        log_entry = json.loads(result[:-1])

        self.assertEqual(result[-1], _logging.record_separator)
        self.assertEqual(len(log_entry.keys()), 4)
        self.assertIn(u"\u2603", log_entry["text"])
        self.assertEqual(log_entry["level"], u"critical")


class StdoutObserverTests(TestCase):

    def test_basic(self):

        stream = NativeStringIO()
        observer = _logging.make_stdout_observer(_file=stream)
        log = make_logger(observer=observer)

        log.info("Hi!", log_system="foo")

        result = stream.getvalue()
        self.assertIn(u"[foo]", result)

    def test_output_nocolour(self):
        """
        The output format is the time, the system in square brackets, and the
        message.
        """
        stream = NativeStringIO()
        observer = _logging.make_stdout_observer(_file=stream,
                                                 format="nocolour")
        event = {'log_level': LogLevel.info,
                 'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
                 'log_source': None, 'log_format': 'Hi there!',
                 'log_system': 'foo', 'log_time': 1434099813.77449}

        observer(event)

        result = stream.getvalue()
        self.assertEqual(result[:-1],
                         formatTime(event["log_time"]) + " [foo] Hi there!")

    def test_output_syslogd(self):
        """
        The syslogd output format is the system in square brackets, and the
        message.
        """
        stream = NativeStringIO()
        observer = _logging.make_stdout_observer(_file=stream,
                                                 format="syslogd")
        event = {'log_level': LogLevel.info,
                 'log_namespace': 'crossbar.test.test_logger.StdoutObserverTests',
                 'log_source': None, 'log_format': 'Hi there!',
                 'log_system': 'foo', 'log_time': 1434099813.77449}

        observer(event)

        result = stream.getvalue()
        self.assertEqual(result[:-1], "[foo] Hi there!")
