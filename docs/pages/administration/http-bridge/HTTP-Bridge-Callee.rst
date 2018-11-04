title: HTTP Bridge Callee toc: [Documentation, Administration, HTTP
Bridge, HTTP Bridge Callee]

HTTP Bridge Callee
==================

    The *HTTP Callee* feature is available starting with Crossbar
    **0.10.3**.

-  The *HTTP Callee* is a service that translates WAMP procedures to
   HTTP requests.

Try it
------

Clone the `Crossbar.io examples
repository <https://github.com/crossbario/crossbarexamples>`__, and go
to the ``rest/callee`` subdirectory.

Now start Crossbar:

.. code:: console

    crossbar start

This example is configured to register a WAMP procedure named
``com.myap.rest``, which sends requests to ``httpbin.org``. The
procedure's complete keyword arguments are detailed further down, but if
we use a kwargs of ``{"url": "get", "method": "GET"}``, Crossbar will
send a HTTP GET request to ``httpbin.org/get`` and respond with the
result. You can test this using the `HTTP
Caller <HTTP%20Bridge%20Caller>`__ configured in the example:

``shell curl -H "Content-Type: application/json" \     -d '{"procedure": "com.myapp.rest", "kwargs": {"url": "get", "method": "GET"}}' \     http://127.0.0.1:8080/call``

This will call the procedure and print the web response to the terminal.

Configuration
-------------

The *HTTP Callee* is configured as a WAMP component. Here it is as part
of a Crossbar configuration:

