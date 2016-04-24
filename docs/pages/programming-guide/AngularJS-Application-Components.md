[Documentation](.) > [Programming Guide](Programming Guide) > Frameworks and Specific Scenarios > AngularJS Application Components

# AngularJS Application Components

> The shell commands shown here assume use of a Unix-like shell. On Windows, we recommend to install [Git for Windows](http://msysgit.github.io/), which includes a bash shell.

> AngularJS users should also check out [angular-wamp](https://github.com/voryx/angular-wamp), which provides some integration for AutobahnJS into AngularJS.

# Minimal Example

The following is a minimalistic example showing how to send and receive events in real-time in AngularJS (JavaScript) running in a browser.

> NOTE: this page is a Work In Progress, started out by a beginning AngularJS programmer. If you find any code smell or anti-idiom/pattern, please correct!

**1. Create a new Crossbar.io node**

```console
cd $HOME
mkdir test1
cd test1
crossbar init
```

**2. Create a file `$HOME/test1/index.html`**

```console
cd $HOME/test1
touch index.html
```

and insert the following contents

```html
<!DOCTYPE html>
<html>
    <head>
        <link href="app.css" rel="stylesheet">
    </head>
    <body ng-app="PubSubAngApp">
       <h1>Real-time messaging with Crossbar.io and AngularJS</h1>
       <div ng-controller="PublishingCtrl" class="controller">
           <input type="text" ng-model="model.message" />
           <button ng-click="clickMe(model.message)">Publish!</button>
       </div>
       <div id="Receiver" ng-controller="ReceivingCtrl" class="controller">
           We received: <span class="received">{{model.message}}</span>
       </div>
       <script>
          AUTOBAHN_DEBUG = true;
       </script>
       <script src="autobahn.js"></script>
       <script src="angular.js"></script>
       <script src="app.js"></script>
    </body>
</html>
```

**3. Create a file `$HOME/test1/app.js`**

```console
cd $HOME/test1
touch app.js
```

and insert the following contents

```js
var connection = new autobahn.Connection({url: 'ws://127.0.0.1:8080/ws', realm: 'realm1'});
var app = angular.module("PubSubAngApp", []);

app.controller("PublishingCtrl", function($scope) {
    $scope.model = { message: "Hello World" };

    $scope.clickMe = function(outgoingMsg) {
        if (connection.session) {
           connection.session.publish("com.myapp.mytopic1", [outgoingMsg]);
           console.log("event published!");
        } else {
           console.log("cannot publish: no session");
        }
    };
});

app.controller("ReceivingCtrl", ['$scope', function($scope) {
    $scope.model = { message: "Nothing..." };

    $scope.showMe = function(incomingMsg) {
        $scope.model.message = incomingMsg;
    };
}]);


// "onopen" handler will fire when WAMP session has been established ..
connection.onopen = function (session) {

   console.log("session established!");

   // our event handler we will subscribe on our topic
   //
   function onevent1(args, kwargs) {
      console.log("got event:", args, kwargs);
      var scope = angular.element(document.getElementById('Receiver')).scope();
      scope.$apply(function() {
          scope.showMe(args[0]);
      });
   }

   // subscribe to receive events on a topic ..
   //
   session.subscribe('com.myapp.mytopic1', onevent1).then(
      function (subscription) {
         console.log("ok, subscribed with ID " + subscription.id);
      },
      function (error) {
         console.log(error);
      }
   ); 
};


// "onclose" handler will fire when connection was lost ..
connection.onclose = function (reason, details) {
   console.log("connection lost", reason);
}


// initiate opening of WAMP connection ..
connection.open();
```

**4. Create a file `$HOME/test1/app.css`**

```console
cd $HOME/test1
touch app.css
```

and insert the following contents

```css
.received {
    font-weight: bold;
}

.controller {
    border: 1px solid black;
    padding: 10px;
}
```

**5. Download the .js files**

```console
cd $HOME/test1
wget ..../autobahn.js (TBD)
wget .../angular.js (TBD)
```

**6. Start the demo**

Start Crossbar.io

```console
cd $HOME/test1
crossbar start
```

Crossbar.io will log to console while starting:

```console
oberstet@COREI7 ~/test1
$ crossbar start
2014-04-02 13:46:44+0200 [Controller 2596] Log opened.
2014-04-02 13:46:44+0200 [Controller 2596] ============================== Crossbar.io ==============================

2014-04-02 13:46:44+0200 [Controller 2596] Crossbar.io 0.9.2 node starting
2014-04-02 13:46:44+0200 [Controller 2596] Warning, could not set process title (setproctitle not installed)
2014-04-02 13:46:44+0200 [Controller 2596] WampWebSocketServerFactory starting on 9000
2014-04-02 13:46:44+0200 [Controller 2596] Starting factory <autobahn.twisted.websocket.WampWebSocketServerFactory instance at 0x032B47B0>
2014-04-02 13:46:44+0200 [Controller 2596] Worker PID 4752 process connected
2014-04-02 13:46:44+0200 [Worker 4752] Log opened.
2014-04-02 13:46:44+0200 [Worker 4752] Warning, could not set process title (setproctitle not installed)
2014-04-02 13:46:44+0200 [Worker 4752] Starting from node directory c:\Users\oberstet\test1\.crossbar.
2014-04-02 13:46:45+0200 [Worker 4752] Running on IOCPReactor reactor.
2014-04-02 13:46:45+0200 [Worker 4752] Entering event loop ..
2014-04-02 13:46:45+0200 [Worker 4752] Connected to node router.
2014-04-02 13:46:45+0200 [Worker 4752] Procedures registered.
2014-04-02 13:46:45+0200 [Controller 2596] Worker 4752: CPU affinity is [0, 1, 2, 3, 4, 5, 6, 7]
2014-04-02 13:46:46+0200 [Controller 2596] Worker 4752: Router started (101)
2014-04-02 13:46:46+0200 [Controller 2596] Worker 4752: Realm started on router 101 (None)
2014-04-02 13:46:46+0200 [Controller 2596] Worker 4752: Transport web/tcp (1) started on router 101
2014-04-02 13:46:46+0200 [Worker 4752] Site starting on 8080
2014-04-02 13:46:46+0200 [Worker 4752] Starting factory <twisted.web.server.Site instance at 0x034BAC10>
...
```

Now open `http://127.0.0.1:8080` in your browser in **two** tabs. In each browser tab, open the JavaScript console (hit F12) to see logging messages. Hit the "Publish!" button and watch the event arrive in the other tab.



> Note: By default, an event published will not be sent to the publisher, even if the latter is also subscribed. This behavior can be modified using the `exclude_me` option.