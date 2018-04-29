Cookie Tracking
===============

Cookie tracking identifies and tracks WAMP-over-WebSocket client
connections using HTTP cookies.

Cookie tracking can be enabled on `WebSocket- <WebSocket-Transport>`__
and `Web-Transport <Web-Transport-and-Services>`__. It is not available
on other transport types such as `RawSocket <RawSocket-Transport>`__.

    While enabling cookie tracking is a prerequisite for cookie-based
    WAMP authentication, it can be used without authentication.

How it works
------------

Cookie tracking is backed by a configurable cookie store. Currently we
have two types of store:

-  memory-backed
-  file-backed

    In the future, we'll have an LMDB backed cookie store as well.

The stored information for a cookie includes the cookie ID as well as
authentication information (see `Cookie
Authentication <Cookie-Authentication>`__).

With a memory-backed cookie store, cookies are stored in in-memory
objects, and, obviously, those cookies will be gone after stopping
Crossbar.io

With a file-backed cookie store, cookies are stored in an append-only,
on-disk file.

Cookie Tracking without Authentication
--------------------------------------

Cookie tracking can be enabled without using cookie-based authentication
as well.

This is the case when

1. no authentication is configured at all
2. only anonymous authentication is configured
3. only non-cookie based authentication is configured

With 1) and 2) and cookie tracking enabled, Crossbar.io will
automatically use the cookie ID as the authentication ID (``authid``)
for the client.

This way, you still can **identify** clients across reconnects using
WAMP ``authid``. Without cookies, in case of 1) and 2), a WAMP client
will get a random ``authid`` **each time** it connects.

On the other hand, with 3), the authentication ID (``authid``) still
comes from the respective authentication method used.

Cookie Tracking with Authentication
-----------------------------------

Please see `Cookie Authentication <Cookie-Authentication>`__.

Configuration
-------------

The following parameters are all optional and shared between different
backing stores:

+------+------+
| opti | desc |
| on   | ript |
|      | ion  |
+======+======+
| **`` | The  |
| name | fiel |
| ``** | d    |
|      | name |
|      | wher |
|      | e    |
|      | Cros |
|      | sbar |
|      | .io  |
|      | will |
|      | stor |
|      | e    |
|      | its  |
|      | (ran |
|      | dom) |
|      | trac |
|      | king |
|      | ID   |
|      | with |
|      | in   |
|      | the  |
|      | Cook |
|      | ie   |
|      | set. |
|      | The  |
|      | defa |
|      | ult  |
|      | is   |
|      | ``"c |
|      | btid |
|      | "``. |
|      | Must |
|      | matc |
|      | h    |
|      | the  |
|      | regu |
|      | lar  |
|      | expr |
|      | essi |
|      | on   |
|      | ``^[ |
|      | a-z] |
|      | [a-z |
|      | 0-9_ |
|      | ]+$` |
|      | `.   |
+------+------+
| **`` | The  |
| leng | leng |
| th`` | th   |
| **   | of   |
|      | the  |
|      | valu |
|      | e    |
|      | for  |
|      | the  |
|      | trac |
|      | king |
|      | ID.  |
|      | The  |
|      | defa |
|      | ult  |
|      | is   |
|      | 24   |
|      | (whi |
|      | ch   |
|      | amou |
|      | nts  |
|      | to   |
|      | 144  |
|      | bits |
|      | of   |
|      | rand |
|      | omne |
|      | ss). |
|      | The  |
|      | defa |
|      | ult  |
|      | shou |
|      | ld   |
|      | be   |
|      | larg |
|      | e    |
|      | enou |
|      | gh   |
|      | to   |
|      | redu |
|      | ce   |
|      | the  |
|      | coll |
|      | isio |
|      | n    |
|      | prob |
|      | abil |
|      | ity  |
|      | to   |
|      | esse |
|      | ntia |
|      | lly  |
|      | zero |
|      | .    |
|      | Must |
|      | be   |
|      | betw |
|      | een  |
|      | 6    |
|      | and  |
|      | 64.  |
+------+------+
| **`` | The  |
| max_ | maxi |
| age` | mum  |
| `**  | Cook |
|      | ie   |
|      | life |
|      | time |
|      | in   |
|      | seco |
|      | nds. |
|      | The  |
|      | defa |
|      | ult  |
|      | is 1 |
|      | day. |
|      | Must |
|      | be   |
|      | betw |
|      | een  |
|      | 1    |
|      | seco |
|      | nd   |
|      | and  |
|      | 10   |
|      | year |
|      | s.   |
+------+------+
| **`` | A    |
| stor | dict |
| e``* | iona |
| *    | ry   |
|      | with |
|      | cook |
|      | ie   |
|      | stor |
|      | e    |
|      | conf |
|      | igur |
|      | atio |
|      | n    |
|      | (see |
|      | belo |
|      | w).  |
+------+------+

The ``store`` is a dictionary with the following attributes for a
**memory-backed** cookie store:

+----------------+-------------------------+
| attribute      | description             |
+================+=========================+
| **``type``**   | Must be ``"memory"``.   |
+----------------+-------------------------+

and for a **file-backed** cookie store:

+------+------+
| attr | desc |
| ibut | ript |
| e    | ion  |
+======+======+
| **`` | Must |
| type | be   |
| ``** | ``"f |
|      | ile" |
|      | ``.  |
+------+------+
| **`` | Eith |
| file | er   |
| name | an   |
| ``** | abso |
|      | lute |
|      | path |
|      | or a |
|      | rela |
|      | tive |
|      | path |
|      | (rel |
|      | ativ |
|      | e    |
|      | to   |
|      | the  |
|      | node |
|      | dire |
|      | ctor |
|      | y)   |
+------+------+

--------------

Examples
--------

To configure a memory-backed cookie store:

.. code:: json

    {
             "transports": [
                {
                   "type": "web",
                   "endpoint": {
                      "type": "tcp",
                      "port": 8080
                   },
                   "paths": {
                      "/": {
                         "type": "static",
                         "directory": "../web"
                      },
                      "ws": {
                         "type": "websocket",
                         "cookie": {
                            "name": "cbtid",
                            "length": 24,
                            "max_age": 864000,
                            "store": {
                               "type": "memory"
                            }
                         }
                      }
                   }
                }
             ]
    }

To configure a file-backed cookie store:

.. code:: json

    {
             "transports": [
                {
                   "type": "web",
                   "endpoint": {
                      "type": "tcp",
                      "port": 8080
                   },
                   "paths": {
                      "/": {
                         "type": "static",
                         "directory": "../web"
                      },
                      "ws": {
                         "type": "websocket",
                         "cookie": {
                            "name": "cbtid",
                            "length": 24,
                            "max_age": 864000,
                            "store": {
                               "type": "file",
                               "filename": "cookies.dat"
                            }
                         }
                      }
                   }
                }
             ]
    }

In above example, the cookie store would reside in
``.crossbar/cookies.dat`` for a default node directory.

    Note that the cookie file is "growing forever". There is no purging
    whatsoever, as the file is written append-only. The LMDB cookie
    store will provide a more advanced store.

--------------
