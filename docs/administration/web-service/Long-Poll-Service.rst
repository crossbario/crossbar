Long-poll Service
=================

The default transport for WAMP is WebSocket. For clients not supporting
WebSocket, or for blocking clients, the WAMP specification defines
`WAMP-over-Longpoll <https://github.com/wamp-proto/wamp-proto/blob/master/rfc/text/advanced/ap_transport_http_longpoll.md>`__,
a WAMP transport that runs over regular HTTP 1.0 requests.

    The HTTP Long-pool transport can come in handy to support old
    browsers lacking WebSocket like IE9 and earlier or old Android
    WebKit. It is also useful to integrate with clients that cannot work
    asynchronously or have an inherent blocking, synchronous execution
    environment like PostgreSQL background processes for database
    sessions.

Configuration
-------------

To configure a Long-poll Service, attach a dictionary element to a path
in your `Web transport <Web%20Transport%20and%20Services>`__:

+-------------------+--------------------------------------------------+
| option            | description                                      |
+===================+==================================================+
| **``type``**      | MUST be ``"longpoll"`` (*required*)              |
+-------------------+--------------------------------------------------+
| **``options``**   | A dictionary of options (optional, see below).   |
+-------------------+--------------------------------------------------+

The ``options`` dictionary has the following configuration parameters:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | An   |
| requ | inte |
| est_ | ger  |
| time | whic |
| out` | h    |
| `**  | dete |
|      | rmin |
|      | es   |
|      | the  |
|      | time |
|      | out  |
|      | in   |
|      | seco |
|      | nds  |
|      | for  |
|      | Long |
|      | -pol |
|      | l    |
|      | requ |
|      | ests |
|      | .    |
|      | If   |
|      | ``0` |
|      | `,   |
|      | do   |
|      | not  |
|      | time |
|      | out. |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | 10`` |
|      | **). |
|      | Afte |
|      | r    |
|      | this |
|      | peri |
|      | od,  |
|      | the  |
|      | requ |
|      | est  |
|      | is   |
|      | retu |
|      | rned |
|      | even |
|      | if   |
|      | ther |
|      | e    |
|      | is   |
|      | no   |
|      | data |
|      | to   |
|      | tran |
|      | smit |
|      | .    |
|      | Note |
|      | that |
|      | clie |
|      | nts  |
|      | may  |
|      | have |
|      | thei |
|      | r    |
|      | own  |
|      | time |
|      | outs |
|      | ,    |
|      | and  |
|      | that |
|      | this |
|      | shou |
|      | ld   |
|      | be   |
|      | set  |
|      | to a |
|      | valu |
|      | e    |
|      | grea |
|      | ter  |
|      | than |
|      | the  |
|      | ``re |
|      | ques |
|      | t_ti |
|      | meou |
|      | t``. |
+------+------+
| **`` | An   |
| sess | inte |
| ion_ | ger  |
| time | whic |
| out` | h    |
| `**  | dete |
|      | rmin |
|      | es   |
|      | the  |
|      | time |
|      | out  |
|      | on   |
|      | inac |
|      | tivi |
|      | ty   |
|      | of   |
|      | sess |
|      | ions |
|      | .    |
|      | If   |
|      | ``0` |
|      | `,   |
|      | do   |
|      | not  |
|      | time |
|      | out. |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | 30`` |
|      | **)  |
+------+------+
| **`` | Limi |
| queu | t    |
| e_li | the  |
| mit_ | numb |
| byte | er   |
| s``* | of   |
| *    | tota |
|      | l    |
|      | queu |
|      | ed   |
|      | byte |
|      | s.   |
|      | If   |
|      | 0,   |
|      | don' |
|      | t    |
|      | enfo |
|      | rce  |
|      | a    |
|      | limi |
|      | t.   |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | 1310 |
|      | 72`` |
|      | **)  |
+------+------+
| **`` | Limi |
| queu | t    |
| e_li | the  |
| mit_ | numb |
| mess | er   |
| ages | of   |
| ``** | queu |
|      | ed   |
|      | mess |
|      | ages |
|      | .    |
|      | If   |
|      | 0,   |
|      | don' |
|      | t    |
|      | enfo |
|      | rce  |
|      | a    |
|      | limi |
|      | t.   |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | 100` |
|      | `**) |
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
|      | **`` |
|      | fals |
|      | e``* |
|      | *).  |
+------+------+
| **`` | If   |
| debu | give |
| g_tr | n    |
| ansp | (e.g |
| ort_ | .    |
| id`` | ``"k |
| **   | jmd3 |
|      | sBLO |
|      | Unb3 |
|      | Fyr" |
|      | ``), |
|      | use  |
|      | this |
|      | fixe |
|      | d    |
|      | tran |
|      | spor |
|      | t    |
|      | ID.  |
|      | (def |
|      | ault |
|      | :    |
|      | **`` |
|      | null |
|      | ``** |
|      | ).   |
+------+------+

**Example**

The *Long-poll Service* is configured on a path of a Web transport -
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
                      "lp": {
                         "type": "longpoll",
                         "options": {
                            "session_timeout": 30
                         }
                      }
                   }
                }
             ]
          }
       ]
    }

Test using curl
---------------

For developers that want to add WAMP-over-Longpoll support to their WAMP
client library, we have an
`example <https://github.com/crossbario/crossbarexamples/tree/master/longpoll_curl>`__
which demonstrates the transport using plain
**`curl <https://curl.haxx.se/>`__** only.

    This example can be useful during development and debugging. It is
    **not** intended for end-users.

Use with AutobahnJS
-------------------

`AutobahnJS <https://github.com/crossbario/autobahn-js>`__ fully
supports WAMP-over-Longpoll and you can find a complete working example
in the Crossbar.io examples
`here <https://github.com/crossbario/crossbarexamples/tree/master/longpoll>`__.

Use with AutobahnPostgres
-------------------------

**upcoming**

`AutobahnPostgres <https://github.com/crossbario/autobahn-postgres>`__
uses WAMP-over-Longpoll to natively integrate PostgreSQL with
Crossbar.io.
