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

from __future__ import absolute_import, print_function

import sys, os

from zope.interface import provider
from twisted.logger import ILogObserver, formatEvent, Logger, LogPublisher, globalLogPublisher, LogLevel, textFileLogObserver
from twisted.python import failure


logPublisher = LogPublisher()
log = Logger(observer=logPublisher)

globalLogPublisher.addObserver(logPublisher)


def _exceptHook(exctype, value, tb):

    print("a")
    print(exctype)
    log.failure("Exception.", failure=failure.Failure(value, exctype, tb))
    print("b")

#sys.excepthook = _exceptHook


def StandardOutObserver(event):


    from colorama import Fore, Back, Style


    if event["log_level"] != LogLevel.info:
        print(event)
        return

    if event.get("log_system", "-") == "-":
        logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
    else:
        logSystem = event["log_system"]

    eventString = "{}[{}]{} {}".format(Fore.BLUE, logSystem, Fore.RESET, formatEvent(event))

    print(eventString, file=sys.stdout)


def StandardErrorObserver(event):


    from colorama import Fore, Back, Style


    if event["log_level"] == LogLevel.info:

        return

    print("omg")

    if event.get("log_system", "-") == "-":
        logSystem = "{:<10} {:>6}".format("Controller", os.getpid())
    else:
        logSystem = event["log_system"]

    eventString = "{}[{}]{} {}".format(Fore.RED, logSystem, Fore.RESET, formatEvent(event))

    print(eventString, file=sys.stderr)



def _setup():
    logPublisher.addObserver(StandardOutObserver)
    logPublisher.addObserver(StandardErrorObserver)
