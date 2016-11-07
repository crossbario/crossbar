title: Getting started with JavaScript in the Browser
toc: [Documentation, Getting Started, Getting started with Browser]

# Getting started with JavaScript in the Browser

In this recipe we will use Crossbar.io to generate an application template for a [WAMP](http://wamp.ws/) application with a JavaScript frontend and backend - both running in the browser.

The open source library [AutobahnJS](https://github.com/crossbario/autobahn-js) is used to provide WAMP functionality.


The frontend and backend components will talk with each other using all four main interactions available in WAMP:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

We will run the whole application with Crossbar.io serving as a WAMP router and static Web server for the frontend files.

## Prerequisites

A modern browser with [WebSocket support](http://caniuse.com/#search=websocket), e.g. Chrome, Firefox, IE10+, Safari or Opera.

## Create an app

To create a new Crossbar.io node and generate a [JavaScript](http://en.wikipedia.org/wiki/JavaScript) / [AutobahnJS](https://github.com/crossbario/autobahn-js) based "Hello world!" example application:

    crossbar init --template hello:browser --appdir $HOME/hello

This will initialize a new node and application under `$HOME/hello` using the application template `hello:browser`.

> To get a list of available templates, use `crossbar templates`.

You should see the application template being initialized:

```console
oberstet@vbox-ubuntu1310:~$ crossbar init --template hello:browser --appdir $HOME/hello
Crossbar.io application directory 'hello' created
Initializing application template 'hello:browser' in directory 'c:\Users\Alex\tmp\hello'
Using template from 'c:/Python27/lib/site-packages/crossbar-0.10.0-py2.7.egg/crossbar/templates/hello/browser'
Creating directory c:\Users\Alex\tmp\hello\.crossbar
Creating directory c:\Users\Alex\tmp\hello\web
Creating file      c:\Users\Alex\tmp\hello\README.md
Creating file      c:\Users\Alex\tmp\hello\.crossbar\config.json
Creating file      c:\Users\Alex\tmp\hello\web\backend.html
Creating file      c:\Users\Alex\tmp\hello\web\frontend.html
Creating file      c:\Users\Alex\tmp\hello\web\index.html
Application template initialized

Start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.
```

## Start the Crossbar.io node

Start your new Crossbar.io node using:

```console
oberstet@vbox-ubuntu1310:~/hello$ crossbar start
2015-01-15 17:26:45+0100 [Controller   6504] Log opened.
2015-01-15 17:26:45+0100 [Controller   6504] ==================== Crossbar.io ====================

2015-01-15 17:26:45+0100 [Controller   6504] Crossbar.io 0.10.0 starting
2015-01-15 17:26:45+0100 [Controller   6504] Running on CPython using IOCPReactor reactor
2015-01-15 17:26:45+0100 [Controller   6504] Starting from node directory c:\Users\Alex\tmp\hello\.crossbar
2015-01-15 17:26:45+0100 [Controller   6504] Starting from local configuration 'c:\Users\Alex\tmp\hello\.crossbar\config
.json'
2015-01-15 17:26:45+0100 [Controller   6504] Warning, could not set process title (setproctitle not installed)
2015-01-15 17:26:45+0100 [Controller   6504] No WAMPlets detected in enviroment.
2015-01-15 17:26:45+0100 [Controller   6504] Starting Router with ID 'worker1' ..
2015-01-15 17:26:45+0100 [Controller   6504] Entering reactor event loop ...
2015-01-15 17:26:45+0100 [Router       6452] Log opened.
2015-01-15 17:26:45+0100 [Router       6452] Warning: could not set worker process title (setproctitle not installed)
2015-01-15 17:26:47+0100 [Router       6452] Running under CPython using IOCPReactor reactor
2015-01-15 17:26:47+0100 [Router       6452] Entering event loop ..
2015-01-15 17:26:47+0100 [Controller   6504] Router with ID 'worker1' and PID 6452 started
2015-01-15 17:26:47+0100 [Controller   6504] Router 'worker1': realm 'realm1' started
2015-01-15 17:26:47+0100 [Controller   6504] Router 'worker1': role 'role1' started on realm 'realm1'
2015-01-15 17:26:47+0100 [Router       6452] Site starting on 8080
2015-01-15 17:26:47+0100 [Controller   6504] Router 'worker1': transport 'transport1' started
```

## Open the frontend

Open [`http://localhost:8080/`](http://localhost:8080/) in your browser. You should see an overview page with a link to start the demo backend and the frontend (You can only start one backend, but as many frontends as you want).

Now all you need to do is open the frontend and the backend pages and open the JavaScript console. In both the frontend and the backend you should see log output like

```
AutobahnJS debug enabled
trying to create WAMP transport of type: websocket
using WAMP transport type: websocket
79 [1, "realm1", Object]
79 WebSocket transport send [1,"realm1",{"roles":{"caller":{"features":{"caller_identification":true,"progressive_call_results":true}},"callee":{"features":{"caller_identification":true,"pattern_based_registration":true,"shared_registration":true,"progressive_call_results":true,"registration_revocation":true}},"publisher":{"features":{"publisher_identification":true,"subscriber_blackwhite_listing":true,"publisher_exclusion":true}},"subscriber":{"features":{"publisher_identification":true,"pattern_based_subscription":true,"subscription_revocation":true}}}}]
autobahn.min.jgz:79 WebSocket transport receive [2,3351038269318367,{"realm":"realm1","authprovider":"static","roles":{"broker":{"features":{"publisher_identification":true,"pattern_based_subscription":true,"subscription_meta_api":true,"payload_encryption_cryptobox":true,"payload_transparency":true,"subscriber_blackwhite_listing":true,"session_meta_api":true,"publisher_exclusion":true,"subscription_revocation":true}},"dealer":{"features":{"payload_encryption_cryptobox":true,"payload_transparency":true,"pattern_based_registration":true,"registration_meta_api":true,"shared_registration":true,"caller_identification":true,"session_meta_api":true,"registration_revocation":true,"progressive_call_results":true}}},"authid":"6XXH-U6KV-7XA5-VNYC-WLKQ-TCSX","authrole":"anonymous","authmethod":"anonymous","x_cb_node_id":"goeddea-workdesktop"}]
Connected
```

**Hooray! That means: it works;)**


## Hacking the code

The JavaScript frontend code is in `web/frontend.html`, the backend code in `web/backend.html`.

The code in both the backend and the frontend each performs all four main interactions:

 1. call a remote procedure
 2. register a procedure for remote calling
 3. publish an event to a topic
 4. subscribe to a topic to receive events

Here is the JavaScript frontend component:

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

and here is the backend component (just the `onopen` handler):

```javascript

// fired when connection is established and session attached
//
connection.onopen = function (session, details) {

   console.log("Connected");

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
```


## Further information

For more information about programming using WAMP and Autobahn](JS, see the [AutobahnJS documentation](http://autobahn.ws/js/), especially the tutorials on

* [Remote Procedure Calls](http://autobahn.ws/js/tutorial_rpc.html)
* [Publish & Subscribe](http://autobahn.ws/js/tutorial_pubsub.html)

For most applications, a non-browser backend will make more sense. You can use JavaScript for this by running the above backend code in Node.js - see

* [Getting started with NodeJS](Getting started with NodeJS)
