title: HTTP Bridge Publisher toc: [Documentation, Administration, HTTP
Bridge, HTTP Bridge Publisher]

HTTP Bridge Publisher
=====================

Introduction
------------

    The *HTTP Publisher* (formerly *HTTP Pusher*) feature is available
    starting with Crossbar **0.9.5**.

The *HTTP Publisher* is a service that allows clients to submit PubSub
events via HTTP/POST requests. Crossbar will receive the event data via
the request and forward the event via standard WAMP to any connected
subscribers in real-time.

Try it
------

Clone the `Crossbar.io examples
repository <https://github.com/crossbario/crossbarexamples>`__, and go
to the ``rest/publisher`` subdirectory.

Now start Crossbar:

.. code:: console

    crossbar start

and open http://localhost:8080 in your browser. Open the JavaScript
console to see events received.

To submit events via HTTP/POST, you can use
`curl <http://curl.haxx.se/>`__:

.. code:: console

    curl -H "Content-Type: application/json" \
       -d '{"topic": "com.myapp.topic1", "args": ["Hello, world"]}' \
       http://127.0.0.1:8080/publish

...or any other HTTP/POST capable tool or library.

Using Python
------------

To make using the *HTTP Publisher* service even easier, we've created a
(trivial) library which you can install by doing:

.. code:: console

    pip install crossbarconnect

    ``crossbarconnect`` does *not* depend on ``crossbar``, ``autobahn``,
    ``twisted`` or ``asyncio``. It only uses the Python standard
    library. It only does HTTP/POST requests.

You can publish events from Python like this:

.. code:: python

    import crossbarconnect

    client = crossbarconnect.Client("http://127.0.0.1:8080/publish")
    client.publish("com.myapp.topic1", "Hello, world!", 23)

The example also contains two Python scripts for testing unsigned
requests:

.. code:: console

    python publish.py

and signed requests:

.. code:: console

    python publish_signed.py

Configuration
-------------

The *HTTP Publisher* is configured on a path of a Web transport - here
is part of a Crossbar configuration:

.. code:: javascript

    {
       "workers": [
          {
             "type": "router",
             ...
             "transports": [
                {
                   "type": "web",
                   ...
                   "paths": {
                      ...
                      "publish": {
                         "type": "publisher",
                         "realm": "realm1",
                         "role": "anonymous"
                      }
                   }
                }
             ]
          }
       ]
    }

The service dictionary has the following parameters:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | MUST |
| type | be   |
| ``** | ``"p |
|      | ubli |
|      | sher |
|      | "``  |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| real | real |
| m``* | m    |
| *    | to   |
|      | whic |
|      | h    |
|      | the  |
|      | forw |
|      | ardi |
|      | ng   |
|      | sess |
|      | ion  |
|      | is   |
|      | atta |
|      | ched |
|      | that |
|      | will |
|      | inje |
|      | ct   |
|      | the  |
|      | subm |
|      | itte |
|      | d    |
|      | even |
|      | ts,  |
|      | e.g. |
|      | ``"r |
|      | ealm |
|      | 1"`` |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| role | fixe |
| ``** | d    |
|      | (aut |
|      | hent |
|      | icat |
|      | ion) |
|      | role |
|      | the  |
|      | forw |
|      | ardi |
|      | ng   |
|      | sess |
|      | ion  |
|      | is   |
|      | auth |
|      | enti |
|      | cate |
|      | d    |
|      | as   |
|      | when |
|      | atta |
|      | chin |
|      | g    |
|      | to   |
|      | the  |
|      | rout |
|      | er-r |
|      | ealm |
|      | ,    |
|      | e.g. |
|      | ``"r |
|      | ole1 |
|      | "``  |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | A    |
| opti | dict |
| ons` | iona |
| `**  | ry   |
|      | of   |
|      | opti |
|      | ons  |
|      | (opt |
|      | iona |
|      | l,   |
|      | see  |
|      | belo |
|      | w).  |
+------+------+

