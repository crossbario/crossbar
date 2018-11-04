title: HTTP Bridge Webhook toc: [Documentation, Administration, HTTP
Bridge, HTTP Bridge Webhook]

HTTP Bridge Webhook
===================

Introduction
------------

    The *HTTP Webhook* feature is available starting with Crossbar
    **0.11.0**.

The *HTTP Webhook Service* broadcasts incoming HTTP/POST requests on a
fixed WAMP topic.

Webhooks are a method of "push notification" used by services such as
GitHub and BitBucket to notify other services when events have happened
through a simple HTTP POST. The HTTP Webhook Service allows you to
consume these events (providing it is accessible by the external
service) through a WAMP PubSub channel (allowing potentially many things
to occur from one webhook notification).

Try it
------

Clone the `Crossbar.io examples
repository <https://github.com/crossbario/crossbarexamples>`__, and go
to the ``rest/webhooks`` subdirectory.

Now start Crossbar:

.. code:: console

    crossbar start

and open http://localhost:8080 in your browser. Open the JavaScript
console to see events received.

To submit an example webhook via HTTP/POST, you can use
`curl <http://curl.haxx.se/>`__:

.. code:: console

    curl -H "Content-Type: text/plain" \
       -d 'fresh webhooks!' \
       http://127.0.0.1:8080/webhook

Configuration
-------------

The *HTTP Webhook Service* is configured on a path of a Web transport -
here is part of a Crossbar configuration:

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
                      "webhook": {
                         "type": "webhook",
                         "realm": "realm1",
                         "role": "anonymous",
                         "options": {
                             "topic": "com.myapp.topic1",
                             "success_response": ""
                         }
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
| ``** | ``"w |
|      | ebho |
|      | ok"` |
|      | `    |
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
|      | (req |
|      | uire |
|      | d,   |
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
| **`` | The  |
| topi | topi |
| c``* | c    |
| *    | to   |
|      | whic |
|      | h    |
|      | the  |
|      | forw |
|      | arde |
|      | d    |
|      | even |
|      | ts   |
|      | will |
|      | be   |
|      | sent |
|      | .    |
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
| **`` | A    |
| succ | stri |
| ess_ | ng   |
| resp | to   |
| onse | send |
| ``** | as   |
|      | the  |
|      | body |
|      | in a |
|      | succ |
|      | essf |
|      | ul   |
|      | repl |
|      | y    |
|      | (def |
|      | ault |
|      | is   |
|      | ``OK |
|      | ``)  |
+------+------+
| **`` | A    |
| erro | stri |
| r_re | ng   |
| spon | to   |
| se`` | send |
| **   | as   |
|      | the  |
|      | body |
|      | in   |
|      | an   |
|      | unsu |
|      | cces |
|      | sful |
|      | repl |
|      | y    |
|      | (def |
|      | ault |
|      | is   |
|      | ``NO |
|      | T OK |
|      | ``)  |
+------+------+
| **`` | The  |
| gith | same |
| ub_s | secr |
| ecre | et   |
| t``* | you  |
| *    | told |
|      | GitH |
|      | ub   |
|      | when |
|      | crea |
|      | ting |
|      | the  |
|      | WebH |
|      | ook  |
|      | conf |
|      | igur |
|      | atio |
|      | n.   |
|      | When |
|      | spec |
|      | ifie |
|      | d,   |
|      | inco |
|      | ming |
|      | WebH |
|      | ooks |
|      | will |
|      | be   |
|      | chec |
|      | ked  |
|      | for  |
|      | vali |
|      | d    |
|      | GitH |
|      | ub   |
|      | sign |
|      | atur |
|      | es   |
|      | via  |
|      | the  |
|      | ``X- |
|      | Hub- |
|      | Sign |
|      | atur |
|      | e``  |
|      | head |
|      | er.  |
|      | A    |
|      | good |
|      | way  |
|      | to   |
|      | make |
|      | a    |
|      | secr |
|      | et   |
|      | is   |
|      | to   |
|      | hex- |
|      | enco |
|      | de   |
|      | 32   |
|      | rand |
|      | om   |
|      | byte |
|      | s    |
|      | (e.g |
|      | .    |
|      | from |
|      | ``os |
|      | .ura |
|      | ndom |
|      | ``). |
+------+------+

With GitHub
-----------

If you set up Crossbar to have a Webhook service, and make it externally
available, you can configure GitHub to send events to it. Underneath
Settings and "Services & Webhooks", you can add a new webhook, which
just requires the URL of the externally-accessible Webhook service. You
can configure GitHub to send certain events, or all events.

When you have configured it, it will send a 'ping' for you to verify it.
As you have configured the Webhook service, you will recieve a message
similar to this (most of the body cut out for brevity) on the WAMP topic
it was configured with.

.. code:: json

    {
        "body": "{\"zen\":\"Design for failure.\",[...more json...]}",
        "headers": {
            "Content-Length": [
                "6188"
            ],
            "X-Github-Event": [
                "ping"
            ],
            "X-Github-Delivery": [
                "7e87c300-462c-11e5-8008-e7623fda32a6"
            ],
            "Accept": [
                "*/*"
            ],
            "User-Agent": [
                "GitHub-Hookshot/4963429"
            ],
            "Host": [
                "atleastfornow.net:8080"
            ],
            "Content-Type": [
                "application/json"
            ]
        }
    }

The message on the WAMP topic will be a dict containing the body as a
string, and the headers as a dictionary of lists.

You will also see the following in the logs:

::

    2015-08-19T04:44:43+0000 [Router        490] Successfully sent webhook from 192.30.252.34 to com.myapp.topic1

For more information on Webhooks, please see GitHub's `Webhooks
Guide <https://developer.github.com/webhooks/>`__.
