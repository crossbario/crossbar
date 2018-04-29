HTTP Bridge Subscriber
======================

Introduction
------------

    The *HTTP Subscriber* feature is available starting with Crossbar
    **0.10.3**.

The *HTTP Subscriber* is a service that forwards PubSub events to HTTP
endpoints.

Try it
------

Clone the `Crossbar.io examples
repository <https://github.com/crossbario/crossbarexamples>`__, and go
to the ``rest/subscriber`` subdirectory.

Now start Crossbar:

.. code:: console

    crossbar start

This example is configured to subscribe all events sent to the
``com.myapp.topic1`` topic to ``httpbin.org/post``. If you publish a
message using the `HTTP Publisher <HTTP%20Bridge%20Publisher>`__
configured in the example, it will forward the message and print the
response of the message in Crossbar's debug log:

.. code:: shell

    curl -H "Content-Type: application/json" \
        -d '{"topic": "com.myapp.topic1", "args": ["Hello, world"]}' \
        http://127.0.0.1:8080/publish

Configuration
-------------

The *HTTP Subscriber* is configured as a WAMP component. Here it is as
part of a Crossbar configuration:

.. code:: javascript

    {
        "workers": [
            {
                "type": "container",
                "options": {
                    "pythonpath": [".."]
                },
                "components": [
                    {
                        "type": "class",
                        "classname": "crossbar.adapter.rest.MessageForwarder",
                        "realm": "realm1",
                        "extra": {
                            "subscriptions": [
                                {"url": "https://httpbin.org/post",
                                 "topic": "com.myapp.topic1"}
                            ],
                            "method": "POST",
                            "expectedcode": 200,
                            "debug": true
                        },
                        "transport": {
                            "type": "websocket",
                            "endpoint": {
                                "type": "tcp",
                                "host": "127.0.0.1",
                                "port": 8080
                            },
                            "url": "ws://127.0.0.1:8080/ws"
                        }
                    }
                ]
            }
        ]
    }

The subscriber is configured through the ``extra`` dictionary:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | A    |
| subs | list |
| crip | of   |
| tion | dict |
| s``* | iona |
| *    | ries |
|      | whic |
|      | h    |
|      | each |
|      | MUST |
|      | cont |
|      | ain  |
|      | ``"u |
|      | rl"` |
|      | `    |
|      | and  |
|      | ``"t |
|      | opic |
|      | "``  |
|      | keys |
|      | .    |
|      | The  |
|      | ``"u |
|      | rl"` |
|      | `    |
|      | key  |
|      | is a |
|      | full |
|      | URL  |
|      | with |
|      | ``ht |
|      | tp`` |
|      | or   |
|      | ``ht |
|      | tps` |
|      | `    |
|      | (for |
|      | exam |
|      | ple, |
|      | ``"h |
|      | ttps |
|      | ://e |
|      | xamp |
|      | le.o |
|      | rg/e |
|      | ndpo |
|      | int" |
|      | ``), |
|      | and  |
|      | the  |
|      | topi |
|      | c    |
|      | is   |
|      | the  |
|      | exac |
|      | t    |
|      | topi |
|      | c    |
|      | whic |
|      | h    |
|      | even |
|      | ts   |
|      | will |
|      | be   |
|      | forw |
|      | arde |
|      | d    |
|      | from |
|      | .    |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| meth | HTTP |
| od`` | meth |
| **   | od   |
|      | whic |
|      | h    |
|      | the  |
|      | forw |
|      | ardi |
|      | ng   |
|      | requ |
|      | ests |
|      | will |
|      | be   |
|      | made |
|      | with |
|      | .    |
|      | (opt |
|      | iona |
|      | l,   |
|      | ``"P |
|      | OST" |
|      | ``   |
|      | by   |
|      | defa |
|      | ult) |
+------+------+
| **`` | The  |
| expe | HTTP |
| cted | stat |
| code | us   |
| ``** | code |
|      | whic |
|      | h    |
|      | is   |
|      | expe |
|      | cted |
|      | from |
|      | the  |
|      | requ |
|      | ests |
|      | .    |
|      | If   |
|      | none |
|      | is   |
|      | give |
|      | n,   |
|      | the  |
|      | stat |
|      | us   |
|      | code |
|      | is   |
|      | not  |
|      | chec |
|      | ked. |
|      | (opt |
|      | iona |
|      | l)   |
+------+------+
| **`` | If   |
| debu | ``tr |
| g``* | ue`` |
| *    | ,    |
|      | then |
|      | the  |
|      | resp |
|      | onse |
|      | body |
|      | will |
|      | be   |
|      | prin |
|      | ted  |
|      | to   |
|      | Cros |
|      | sbar |
|      | 's   |
|      | debu |
|      | g    |
|      | log. |
|      | (opt |
|      | iona |
|      | l,   |
|      | ``fa |
|      | lse` |
|      | `    |
|      | by   |
|      | defa |
|      | ult) |
+------+------+

Handling Forwarded Events
-------------------------

The Subscriber, upon recieving a PubSub event that it has been
configured to subscribe to, will send a request to the URL associated
with the topic. The body will be a JSON encoded dictionary and contain
two keys, ``"args"`` and ``"kwargs"`` from the PubSub event. Here is an
example Flask application that prints the pubsub event to the terminal:

.. code:: python

    import json
    from flask import Flask, request
    app = Flask(__name__)

    @app.route("/", methods=["POST"])
    def message():
        body = json.loads(request.get_data())
        print("args:", body["args"], "kwargs:", body["kwargs"])
        return b"OK"

    if __name__ == "__main__":
        app.run()

When this server is started, Crossbar is configured to forward the event
to it, and the example event at the top of the page is published, you
should see:

.. code:: console

    $ python ~/example.py
     * Running on http://127.0.0.1:5000/
    ('args:', [u'Hello, world'], 'kwargs:', {})
    127.0.0.1 - - [21/Apr/2015 21:01:05] "POST / HTTP/1.1" 200 -
