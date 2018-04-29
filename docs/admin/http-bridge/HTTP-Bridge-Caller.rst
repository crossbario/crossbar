HTTP Bridge Caller
==================

Introduction
------------

    The *HTTP Caller* feature is available starting with Crossbar
    **0.10.3**.

The *HTTP Caller* is a service that allows clients to perform WAMP calls
via HTTP/POST requests. Crossbar will forward the call to the performing
server and return the result.

Try it
------

Clone the `Crossbar.io examples
repository <https://github.com/crossbario/crossbarexamples>`__, and go
to the ``rest/caller`` subdirectory.

Now start Crossbar:

.. code:: console

    crossbar start

This will register a simple procedure that takes two integers, adds them
together, and returns the result.

To test this out, you can use `curl <http://curl.haxx.se/>`__:

.. code:: console

    curl -H "Content-Type: application/json" \
        -d '{"procedure": "com.example.add2", "args": [1, 2]}' \
        http://127.0.0.1:8080/call

...or any other HTTP/POST capable tool or library.

Configuration
-------------

The *HTTP Caller* is configured on a path of a Web transport - here is
part of a Crossbar configuration:

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
                      "call": {
                         "type": "caller",
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
| ``** | ``"c |
|      | alle |
|      | r"`` |
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

Making Requests
---------------

To call WAMP procedures through Crossbar, issue a HTTP/POST request to
the URL of the Crossbar HTTP Caller service with:

1. Content type ``application/json``
2. Body containing a JSON object
3. Two query parameters: ``timestamp`` and ``seq``

For a call to a HTTP Caller service, the body MUST be a JSON object with
the following attributes:

-  ``procedure``: A string with the URI of the procedure to call.
-  ``args``: An (optional) list of positional event payload arguments.
-  ``kwargs``: An (optional) dictionary of keyword event payload
   arguments.

Signed Requests
~~~~~~~~~~~~~~~

Signed requests work like unsigned requests, but have the following
additional query parameters. All query parameters (below and above) are
mandatory for signed requests.

-  ``key``: The key to be used for computing the signature.
-  ``nonce``: A random integer from [0, 2^53]
-  ``signature``: See below.

The signature computed as the Base64 encoding of the following value:

::

    HMAC[SHA256]_{secret} (key | timestamp | seq | nonce | body)

Here, ``secret`` is the secret shared between the publishing application
and Crossbar. This value will never travel over the wire.

The **HMAC[SHA256]** is computed w.r.t. the ``secret``, and over the
concatenation

::

    key | timestamp | seq | nonce | body

The ``body`` is the JSON serialized event. You can look at working code
`here <https://github.com/crossbario/crossbarconnect/blob/master/python/lib/crossbarconnect/client.py#L197>`__.
