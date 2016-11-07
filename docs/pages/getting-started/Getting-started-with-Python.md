title: Getting started with Python
toc: [Documentation, Getting Started, Getting started with Python]

# Getting started with Python

In this recipe we will use Crossbar.io to generate an application template for a [WAMP](http://wamp.ws/) application written in Python using [AutobahnPython](https://github.com/crossbario/autobahn-python), an open-source WAMP implementation. The generated application includes a JavaScript frontend to run in a browser.

The frontend and backend components will talk with each other using all four main interactions available in WAMP:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

We will run the whole application with Crossbar.io serving as a WAMP router, static Web server and Python/Autobahn application component host.

> Note: Python application components *can* be run by Crossbar.io, but they can equally run [completely separately](http://autobahn.ws/python/wamp/programming.html).

## Prerequisites

[CPython](https://www.python.org/) or [PyPy](http://pypy.org/) and [AutobahnPython](https://github.com/crossbario/autobahn-python) - but those will have been installed with Crossbar.io already.

## Create an app

To create a new Crossbar.io node and generate a [Python](https://www.python.org/) / [AutobahnPython](https://github.com/crossbario/autobahn-python) based "Hello world!" example application:

```console
oberstet@vbox-ubuntu1310:~$ crossbar init --template hello:python --appdir $HOME/hello
Crossbar.io application directory '/home/oberstet/hello' created
Initializing application template 'hello:python' in directory '/home/oberstet/hello'
Creating directory /home/oberstet/hello/.crossbar
Creating directory /home/oberstet/hello/hello
Creating file      /home/oberstet/hello/MANIFEST.in
Creating file      /home/oberstet/hello/README.md
Creating file      /home/oberstet/hello/setup.py
Creating file      /home/oberstet/hello/.crossbar/config.json
Creating directory /home/oberstet/hello/hello/web
Creating file      /home/oberstet/hello/hello/__init__.py
Creating file      /home/oberstet/hello/hello/hello.py
Creating file      /home/oberstet/hello/hello/web/autobahn.min.js
Creating file      /home/oberstet/hello/hello/web/index.html
Application template initialized

To start your node, run 'crossbar start --cbdir /home/oberstet/hello/.crossbar'
```

This will initialize a new node and application under `$HOME/hello` using the application template `hello:python`.

> To get a list of available templates, use `crossbar templates`.


## Start the node

Start your new Crossbar.io node:

```console
oberstet@vbox-ubuntu1310:~$ cd hello
oberstet@vbox-ubuntu1310:~/hello$ crossbar start
2014-09-17 10:26:10+0200 [Controller   1140] Log opened.
2014-09-17 10:26:10+0200 [Controller   1140] ============================== Crossbar.io ==============================

2014-09-17 10:26:10+0200 [Controller   1140] Crossbar.io 0.9.7-6 starting
2014-09-17 10:26:14+0200 [Controller   1140] Running on CPython using IOCPReactor reactor
2014-09-17 10:26:14+0200 [Controller   1140] Starting from node directory c:\Temp\.crossbar
2014-09-17 10:26:14+0200 [Controller   1140] Starting from local configuration 'c:\Temp\.crossbar\config.json'
2014-09-17 10:26:14+0200 [Controller   1140] Warning, could not set process title (setproctitle not installed)
2014-09-17 10:26:14+0200 [Controller   1140] No WAMPlets detected in enviroment.
2014-09-17 10:26:14+0200 [Controller   1140] Starting Router with ID 'worker1' ..
2014-09-17 10:26:15+0200 [Router       5876] Log opened.
2014-09-17 10:26:15+0200 [Router       5876] Warning: could not set worker process title (setproctitle not installed)
2014-09-17 10:26:18+0200 [Router       5876] Running under CPython using IOCPReactor reactor
2014-09-17 10:26:20+0200 [Router       5876] Entering event loop ..
2014-09-17 10:26:20+0200 [Controller   1140] Router with ID 'worker1' and PID 5876 started
2014-09-17 10:26:20+0200 [Controller   1140] Router 'worker1': PYTHONPATH extended
2014-09-17 10:26:20+0200 [Controller   1140] Router 'worker1': realm 'realm1' started
2014-09-17 10:26:20+0200 [Controller   1140] Router 'worker1': role 'role1' started on realm 'realm1'
2014-09-17 10:26:20+0200 [Controller   1140] Router 'worker1': transport 'transport1' started
2014-09-17 10:26:20+0200 [Controller   1140] Starting Container with ID 'worker2' ..
2014-09-17 10:26:20+0200 [Router       5876] Site starting on 8080
2014-09-17 10:26:21+0200 [Container    5484] Log opened.
2014-09-17 10:26:21+0200 [Container    5484] Warning: could not set worker process title (setproctitle not installed)
2014-09-17 10:26:24+0200 [Container    5484] Running under CPython using IOCPReactor reactor
2014-09-17 10:26:26+0200 [Container    5484] Entering event loop ..
2014-09-17 10:26:26+0200 [Controller   1140] Container with ID 'worker2' and PID 5484 started
2014-09-17 10:26:26+0200 [Controller   1140] Container 'worker2': PYTHONPATH extended
2014-09-17 10:26:26+0200 [Controller   1140] Container 'worker2': component 'component1' started
2014-09-17 10:26:26+0200 [Container    5484] subscribed to topic 'onhello'
2014-09-17 10:26:26+0200 [Container    5484] procedure add2() registered
2014-09-17 10:26:26+0200 [Container    5484] published to 'oncounter' with counter 0
2014-09-17 10:26:27+0200 [Container    5484] published to 'oncounter' with counter 1
...
```

## Open the frontend

Open [`http://localhost:8080/`](http://localhost:8080/) in your browser. When you watch the browser's JavaScript console.

You have just watched the Python backend component talking to the JavaScript frontend component and vice-versa. The calls and events were exchanged over [WAMP](http://wamp.ws/) and routed by Crossbar.io between the application components.

## Hacking the code

All the Python backend code is in `hello/hello.py` while all the JavaScript frontend code is in `hello/web/index.html`.

The code in both the backend and the frontend each performs all four main interactions:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

Here is the Python backend component:

```python
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.util import sleep
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError


class AppSession(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):

        ## SUBSCRIBE to a topic and receive events
        ##
        def onhello(msg):
            print("event for 'onhello' received: {}".format(msg))

        sub = yield self.subscribe(onhello, 'com.example.onhello')
        print("subscribed to topic 'onhello'")

        ## REGISTER a procedure for remote calling
        ##
        def add2(x, y):
            print("add2() called with {} and {}".format(x, y))
            return x + y

        reg = yield self.register(add2, 'com.example.add2')
        print("procedure add2() registered")

        ## PUBLISH and CALL every second .. forever
        ##
        counter = 0
        while True:

            ## PUBLISH an event
            ##
            yield self.publish('com.example.oncounter', counter)
            print("published to 'oncounter' with counter {}".format(counter))
            counter += 1

            ## CALL a remote procedure
            ##
            try:
                res = yield self.call('com.example.mul2', counter, 3)
                print("mul2() called with result: {}".format(res))
            except ApplicationError as e:
                ## ignore errors due to the frontend not yet having
                ## registered the procedure we would like to call
                if e.error != 'wamp.error.no_such_procedure':
                    raise e

            yield sleep(1)
```

And here the JavaScript frontend component:

```javascript
// the URL of the WAMP Router (Crossbar.io)
//
var wsuri;
if (document.location.origin == "file://") {
   wsuri = "ws://127.0.0.1:8080/ws";
} else {
   wsuri = (document.location.protocol === "http:" ? "ws:" : "wss:") + "//" +
               document.location.host + "/ws";
}

// the WAMP connection to the Router
//
var connection = new autobahn.Connection({
   url: wsuri,
   realm: "realm1"
});

// timers
//
var t1, t2;

// fired when connection is established and session attached
//
connection.onopen = function (session, details) {

   console.log("Connected");

   // SUBSCRIBE to a topic and receive events
   //
   function on_counter (args) {
      var counter = args[0];
      console.log("on_counter() event received with counter " + counter);
   }
   session.subscribe('com.example.oncounter', on_counter).then(
      function (sub) {
         console.log('subscribed to topic');
      },
      function (err) {
         console.log('failed to subscribe to topic', err);
      }
   );

   // PUBLISH an event every second
   //
   t1 = setInterval(function () {

      session.publish('com.example.onhello', ['Hello from JavaScript (browser)']);
      console.log("published to topic 'com.example.onhello'");
   }, 1000);

   // REGISTER a procedure for remote calling
   //
   function mul2 (args) {
      var x = args[0];
      var y = args[1];
      console.log("mul2() called with " + x + " and " + y);
      return x * y;
   }
   session.register('com.example.mul2', mul2).then(
      function (reg) {
         console.log('procedure registered');
      },
      function (err) {
         console.log('failed to register procedure', err);
      }
   );

   // CALL a remote procedure every second
   //
   var x = 0;

   t2 = setInterval(function () {

      session.call('com.example.add2', [x, 18]).then(
         function (res) {
            console.log("add2() result:", res);
         },
         function (err) {
            console.log("add2() error:", err);
         }
      );

      x += 3;
   }, 1000);
};

// fired when connection was lost (or could not be established)
//
connection.onclose = function (reason, details) {
   console.log("Connection lost: " + reason);
   if (t1) {
      clearInterval(t1);
      t1 = null;
   }
   if (t2) {
      clearInterval(t2);
      t2 = null;
   }
}

// now actually open the connection
//
connection.open();
```

For more information on Python components, see the [Autobahn Python documentation](http://autobahn.ws/python/index.html).