.. code:: javascript

    {
        "type": "container",
        "options": {
            "pythonpath": [".."]
        },
        "components": [
            {
                "type": "class",
                "classname": "crossbar.adapter.rest.RESTCallee",
                "realm": "realm1",
                "extra": {
                    "procedure": "com.myapp.rest",
                    "baseurl": "https://httpbin.org/"
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

The callee is configured through the ``extra`` dictionary:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | The  |
| proc | WAMP |
| edur | proc |
| e``* | edur |
| *    | e    |
|      | name |
|      | to   |
|      | regi |
|      | ster |
|      | the  |
|      | call |
|      | ee   |
|      | as.  |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| base | base |
| url` | URL  |
| `**  | that |
|      | the  |
|      | call |
|      | ee   |
|      | will |
|      | use. |
|      | All  |
|      | call |
|      | s    |
|      | will |
|      | work |
|      | down |
|      | ward |
|      | from |
|      | this |
|      | URL. |
|      | If   |
|      | you  |
|      | wish |
|      | to   |
|      | call |
|      | any  |
|      | URL, |
|      | set  |
|      | it   |
|      | as   |
|      | an   |
|      | empt |
|      | y    |
|      | stri |
|      | ng   |
|      | ``"" |
|      | ``.  |
|      | This |
|      | URL  |
|      | must |
|      | cont |
|      | ain  |
|      | the  |
|      | prot |
|      | ocol |
|      | (e.g |
|      | .    |
|      | ``"h |
|      | ttps |
|      | ://" |
|      | ``)  |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+

When making calls to the registered WAMP procedure, you can use the
following keyword arguments:

+------+------+
| argu | desc |
| ment | ript |
|      | ion  |
+======+======+
| **`` | The  |
| meth | HTTP |
| od`` | meth |
| **   | od.  |
|      | (*re |
|      | quir |
|      | ed*) |
+------+------+
| **`` | The  |
| url` | url  |
| `**  | whic |
|      | h    |
|      | will |
|      | be   |
|      | appe |
|      | nded |
|      | to   |
|      | the  |
|      | conf |
|      | igur |
|      | d    |
|      | base |
|      | URL. |
|      | For  |
|      | exam |
|      | ple, |
|      | if   |
|      | the  |
|      | base |
|      | URL  |
|      | was  |
|      | ``"h |
|      | ttp: |
|      | //ex |
|      | ampl |
|      | e.co |
|      | m"`` |
|      | ,    |
|      | prov |
|      | idin |
|      | g    |
|      | ``"t |
|      | est" |
|      | ``   |
|      | as   |
|      | this |
|      | argu |
|      | ment |
|      | woul |
|      | d    |
|      | send |
|      | the  |
|      | requ |
|      | est  |
|      | to   |
|      | ``ht |
|      | tp:/ |
|      | /exa |
|      | mple |
|      | .com |
|      | /tes |
|      | t``. |
|      | (opt |
|      | iona |
|      | l,   |
|      | uses |
|      | the  |
|      | conf |
|      | igur |
|      | ed   |
|      | base |
|      | URL  |
|      | if   |
|      | not  |
|      | prov |
|      | ided |
|      | )    |
+------+------+
| **`` | The  |
| body | body |
| ``** | of   |
|      | the  |
|      | requ |
|      | est  |
|      | as a |
|      | stri |
|      | ng.  |
|      | (opt |
|      | iona |
|      | l,   |
|      | empt |
|      | y    |
|      | if   |
|      | not  |
|      | prov |
|      | ided |
|      | )    |
+------+------+
| **`` | A    |
| head | dict |
| ers` | iona |
| `**  | ry,  |
|      | cont |
|      | aini |
|      | ng   |
|      | the  |
|      | head |
|      | er   |
|      | name |
|      | s    |
|      | as   |
|      | the  |
|      | key, |
|      | and  |
|      | a    |
|      | *lis |
|      | t*   |
|      | of   |
|      | head |
|      | er   |
|      | valu |
|      | es   |
|      | as   |
|      | the  |
|      | valu |
|      | e.   |
|      | For  |
|      | exam |
|      | ple, |
|      | to   |
|      | send |
|      | a    |
|      | ``Co |
|      | nten |
|      | t-Ty |
|      | pe`` |
|      | of   |
|      | ``ap |
|      | plic |
|      | atio |
|      | n/js |
|      | on`` |
|      | ,    |
|      | you  |
|      | woul |
|      | d    |
|      | use  |
|      | ``{" |
|      | Cont |
|      | ent- |
|      | Type |
|      | ": [ |
|      | "app |
|      | lica |
|      | tion |
|      | /jso |
|      | n"]} |
|      | ``   |
|      | as   |
|      | the  |
|      | argu |
|      | ment |
|      | .    |
|      | (opt |
|      | iona |
|      | l)   |
+------+------+
| **`` | Requ |
| para | est  |
| ms`` | para |
| **   | mete |
|      | rs   |
|      | to   |
|      | send |
|      | ,    |
|      | as a |
|      | dict |
|      | iona |
|      | ry.  |
|      | (opt |
|      | iona |
|      | l)   |
+------+------+

Examples
--------

Wikipedia
~~~~~~~~~

Wikipedia has a web API that we can use for this demonstration.

Configure the ``RESTCallee`` WAMP component:

.. code:: javascript

    "extra": {
        "procedure": "org.wikipedia.en.api",
        "baseurl": "http://en.wikipedia.org/w/api.php"
    }

This code snippet calls the procedure with the parameters to look up the
current revision of the Twisted Wikipedia page, reads the web response
as JSON, and then pretty prints the response to the terminal.

.. code:: python

    import json
    from twisted.internet import reactor
    from twisted.internet.defer import inlineCallbacks
    from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner

    class AppSession(ApplicationSession):

        @inlineCallbacks
        def onJoin(self, details):
            res = yield self.call("org.wikipedia.en.api",
                                  method="GET",
                                  url="",
                                  params={
                                      "format": "json",
                                      "action": "query",
                                      "titles": "Twisted (software)",
                                      "prop": "revisions",
                                      "rvprop": "content"
                                  })

            pageContent = json.loads(res["content"])
            print(json.dumps(pageContent, sort_keys=True,
                             indent=4, separators=(',', ': ')))
            reactor.stop()

    if __name__ == '__main__':
        from autobahn.twisted.wamp import ApplicationRunner
        runner = ApplicationRunner("ws://127.0.0.1:8080/ws", "realm1")
        runner.run(AppSession)
