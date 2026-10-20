Issue:    crossbario/crossbar#2048
Title:    Adjust MQTT bridge to multi-node/clustering changes
URL:      https://github.com/crossbario/crossbar/issues/2048
State:    OPEN at freeze
Author:   @jsanyi
Updated:  2026-10-20T16:42:51Z
Comments: 5
Frozen:   2026-10-20T16:44:47Z by `just new-branch`
SHA-256:  3b4b5fc1cafd103c6c6b9c73f5c3723488bec2673b8414c7be595ad8bcbb19c5 (of everything below the line)

---

I'm running 22.6.1 from a pip install in venv, and cannot get mqtt transport working, see crash log below.

=====

```
2022-09-08T10:06:50+0200 [Router      17775] Unhandled Error
Traceback (most recent call last):
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/python/log.py", line 80, in callWithContext
    return context.call({ILogContext: newCtx}, func, *args, **kw)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/python/context.py", line 117, in callWithContext
    return self.currentContext().callWithContext(ctx, func, *args, **kw)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/python/context.py", line 82, in callWithContext
    return func(*args, **kw)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/posixbase.py", line 683, in _doReadOrWrite
    why = selectable.doRead()
--- <exception caught here> ---
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/tcp.py", line 1410, in doRead
    protocol.makeConnection(transport)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/protocol.py", line 509, in makeConnection
    self.connectionMade()
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/crossbar/bridge/mqtt/wamp.py", line 222, in connectionMade
    self._when_ready()
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/crossbar/bridge/mqtt/wamp.py", line 241, in _when_ready
    self._wamp_session.onOpen(self._wamp_transport)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/crossbar/router/session.py", line 421, in onOpen
    assert isinstance(transport,
builtins.AssertionError: unexpected router transport type <class 'crossbar.bridge.mqtt.wamp.WampTransport'>

2022-09-08T10:06:50+0200 [Router      17775] WampMQTTServerProtocol.process_connect(packet=Connect(client_id='mqtt-explorer-a16589b3', flags=ConnectFlags(username=False, password=False, will=False, will_retain=False, will_qos=0, clean_session=True, reserved=False), keep_alive=60, will_topic=None, will_message=None, username=None, password=None))
2022-09-08T10:06:50+0200 [Router      17775] Error handling a Connect, dropping connection
2022-09-08T10:06:50+0200 [Router      17775] Unhandled Error
Traceback (most recent call last):
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/crossbar/worker/main.py", line 351, in _run_command_exec_worker
    reactor.run()
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/base.py", line 1318, in run
    self.mainLoop()
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/base.py", line 1331, in mainLoop
    reactorBaseSelf.doIteration(t)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/epollreactor.py", line 244, in doPoll
    log.callWithLogger(selectable, _drdw, selectable, fd, event)
--- <exception caught here> ---
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/python/log.py", line 96, in callWithLogger
    return callWithContext({"system": lp}, func, *args, **kw)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/python/log.py", line 80, in callWithContext
    return context.call({ILogContext: newCtx}, func, *args, **kw)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/python/context.py", line 117, in callWithContext
    return self.currentContext().callWithContext(ctx, func, *args, **kw)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/python/context.py", line 82, in callWithContext
    return func(*args, **kw)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/posixbase.py", line 696, in _doReadOrWrite
    self._disconnectSelectable(selectable, why, inRead)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/posixbase.py", line 300, in _disconnectSelectable
    selectable.connectionLost(f)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/twisted/internet/tcp.py", line 326, in connectionLost
    protocol.connectionLost(reason)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/crossbar/bridge/mqtt/wamp.py", line 227, in connectionLost
    self._wamp_session.onMessage(msg)
  File "/home/crossbar/crossbar-venv/lib/python3.10/site-packages/crossbar/router/session.py", line 457, in onMessage
    if not self._pending_session_id:
builtins.AttributeError: 'RouterSession' object has no attribute '_pending_session_id'
```

=====

This is my transport configuration:

