##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from txaio import make_logger, time_ns

from crossbar.common.checkconfig import check_dict_args

__all__ = ('Monitor', )


class Monitor(object):
    """
    Host monitor base class.
    """

    ID = 'abstract'
    """
    Sensor ID, must defined in derived class.
    """

    log = make_logger()

    def __init__(self, config=None):
        """

        :param config: Submonitor specific configuration.
        :type config: dict or None
        """
        # submonitor specific configuration
        self._config = config

        # incremented on each poll
        self._tick = 0

        # time of last poll: ns Unix time UTC
        self._last_poll = None

        # effective period corresponding to last poll in ns
        self._last_period = None

        # last polled value
        self._last_value = None

        # total elapsed CPU time in ns reading this sensor
        self._elapsed = 0

    def check(self, config):
        """
        Check submonitor configuration item.

        Override in your derived submonitor class.

        Raise a `crossbar.common.checkconfig.InvalidConfigException` exception
        when you find an error in the item configuration.

        :param config: The submonitor configuration item to check.
        :type config: dict
        """
        check_dict_args({}, config, '{} monitor configuration'.format(self.ID))

    def poll(self):
        """
        Measure current stats value and return new stats.

        Override in your derived submonitor class.

        :returns: Current stats from monitor.
        :rtype: dict
        """
        self._tick += 1

        now = time_ns()
        if self._last_poll:
            self._last_period = now - self._last_poll

        current = {
            u'tick': self._tick,

            # the UTC timestamp when measurement was taken
            u'timestamp': now,

            # the effective last period in ns
            u'last_period': self._last_period,

            # duration in seconds the retrieval of sensor values took
            u'elapsed': self._elapsed,
        }

        self._last_poll = now
        self._last_value = current

        return current

    def get(self, details=None):
        """
        Get last stats/mesasurement values.

        Usually, there is no need to override this in a derived submonitor, as
        the default implementation already handles storing and returning the
        last submonitor reading.

        :returns: Last stats/values from monitor.
        :rtype: dict or None (when not yet polled)
        """
        self.log.info('{klass}.get(details={})', klass=self.__class__.__name__, details=details)
        return self._last_value
