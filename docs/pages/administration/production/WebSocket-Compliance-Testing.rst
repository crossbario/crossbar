title: WebSocket Compliance Testing toc: [Documentation, Administration,
Going to Production, WebSocket Compliance Testing]

WebSocket Compliance Testing
============================

Crossbar.io has best-in-class compliance to the WebSocket protocol
(RFC6455).

    Compliance is testified via the
    `**Autobahn**\ Testsuite <http://autobahn.ws/testsuite/>`__, the
    `industry standard <http://autobahn.ws/testsuite/#users>`__
    WebSocket compliance testsuite which includes more than 500
    automated test cases. Crossbar.io passed *all* tests - 100% strict.
    No matter what WebSocket server you use, we encourage you to run the
    testsuite against it and compare.

Protocol compliance is very important for two reasons: \*
interoperability \* security

You don't want an evil client disturb or break your servers, or fail to
serve clients because of interoperability issues.

Testing yourself
----------------

Install the testsuite:

::

    pip install -U autobahntestsuite

Create a Crossbar.io node with a node configuration starting a WebSocket
testee transport:

.. code:: json

    {
       "workers": [
          {
             "type": "router",
             "transports": [
                {
                   "type": "websocket.testee",
                   "endpoint": {
                      "type": "tcp",
                      "port": 9001,
                      "backlog": 1024
                   },
                   "options": {
                      "compression": {
                         "deflate": {
                         }
                      }
                   }
                }
             ]
          }
       ]
    }

Now create a file ``fuzzingclient.json``:

.. code:: json

    {
       "servers": [
                      {
                         "agent": "Crossbar.io",
                         "url": "ws://127.0.0.1:9001"
                      }
                   ],
       "cases": ["*"],
       "exclude-cases": [],
       "exclude-agent-cases": {}
    }

This test specification defines which test cases to run against what
servers.

Then, start Crossbar.io in a first terminal

::

    crossbar start

and start the testsuite in a second terminal

::

    wstest -m fuzzingclient -s fuzzingclient.json

Testing will take some time. It runs over 500 test cases. In the end,
it'll generate HTML report files. Open the
``reports/servers/index.html`` overview page in your browser - click on
the green "Pass" links to view the case detail reports.

Configuration
-------------

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | ID   |
| id`` | of   |
| **   | the  |
|      | tran |
|      | spor |
|      | t    |
|      | with |
|      | in   |
|      | the  |
|      | runn |
|      | ing  |
|      | node |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | tran |
|      | spor |
|      | t<N> |
|      | ``** |
|      | wher |
|      | e    |
|      | ``N` |
|      | `    |
|      | is   |
|      | numb |
|      | ered |
|      | auto |
|      | mati |
|      | call |
|      | y    |
|      | star |
|      | ting |
|      | from |
|      | ``1` |
|      | `)   |
+------+------+
| **`` | Type |
| type | of   |
| ``** | tran |
|      | spor |
|      | t    |
|      | -    |
|      | must |
|      | be   |
|      | ``"w |
|      | ebso |
|      | cket |
|      | .tes |
|      | tee" |
|      | ``.  |
+------+------+
| **`` | List |
| endp | enin |
| oint | g    |
| ``** | endp |
|      | oint |
|      | for  |
|      | tran |
|      | spor |
|      | t.   |
|      | See  |
|      | `Tra |
|      | nspo |
|      | rt   |
|      | Endp |
|      | oint |
|      | s <T |
|      | rans |
|      | port |
|      | %20E |
|      | ndpo |
|      | ints |
|      | >`__ |
|      | for  |
|      | conf |
|      | igur |
|      | atio |
|      | n    |
+------+------+
| **`` | Turn |
| debu | on   |
| g``* | debu |
| *    | g    |
|      | logg |
|      | ing  |
|      | for  |
|      | this |
|      | tran |
|      | spor |
|      | t    |
|      | inst |
|      | ance |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | fals |
|      | e``* |
|      | *).  |
+------+------+
| **`` | The  |
| url` | WebS |
| `**  | ocke |
|      | t    |
|      | serv |
|      | er   |
|      | URL  |
|      | to   |
|      | use  |
|      | (def |
|      | ault |
|      | :    |
|      | ``nu |
|      | ll`` |
|      | )    |
+------+------+
| **`` | See  |
| opti | `Web |
| ons` | Sock |
| `**  | et   |
|      | Opti |
|      | ons  |
|      | <Web |
|      | Sock |
|      | et-O |
|      | ptio |
|      | ns>` |
|      | __   |
+------+------+
