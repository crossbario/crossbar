title: Getting started with JavaScript in NodeJS
toc: [Documentation, Getting Started, Getting started with NodeJS]

# Getting started with JavaScript in NodeJS

In this recipe we will use Crossbar.io to generate an application template for a [WAMP](http://wamp.ws/) application with a JavaScript frontend and backend.

Both components use the open source library [AutobahnJS](https://github.com/crossbario/autobahn-js) to provide WAMP functionality.

The backend runs under [NodeJS](http://nodejs.org/), the frontend in the browser

The frontend and backend components will talk with each other using all four main interactions available in WAMP:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

We will run the whole application with Crossbar.io serving as a WAMP router, static Web server for the frontend files and JavaScript/NodeJS application component host for the backend code.

> Note: Node.js application components *can* be run by Crossbar.io, but they can equally run completely separately!


## Prerequisites

Install [NodeJS](http://nodejs.org/) and the [Node package manager](https://www.npmjs.org/).

As an example, on Linux/BSD systems, do

   sudo apt-get -y install nodejs npm
   sudo ln -s /usr/bin/nodejs /usr/bin/node

> You will need a recent NodeJS version (0.10.x). Linux distributions might only include versions too old. E.g. on Ubuntu 12.04, you [need](https://github.com/crossbario/autobahn-js/issues/92) a couple of [extra steps](https://github.com/joyent/node/wiki/Installing-Node.js-via-package-manager#ubuntu-mint-elementary-os):
>
>     sudo add-apt-repository ppa:chris-lea/node.js
>     sudo apt-get update
>     sudo apt-get install python-software-properties nodejs

For other systems, follow the installation instructions at the [NodeJS website](http://nodejs.org/).

## Create an app

To create a new Crossbar.io node and generate a [JavaScript](http://en.wikipedia.org/wiki/JavaScript) / [AutobahnJS](https://github.com/crossbario/autobahn-js) based "Hello world!" example application:

   crossbar init --template hello:nodejs --appdir $HOME/hello

This will initialize a new node and application under `$HOME/hello` using the application template `hello:nodejs`.

> To get a list of available templates, use `crossbar templates`.

You should see the application template being initialized:

```console
oberstet@vbox-ubuntu1310:~$ crossbar init --template hello:nodejs --appdir $HOME/hello
Crossbar.io application directory '/home/oberstet/hello' created
Initializing application template 'hello:nodejs' in directory '/home/oberstet/hello'
Creating directory /home/oberstet/hello/web
Creating directory /home/oberstet/hello/node
Creating directory /home/oberstet/hello/.crossbar
Creating file      /home/oberstet/hello/README.md
Creating file      /home/oberstet/hello/web/autobahn.min.js
Creating file      /home/oberstet/hello/web/index.html
Creating file      /home/oberstet/hello/node/hello.js
Creating file      /home/oberstet/hello/.crossbar/config.json
Application template initialized

To start your node, run 'crossbar start --cbdir /home/oberstet/hello/.crossbar'
```

## Install dependencies

Now install the dependencies (really just AutobahnJS) by doing

   npm install autobahn


## Adjust the Node.js path

When starting a guest worker, like Node.js, Crossbar.io tries to determine the path to the executable based on the preset in the config. The string `node` which we've set works on most systems, but on some (e.g. Ubuntu), you'll have to open up `.crossbar/config.json` and replace `"executable": "node"` with `"executable": "nodejs"`.


## Start the node

Start your new Crossbar.io node using:

```console
oberstet@vbox-ubuntu1310:~$ cd hello
oberstet@vbox-ubuntu1310:~/hello$ crossbar start
2014-06-25 22:48:31+0200 [Controller   5849] Log opened.
2014-06-25 22:48:31+0200 [Controller   5849] ============================== Crossbar.io ==============================

2014-06-25 22:48:31+0200 [Controller   5849] Crossbar.io 0.9.6 starting
2014-06-25 22:48:32+0200 [Controller   5849] Running on CPython using EPollReactor reactor
2014-06-25 22:48:32+0200 [Controller   5849] Starting from node directory /home/oberstet/hello/.crossbar
2014-06-25 22:48:32+0200 [Controller   5849] Starting from local configuration '/home/oberstet/hello/.crossbar/config.json'
2014-06-25 22:48:32+0200 [Controller   5849] No WAMPlets detected in enviroment.
2014-06-25 22:48:32+0200 [Controller   5849] Starting Router with ID 'worker1' ..
2014-06-25 22:48:32+0200 [Router       5858] Log opened.
2014-06-25 22:48:33+0200 [Router       5858] Running under CPython using EPollReactor reactor
2014-06-25 22:48:33+0200 [Router       5858] Entering event loop ..
2014-06-25 22:48:34+0200 [Controller   5849] Router with ID 'worker1' and PID 5858 started
2014-06-25 22:48:34+0200 [Router       5858] Monkey-patched MIME table (0 of 551 entries)
2014-06-25 22:48:34+0200 [Router       5858] Site starting on 8080
2014-06-25 22:48:34+0200 [Controller   5849] Router 'worker1': transport 'transport1' started
2014-06-25 22:48:34+0200 [Controller   5849] Starting Guest with ID 'worker2' ..
2014-06-25 22:48:34+0200 [Controller   5849] GuestWorkerClientProtocol.connectionMade
2014-06-25 22:48:34+0200 [Controller   5849] Guest with ID 'worker2' and PID 5861 started
2014-06-25 22:48:34+0200 [Controller   5849] Guest 'worker2': started
2014-06-25 22:48:34+0200 [Guest        5861] subscribed to topic 'onhello'
2014-06-25 22:48:34+0200 [Guest        5861] procedure add2() registered
2014-06-25 22:48:35+0200 [Guest        5861] published to 'oncounter' with counter 0
2014-06-25 22:48:36+0200 [Guest        5861] published to 'oncounter' with counter 1
2014-06-25 22:48:37+0200 [Guest        5861] published to 'oncounter' with counter 2
...
```

## Open the frontend

Open [`http://localhost:8080/`](http://localhost:8080/) in your browser. When you watch the browser's JavaScript console, you should see something like this scrolling past you:

```
Array[4]
WebSocket transport send [70,1,{},[15]]
Array[5]
WebSocket transport send [16,2700639003043124,{},"com.example.onhello",["Hello from JavaScript (browser)"]]
published to topic 'com.example.onhello'
Array[5]
WebSocket transport send [48,3944620048701570,{},"com.example.add2",[0,18]]
WebSocket transport receive [50,3944620048701570,{},[18]]
add2() result: 18
WebSocket transport receive [36,1458377950842230,5111639174278683,{},[6]]
on_counter() event received with counter 6
WebSocket transport receive [68,3,850599850048825,{},[6,3]]
mul2() called with 6 and 3
```

You have just watched the JavaScript (NodeJS) backend component talking to the JavaScript frontend component and vice-versa. The calls and events were exchanged over [WAMP](http://wamp.ws/) and routed by Crossbar.io between the application components.


## Hacking the code

All the JavaScript (NodeJS)backend code is in `node/hello.js` while all the JavaScript frontend code is in `web/index.html`.

The code in both the backend and the frontend each performs all four main interactions:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

Here is the JavaScript (NodeJS) backend component:

```javascript
var autobahn = require('autobahn');

var connection = new autobahn.Connection({
   url: 'ws://127.0.0.1:8080/ws',
   realm: 'realm1'}
);

connection.onopen = function (session) {

   // SUBSCRIBE to a topic and receive events
   //
   function onhello (args) {
      var msg = args[0];
      console.log("event for 'onhello' received: " + msg);
   }
   session.subscribe('com.example.onhello', onhello).then(
      function (sub) {
         console.log("subscribed to topic 'onhello'");
      },
      function (err) {
         console.log("failed to subscribed: " + err);
      }
   );


   // REGISTER a procedure for remote calling
   //
   function add2 (args) {
      var x = args[0];
      var y = args[1];
      console.log("add2() called with " + x + " and " + y);
      return x + y;
   }
   session.register('com.example.add2', add2).then(
      function (reg) {
         console.log("procedure add2() registered");
      },
      function (err) {
         console.log("failed to register procedure: " + err);
      }
   );


   // PUBLISH and CALL every second .. forever
   //
   var counter = 0;
   setInterval(function () {

      // PUBLISH an event
      //
      session.publish('com.example.oncounter', [counter]);
      console.log("published to 'oncounter' with counter " + counter);

      // CALL a remote procedure
      //
      session.call('com.example.mul2', [counter, 3]).then(
         function (res) {
            console.log("mul2() called with result: " + res);
         },
         function (err) {
            if (err.error !== 'wamp.error.no_such_procedure') {
               console.log('call of mul2() failed: ' + err);
            }
         }
      );

      counter += 1;
   }, 1000);
};

connection.open();
```

And here is the JavaScript frontend component:

```javascript
// the URL of the WAMP Router (Crossbar.io)
//
var wsuri = "ws://localhost:8080/ws";


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

## Further information

For more information about programming using WAMP and Autobahn](JS, see the [Autobahn&#124;JS documentation](http://autobahn.ws/js/), especially the tutorials on

* [Remote Procedure Calls](http://autobahn.ws/js/tutorial_rpc.html)
* [Publish & Subscribe](http://autobahn.ws/js/tutorial_pubsub.html)
