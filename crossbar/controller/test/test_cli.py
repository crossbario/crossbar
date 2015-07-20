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


from twisted.trial import unittest
from twisted.python.compat import NativeStringIO
from twisted.internet.selectreactor import SelectReactor

from crossbar.controller import cli
from crossbar import _logging

from twisted.logger import LogPublisher, LogBeginner

from weakref import WeakKeyDictionary

import os
import sys
import warnings


class dot_accessible_dict(dict):
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __getattr__(self, attr):
        return self.get(attr)


class CLITestBase(unittest.TestCase):

    def setUp(self):

        self.stderr = NativeStringIO()
        self.stdout = NativeStringIO()

        self.publisher = LogPublisher()
        self.beginner = LogBeginner(LogPublisher(), self.stderr, sys, warnings)

        self.patch(_logging, "_stderr", self.stderr)
        self.patch(_logging, "_stdout", self.stdout)
        self.patch(_logging, "log_publisher", self.publisher)
        self.patch(_logging, "globalLogBeginner", self.beginner)
        self.patch(_logging, "_loggers", WeakKeyDictionary())
        self.patch(_logging, "_loglevel", "info")

    def make_options(self, opts):
        options = dot_accessible_dict(opts)
        options.__dict__ = opts
        return options

    def tearDown(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


class StartTests(CLITestBase):

    def setUp(self):

        CLITestBase.setUp(self)

        # Set up the configuration directories
        self.cbdir = self.mktemp()
        os.mkdir(self.cbdir)
        self.config = os.path.join(self.cbdir, "config.json")

    def test_start(self):
        """
        A basic start, that doesn't actually enter the reactor.
        """
        with open(self.config, "w") as f:
            f.write("""{"controller": {}}""")

        reactor = SelectReactor()
        reactor.run = lambda: False
        opt = {
            "loglevel": "info",
            "cbdir": self.cbdir,
            "config": "config.json",
            "logtofile": False,
            "logformat": "syslogd",
        }

        cli.run_command_start(self.make_options(opt), reactor)
        self.assertIn("Entering reactor event loop", self.stdout.getvalue())

    def test_configValidationFailure(self):
        """
        Running `crossbar start` with an invalid config will print a warning.
        """
        with open(self.config, "w") as f:
            f.write("")

        reactor = SelectReactor()
        opt = {
            "loglevel": "info",
            "cbdir": self.cbdir,
            "config": "config.json",
            "logtofile": False,
            "logformat": "syslogd",
        }

        with self.assertRaises(SystemExit) as e:
            cli.run_command_start(self.make_options(opt), reactor)

        # Exit with code 1
        self.assertEqual(e.exception.args[0], 1)

        # The proper warning should be emitted
        self.assertIn("*** Configuration validation failed ***",
                      self.stderr.getvalue())
        self.assertIn(("configuration file does not seem to be proper JSON "
                       "('No JSON object could be decoded"),
                      self.stderr.getvalue())
