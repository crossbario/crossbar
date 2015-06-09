from twisted.trial.unittest import TestCase

from mock import Mock

from crossbar._logging import make_logger, CrossbarLogger


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
        log = make_logger("info", logger=Mock)

        log.error("Foo happened!!!")
        log.logger.error.assert_called_with("Foo happened!!!")

        log.warn("Stuff", foo="bar")
        log.logger.warn.assert_called_with("Stuff", foo="bar")


    def test_logger_emits_if_higher(self):
        """
        A Logger that has a log level of a higher severity will not emit
        messages of a lower severity.
        """
        log = make_logger("info", logger=Mock)
