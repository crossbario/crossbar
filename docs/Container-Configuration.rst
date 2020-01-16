:orphan:

IoT Microservice Weather Balloon example using Container Component with Dynamic Authentication
==============================================================================================

This complete example shows a crossbar.io configuration with two types of components together: a router component handling authorization and a container component. The container component registers a python app with a pretend balloon-popping procedure. As soon as index.html opens in your browser, the "pop" remote procedure is called. Use your imagination as to how to make this fun with your next IoT project!

TL;DR
Crossbar.io router components share the same single process as the router worker, so it makes sense to keep any router components simple and light as possible, for example just to handle authorization. Container component workers can run python applications natively, and unlike router components, each run on their own process. This is very useful to keep in mind when you design your services: keep loads off the main router worker process so if any of your applications go down, it may not take the router with it. Enjoy!


Disambiguation: containers discussed here are not related to Docker Containers
------------------------------------------------------------------------------

Yes, it is initially confusing as the terms are identical, especially as Crossbar.io can also be deployed using Docker Containers. Docker Containers consist of an entire runtime environment: application, all its dependencies, libraries and other binaries, and configuration files bundled into one package. Crossbar instantiated through Docker Containers is discussed elsewhere.

Here, we're talking about containers and their components as a type of worker description in config.json.


Why container components are useful: eg. microservices and cloud control of remote devices
------------------------------------------------------------------------------------------

Router components and container components share similarities: both are natively-run python classes spawned and hosted by the router process that derive from ``autobahn.twisted.wamp.ApplicationSession``. Unlike router components (and more like guest workers discussed elsewhere) container components each start and run on a separate worker process to the main router worker process, making your entire setup more efficient, robust and easier to scale. You do have to specifically handle authentication and authorization functionality within a container component (covered below) that router components handle implicitly.

Container components therefore have a kind of hybrid functionality: spawned and hosted by crossbar, yet exhibiting standalone behaviors like a client. Hybrid behavior can be especially useful, for example in IoT appications where components represent microservices on devices that may come online and offline at any time or fail in unpredictable ways. To run and scale microservices on separate processes might make the difference between a graceful degradation of your service and application failure.

Programming pros:
	Container components relieve the application programmer from most boilerplate code needed to hook up application components into Crossbar.io through WAMP, run on a separate process, and further blur the distinction between frontend and backend which is more inline with realworld user interactivity.

Programming cons:
	In contrast to a router component, you have to assign the role of a container component for the transport that the component connects to (eg. websocket). You do this explicitly in the python code of the container component, or through environment variables accessed by the component on startup. Each container component class must also include explicit onConnect and onChallenge definitions to set the authentication method for the user and role, even if that role is "anonymous".
	
At least that's how it works currently with Crossbar.io v19.11.2. Making it a little more confusing, the above doesn't apply when you use TLS explicit authentication discussed elsewhere. The docs and older online examples show a container component example without the onConnect and onChallenge defs...but that example uses TLS, the exception to the exception!

The requirement for the two defs may disappear in a future version of Crossbar.io. Read on and the following example will make it all clear.


But first, authentication vs authorization: a refresher
-------------------------------------------------------

Authentication confirms identity, authorization confirms service level. In Crossbar.io, authorization is defined by "roles". You define the name of each role along with its permissions (pub/sub/rrpc) for each realm under "router" in config.json.

It's easy to confuse or conflate these two terms as our minds tend to merge them. That's only natural, as in fact they must be linked as each concept is meaningless alone. In Crossbar, authentication includes the user's role, the critical attribute linking authentication to authorization. In config.json, router->realm->roles determine and enumerate what each role is authorized to do, or not do.

Keeping these concepts distinct yet linked in our mind might be a helpful guide as Crossbar.io router components and container components handle both a litle differently.

There are four files. Make sure you have autobahn.min.js in a shared location, for example `shared/autobahn/autobahn.min.js` as this is necessary for your index.html to work:
-config.json is the Crossbar.io configuration file
-authenticator.py provides dynamic wamp-cra authentication and contains the class ``AuthenticatorSession`` along with a tiny flat database of users and roles
-balloon.py contains the class ``App`` which provides the means for the balloon to publish solar radiation data, and to register the routed remote procedure call (rRPC) that enables users to "pop" the balloon
-index.htm is the browser client that calls the rRPC on loading.

`config.json`

