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

from zope.interface import provider

from twisted.logger import ILogObserver, formatEvent, Logger, LogPublisher
from twisted.logger import LogLevel, globalLogBeginner

logPublisher = LogPublisher()
log = Logger(observer=logPublisher)

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


def makeStandardOutObserver(levels=(LogLevel.info, LogLevel.debug)):
    """
    Create an observer which prints logs to L{sys.stdout}.
    """
    @provider(ILogObserver)
    def StandardOutObserver(event):

        if event["log_level"] not in levels:
            return

        if event.get("log_system", "-") == "-":
            logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
        else:
            logSystem = event["log_system"]

        if "Controller" in logSystem:
            fore = Fore.BLUE
        elif "Router" in logSystem:
            fore = Fore.YELLOW
        elif "Container" in logSystem:
            fore = Fore.CYAN
        else:
            fore = Fore.WHITE

        eventString = "{}[{}]{} {}".format(fore, logSystem,
                                           Fore.RESET, formatEvent(event))

        print(eventString, file=sys.stdout)

    return StandardOutObserver


def makeStandardErrObserver(levels=(LogLevel.warn, LogLevel.error,
                                    LogLevel.critical)):
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

        eventString = "{}[{}]{} {}".format(Fore.RED, logSystem,
                                           Fore.RESET, formatEvent(event))

        print(eventString, file=sys.stderr)

    return StandardErrorObserver


def startLogging():
    globalLogBeginner.beginLoggingTo([logPublisher], redirectStandardIO=False)
