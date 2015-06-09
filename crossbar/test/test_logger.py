from twisted.trial.unittest import TestCase

from mock import Mock

from crossbar._logging import make_logger, CrossbarLogger


_log = make_logger("info", logger=Mock)

def _makelog():
    log = make_logger("info", logger=Mock)
    return log


class _InitLoggerMaker(object):
    def __init__(self):
        self.log = make_logger("info", logger=Mock)


class _ClassDefLoggerMaker(object):
    log = make_logger("info", logger=Mock)


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

        self.assertEqual(log.logger.critical.call_count, 0)
        self.assertEqual(log.logger.error.call_count, 1)
        self.assertEqual(log.logger.warn.call_count, 0)
        self.assertEqual(log.logger.info.call_count, 1)
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