```
                {
                    "id": "mqtt001",
                    "type": "mqtt",
                    "endpoint": {
                        "type": "tcp",
                        "port": 1883
                    },
                    "options": {
                        "realm": "realm1",
                        "role": "anonymous",
                        "payload_mapping": {
                            "": {
                                "type": "native",
                                "serializer": "json"
                            }
                        },
                        "auth": {
                            "anonymous": {
                                "type": "static",
                                "role": "anonymous"
                            }
                        }
                    }
                }
```


---

## Comments at freeze (5)

### @oberstet, 2022-09-09T16:07:23Z

ah, right, looks like `WampMQTTServerProtocol` needs some adjustment to the recent multi-node / clustering (proxy workers, rlinks) changes in crossbar. nothing big, but someone would need to dig into.

### @richard-pianka, 2023-03-29T23:41:15Z

has there been any progress on this issue?

### @richard-pianka, 2023-04-18T13:37:40Z

apologies for the double comment – this is blocking us from upgrading to newer versions of crossbar.  we're willing to pay to have this issue resolved if someone with more expertise is willing to fix it.

/cc @oberstet 

### @oberstet, 2023-04-18T14:15:25Z

@richard-pianka Hi Richard, sorry for not reacting before, but I'm busy these days with mundane things like making money;) However, as you mention you would pay for fixing this, so I'd be happy to resolve it. Please get in touch with me via email "tobias dot oberstein at gmail dot com".

> As mentioned before, I don't expect this to be complex but tricky to fix the right location in the right way. I know the code base inside out, and for fixing the issue, I'd also create proper, automated test cases using your MQTT client library (or any standard one that fits the bill, like we already use in crossbar-examples) and actually running Crossbar.io in multi-process/node clustered configuration (multiple proxy and router worker) - the whole reason for the original change that lead to this regression ...

### @oberstet, 2026-10-20T16:42:51Z

Root cause, checked on current master (4d2a46fb), ahead of the 26.10.1 release (#2356):

An MQTT client never gets a WAMP session. When the MQTT `CONNECT` is processed,
`WampMQTTServerProtocol._when_ready()` (`src/crossbar/bridge/mqtt/wamp.py`) creates a
`RouterSession` and calls `onOpen()` with the bridge's own `WampTransport`. Since
33f48c81 (#1991, 2022-04-20, first released in 22.4.1), `RouterSession.onOpen()`
asserts the transport type:

```python
assert isinstance(
    transport,
    (WampWebSocketServerProtocol, WampRawSocketServerProtocol, NativeWorkerClientProtocol, MagicMock),
), "unexpected router transport type {}".format(type(transport))
```

`WampTransport` is not one of these types, so `onOpen()` raises before it sets
`_pending_session_id`. The traceback above is the follow-on: on disconnect,
`connectionLost()` passes a message to the half-initialized session, and `onMessage()`
fails with `AttributeError: 'RouterSession' object has no attribute '_pending_session_id'`.

Proof: running the MQTT -> WAMP test `_test_basic_publish`
(`src/crossbar/bridge/mqtt/test/test_wamp.py`) fails with

```
AssertionError: unexpected router transport type <class 'crossbar.bridge.mqtt.wamp.WampTransport'>
```

CI did not catch this because all six MQTT -> WAMP tests in that file have been disabled
(renamed `_test_*`) since d733a56d (2017-05-02). Only the MQTT protocol (packet) tests
run; #2321 made those pass again in 26.10.1, but they do not cover the WAMP side.

Allowing `WampTransport` in the assert alone is not enough. With that change, the six
tests still fail: their harness predates the realm container used by authentication
(`'NoneType' object has no attribute 'has_realm'`, the router factory in the test has no
worker), and `WampTransport` lacks transport attributes `RouterSession` now uses.

Plan (fix before 26.10.1): re-enable the six tests (red), then fix `WampTransport` /
`RouterSession.onOpen()` and the test harness (green).

_This analysis was done with AI assistance (Claude Code)._


