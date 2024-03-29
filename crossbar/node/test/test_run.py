#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import json
import os
import sys
import unittest

from twisted.internet.selectreactor import SelectReactor
from twisted.internet.task import LoopingCall

from crossbar.node import main
from crossbar import edge
from .test_cli import CLITestBase

# Turn this to `True` to print the stdout/stderr of the Crossbars spawned
DEBUG = False


def make_lc(self, reactor, func):

    if DEBUG:
        self.stdout_length = 0
        self.stderr_length = 0

    def _(lc, reactor):
        if DEBUG:
            stdout = self.stdout.getvalue()
            stderr = self.stderr.getvalue()

            if self.stdout.getvalue()[self.stdout_length:]:
                print(self.stdout.getvalue()[self.stdout_length:], file=sys.__stdout__)
            if self.stderr.getvalue()[self.stderr_length:]:
                print(self.stderr.getvalue()[self.stderr_length:], file=sys.__stderr__)

            self.stdout_length = len(stdout)
            self.stderr_length = len(stderr)

        return func(lc, reactor)

    lc = LoopingCall(_)
    lc.a = (lc, reactor)
    lc.clock = reactor
    lc.start(0.1)
    return lc


if not os.environ.get("CB_FULLTESTS"):

    @unittest.skip("FIXME (broken unit test)")
    class ContainerRunningTests(CLITestBase):
        def setUp(self):

            CLITestBase.setUp(self)

            # Set up the configuration directories
            self.cbdir = os.path.abspath(self.mktemp())
            os.mkdir(self.cbdir)
            self.config = os.path.abspath(os.path.join(self.cbdir, "config.json"))
            self.code_location = os.path.abspath(self.mktemp())
            os.mkdir(self.code_location)

        def _start_run(self, config, app, stdout_expected, stderr_expected, end_on):

            if 'version' not in config:
                config['version'] = 2

            with open(self.config, "wb") as f:
                f.write(json.dumps(config, ensure_ascii=False).encode('utf8'))

            with open(self.code_location + "/myapp.py", "w") as f:
                f.write(app)

            reactor = SelectReactor()

            make_lc(self, reactor, end_on)

            # In case it hard-locks
            reactor.callLater(self._subprocess_timeout, reactor.stop)

            main.main("crossbar", ["start", "--cbdir={}".format(self.cbdir), "--logformat=syslogd"],
                      reactor=reactor,
                      personality=edge.Personality)

            out = self.stdout.getvalue()
            err = self.stderr.getvalue()
            for i in stdout_expected:
                if i not in out:
                    self.fail("Error: '{}' not in:\n{}".format(i, out))

            for i in stderr_expected:
                if i not in err:
                    self.fail("Error: '{}' not in:\n{}".format(i, err))

        def test_start_run(self):
            """
            A basic start, that enters the reactor.
            """
            expected_stdout = ["Entering reactor event loop", "Loaded the component!"]
            expected_stderr = []

            def _check(lc, reactor):
                if "Loaded the component!" in self.stdout.getvalue():
                    lc.stop()
                    try:
                        reactor.stop()
                    except:
                        pass

            config = {
                "version":
                2,
                "controller": {},
                "workers": [{
                    "type":
                    "router",
                    "options": {
                        "pythonpath": ["."]
                    },
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

            myapp = """#!/usr/bin/env python
    from twisted.logger import Logger
    from autobahn.twisted.wamp import ApplicationSession
    from autobahn.wamp.exception import ApplicationError

    class MySession(ApplicationSession):

        log = Logger()

        def onJoin(self, details):
            self.log.info("Loaded the component!")
    """

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_start_run_guest(self):
            """
            A basic start of a guest.
            """
            expected_stdout = ["Entering reactor event loop", "Loaded the component!"]
            expected_stderr = []

            def _check(lc, reactor):
                if "Loaded the component!" in self.stdout.getvalue():
                    lc.stop()
                    try:
                        reactor.stop()
                    except:
                        pass

            config = {
                "version":
                2,
                "controller": {},
                "workers": [{
                    "type":
                    "router",
                    "options": {
                        "pythonpath": ["."]
                    },
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type": "guest",
                    "executable": sys.executable,
                    "arguments": [os.path.join(self.code_location, "myapp.py")]
                }]
            }

            myapp = """#!/usr/bin/env python
    print("Loaded the component!")
    """

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_start_utf8_logging(self):
            """
            Logging things that are UTF8 but not Unicode should work fine.
            """
            expected_stdout = ["Entering reactor event loop", "\u2603"]
            expected_stderr = []

            def _check(lc, reactor):
                if "\u2603" in self.stdout.getvalue():
                    lc.stop()
                    try:
                        reactor.stop()
                    except:
                        pass

            config = {
                "version":
                2,
                "controller": {},
                "workers": [{
                    "type":
                    "router",
                    "options": {
                        "pythonpath": ["."]
                    },
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

            myapp = """#!/usr/bin/env python
    from twisted.logger import Logger
    from autobahn.twisted.wamp import ApplicationSession
    from autobahn.wamp.exception import ApplicationError

    class MySession(ApplicationSession):

        log = Logger()

        def onJoin(self, details):
            self.log.info("\\u2603")
    """

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_run_exception_utf8(self):
            """
            Raising an ApplicationError with Unicode will raise that error through
            to the caller.
            """
            config = {
                "workers": [{
                    "type":
                    "router",
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

            myapp = """from twisted.logger import Logger
    from autobahn.twisted.wamp import ApplicationSession
    from autobahn.wamp.exception import ApplicationError
    from twisted.internet.defer import inlineCallbacks

    class MySession(ApplicationSession):

        log = Logger()

        @inlineCallbacks
        def onJoin(self, details):

            def _err():
                raise ApplicationError("com.example.error.form_error", "\\u2603")
            e = yield self.register(_err, 'com.example.err')

            try:
                yield self.call('com.example.err')
            except ApplicationError as e:
                assert e.args[0] == "\\u2603"
                print("Caught error:", e)
            except:
                print('other err:', e)

            self.log.info("Loaded the component")
    """

            expected_stdout = ["Loaded the component", "\u2603", "Caught error:"]
            expected_stderr = []

            def _check(lc, reactor):
                if "Loaded the component" in self.stdout.getvalue():
                    lc.stop()
                    try:
                        reactor.stop()
                    except:
                        pass

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_failure1(self):

            config = {
                "workers": [{
                    "type":
                    "router",
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "components": [{
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
                    }]
                }]
            }

            myapp = """from twisted.logger import Logger
    from autobahn.twisted.wamp import ApplicationSession

    class MySession(ApplicationSession):

        log = Logger()

        def __init__(self, config):
            self.log.info("MySession.__init__()")
            ApplicationSession.__init__(self, config)

        def onJoin(self, details):
            self.log.info("MySession.onJoin()")
    """

            expected_stdout = []
            expected_stderr = ["No module named"]

            def _check(_1, _2):
                pass

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_failure2(self):

            config = {
                "workers": [{
                    "type":
                    "router",
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

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

            def _check(_1, _2):
                pass

            expected_stdout = []
            if sys.version_info >= (3, 5):
                expected_stderr = ["module 'myapp' has no attribute 'MySession2'"]
            else:
                expected_stderr = ["'module' object has no attribute 'MySession2'"]

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_failure3(self):

            config = {
                "workers": [{
                    "type":
                    "router",
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

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

            def _check(_1, _2):
                pass

            expected_stdout = []
            expected_stderr = ["Component instantiation failed", "division by zero"]

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_failure4(self):

            config = {
                "workers": [{
                    "type":
                    "router",
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

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

            def _check(_1, _2):
                pass

            expected_stdout = []
            expected_stderr = ["Fatal error in component", "While firing onJoin", "division by zero"]

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_failure5(self):

            config = {
                "version":
                2,
                "controller": {},
                "workers": [{
                    "type":
                    "router",
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

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

            def _check(_1, _2):
                pass

            expected_stdout = []
            expected_stderr = ["Component 'component1' failed to start; shutting down node."]

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_failure6(self):

            config = {
                "version":
                2,
                "controller": {},
                "workers": [{
                    "type":
                    "router",
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

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

            def _check(_1, _2):
                pass

            expected_stdout = [
                "Session ended: CloseDetails", "Sleeping a couple of secs and then shutting down",
                "Container is hosting no more components: shutting down"
            ]
            expected_stderr = []

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

        def test_failure7(self):

            config = {
                "workers": [{
                    "type":
                    "router",
                    "realms": [{
                        "name":
                        "realm1",
                        "roles": [{
                            "name":
                            "anonymous",
                            "permissions": [{
                                "uri": "*",
                                "allow": {
                                    "publish": True,
                                    "subscribe": True,
                                    "call": True,
                                    "register": True
                                }
                            }]
                        }]
                    }],
                    "transports": [{
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
                    }]
                }, {
                    "type":
                    "container",
                    "options": {
                        "pythonpath": [self.code_location]
                    },
                    "components": [{
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
                    }]
                }]
            }

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

            def _check(_1, _2):
                pass

            expected_stdout = []
            expected_stderr = [("Could not connect container component to router - transport " "establishment failed")]

            self._start_run(config, myapp, expected_stdout, expected_stderr, _check)

    @unittest.skip("FIXME (broken unit test)")
    class InitTests(CLITestBase):
        def test_hello(self):
            def _check(lc, reactor):
                if "published to 'oncounter'" in self.stdout.getvalue():
                    lc.stop()
                    try:
                        reactor.stop()
                    except:
                        pass

            appdir = self.mktemp()
            cbdir = os.path.join(appdir, ".crossbar")

            reactor = SelectReactor()
            main.main("crossbar", ["init", "--appdir={}".format(appdir)],
                      reactor=reactor,
                      personality=edge.Personality)

            self.assertIn("Application template initialized", self.stdout.getvalue())

            reactor = SelectReactor()
            make_lc(self, reactor, _check)

            # In case it hard-locks
            reactor.callLater(self._subprocess_timeout, reactor.stop)

            main.main("crossbar", ["start", "--cbdir={}".format(cbdir.path), "--logformat=syslogd"],
                      reactor=reactor,
                      personality=edge.Personality)

            stdout_expected = ["published to 'oncounter'"]

            for i in stdout_expected:
                self.assertIn(i, self.stdout.getvalue())
