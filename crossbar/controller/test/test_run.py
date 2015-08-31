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

from six import PY3

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

        if "%s" in config:
            config = config % ("/".join(code_location.split(os.sep),))

        with open(self.config, "w") as f:
            f.write(config)

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
        expected_stderr = []

        def _check(lc, reactor):
            if "Loaded the component!" in self.stdout.getvalue():
                lc.stop()
                try:
                    reactor.stop()
                except:
                    pass

        config = """{
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
            """

        myapp = """#!/usr/bin/env python
from twisted.internet.defer import inlineCallbacks
from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

class MySession(ApplicationSession):

    log = Logger()

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info("Loaded the component!")
"""

        self._start_run(config, myapp, expected_stdout, expected_stderr,
                        _check)

    def test_failure1(self):

        config = """{
   "workers": [
      {
         "type": "router",
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
                     "type": "static",
                     "directory": ".."
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
"""
        myapp = """from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession

class MySession(ApplicationSession):

    log = Logger()

    def __init__(self, config):
        self.log.info("MySession.__init__()")
        ApplicationSession.__init__(self, config)

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info("MySession.onJoin()")
"""

        expected_stdout = []
        expected_stderr = ["No module named"]
        _check = lambda _1, _2: None

        self._start_run(config, myapp, expected_stdout, expected_stderr,
                        _check)

    def test_failure2(self):

        config = """{
   "workers": [
      {
         "type": "router",
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
                     "type": "static",
                     "directory": ".."
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
               "classname": "myapp.MySession2",
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
"""
        myapp = """
from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession

class MySession(ApplicationSession):

    log = Logger()

    def __init__(self, config):
        self.log.info("MySession.__init__()")
        ApplicationSession.__init__(self, config)

    def onJoin(self, details):
        self.log.info("MySession.onJoin()")
"""

        _check = lambda _1, _2: None
        expected_stdout = []
        expected_stderr = ["'module' object has no attribute 'MySession2'"]

        self._start_run(config, myapp, expected_stdout, expected_stderr,
                        _check)

    def test_failure3(self):

        config = """{
   "workers": [
      {
         "type": "router",
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
                     "type": "static",
                     "directory": ".."
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
"""
        myapp = """
from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession

class MySession(ApplicationSession):

    log = Logger()

    def __init__(self, config):
        a = 1 / 0
        self.log.info("MySession.__init__()")
        ApplicationSession.__init__(self, config)

    def onJoin(self, details):
        self.log.info("MySession.onJoin()")
"""

        _check = lambda _1, _2: None
        expected_stdout = []
        expected_stderr = ["Component instantiation failed"]
        if PY3:
            expected_stderr.append("division by zero")
        else:
            expected_stderr.append("integer division or modulo by zero")

        self._start_run(config, myapp, expected_stdout, expected_stderr,
                        _check)

    def test_failure4(self):

        config = """{
   "workers": [
      {
         "type": "router",
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
                     "type": "static",
                     "directory": ".."
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
"""

        myapp = """
from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession

class MySession(ApplicationSession):

    log = Logger()

    def __init__(self, config):
        self.log.info("MySession.__init__()")
        ApplicationSession.__init__(self, config)

    def onJoin(self, details):
        self.log.info("MySession.onJoin()")
        a = 1 / 0 # trigger exception
"""

        _check = lambda _1, _2: None
        expected_stdout = []
        expected_stderr = ["Fatal error in component", "While firing onJoin"]
        if PY3:
            expected_stderr.append("division by zero")
        else:
            expected_stderr.append("integer division or modulo by zero")

        self._start_run(config, myapp, expected_stdout, expected_stderr,
                        _check)

    def test_failure5(self):

        config = """{
   "controller": {
   },
   "workers": [
      {
         "type": "router",
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
                     "type": "static",
                     "directory": ".."
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
"""

        myapp = """
from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession

class MySession(ApplicationSession):

    log = Logger()

    def __init__(self, config):
        self.log.info("MySession.__init__()")
        ApplicationSession.__init__(self, config)

    def onJoin(self, details):
        self.log.info("MySession.onJoin()")
        self.leave()

    def onLeave(self, details):
        self.log.info("Session ended: {details}", details=details)
        self.disconnect()
"""

        _check = lambda _1, _2: None
        expected_stdout = []
        expected_stderr = [
            "Component 'component1' failed to start; shutting down node."
        ]

        self._start_run(config, myapp, expected_stdout, expected_stderr,
                        _check)

    def test_failure6(self):

        config = """{
   "controller": {
   },
   "workers": [
      {
         "type": "router",
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
                     "type": "static",
                     "directory": ".."
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
"""

        myapp = """
from twisted.logger import Logger
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.util import sleep

class MySession(ApplicationSession):

    log = Logger()

    def __init__(self, config):
        self.log.info("MySession.__init__()")
        ApplicationSession.__init__(self, config)

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info("MySession.onJoin()")
        self.log.info("Sleeping a couple of secs and then shutting down ..")
        yield sleep(2)
        self.leave()

    def onLeave(self, details):
        self.log.info("Session ended: {details}", details=details)
        self.disconnect()

"""

        _check = lambda _1, _2: None
        expected_stdout = [
            "Session ended: CloseDetails",
            "Sleeping a couple of secs and then shutting down",
            "Container is hosting no more components: shutting down"
        ]
        expected_stderr = []

        self._start_run(config, myapp, expected_stdout, expected_stderr,
                        _check)

    def test_failure7(self):

        config = """{
   "workers": [
      {
         "type": "router",
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
                     "type": "static",
                     "directory": ".."
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
                     "port": 8090
                  },
                  "url": "ws://127.0.0.1:8090/ws"
               }
            }
         ]
      }
   ]
}
"""

        myapp = """
from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession

class MySession(ApplicationSession):

    log = Logger()

    def __init__(self, config):
        self.log.info("MySession.__init__()")
        ApplicationSession.__init__(self, config)

    def onJoin(self, details):
        self.log.info("MySession.onJoin()")
        self.leave()
"""

        _check = lambda _1, _2: None
        expected_stdout = []
        expected_stderr = [
            ("Could not connect container component to router - transport "
             "establishment failed")
        ]

        self._start_run(config, myapp, expected_stdout, expected_stderr,
                        _check)


if not os.environ.get("CB_FULLTESTS"):
    del RunningTests
