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

from twisted.internet.selectreactor import SelectReactor
from twisted.internet.task import LoopingCall

from crossbar.controller import cli
from .test_cli import CLITestBase


def make_lc(reactor, func):
    lc = LoopingCall(func)
    lc.a = (lc, reactor)
    lc.clock = reactor
    lc.start(0.1)
    return lc


class RunningTests(CLITestBase):

    def setUp(self):

        CLITestBase.setUp(self)

        # Set up the configuration directories
        self.cbdir = os.path.abspath(self.mktemp())
        os.mkdir(self.cbdir)
        self.config = os.path.abspath(os.path.join(self.cbdir, "config.json"))

    def _start_run(self, config, app, stdout_expected, stderr_expected,
                   end_on):
        code_location = os.path.abspath(self.mktemp())
        os.mkdir(code_location)

        with open(self.config, "w") as f:
            f.write(config % ("/".join(code_location.split(os.sep),)))

        with open(code_location + "/myapp.py", "w") as f:
            f.write(app)

        reactor = SelectReactor()

        make_lc(reactor, end_on)

        # In case it hard-locks
        reactor.callLater(self._subprocess_timeout, reactor.stop)

        cli.run("crossbar",
                ["start",
                 "--cbdir={}".format(self.cbdir),
                 "--logformat=syslogd"],
                reactor=reactor)

        for i in stdout_expected:
            self.assertIn(i, self.stdout.getvalue())

        for i in stderr_expected:
            self.assertIn(i, self.stderr.getvalue())


    def test_start_run(self):
        """
        A basic start, that enters the reactor.
        """
        expected_stdout = [
            "Entering reactor event loop", "Loaded the component!"
        ]


        def _check(lc, reactor):
            if "Loaded the component!" in self.stdout.getvalue():
                lc.stop()
                try:
                    reactor.stop()
                except:
                    pass

        self._start_run("""{
   "controller": {
   },
   "workers": [
      {
         "type": "router",
         "options": {
            "pythonpath": ["."]
         },
         "realms": [
            {
               "name": "realm1",
               "roles": [
                  {
                     "name": "anonymous",
                     "permissions": [
                        {
                           "uri": "*",
                           "publish": true,
                           "subscribe": true,
                           "call": true,
                           "register": true
                        }
                     ]
                  }
               ]
            }
         ],
         "transports": [
            {
               "type": "web",
               "endpoint": {
                  "type": "tcp",
                  "port": 8080
               },
               "paths": {
            "/": {
              "directory": ".",
              "type": "static"
            },
                  "ws": {
                     "type": "websocket"
                  }
               }
            }
         ]
      },
      {
         "type": "container",
         "options": {
            "pythonpath": ["%s"]
         },
         "components": [
            {
               "type": "class",
               "classname": "myapp.MySession",
               "realm": "realm1",
               "transport": {
                  "type": "websocket",
                  "endpoint": {
                     "type": "tcp",
                     "host": "127.0.0.1",
                     "port": 8080
                  },
                  "url": "ws://127.0.0.1:8080/ws"
               }
            }
         ]
      }
   ]
}
            """,
"""#!/usr/bin/env python
from twisted.internet.defer import inlineCallbacks
from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

class MySession(ApplicationSession):

    log = Logger()

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info("Loaded the component!")
""", expected_stdout, [], _check)


if not os.environ.get("CB_FULLTESTS"):
    del RunningTests
