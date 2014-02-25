# Crossbar.io

Open-source multi-protocol application router:

 * RPC and PubSub for distributed applications
 * Direct-to-database messaging
 * No application server needed


## What is that?

**Crossbar.io** is an application _router_: it can route remote procedure calls to endpoints and at the same time can act as a message broker to dispatch events in (soft) real-time to subscribers.

It provides application _infrastructure_ services to application components running in a distributed system and does so using two well-known, powerful messaging patterns:

 * **Remote Procedure Calls** where **Crossbar.io** acts as a *dealer* mediating between *callers* and *callees*
 * **Publish & Subscribe**, where **Crossbar.io** acts as a *broker* mediating between *publishers* and *subscribers*

For example, **Crossbar.io** allows you to

  * Call database stored procedures from JavaScript
  * Subscribe to topics and receive events in JavaScript
  * Publish events to topics from within database stored procedures or triggers

## Why?

### Less complexity

 * no application server required
 * logically 2-tier architecture
 * clean separation of frontend and backend code
 * fewer wheels to keep running and maintain
 * only JavaScript and PL/SQL know-how needed

### More power

 * create next-generation, single-page HTML5 frontends
 * create real-time enabled applications
 * push information from within the database
 * drive Web and Mobile frontends from the same backend API

## How does it work?

**Crossbar.io** is _multi-protocol_ - it speaks:

  * [The WebSocket Protocol](http://tools.ietf.org/html/rfc6455)
  * [The WebSocket Application Messaging Protocol (WAMP)](http://wamp.ws/)
  * Oracle database protocol
  * PostgreSQL database protocol
  * HTTP, FTP

**Crossbar.io** support *Oracle* today, with support for *PostgreSQL* upcoming.

**Crossbar.io** is written in Python, and builds on [Twisted](http://twistedmatrix.com/) and [Autobahn](http://autobahn.ws/).

It's fully asynchronous, high-performance with critical code paths accelerated in native code, and also able to run on [PyPy](http://pypy.org/), a [JITting](http://en.wikipedia.org/wiki/Just-in-time_compilation) Python implementation and competitive with e.g. NodeJS and Java based servers.

> As a first *indication*, you might have a look at the performance test section 9 in the reports [here](http://autobahn.ws/testsuite/reports/servers/index.html). The testing details are [here](https://github.com/tavendo/AutobahnTestSuite/tree/master/examples/publicreports). The usual caveats wrt any performance testing and benchmarking apply.

**Crossbar.io** can scale up on a 2 core/4GB Ram virtual machine to (at least == tested) 180k concurrently active connections. A scale out / cluster / federation architecture is currently under design.


oberstet@corei7ub1310:~/tmp$ ~/python1/bin/crossbar start
2014-02-25 18:45:46+0100 [-] Log opened.
2014-02-25 18:45:46+0100 [-] Worker forked with PID 9053
2014-02-25 18:45:46+0100 [-] Worker forked with PID 9054
2014-02-25 18:45:46+0100 [-] Log opened.
2014-02-25 18:45:46+0100 [-] Log opened.
2014-02-25 18:45:47+0100 [-] Worker 9053: starting on EPollReactor ..
2014-02-25 18:45:47+0100 [-] Worker 9054: starting on EPollReactor ..
2014-02-25 18:45:47+0100 [-] Worker 9053: Router started.
2014-02-25 18:45:47+0100 [-] Worker 9053: Class 'crossbar.demo.TimeService' (1) started in realm 'realm1'
2014-02-25 18:45:47+0100 [-] WampWebSocketServerFactory starting on 9000
2014-02-25 18:45:47+0100 [-] Starting factory <autobahn.twisted.websocket.WampWebSocketServerFactory instance at 0x3036d88>
2014-02-25 18:45:47+0100 [-] Worker 9053: Transport websocket/tcp:9000 (1) started
2014-02-25 18:45:47+0100 [-] WampWebSocketServerFactory starting on '/tmp/mysocket'
2014-02-25 18:45:47+0100 [-] Starting factory <autobahn.twisted.websocket.WampWebSocketServerFactory instance at 0x3037908>
2014-02-25 18:45:47+0100 [-] Worker 9053: Transport websocket/unix:/tmp/mysocket (2) started
2014-02-25 18:45:47+0100 [-] Starting factory <autobahn.twisted.websocket.WampWebSocketClientFactory instance at 0x3485bd8>
2014-02-25 18:45:47+0100 [-] Worker 9054: Component container started.
2014-02-25 18:45:47+0100 [-] Worker 9054: Class 'crossbar.demo.TickService' started in realm 'realm1'


oberstet@corei7ub1310:~/tmp$ cat .cbdata/config.json 
{
   "processes": [
      {
         "type": "router",
         "options": {
            "classpaths": ["."]
         },
         "realms": {
            "realm1": {
               "roles": {
                  "com.example.anonymous": {
                     "authentication": null,
                     "grants": {
                        "create": true,
                        "join": true,
                        "access": {
                           "*": {
                              "publish": true,
                              "subscribe": true,
                              "call": true,
                              "register": true
                           }
                        }
                     }
                  }
               },
               "classes": [
                  "crossbar.demo.TimeService"
               ]
            }
         },
         "transports": [
            {
               "type": "websocket",
               "endpoint": "tcp:9000",
               "url": "ws://localhost:9000"
            },
            {
               "type": "websocket",
               "endpoint": "unix:/tmp/mysocket",
               "url": "ws://localhost"
            }
         ]
      },
      {
         "type": "component.python",
         "options": {
            "classpaths": ["."]
         },
         "class": "crossbar.demo.TickService",
         "router": {
            "type": "websocket",
            "endpoint": "unix:/tmp/mysocket",
            "url": "ws://localhost",
            "realm": "realm1"
         }
      }
   ]
}
oberstet@corei7ub1310:~/tmp$ 


oberstet@corei7ub1310:~/scm/tavendo/autobahn/AutobahnPython/examples/twisted/wamp/basic$ make client_rpc_timeservice_frontend
PYTHONPATH=../../../../autobahn python client.py --component "rpc.timeservice.frontend.Component"
/usr/lib/python2.7/dist-packages/zope/__init__.py:3: UserWarning: Module twisted was already imported from /usr/lib/python2.7/dist-packages/twisted/__init__.pyc, but /home/oberstet/scm/tavendo/autobahn/AutobahnPython/autobahn is being added to sys.path
  import pkg_resources
Current time from time service: 2014-02-25T17:29:18Z