The ``options`` dictionary has the following configuration parameters:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | A    |
| key` | stri |
| `**  | ng   |
|      | that |
|      | when |
|      | pres |
|      | ent  |
|      | prov |
|      | ides |
|      | the  |
|      | *key |
|      | *    |
|      | from |
|      | whic |
|      | h    |
|      | requ |
|      | est  |
|      | sign |
|      | atur |
|      | es   |
|      | are  |
|      | comp |
|      | uted |
|      | .    |
|      | If   |
|      | pres |
|      | ent, |
|      | the  |
|      | ``se |
|      | cret |
|      | ``   |
|      | must |
|      | also |
|      | be   |
|      | prov |
|      | ided |
|      | .    |
|      | E.g. |
|      | ``"m |
|      | yapp |
|      | 1"`` |
|      | .    |
+------+------+
| **`` | A    |
| secr | stri |
| et`` | ng   |
| **   | with |
|      | the  |
|      | *sec |
|      | ret* |
|      | from |
|      | whic |
|      | h    |
|      | requ |
|      | est  |
|      | sign |
|      | atur |
|      | es   |
|      | are  |
|      | comp |
|      | uted |
|      | .    |
|      | If   |
|      | pres |
|      | ent, |
|      | the  |
|      | ``ke |
|      | y``  |
|      | must |
|      | also |
|      | be   |
|      | prov |
|      | ided |
|      | .    |
|      | E.g. |
|      | ``"k |
|      | kjH6 |
|      | 8Giu |
|      | UZ"` |
|      | `).  |
+------+------+
| **`` | An   |
| post | inte |
| _bod | ger  |
| y_li | when |
| mit` | pres |
| `**  | ent  |
|      | limi |
|      | ts   |
|      | the  |
|      | leng |
|      | th   |
|      | (in  |
|      | byte |
|      | s)   |
|      | of a |
|      | HTTP |
|      | /POS |
|      | T    |
|      | body |
|      | that |
|      | will |
|      | be   |
|      | acce |
|      | pted |
|      | .    |
|      | If   |
|      | the  |
|      | requ |
|      | est  |
|      | body |
|      | exce |
|      | ed   |
|      | this |
|      | limi |
|      | t,   |
|      | the  |
|      | requ |
|      | est  |
|      | is   |
|      | reje |
|      | cted |
|      | .    |
|      | If   |
|      | 0,   |
|      | acce |
|      | pt   |
|      | unli |
|      | mite |
|      | d    |
|      | leng |
|      | th.  |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *)   |
+------+------+
| **`` | An   |
| time | inte |
| stam | ger  |
| p_de | when |
| lta_ | pres |
| limi | ent  |
| t``* | limi |
| *    | ts   |
|      | the  |
|      | diff |
|      | eren |
|      | ce   |
|      | (in  |
|      | seco |
|      | nds) |
|      | betw |
|      | een  |
|      | a    |
|      | sign |
|      | atur |
|      | e's  |
|      | time |
|      | stam |
|      | p    |
|      | and  |
|      | curr |
|      | ent  |
|      | time |
|      | .    |
|      | If   |
|      | 0,   |
|      | allo |
|      | w    |
|      | any  |
|      | dive |
|      | rgen |
|      | ce.  |
|      | (def |
|      | ault |
|      | :    |
|      | **0* |
|      | *).  |
+------+------+
| **`` | A    |
| requ | list |
| ire_ | of   |
| ip`` | stri |
| **   | ngs  |
|      | with |
|      | sing |
|      | le   |
|      | IP   |
|      | addr |
|      | esse |
|      | s    |
|      | or   |
|      | IP   |
|      | netw |
|      | orks |
|      | .    |
|      | When |
|      | give |
|      | n,   |
|      | only |
|      | clie |
|      | nts  |
|      | with |
|      | an   |
|      | IP   |
|      | from |
|      | the  |
|      | desi |
|      | gnat |
|      | ed   |
|      | list |
|      | are  |
|      | acce |
|      | pted |
|      | .    |
|      | Othe |
|      | rwis |
|      | e    |
|      | a    |
|      | requ |
|      | est  |
|      | is   |
|      | deni |
|      | ed.  |
|      | E.g. |
|      | ``[" |
|      | 192. |
|      | 168. |
|      | 1.1/ |
|      | 255. |
|      | 255. |
|      | 255. |
|      | 0",  |
|      | "127 |
|      | .0.0 |
|      | .1"] |
|      | ``   |
|      | (def |
|      | ault |
|      | :    |
|      | **-* |
|      | *).  |
+------+------+
| **`` | A    |
| requ | flag |
| ire_ | that |
| tls` | indi |
| `**  | cate |
|      | s    |
|      | if   |
|      | only |
|      | requ |
|      | ests |
|      | runn |
|      | ing  |
|      | over |
|      | TLS  |
|      | are  |
|      | acce |
|      | pted |
|      | .    |
|      | (def |
|      | ault |
|      | :    |
|      | **fa |
|      | lse* |
|      | *).  |
+------+------+
| **`` | A    |
| debu | bool |
| g``* | ean  |
| *    | that |
|      | acti |
|      | vate |
|      | s    |
|      | debu |
|      | g    |
|      | outp |
|      | ut   |
|      | for  |
|      | this |
|      | serv |
|      | ice. |
|      | (def |
|      | ault |
|      | :    |
|      | **fa |
|      | lse* |
|      | *).  |
+------+------+

Running Standalone
------------------

If you only want to run WebSocket and the HTTP Publisher Service (and no
other Web path services), here is an example configuration:

.. code:: javascript

    {
       "version": 2,
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
                               "allow": {
                                  "call": true,
                                  "register": true,
                                  "publish": true,
                                  "subscribe": true
                               }
                            }
                         ]
                      }
                   ]
                }
             ],
             "transports": [
                {
                   "type": "websocket",
                   "endpoint": {
                      "type": "tcp",
                      "port": 9000
                   }
                },
                {
                   "type": "web",
                   "endpoint": {
                      "type": "tcp",
                      "port": 8080
                   },
                   "paths": {
                      "/": {
                         "type": "publisher",
                         "realm": "realm1",
                         "role": "anonymous"
                      }
                   }
                }
             ]
          }
       ]
    }

This will run:

1. a WAMP-over-WebSocket endpoint on ``ws://localhost:9000``
2. a HTTP Push Bridge endpoint on ``http://localhost:8080``

You can test this using

.. code:: html

    <!DOCTYPE html>
    <html>
       <body>
          <script src="autobahn.min.js"></script>
          <script>
             var connection = new autobahn.Connection({
                url: "ws://127.0.0.1:9000",
                realm: "realm1"
             });

             connection.onopen = function (session) {

                console.log("Connected");

                function onevent (args, kwargs) {
                   console.log("Got event:", args, kwargs);
                }

                session.subscribe('com.myapp.topic1', onevent);
             };

             connection.onclose = function () {
                console.log("Connection lost", arguments);
             }

             connection.open();
          </script>
       </body>
    </html>

and publishing from curl:

.. code:: console

    curl -H "Content-Type: application/json" \
       -d '{"topic": "com.myapp.topic1", "args": ["Hello, world"]}' \
       http://127.0.0.1:8080/
       ```

    ## Making Requests

    To submit events through Crossbar, issue a HTTP/POST request to the URL of the Crossbar HTTP Publisher service with:

    1. Content type `application/json`
    2. Body containing a JSON object
    3. Two query parameters: `timestamp` and `seq`

    For a call to a HTTP Publisher service, the body MUST be a JSON object with the following attributes:

    * `topic`: A string with the URI of the topic to publish to.
    * `args`: An (optional) list of positional event payload arguments.
    * `kwargs`: An (optional) dictionary of keyword event payload arguments.
    * `options`: An (optional) dictionary of WAMP publication options (see below).

    ### Signed Requests

    Signed requests work like unsigned requests, but have the following additional query parameters. All query parameters (below and above) are mandatory for signed requests.

    * `key`: The key to be used for computing the signature.
    * `nonce`: A random integer from [0, 2^53]
    * `signature`: See below.

    The signature computed as the Base64 encoding of the following value:

HMAC[SHA256]\_{secret} (key \| timestamp \| seq \| nonce \| body)

::


    Here, `secret` is the secret shared between the publishing application and Crossbar. This value will never travel over the wire.

    The **HMAC[SHA256]** is computed w.r.t. the `secret`, and over the concatenation

key \| timestamp \| seq \| nonce \| body \`\`\`

The ``body`` is the JSON serialized event.

PHP - Symfony Publisher Bundle
------------------------------

For PHP/Symfony users, there is a bundle which makes publishing via HTTP
comfortable - `Crossbar HTTP Publisher
Bundle <https://github.com/facile-it/crossbar-http-publisher-bundle>`__
(thanks to `peelandsee <https://github.com/peelandsee>`__ for providing
this).
