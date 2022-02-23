###############################################################################
#
# Copyright (c) Crossbar.io Technologies GmbH. All rights reserved.
#
###############################################################################

from __future__ import print_function
from __future__ import absolute_import

import os
import re
from os.path import join

from functools import partial

from autobahn.wamp import types, exception
from autobahn.twisted.util import sleep
from autobahn.twisted.component import Component
from twisted.internet.defer import Deferred, FirstError, inlineCallbacks, DeferredList
from twisted.logger import globalLogPublisher

import treq
import pytest

# do not directly import fixtures, or session-scoped ones will get run
# twice.
from ..helpers import _cleanup_crossbar, start_crossbar, functest_session



@inlineCallbacks
def test_proxy(request, virtualenv, reactor, session_temp):
    '''
    '''

    cbdir = join(session_temp, "proxy_cb")
    os.mkdir(cbdir)

    # XXX could pytest.mark.paramtrize on transports, for example, to
    # test both websocket and rawsocket -- but then would need to
    # provide the configuration onwards somehow...
    crossbar_config = {
        "version": 2,
        "controller": {
            "id": "node1",
        },
        "workers": [
            {
                "type": "router",
                "realms": [
                    {
                        "name": "foo",
                        "roles": [
                            {
                                "name": "anonymous",
                                "permissions": [
                                    {
                                        "uri": "",
                                        "match": "prefix",
                                        "allow": {
                                            "call": True,
                                            "register": True,
                                            "publish": True,
                                            "subscribe": True
                                        },
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True
                                        },
                                        "cache": True
                                    }
                                ]
                            },
                            {
                                "name": "quux",
                                "permissions": [
                                    {
                                        "uri": "",
                                        "match": "prefix",
                                        "allow": {
                                            "call": True,
                                            "register": True,
                                            "publish": True,
                                            "subscribe": True
                                        },
                                        "disclose": {
                                            "caller": True,
                                            "publisher": True
                                        },
                                        "cache": True
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "transports": [
                    {
                        "type": "rawsocket",
                        "endpoint": {
                            "type": "unix",
                            "path": "router.sock"
                        },
                        "options": {
                            "max_message_size": 1048576
                        },
                        "serializers": ["cbor"],
                        "auth": {
                            "anonymous-proxy": {
                                "type": "static",
                                "role": "quux"
                            }
                        }
                    }
                ]
            },
            {
                "type": "proxy",
                "id": "first_proxy",
                "routes": {
                    "foo": {
                        "quux": "backend_zero",
                        "anonymous": "backend_zero"
                    }
                },
                "connections": {
                    "backend_zero": {
                        "realm": "foo",
                        "transport": {
                            "type": "rawsocket",
                            "endpoint": {
                                "type": "unix",
                                "path": "router.sock",
                                "serializer": "cbor"
                            }
                        },
                        "url": "rs://localhost"
                    }
                },
                "transports": [
                    {
                        "type": "web",
                        "id": "ws_test_0",
                        "endpoint": {
                            "type": "tcp",
                            "port": 8443,
                            "shared": True,
                        },
                        "paths": {
                            "autobahn": {
                                "type": "archive",
                                "archive": "autobahn.zip",
                                "origin": "https://github.com/crossbario/autobahn-js-browser/archive/master.zip",
                                "download": True,
                                "cache": True,
                                "mime_types": {
                                    ".min.js": "text/javascript",
                                    ".jgz": "text/javascript"
                                }
                            },
                            "ws": {
                                "type": "websocket",
                                "serializers": [
                                    "cbor", "msgpack", "json"
                                ],
                                "auth": {
                                    "anonymous": {
                                        "type": "static",
                                        "role": "quux"
                                    }
                                },
                                "options": {
                                    "allowed_origins": ["*"],
                                    "allow_null_origin": True,
                                    "enable_webstatus": True,
                                    "max_frame_size": 1048576,
                                    "max_message_size": 1048576,
                                    "auto_fragment_size": 65536,
                                    "fail_by_drop": True,
                                    "open_handshake_timeout": 2500,
                                    "close_handshake_timeout": 1000,
                                    "auto_ping_interval": 10000,
                                    "auto_ping_timeout": 5000,
                                    "auto_ping_size": 12,
                                    "auto_ping_restart_on_any_traffic": True,
                                    "compression": {
                                        "deflate": {
                                            "request_no_context_takeover": False,
                                            "request_max_window_bits": 13,
                                            "no_context_takeover": False,
                                            "max_window_bits": 13,
                                            "memory_level": 5
                                        }
                                    }
                                }
                            },
                            "info": {
                                "type": "nodeinfo"
                            },
                            "/": {
                                "type": "static",
                                "directory": join(cbdir, "web"),
                                "options": {
                                    "enable_directory_listing": False
                                }
                            }
                        }
                    }
                ]
            },
            {
                "type": "proxy",
                "id": "second_proxy",
                "routes": {
                    "foo": {
                        "quux": "backend_zero",
                        "anonymous": "backend_zero"
                    }
                },
                "connections": {
                    "backend_zero": {
                        "realm": "foo",
                        "transport": {
                            "type": "rawsocket",
                            "endpoint": {
                                "type": "unix",
                                "path": "router.sock",
                                "serializer": "cbor"
                            }
                        },
                        "url": "rs://localhost"
                    }
                },
                "transports": [
                    {
                        "type": "web",
                        "endpoint": {
                            "type": "tcp",
                            "port": 8443,
                            "shared": True,
                        },
                        "paths": {
                            "autobahn": {
                                "type": "archive",
                                "archive": "autobahn.zip",
                                "origin": "https://github.com/crossbario/autobahn-js-browser/archive/master.zip",
                                "download": True,
                                "cache": True,
                                "mime_types": {
                                    ".min.js": "text/javascript",
                                    ".jgz": "text/javascript"
                                }
                            },
                            "ws": {
                                "type": "websocket",
                                "serializers": [
                                    "cbor", "msgpack", "json"
                                ],
                                "options": {
                                    "allowed_origins": ["*"],
                                    "allow_null_origin": True,
                                    "enable_webstatus": True,
                                    "max_frame_size": 1048576,
                                    "max_message_size": 1048576,
                                    "auto_fragment_size": 65536,
                                    "fail_by_drop": True,
                                    "open_handshake_timeout": 2500,
                                    "close_handshake_timeout": 1000,
                                    "auto_ping_interval": 10000,
                                    "auto_ping_timeout": 5000,
                                    "auto_ping_size": 12,
                                    "auto_ping_restart_on_any_traffic": True,
                                    "compression": {
                                        "deflate": {
                                            "request_no_context_takeover": False,
                                            "request_max_window_bits": 13,
                                            "no_context_takeover": False,
                                            "max_window_bits": 13,
                                            "memory_level": 5
                                        }
                                    }
                                }
                            },
                            "info": {
                                "type": "nodeinfo"
                            },
                            "/": {
                                "type": "static",
                                "directory": join(cbdir, "web"),
                                "options": {
                                    "enable_directory_listing": False
                                }
                            },
                        }
                    }
                ]
            }
        ]
    }

    class WaitForTransportAndProxy(object):
        """
        Super hacky, but ... other suggestions? Could busy-wait for ports
        to become connect()-able? Better text to search for?
        """
        def __init__(self, done):
            self.data = ''
            self.done = done
            # found: transport, proxy0, proxy1
            self._found = [False, False, False]

        def write(self, data):
            print(data, end='')
            if self.done.called:
                return

            # in case it's not line-buffered for some crazy reason
            self.data = self.data + data
            if not self._found[0] and "started Transport ws_test_0" in self.data:
                print("Detected transport starting up")
                self._found[0] = True
            if not self._found[1] and "Proxy first_proxy has started" in self.data:
                print("first proxy started")
                self._found[1] = True
            if not self._found[2] and "Proxy second_proxy has started" in self.data:
                print("second proxy started")
                self._found[2] = True
            if all(self._found) and not self.done.called:
                self.done.callback(None)
            if "Address already in use" in self.data:
                self.done.errback(RuntimeError("Address already in use"))

    listening = Deferred()
    protocol = yield start_crossbar(
            reactor, virtualenv,
            cbdir, crossbar_config,
            stdout=WaitForTransportAndProxy(listening),
            stderr=WaitForTransportAndProxy(listening),
            log_level='debug' if request.config.getoption('logdebug', False) else False,
    )
    request.addfinalizer(partial(_cleanup_crossbar, protocol))

    static_content = "<html><body>it worked</body></html>\n"
    os.mkdir(join(cbdir, "web"))
    fname = join(cbdir, "web", "index.html")
    with open(fname, "w") as f:
        f.write(static_content)

    timeout = sleep(40)
    results = yield DeferredList([timeout, listening], fireOnOneErrback=True, fireOnOneCallback=True)

    if timeout.called:
        raise RuntimeError("Timeout waiting for crossbar to start")

    # test static resource web responses
    for _ in range(200):
        response = yield treq.get('http://localhost:8443/')
        result = yield response.text()
        assert result == static_content

    # make some proxy-connections. The setup here is one session that
    # registers a callable and 10 other sessions that call it;
    # we'll grep the logs after to confirm we access via more than one
    # proxy worker.

    callee = Component(
        transports=[{
            "url": "ws://localhost:8443/ws",
            "type": "websocket",
        }],
        realm="foo",
        authentication={
            "anonymous": {
                "authrole": "quux"
            }
        },
    )

    callee_ready = Deferred()

    @callee.register(u"test.callable")
    def call_test(*args, **kw):
        # print("called: {} {}".format(args, kw))
        return args, kw

    @callee.on_ready
    def _(session):
        callee_ready.callback(None)
    callee.start()

    yield callee_ready

    num_callees = 10
    caller_sessions = []
    results = []
    for _ in range(num_callees):

        @inlineCallbacks
        def main(reactor, session):
            # print("main: {} {}".format(reactor, session))
            r = yield session.call(u"test.callable", "arg0", "arg1", keyword="keyword")
            results.append(r)
            yield session.leave()

        caller = Component(
            transports=[{
                "url": "ws://localhost:8443/ws",
                "type": "websocket"
            }],
            realm="foo",
            authentication={
                "anonymous": {
                    "authrole": "quux"
                }
            },
            main=main,
        )
        caller_sessions.append(caller.start())

    # all calls should complete, and not error
    done = yield DeferredList(caller_sessions)
    for ok, res in done:
        assert ok, "some caller session failed"

    # all calls should have succeeded with the same result
    assert len(results) == num_callees
    for result in results:
        # note: original return-value would have been a tuple, but
        # WAMP only supports lists
        assert result == [["arg0", "arg1"], dict(keyword="keyword")]

    # this just checks that we see "any log lines at all" from both
    # Proxy processes .. maybe we can get a little more specific and
    # look for particular logs?
    proxy_pids = set()
    m = re.compile(" \\[Proxy\\s*([0-9]+)\\] ")
    for line in protocol.logs.getvalue().splitlines():
        x = m.search(line)
        if x:
            # print("PROXY: {}".format(line))
            proxy_pids.add(int(x.group(1)))

    # we should see log-lines from both proxy processes
    assert len(proxy_pids) == 2, "Expected two different proxy processes to log"