.. code::json
{
    "version": 2,
    "workers": [
        {
            "type": "router",
            "options": {
                "pythonpath": [
                    ".."
                ]
            },
            "realms": [
                {
                    "name": "realm1",
                    "roles": [
                        {
                            "name": "authenticator",
                            "permissions": [
                                {
                                    "uri": "com.balloon.authenticate",
                                    "match": "exact",
                                    "allow": {
                                        "call": false,
                                        "register": true,
                                        "publish": false,
                                        "subscribe": false
                                    },
                                    "disclose": {
                                        "caller": false,
                                        "publisher": false
                                    },
                                    "cache": true
                                }
                            ]
                        },
                        {
                            "name": "backend",
                            "permissions": [
                                {
                                    "uri": "com.balloon.pop",
                                    "match": "exact",
                                    "allow": {
                                        "call": false,
                                        "register": true,
                                        "publish": false,
                                        "subscribe": false
                                    },
                                    "disclose": {
                                        "caller": false,
                                        "publisher": false
                                    },
                                    "cache": true
                                }
                            ]
                        },
                        {
                            "name": "anonymous",
                            "permissions": [
                                {
                                    "uri": "com.balloon.data",
                                    "match": "exact",
                                    "allow": {
                                        "call": true,
                                        "register": false,
                                        "publish": false,
                                        "subscribe": true
                                    },
                                    "disclose": {
                                        "caller": false,
                                        "publisher": false
                                    },
                                    "cache": true
                                }
                            ]
                        },
                        {
                            "name": "balloonpopper",
                            "permissions": [
                                {
                                    "uri": "com.balloon.pop",
                                    "match": "exact",
                                    "allow": {
                                        "call": true,
                                        "register": false,
                                        "publish": false,
                                        "subscribe": false
                                    },
                                    "disclose": {
                                        "caller": false,
                                        "publisher": false
                                    },
                                    "cache": true
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
                        "port": 8000
                    },
                    "paths": {
                        "/": {
                            "type": "static",
                            "directory": "../web"
                        },
                        "shared": {
                            "type": "static",
                            "directory": "../../_shared-web-resources"
                        },
                        "ws": {
                            "type": "websocket",
                            "auth": {
                                "wampcra": {
                                    "type": "dynamic",
                                    "authenticator": "com.balloon.authenticate"
                                }
                            }
                        }
                    }
                }
            ],
            "components": [
                {
                    "type": "class",
                    "classname": "authenticator.AuthenticatorSession",
                    "realm": "realm1",
                    "role": "authenticator"
                }
            ]
        },
        {
            "type": "container",
            "options": {
                "pythonpath": [".."]
            },
            "components": [
                {
                    "type": "class",
                    "classname": "balloon.App",
                    "realm": "realm1",
                    "transport": {
                        "type": "websocket",
                        "endpoint": {
                            "type": "tcp",
                            "host": "127.0.0.1",
                            "port": 8000
                        },
                        "url": "ws://127.0.0.1:8000/ws"
                    }
                }
            ]
        }
    ]
}

`authenticator.py`

.. code::python
from pprint import pprint

from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError


# our user "database"
USERDB = {
   'karina': {
      # these are required:
      'secret': 'secret2',  # the secret/password to be used
      'role': 'frontend'    # the auth role to be assigned when authentication succeeds
   },
   'ingemar': {
      'authid': 'ID09125',  # assign a different auth ID during authentication
      'secret': '123456',
      'role': 'balloonpopper'
   },
   'anohni': {
      # use salted passwords

      # autobahn.wamp.auth.derive_key(secret.encode('utf8'), salt.encode('utf8')).decode('ascii')
      'secret': 'prq7+YkJ1/KlW1X0YczMHw==',
      'role': 'authenticator',
      'salt': 'salt123',
      'iterations': 100,
      'keylen': 16
   }
}

class AuthenticatorSession(ApplicationSession):

   @inlineCallbacks
   def onJoin(self, details):
      #print("AuthenticatorSession joined: {}".format(details))
      def authenticate(realm, authid, details):
         print("WAMP-CRA dynamic authenticator invoked: realm='{}', authid='{}'".format(realm, authid))
         #print(details)

         if authid in USERDB:
            # return a dictionary with authentication information ...
            return USERDB[authid]
         else:
            raise ApplicationError(u'com.example.no_such_user', 'could not authenticate session - no such user {}'.format(authid))

      try:
         yield self.register(authenticate, u'com.balloon.authenticate')
         print("WAMP-CRA dynamic authenticator registered!")
      except Exception as e:
         print("Failed to register dynamic authenticator: {0}".format(e))
 
`balloon.py`

.. code::python
from autobahn.twisted.wamp import ApplicationSession
from twisted.internet.defer import inlineCallbacks

def prCyan(skk): print("\033[96m {}\033[00m" .format(skk))

USER = u'anohni'
USER_SECRET = u'secret1'

class App(ApplicationSession):
    
    def onConnect(self):
        self.join(self.config.realm, [u"wampcra"], USER)

    def onChallenge(self, challenge):
      if challenge.method == u'wampcra':
          prCyan("WAMP-CRA challenge received: {}".format(challenge))
          if u'salt' in challenge.extra:
            # salted secret
              key = auth.derive_key(USER_SECRET,
                                  challenge.extra['salt'],
                                  challenge.extra['iterations'],
                                  challenge.extra['keylen'])
              #prCyan("key: {}".format(key))
          else:
              # plain, unsalted secret
              key = USER_SECRET

          # compute signature for challenge, using the key
          signature = auth.compute_wcs(key, challenge.extra['challenge'])
          #print('signature',signature)

          # return the signature to the router for verification
          return signature
      else:
          raise Exception('Invalid authmethod {}'.format(challenge.method))

    @inlineCallbacks
    def onJoin(self, details):
    ## publish to a couple of topics we are allowed to publish to.
      ##
      for topic in [
         u'com.example.topic1',
         u'com.foobar.topic1']:
         try:
            yield self.publish(topic, "hello", options = PublishOptions(acknowledge = True))
            print("ok, event published to topic {}".format(topic))
         except Exception as e:
            print("publication to topic {} failed: {}".format(topic, e))
    ## REGISTER a procedure for remote calling
        ##
        def add2(x, y):
            self.log.info("add2() called with {x} and {y}", x=x, y=y)
            return x + y

        reg = yield self.register(add2, 'com.example.add2')
        self.log.info("procedure add2() registered")
        
    ##@wamp.register(u'com.example.add2')
   ##def adding2(self,x,y):
   ##   self.log.info("add2() called with {x} and {y}", x=x, y=y)
   ##   result = x + y
   ##   return result
   
    def onJoin(self, details):
        yield self.register(self.test, u'com.example.test')
        self.log.info('component app.App registered com.example.test')
        prCyan('component app.App registered com.example.test') 

    def test(self):
        pass
        
    ## REGISTER a procedure for remote calling
      ##
      def add2(x, y):
         print("add2() called with {} and {}".format(x, y))
         return x + y

      try:
         reg = yield self.register(add2, u'com.example.add2')
         print("procedure add2() registered")
      except Exception as e:
         print("could not register procedure: {}".format(e))    
        
`index.html`

.. code::html    
<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
</head>
   <body>
      <h1>Hello WAMP</h1>
      <p>Open JavaScript console to watch output.</p>
			<p>There is a hidden message for you. Click to see it.</p>
    <button onclick="myFunction()">Click me!</button>
    <p id="demo"></p>

      <script>AUTOBAHN_DEBUG = true;</script>
      <script src="shared/autobahn/autobahn.min.js"></script>

      <script>

         console.log("Ok, AutobahnJS loaded", autobahn.version);
         //
         var wsuri;
         if (document.location.origin === "null" || document.location.origin === "file://") {
            wsuri = "ws://127.0.0.1:8000/ws";

         } else {
            wsuri = (document.location.protocol === "http:" ? "ws:" : "wss:") + "//" +
                        document.location.host + "/ws";
         }
         // authenticate using
         //var user = "karina";
         //var key = "secret2";

         // authenticate using
         var user = "ingemar";
         var key = "123456";

         // authenticate using
         //var user = "anohni";
         //var key = autobahn.auth_cra.derive_key("secret1", "salt123", 100, 16);
		 console.log("key=", key);
         // this callback is fired during WAMP-CRA authentication
         //
         function onchallenge (session, method, extra) {

            console.log("onchallenge", method, extra);

            if (method === "wampcra") {

               console.log("authenticating via '" + method + "' and challenge '" + extra.challenge + "'");

               return autobahn.auth_cra.sign(key, extra.challenge);

            } else {
               throw "don't know how to authenticate using '" + method + "'";
            }
         }

         // the WAMP connection to the Router
         //
         var connection = new autobahn.Connection({
            url: wsuri,
            realm: "realm1",
            // the following attributes must be set of WAMP-CRA authentication
            //
            authmethods: ["wampcra"],
            authid: user,
            onchallenge: onchallenge
         });

         // timers
         //
         var t1, t2;
	 function myFunction() {
	 	document.getElementById("demo").innerHTML = "Hello Dear Visitor!</br> We are happy that you've chosen our website to learn programming languages. We're sure you'll become one of the best programmers in your country. Good luck to you!";
	 }

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
            //t1 = setInterval(function () {

            //   session.publish('com.example.onhello', ['Hello from JavaScript (browser)']);
            //   console.log("published to topic 'com.example.onhello'");
            //}, 1000);


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

						// CALL a remote procedure
						x = 56;
						session.call('com.balloon.pop', [x, 18]).then(
                  function (res) {
                     console.log("pop() result:", res);
                  },
                  function (err) {
                     console.log("pop() error:", err);
                  }
               );





            // CALL a remote procedure every second
            //
            //var x = 0;

            //t2 = setInterval(function () {

            //   session.call('com.example.add2', [x, 18]).then(
            //      function (res) {
            //         console.log("add2() result:", res);
            //      },
            //      function (err) {
            //         console.log("add2() error:", err);
            //      }
            //   );

            //   x += 3;
            //}, 1000);
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

      </script>
   </body>
</html>
  
The worker itself has the options

1. ``type``: must be ``"container"``\ (*required*)
2. ``options``: a dictionary of configuration options
3. ``components``: a list Python components to run in the container
   (*required*)

``options`` are those :doc:`shared by Native
Workers <Native-Worker-Options>` as well as:

1. ``shutdown``: ``shutdown-on-last-worker-exit`` (the default),
   ``shutdown-manual``, ``shutdown-on-any-component-stopped``,
   or ``shutdown-on-any-component-failed``. These should be self-explanatory.

For a ``component``, the ``type`` is *required* and should be ``class``.

Both types share the following options:

1. ``id``: The ID of the node
2. ``realm``: The realm to connect to (*required*)
3. ``transport``: the data for connecting to the router (*required*)
4. ``extra``: Optional data provided to the class when instantiating

For the type ``class``, you need to set

-  ``classname``: the Python WAMP application class, a module/classname
   of a class derived from ``autobahn.twisted.wamp.ApplicationSession``
   (*required*)

Failures
--------

A number of failures can happen starting your component:

-  module not found
-  syntax error in module
-  class not found
-  class could not be instantiated
-  object throws an exception

Further, what is happening when you leave the realm or disconnect the
transport from the session?

Configuration
-------------

+-----------------------+---------------------------------------------------------------------+
| parameter             | description                                                         |
+=======================+=====================================================================+
| **``id``**            | Optional container ID (default: ``"container<N>"``)                 |
+-----------------------+---------------------------------------------------------------------+
| **``type``**          | Must be ``"container"``.                                            |
+-----------------------+---------------------------------------------------------------------+
| **``options``**       | Please see :doc:`Native Worker Options <Native-Worker-Options>` .   |
+-----------------------+---------------------------------------------------------------------+
| **``components``**    | A list of components. Please see below.                             |
+-----------------------+---------------------------------------------------------------------+
| **``connections``**   | Not yet implemented.                                                |
+-----------------------+---------------------------------------------------------------------+

Container components are either **plain Python classes**:

+---------------------+--------------------------------------------------------------+
| parameter           | description                                                  |
+=====================+==============================================================+
| **``id``**          | Optional component ID (default: ``"component<N>"``)          |
+---------------------+--------------------------------------------------------------+
| **``type``**        | Must be ``"class"``.                                         |
+---------------------+--------------------------------------------------------------+
| **``realm``**       | The realm to join with the component.                        |
+---------------------+--------------------------------------------------------------+
| **``transport``**   | The configured connecting transport.                         |
+---------------------+--------------------------------------------------------------+
| **``classname``**   | The fully qualified Python classname to use.                 |
+---------------------+--------------------------------------------------------------+
| **``extra``**       | Arbitrary custom data forwarded to the class ctonstructor.   |
+---------------------+--------------------------------------------------------------+
